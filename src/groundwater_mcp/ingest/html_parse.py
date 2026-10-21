# -*- coding: utf-8 -*-
"""解析《地下水动态月报》官方 HTML5 翻页书文本层（2024 年 1—9 月）。

官方 2024 年各期只保留了 FlipBuilder HTML5 播放器，页面全文在
`mobile/javascript/search_config.js` 的 `var textForPages` 中；本模块把保存下来的
pageN.html 文本当作“纯文本版月报”，用与 PDF 版相同的表结构规则抽取 17 张表。
表格是文本流而非带线表格，因此按“表 N 标题”切段，再用各地貌单元/省份名定位行。
"""
from __future__ import annotations

import html as H
import json
import re
from pathlib import Path
from typing import Any

from .pdf_parse import (
    DIST_BINS,
    PRECIP_GROUPS,
    SHALLOW_REGIONS,
    SHANXI_BASINS,
    _to_float,
    _to_int,
    extract_shallow_narrative,
    extract_summary,
)

CAPTION_KEYWORDS = (
    "平均降水量",
    "地下水埋深变化",
    "地下水埋深及与上月",
    "深层地下水水位较去年同期",
    r"裂隙水、岩溶水重点监测站?",
    r"水温重点监测站?",
    r"泉流量重点(?:监测)?站",
)
CAPTION_RE = re.compile(
    r"表\s*(\d+)\s+(?!。)([^。]{0,90}?(?:" + "|".join(CAPTION_KEYWORDS) + r"))"
)
HEADING_RE = re.compile(r"[一二三四五]、\s*(?:综述|降水(?:量)?|浅层地下水埋深及变化|深层地下水水位变化情况|重点站监测情况)")

CITY_SUFFIXES = ("市", "区", "县", "州", "盟", "旗", "师")
CITY_TO_PROVINCE: dict[str, str] = {}


def _load_cities() -> dict[str, str]:
    if CITY_TO_PROVINCE:
        return CITY_TO_PROVINCE
    path = Path(__file__).resolve().parent.parent / "data" / "geo" / "china_cities.geojson"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for feat in data.get("features", []):
            props = feat.get("properties", {})
            name, prov = props.get("name"), props.get("province")
            if name and prov:
                CITY_TO_PROVINCE[name] = prov
    return CITY_TO_PROVINCE


def _strip_tags(text: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return H.unescape(text)


def load_pages(directory: str | Path) -> list[str]:
    """读取 HTML5 文本层的逐页文件，返回规范化后的页面文本。"""
    directory = Path(directory)
    pages = []
    for path in sorted(directory.glob("page*.html"), key=lambda p: int(re.findall(r"\d+", p.stem)[0])):
        raw = path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'<div class="page"[^>]*>([\s\S]*?)</div>', raw)
        body = _strip_tags(m.group(1) if m else raw)
        body = re.sub(r"[ \t\u3000]+", " ", body)
        body = re.sub(r"\n+", " ", body).strip()
        pages.append(body)
    return pages


def _clean_km2(text: str) -> str:
    """去掉 km² 上标被拆成行内独立数字造成的噪声（只影响少量数字前的 '2'）。"""
    return re.sub(r"(?<=[。，、；：m²])\s*2\s+(?=[减增持占])", " ", text)


def _sections(full_text: str) -> dict[str, str]:
    matches = list(HEADING_RE.finditer(full_text))
    out: dict[str, str] = {}
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        out[m.group(0).strip()] = full_text[start:end]
    return out


def _caption_segments(full_text: str) -> list[tuple[int, str, str]]:
    matches = list(CAPTION_RE.finditer(full_text))
    out = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        out.append((int(m.group(1)), m.group(0).strip(), full_text[start:end]))
    return out


def _caption_page(pages: list[str], caption: str) -> int | None:
    key = caption[:24]
    for idx, text in enumerate(pages):
        if key in text:
            return idx + 1
    return None


def _find_numbers(text: str, start: int, count: int) -> list[str] | None:
    m = re.match(r"((?:[-\d./]+)(?:\s+[-\d./]+){%d})" % (count - 1), text[start:].strip())
    if not m:
        return None
    return m.group(1).split()


def _unit_regex(base: str) -> str:
    """地貌单元名 → 正则：兼容“平原 / 一般平原 / 省略平原”写法差异。"""
    escaped = re.escape(base)
    return escaped.replace(r"平原", r"(?:(?:一般)?平原)?") if base.endswith("平原") else escaped


