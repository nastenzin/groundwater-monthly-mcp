# -*- coding: utf-8 -*-
"""下载并合并中国省级 / 地级行政区边界 GeoJSON（阿里 DataV）。

数据源：https://geo.datav.aliyun.com/areas_v3/bound/
  - 100000_full.json            全国省级
  - {adcode}_full.json          各省下级（地级市；直辖市/特别行政区为区县）

输出：
  src/groundwater_mcp/data/geo/china_provinces.geojson
       properties: {name, adcode, level}
  src/groundwater_mcp/data/geo/china_cities.geojson
       properties: {name, adcode, province}

坐标统一保留 3 位小数（约 110m 精度），并去掉连续重复点以控制体积。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "src" / "groundwater_mcp" / "data" / "geo"
BASES = [
    "https://geo.datav.aliyun.com/areas_v3/bound",
    "http://geo.datav.aliyun.com/areas_v3/bound",
]
MIN_INTERVAL = 0.35  # 请求间隔，避免被限流
_last_request = [0.0]

CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# 直辖市 -> 在城市文件里以“省即市”的方式复制一份
MUNICIPALITIES = {"110000", "120000", "310000", "500000"}


def fetch_json(rel_path: str) -> dict | None:
    """带 https/http 回退、重试的下载。失败返回 None。"""
    for base in BASES:
        url = f"{base}/{rel_path}"
        for attempt in range(3):
            wait = MIN_INTERVAL - (time.time() - _last_request[0])
            if wait > 0:
                time.sleep(wait)
            try:
                resp = requests.get(
                    url, timeout=45, headers={"User-Agent": "Mozilla/5.0 geo-fetch"}
                )
                _last_request[0] = time.time()
                if resp.status_code == 200 and len(resp.content) > 200:
                    return resp.json()
                print(f"  ! {url} -> HTTP {resp.status_code}", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001 - 网络异常统一重试
                _last_request[0] = time.time()
                print(f"  ! {url} -> {exc}", file=sys.stderr)
            time.sleep(1.0 + attempt)
    return None


def clean_ring(ring: list, ndigits: int = 3) -> list:
    """坐标四舍五入到 ndigits 位小数，并去掉连续重复点。"""
    out = []
    for pt in ring:
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        rounded = [round(float(pt[0]), ndigits), round(float(pt[1]), ndigits)]
        if not out or rounded != out[-1]:
            out.append(rounded)
    return out


def clean_geometry(geom: dict) -> dict | None:
    """清理几何：坐标取 3 位小数，去掉连续重复点，丢弃退化环。"""
    if not isinstance(geom, dict):
        return None
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon":
        rings = [clean_ring(r) for r in coords]
        if not rings or len(rings[0]) < 4:
            return None
        rings = [r for r in rings if len(r) >= 4]
        return {"type": "Polygon", "coordinates": rings}
    if gtype == "MultiPolygon":
        polys = []
        for poly in coords:
            rings = [clean_ring(r) for r in poly]
            if not rings or len(rings[0]) < 4:
                continue
            polys.append([r for r in rings if len(r) >= 4])
        if not polys:
            return None
        return {"type": "MultiPolygon", "coordinates": polys}
    return None


def norm_name(name: str) -> str:
    return "".join(str(name).split())


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("[1/3] 下载全国省级边界 ...")
    country = fetch_json("100000_full.json")
    if not country:
        print("FATAL: 全国边界下载失败", file=sys.stderr)
        return 1
    prov_feats = []
    for feat in country.get("features", []):
        props = feat.get("properties") or {}
        name = norm_name(props.get("name") or "")
        adcode = str(props.get("adcode") or "")
        level = props.get("level")
        if not name or not adcode or not CJK_RE.search(name):
            continue
        if level != "province":
            continue
        geom = clean_geometry(feat.get("geometry"))
        if not geom:
            continue
        prov_feats.append(
            {
                "type": "Feature",
                "properties": {
                    "name": name,
                    "adcode": adcode,
                    "level": "province",
                },
                "geometry": geom,
            }
        )
    if len(prov_feats) < 30:
        print(f"FATAL: 省级要素过少 ({len(prov_feats)})", file=sys.stderr)
        return 1
    print(f"  省级要素 {len(prov_feats)} 个")

    print("[2/3] 下载各省地级边界 ...")
    city_feats = []
    fallback_city_provinces = []
    for i, pf in enumerate(prov_feats, 1):
        pname = pf["properties"]["name"]
        adcode = pf["properties"]["adcode"]
        data = fetch_json(f"{adcode}_full.json")
        got = 0
        if data:
            for feat in data.get("features", []):
                props = feat.get("properties") or {}
                name = norm_name(props.get("name") or "")
                level = props.get("level")
                cad = str(props.get("adcode") or "")
                if level != "city" or not name or not CJK_RE.search(name) or not cad:
                    continue
                geom = clean_geometry(feat.get("geometry"))
                if not geom:
                    continue
                city_feats.append(
                    {
                        "type": "Feature",
                        "properties": {
                            "name": name,
                            "adcode": cad,
                            "province": pname,
                        },
                        "geometry": geom,
                    }
                )
                got += 1
        if got == 0:
            # 直辖市 / 特别行政区 / 数据缺失：把省本身作为“市”兜底
            fallback_city_provinces.append((pname, adcode))
            city_feats.append(
                {
                    "type": "Feature",
                    "properties": {
                        "name": pname,
                        "adcode": adcode,
                        "province": pname,
                    },
                    "geometry": pf["geometry"],
                }
            )
        print(f"  [{i:02d}/{len(prov_feats)}] {pname} ({adcode}) -> city {got}"
              + ("" if got else " (fallback=province)"))

    print("[3/3] 写出文件 ...")
    prov_out = {"type": "FeatureCollection", "features": prov_feats}
    city_out = {"type": "FeatureCollection", "features": city_feats}
    p_path = OUT_DIR / "china_provinces.geojson"
    c_path = OUT_DIR / "china_cities.geojson"
    p_path.write_text(
        json.dumps(prov_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    c_path.write_text(
        json.dumps(city_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )

    # 校验：必须含中文 name
    for path in (p_path, c_path):
        data = json.loads(path.read_text(encoding="utf-8"))
        names = [f["properties"]["name"] for f in data["features"]]
        assert names and all(CJK_RE.search(n) for n in names), f"{path} 缺少中文 name"
        print(f"  {path.name}: {len(names)} 个要素, {path.stat().st_size/1024:.1f} KB")

    print("fallback(省即市):", ", ".join(p for p, _ in fallback_city_provinces) or "无")
    print("sample provinces:", [f["properties"]["name"] for f in prov_feats[:5]])
    print("sample cities:", [f["properties"]["name"] for f in city_feats[:5]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
