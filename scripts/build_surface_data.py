# -*- coding: utf-8 -*-
"""批量数字化《地下水动态月报》PDF 中的埋深等值面图，输出 data/surface/parsed/*.json。

用法:
    python scripts/build_surface_data.py                 # 全部 PDF 期次
    python scripts/build_surface_data.py --periods 2025-12 --limit 3
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from groundwater_mcp.ingest import surface as surf  # noqa: E402

PDF_DIR = ROOT / "data" / "pdfs"
OUT_DIR = ROOT / "data" / "surface" / "parsed"
TMP_DIR = ROOT / "data" / "surface" / "tmp"
DB = ROOT / "src" / "groundwater_mcp" / "data" / "groundwater.db"
CITY_FILE = ROOT / "src" / "groundwater_mcp" / "data" / "geo" / "city_points.json"
UNITS = ROOT / "src" / "groundwater_mcp" / "data" / "geo" / "units.geojson"

REGION_ALIAS = {
    "三江": "三江平原", "三江平原": "三江平原",
    "内蒙古呼包平原": "呼包平原", "呼包平原": "呼包平原",
    "河套平原": "河套平原", "内蒙古河套平原": "河套平原",
    "陕西关中平原": "关中平原", "关中平原": "关中平原",
    "宁夏银川卫宁平原": "银川卫宁平原", "银川卫宁平原": "银川卫宁平原",
    "青海柴达木盆地": "柴达木盆地", "柴达木盆地": "柴达木盆地",
    "新疆塔里木盆地监控区": "塔里木盆地", "塔里木盆地": "塔里木盆地",
    "新疆准噶尔盆地监控区": "准噶尔盆地", "准噶尔盆地": "准噶尔盆地",
    "甘肃河西走廊平原": "河西走廊平原", "河西走廊平原": "河西走廊平原",
    "河南省南襄山间平原": "河南省南襄山间平原",
    "山西主要盆地": "山西主要盆地",
}
SHANXI = ["大同盆地", "忻定盆地", "长治盆地", "运城盆地", "临汾盆地", "太原盆地"]


def _canon_names() -> set[str]:
    try:
        feats = json.loads(UNITS.read_text(encoding="utf-8"))["features"]
        return {f["properties"]["name"] for f in feats}
    except Exception:  # noqa: BLE001
        return set()


CANON = _canon_names()


def normalize_region(p: str) -> str:
    """把图题中的区域写法归一到监测区名称（兼容旧版“一般平原/监控区”等后缀）。"""
    if p in REGION_ALIAS:
        return REGION_ALIAS[p]
    if p in CANON:
        return p
    cand = p
    for _ in range(3):
        if cand in CANON:
            return cand
        stripped = False
        for suf in ("监控区", "一般平原", "台地平原", "平原", "盆地"):
            if cand.endswith(suf) and len(cand) > len(suf):
                cand = cand[: -len(suf)]
                stripped = True
                break
        if stripped:
            continue
        break
    for suf in ("平原", "盆地", "台地平原"):
        if cand + suf in CANON:
            return cand + suf
    return REGION_ALIAS.get(p, p)


def caption_regions(caption: str) -> list[str]:
    t = re.sub(r"^图\s*\d+\s*", "", caption)
    t = re.sub(r"\d+\s*月份", "", t)
    t = t.replace("地下水埋深等值面图", "").replace("埋深等值面图", "")
    t = re.sub(r"[（(].*?[)）]", "", t).strip()
    parts = re.split(r"[和及、与]", t)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        p = normalize_region(p)
        if p == "山西主要盆地":
            out.extend(SHANXI)
        else:
            out.append(p)
    return out


def load_expected(period: str) -> dict[str, dict]:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rows = list(conn.execute(
        "SELECT region, mean_depth_m, area_km2, area_share_pct FROM shallow_regions WHERE period=?",
        (period,)))
    conn.close()
    out = {}
    for r in rows:
        area_total = None
        if r["area_km2"] and r["area_share_pct"]:
            area_total = r["area_km2"] / (r["area_share_pct"] / 100.0)
        out[r["region"]] = {"mean": r["mean_depth_m"], "area_km2": area_total}
    return out


def unit_polygon(regions: list[str]):
    feats = json.loads(UNITS.read_text(encoding="utf-8"))["features"]
    polys = [shape(f["geometry"]) for f in feats if f["properties"]["name"] in regions]
    return unary_union(polys) if polys else None


def expected_for(regions: list[str], exp: dict[str, dict]) -> dict:
    areas = [exp[r]["area_km2"] for r in regions if r in exp and exp[r]["area_km2"]]
    means = [exp[r]["mean"] for r in regions if r in exp and exp[r]["mean"] is not None
             and exp[r]["area_km2"]]
    area = float(sum(areas)) if areas else None
    poly = unit_polygon(regions)
    centroid = poly.centroid if poly is not None else None
    mean = None
    if area and means:
        mean = float(sum(m * exp[r]["area_km2"] for r, m in
                         [(r, exp[r]["mean"]) for r in regions
                          if r in exp and exp[r]["mean"] is not None and exp[r]["area_km2"]])
                     / sum(exp[r]["area_km2"] for r in regions
                           if r in exp and exp[r]["mean"] is not None and exp[r]["area_km2"]))
    return {"area_km2": area, "mean": mean, "polygon": poly,
            "centroid": (centroid.x, centroid.y) if centroid is not None else None}


def _caption_lines(page):
    """返回 [(y0, y1, text)]，用于把图题与图件按垂直顺序对应。"""
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            txt = "".join(s["text"] for s in line["spans"]).strip()
            if not txt:
                continue
            out.append((line["bbox"][1], line["bbox"][3], txt))
    return out


def extract_figures(pdf: Path) -> list[dict]:
    docs = pymupdf.open(pdf)
    figs = []
    for pno in range(docs.page_count):
        page = docs[pno]
        lines = _caption_lines(page)
        imgs = []
        for info in page.get_images(full=True):
            bb = page.get_image_bbox(info)
            imgs.append({"w": info[2], "h": info[3], "xref": info[0], "bbox": bb,
                         "y0": bb.y0, "x0": bb.x0, "area": info[2] * info[3]})
        if not imgs:
            continue
        used = set()
        for idx in range(len(lines)):
            y0, y1, txt = lines[idx]
            m = re.match(r"^图\s*(\d+)\s*$", txt)
            caption = None
            if m:
                # 图题可能同 y 分 span，或紧随下一行
                for y0b, y1b, txtb in lines:
                    if "等值面图" in txtb and (abs(y0b - y0) < 6 or y1 - 2 <= y0b <= y1 + 32):
                        caption = txtb
                        break
                if caption is None or "埋深等值面图" not in caption:
                    continue
            else:
                mm = re.match(r"^图\s*(\d+)\s*([^\n]*埋深等值面图[^\n]*)$", txt)
                if not mm:
                    continue
                m, caption = mm, txt
            fno = int(m.group(1))
            cap_y = y1
            # 图题通常在对应图件下方：优先选“图底紧接图题上方”的那张；
            # 夹在两张图之间时也不能选下一张，故按 y1 最接近图题的规则。
            cands = []
            for i in imgs:
                if id(i) in used or i["area"] < 150000:
                    continue
                ratio = i["w"] / max(1, i["h"])
                if not (0.3 <= ratio <= 3.0):
                    continue
                cands.append(i)
            if not cands:
                continue
            above = [i for i in cands if i["bbox"].y1 <= cap_y + 20]
            if above:
                map_img = max(above, key=lambda i: i["bbox"].y1)
            else:
                map_img = min(cands, key=lambda i: i["bbox"].y0)
            used.add(id(map_img))
            # 图例：在较小的图片里找“能解码出 10 个色块”的那一张
            legend = None
            smalls = [i for i in imgs if id(i) not in used and i["area"] < map_img["area"] * 0.35
                      and i["w"] >= 90 and i["h"] >= 70 and 0.8 <= i["w"] / max(1, i["h"]) <= 2.6]
            smalls.sort(key=lambda i: i["area"], reverse=True)
            for cand in smalls:
                try:
                    base = docs.extract_image(cand["xref"])
                    arr = cv2.imdecode(np.frombuffer(base["image"], np.uint8), cv2.IMREAD_COLOR)
                    if arr is not None and len(surf.decode_legend_array(arr)) == 10:
                        legend = cand
                        break
                except Exception:  # noqa: BLE001
                    continue
            if legend is None and smalls:
                legend = smalls[0]
            figs.append({"page": pno + 1, "fig_no": fno, "caption": caption.strip(),
                         "map": map_img, "legend": legend})
    docs.close()
    return figs


def save_img(doc, info, dest: Path) -> Path:
    base = doc.extract_image(info["xref"])
    dest.write_bytes(base["image"])
    return dest


def process_period(period: str, limit: int | None = None) -> dict:
    pdf = PDF_DIR / f"{period}.pdf"
    if not pdf.exists():
        pdf = ROOT / "data" / "legacy" / "pdfs" / f"{period}.pdf"
    exp = load_expected(period)
    cities = surf.load_city_points(CITY_FILE)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf)
    maps = []
    figs = extract_figures(pdf)
    if limit:
        figs = figs[:limit]
    for fig in figs:
        if fig["legend"] is None:
            continue
        regions = caption_regions(fig["caption"])
        e = expected_for(regions, exp)
        try:
            map_path = save_img(doc, fig["map"], TMP_DIR / f"{period}_f{fig['fig_no']}_map.jpg")
            leg_path = save_img(doc, fig["legend"], TMP_DIR / f"{period}_f{fig['fig_no']}_leg.jpg")
            rec = surf.digitize_figure(map_path, leg_path, regions, cities, e)
        except Exception as exc:  # noqa: BLE001
            maps.append({"figure": fig["fig_no"], "page": fig["page"], "error": repr(exc)})
            continue
        rec.update({"period": period, "figure": fig["fig_no"], "page": fig["page"],
                    "caption": fig["caption"], "regions": regions,
                    "expected_mean_m": round(e["mean"], 2) if e["mean"] else None,
                    "mean_error_m": (round(rec["mean_depth_m"] - e["mean"], 2)
                                     if e["mean"] and rec.get("mean_depth_m") is not None else None)})
        maps.append(rec)
    doc.close()
    return {"period": period, "count": len(maps), "maps": maps}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--periods", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    periods = args.periods or sorted(
        {p.stem for p in PDF_DIR.glob("*.pdf")}
        | {p.stem for p in (ROOT / "data" / "legacy" / "pdfs").glob("*.pdf")})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for period in periods:
        if not (PDF_DIR / f"{period}.pdf").exists() and not (
                (ROOT / "data" / "legacy" / "pdfs" / f"{period}.pdf").exists()):
            continue
        res = process_period(period, limit=args.limit)
        (OUT_DIR / f"{period}.json").write_text(
            json.dumps(res, ensure_ascii=False), encoding="utf-8")
        ok = [m for m in res["maps"] if "error" not in m]
        good = [m for m in ok if m.get("quality") in ("high", "medium")]
        print(f"{period}: figures={len(res['maps'])} ok={len(ok)} calibrated={len(good)}")


if __name__ == "__main__":
    main()