def _parse_precip(table_no: int, caption: str, segment: str, period: str) -> list[dict]:
    group = PRECIP_GROUPS.get(table_no, caption)
    units: list[tuple[str, str, str]] = []  # (province, unit, regex base)
    if table_no == 1:
        units = [("", u, u) for u in ("三江平原", "松嫩平原", "辽河平原", "穆棱兴凯平原")]
    elif table_no == 2:
        units = [("", u, u) for u in ("北京", "天津", "河北", "河南", "山东", "江苏", "安徽")]
    elif table_no == 3:
        province_map = {
            "大同盆地": "山西", "忻定盆地": "山西", "长治盆地": "山西", "运城盆地": "山西",
            "临汾盆地": "山西", "太原盆地": "山西", "呼包平原": "内蒙古", "河套平原": "内蒙古",
            "关中平原": "陕西", "河西走廊": "甘肃", "银川卫宁平原": "宁夏", "柴达木盆地": "青海",
            "塔里木盆地": "新疆", "准噶尔盆地": "新疆",
        }
        units = [(p, u, u) for u, p in province_map.items()]
    elif table_no == 4:
        units = [("", u, u) for u in ("长江三角洲平原", "江汉平原", "鄱阳湖平原", "浙东沿海平原")]
    elif table_no == 5:
        units = [("", u, u) for u in (
            "河南省南襄山间平原", "成都平原", "广东珠江三角洲平原", "雷州半岛平原", "琼北台地平原",
        )]
    rows = []
    seen = set()

    def add(province: str, unit: str, precip: float, anomaly: float) -> None:
        key = (unit, precip)
        if key in seen:
            return
        seen.add(key)
        rows.append(
            {
                "table_no": table_no,
                "group": group,
                "province": province,
                "unit": unit,
                "precip_mm": precip,
                "anomaly_pct": anomaly,
            }
        )

    for province, unit, base in units:
        m = re.search(_unit_regex(base) + r"\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", segment)
        if m:
            add(province, unit, float(m.group(1)), float(m.group(2)))
            continue
        # 旧版把“银川卫宁平原”拆成两行
        if unit == "银川卫宁平原":
            for sub in ("银川平原", "卫宁平原"):
                m = re.search(_unit_regex(sub) + r"\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", segment)
                if m:
                    add(province, sub, float(m.group(1)), float(m.group(2)))
    return rows


def _parse_distribution(table_no: int, caption: str, segment: str) -> dict | None:
    def values(keyword: str) -> list[float] | None:
        m = re.search(keyword + r"[^()]{0,4}[（(]%[）)]\s+((?:[-\d./]+)(?:\s+[-\d./]+){6})", segment)
        if not m:
            m = re.search(keyword + r"[（(]%[）)]\s+((?:[-\d./]+)(?:\s+[-\d./]+){6})", segment)
        if not m:
            return None
        out = []
        for token in m.group(1).split():
            out.append(0.0 if token == "/" else _to_float(token))
        return out

    methods = {}
    prev = values("与上月相比")
    if prev:
        methods["prev_month"] = {"values_pct": prev}
    year = values("与去年同期相比")
    if year:
        methods["last_year"] = {"values_pct": year}
    if not methods:
        return None
    region_label = re.split(r"\d+月份", caption, maxsplit=1)[0]
    region_label = re.sub(r"^表\s*\d+\s*", "", region_label).strip()
    regions = [r for r in re.split(r"[和及、]", region_label) if r]
    return {
        "table_no": table_no,
        "caption": caption,
        "region_label": region_label,
        "regions": regions,
        "bins": list(DIST_BINS),
        "methods": methods,
    }


def _parse_shanxi(segment: str) -> list[dict]:
    rows = []
    for basin in SHANXI_BASINS:
        m = re.search(
            re.escape(basin) + r"\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)", segment
        )
        if not m:
            continue
        rows.append(
            {
                "basin": basin,
                "mean_depth_m": float(m.group(1)),
                "max_depth_m": float(m.group(2)),
                "min_depth_m": float(m.group(3)),
                "change_prev_month_m": float(m.group(4)),
                "change_last_year_m": float(m.group(5)),
            }
        )
    return rows


DEEP_PROVINCES = [
    "天津", "河北", "山西", "辽宁", "黑龙江", "上海", "江苏", "浙江", "安徽", "江西",
    "山东", "河南", "湖南", "广东", "海南", "重庆", "云南", "甘肃", "新疆（含兵团）", "总计",
]


def _parse_deep(segment: str) -> list[dict]:
    rows = []
    for province in DEEP_PROVINCES:
        m = re.search(
            re.escape(province) + r"\s+(\d{2,5})\s+((?:[-\d./]+)(?:\s+(?:[-\d./]+)){4})", segment
        )
        if not m:
            continue
        total = int(m.group(1))
        vals = [0.0 if t == "/" else _to_float(t) for t in m.group(2).split()]
        rows.append(
            {
                "province": province,
                "total_stations": total,
                "up_gt2_pct": vals[0],
                "up_0_5_2_pct": vals[1],
                "stable_pct": vals[2],
                "down_0_5_2_pct": vals[3],
                "down_gt2_pct": vals[4],
            }
        )
    return rows


PROVINCE_NAMES = {
    "河北", "山西", "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建", "江西",
    "山东", "河南", "湖北", "湖南", "广东", "广西", "海南", "四川", "贵州", "云南",
    "西藏", "陕西", "甘肃", "青海", "宁夏", "新疆", "内蒙古", "北京", "天津", "上海",
    "重庆", "兵团", "新疆（含兵团）",
}


def _is_city_token(token: str) -> bool:
    return len(token) <= 14 and token.endswith(CITY_SUFFIXES) and token not in PROVINCE_NAMES


def _nearest_city_tokens(tokens: list[str], idx: int, radius: int = 6) -> str:
    best, best_dist = "", 10**9
    for j in range(max(0, idx - radius), min(len(tokens), idx + radius)):
        if _is_city_token(tokens[j]):
            dist = abs(j - idx)
            if dist < best_dist:
                best, best_dist = tokens[j], dist
    return best


def _nearest_city(segment: str, pos: int, radius: int = 120) -> str:
    window = segment[max(0, pos - radius) : pos + radius]
    best = ""
    best_dist = 10**9
    for m in re.finditer(r"[\u4e00-\u9fa5]{2,12}?(?:市|区|县|州|盟|旗|师)", window):
        dist = abs((m.start() + max(0, pos - radius)) - pos)
        if dist < best_dist:
            best_dist = dist
            best = m.group(0)
    return best


def _province_of_city(city: str) -> str:
    mapping = _load_cities()
    if city in mapping:
        return mapping[city]
    # 去掉常见后缀再试
    for suffix in CITY_SUFFIXES:
        if city.endswith(suffix) and city[: -len(suffix)] in mapping:
            return mapping[city[: -len(suffix)]]
    return ""


def _parse_water_stations(segment: str, table_no: int) -> list[dict]:
    tokens = [t for t in segment.split() if t]
    rows = []
    for idx, token in enumerate(tokens):
        if token not in {"裂隙水", "岩溶水"}:
            continue
        # 站名：向前收集，遇到省/市名或已到开头即停
        j = idx - 1
        station_tokens: list[str] = []
        while j >= 0 and len(station_tokens) < 4:
            t = tokens[j]
            if t in PROVINCE_NAMES or _is_city_token(t):
                break
            if t and not re.fullmatch(r"[-\d.]+", t):
                station_tokens.insert(0, t)
            j -= 1
        station = "".join(station_tokens)
        if not station:
            continue
        # 数值：向后 3 个
        vals = []
        k = idx + 1
        while k < len(tokens) and len(vals) < 3:
            if tokens[k] in {"裂隙水", "岩溶水", "省级行政区", "地级行政区", "站名", "水位", "含水介质"}:
                break
            nums = tokens[k].split()
            if all(re.fullmatch(r"-?[\d.]+", x) for x in nums):
                vals.extend(nums)
            else:
                break
            k += 1
        if len(vals) < 3:
            continue
        city = _nearest_city_tokens(tokens, idx - len(station_tokens) - 1)
        rows.append(
            {
                "province": _province_of_city(city),
                "city": city,
                "station": station,
                "medium": token,
                "water_level_m": float(vals[0]),
                "change_prev_month_m": float(vals[1]),
                "change_last_year_m": float(vals[2]),
            }
        )
    # 去重
    seen, unique = set(), []
    for r in rows:
        key = (r["city"], r["station"], r["medium"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def _parse_temp(segment: str) -> list[dict]:
    rows = []
    tokens = [t for t in segment.split() if t]
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if _is_city_token(token):
            city = token
            j = i + 1
            station_tokens = []
            while j < len(tokens) and len(station_tokens) < 4:
                t = tokens[j]
                if re.fullmatch(r"\d+(?:\.\d+)?", t):
                    break
                station_tokens.append(t)
                j += 1
            if station_tokens and j + 1 < len(tokens):
                temp_s, depth_s = tokens[j], tokens[j + 1]
                temp, depth = _to_float(temp_s), _to_float(depth_s)
                if temp is not None and depth is not None and 0 <= temp <= 45 and 0 <= depth <= 400:
                    rows.append(
                        {
                            "province": _province_of_city(city),
                            "city": city,
                            "station": "".join(station_tokens),
                            "water_temp_c": temp,
                            "depth_m": depth,
                            "note": "",
                        }
                    )
                    i = j + 2
                    continue
        i += 1
    # 去重（同一站可能被邻近 token 重复匹配）
    seen = set()
    unique = []
    for row in rows:
        key = (row["city"], row["station"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _parse_springs(segment: str, table_no: int) -> list[dict]:
    tokens = [t for t in segment.split() if t]
    header = {"省级行政区", "地级行政区", "站名", "月平均流量", "最大流量", "最小流量", "表", "省级", "地级"}
    rows = []
    current_city = ""
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token in header or "泉流量" in token or "监测站" in token or token.startswith("表"):
            i += 1
            continue
        if token in PROVINCE_NAMES:
            i += 1
            continue
        if _is_city_token(token):
            current_city = token
            i += 1
            continue
        if len(token) > 20 or re.fullmatch(r"[\d.]+", token):
            i += 1
            continue
        # 检查 token 之后是否为 1~3 个数值/断流
        k = i + 1
        vals: list[float | None] = []
        while k < len(tokens) and len(vals) < 3 and re.fullmatch(r"(?:-?\d+(?:\.\d+)?)|断流", tokens[k]):
            vals.append(None if tokens[k] == "断流" else float(tokens[k]))
            k += 1
        if not vals:
            i += 1
            continue
        station = token
        # 站名可能被拆成两个 token（如“柳铁三水源 地”）
        if i + 1 < len(tokens) and not re.fullmatch(r"(?:-?\d+(?:\.\d+)?)|断流", tokens[i + 1]) and station.endswith(("水源", "水源地", "泉")):
            station += tokens[i + 1]
            k += 1
        city = current_city or _nearest_city_tokens(tokens, i)
        # 省名可能在行末（合并单元格），取最近的省名覆盖
        province = _province_of_city(city)
        province_pos = -1
        for j in range(i, max(-1, i - 6), -1):
            if tokens[j] in PROVINCE_NAMES:
                province = tokens[j]
                province_pos = j
                break
        else:
            for j in range(k, min(len(tokens), k + 6)):
                if tokens[j] in PROVINCE_NAMES:
                    province = tokens[j]
                    province_pos = j
                    break
        if province_pos >= 0:
            near_city = _nearest_city_tokens(tokens, province_pos, radius=4)
            if near_city and _province_of_city(near_city) == province:
                city = near_city
        mean = vals[0] if vals else None
        rows.append(
            {
                "province": province,
                "city": city,
                "station": station,
                "mean_flow_m3s": mean,
                "max_flow_m3s": vals[1] if len(vals) > 1 else None,
                "min_flow_m3s": vals[2] if len(vals) > 2 else None,
                "note": "断流" if (None in vals or len(vals) == 1) else "",
            }
        )
        i = k
    # 去重
    seen, unique = set(), []
    for r in rows:
        key = (r["city"], r["station"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def parse_html_report(directory: str | Path, period: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = dict(meta or {})
    year, month = (int(x) for x in period.split("-"))
    pages = load_pages(directory)
    if not pages:
        raise ValueError(f"没有可解析的 HTML 页面：{directory}")
    full_text = _clean_km2("\n".join(pages))
    sections = _sections(full_text)
    captions = _caption_segments(full_text)

    result: dict[str, Any] = {
        "period": period,
        "year": year,
        "month": month,
        "title": meta.get("title") or f"《地下水动态月报》{year}年{month}月",
        "publish_date": meta.get("publish_date"),
        "detail_url": meta.get("detail_url"),
        "pdf_url": meta.get("pdf_url"),
        "source_pdf": str(directory),
        "source_kind": "html5-text-layer",
        "pages": len(pages),
        "tables": {},
        "precipitation": [],
        "shallow_narrative": [],
        "shallow_distribution": [],
        "shanxi_basins": [],
        "deep_provinces": [],
        "deep_summary": {},
        "water_stations": [],
        "temperature_stations": [],
        "springs": [],
        "summary": {},
        "sections": [{"heading": h, "text": t.strip(), "line_count": 0} for h, t in sections.items()],
        "page_texts": [{"page": i + 1, "text": t} for i, t in enumerate(pages)],
        "warnings": [],
    }

    tables: dict[int, dict] = {}
    for table_no, caption, segment in captions:
        page = _caption_page(pages, caption)
        rows: list[list[str]] = []
        if table_no in PRECIP_GROUPS:
            data = _parse_precip(table_no, caption, segment, period)
            result["precipitation"].extend(data)
            rows = [["地貌单元", "平均降水量(mm)", "降水量距平(%)"]] + [
                [r["unit"], str(r["precip_mm"]), str(r["anomaly_pct"])] for r in data
            ]
        elif "地下水埋深及与上月" in caption:
            data = _parse_shanxi(segment)
            result["shanxi_basins"] = data
            rows = [["地貌单元", "平均埋深(m)", "最大埋深(m)", "最小埋深(m)", "与上月相比(m)", "与去年同期相比(m)"]] + [
                [r["basin"], str(r["mean_depth_m"]), str(r["max_depth_m"]), str(r["min_depth_m"]),
                 str(r["change_prev_month_m"]), str(r["change_last_year_m"])]
                for r in data
            ]
        elif "地下水埋深变化" in caption:
            dist = _parse_distribution(table_no, caption, segment)
            if dist:
                result["shallow_distribution"].append(dist)
                rows = [["埋深变幅级别(m)"] + dist["bins"]]
                for method, payload in dist["methods"].items():
                    rows.append([method] + ["" if v is None else str(v) for v in payload["values_pct"]])
        elif "深层地下水水位" in caption:
            data = _parse_deep(segment)
            result["deep_provinces"] = data
            rows = [["省级行政区", "总站数", "上升超2m", "上升0.5~2m", "稳定", "下降0.5~2m", "下降超2m"]] + [
                [r["province"], str(r["total_stations"]), str(r["up_gt2_pct"]), str(r["up_0_5_2_pct"]),
                 str(r["stable_pct"]), str(r["down_0_5_2_pct"]), str(r["down_gt2_pct"])]
                for r in data
            ]
        elif "裂隙水" in caption and "含水介质" in segment:
            data = _parse_water_stations(segment, table_no)
            result["water_stations"] = data
            rows = [["省级行政区", "地级行政区", "站名", "含水介质", "水位(m)", "与上月相比(m)", "与去年同期相比(m)"]] + [
                [r["province"], r["city"], r["station"], r["medium"], str(r["water_level_m"]),
                 str(r["change_prev_month_m"]), str(r["change_last_year_m"])]
                for r in data
            ]
        elif "水温" in caption:
            data = _parse_temp(segment)
            result["temperature_stations"] = data
            rows = [["省级行政区", "地级行政区", "站名", "水温(℃)", "埋深(m)"]] + [
                [r["province"], r["city"], r["station"], str(r["water_temp_c"]), str(r["depth_m"])]
                for r in data
            ]
        elif "泉流量" in caption:
            data = _parse_springs(segment, table_no)
            result["springs"] = data
            rows = [["省级行政区", "地级行政区", "站名", "月平均流量", "最大流量", "最小流量"]] + [
                [r["province"], r["city"], r["station"],
                 "" if r["mean_flow_m3s"] is None else str(r["mean_flow_m3s"]),
                 "" if r["max_flow_m3s"] is None else str(r["max_flow_m3s"]),
                 "" if r["min_flow_m3s"] is None else str(r["min_flow_m3s"])]
                for r in data
            ]
        else:
            result["warnings"].append(f"表{table_no} 未识别的表类型：{caption}")
        tables[table_no] = {"caption": caption, "page": page, "rows": rows or [[segment[:2000]]]}
    result["tables"] = {str(k): v for k, v in sorted(tables.items())}

    # 叙述性数据
    summary_text = ""
    shallow_text = ""
    deep_text = ""
    for heading, text in sections.items():
        if heading.startswith("一、"):
            summary_text = text
        elif heading.startswith("三、"):
            shallow_text = text
        elif heading.startswith("四、"):
            deep_text = text
    result["summary"] = extract_summary(summary_text)
    result["shallow_narrative"] = extract_shallow_narrative(shallow_text)
    result["deep_summary"] = {
        "text": deep_text.strip(),
        "total_stations": sum(p["total_stations"] for p in result["deep_provinces"] if p["province"] != "总计"),
        "up_pct": result["summary"].get("deep_up_pct"),
        "stable_pct": result["summary"].get("deep_stable_pct"),
        "down_pct": result["summary"].get("deep_down_pct"),
    }
    if len(result["shallow_narrative"]) < 18:
        result["warnings"].append(f"shallow_narrative 解析数量偏少：{len(result['shallow_narrative'])}")
    if len(result["precipitation"]) < 30:
        result["warnings"].append(f"precipitation 解析数量偏少：{len(result['precipitation'])}")
    if len(result["shallow_distribution"]) < 6:
        result["warnings"].append(f"shallow_distribution 解析数量偏少：{len(result['shallow_distribution'])}")
    return result
