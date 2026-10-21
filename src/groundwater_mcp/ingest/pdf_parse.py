# -*- coding: utf-8 -*-
"""解析《地下水动态月报》PDF，抽取 17 张表与叙述性数据。

数据来源：水利部网站公开发布的《地下水动态月报》PDF。
解析基于 pdfplumber：先用目录行（表N 标题）切分页面区域，再在区域内抽取表格，
从而避免相邻表格被合并（如 表10+表11 同页、表15/16 跨页）的问题。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pdfplumber

# ---------------------------------------------------------------------------
# 基础常量
# ---------------------------------------------------------------------------
CAPTION_RE = re.compile(r"^表\s*(\d+)\s*[、.．:：]?\s*(.+)$")
SECTION_RE = re.compile(r"^[一二三四五六七八九十]+、\s*\S")
SUBSECTION_RE = re.compile(r"^\d+\s*[.．、]\s*\S")
TOC_RE = re.compile(r"^目\s*录$")
PAGE_NO_RE = re.compile(r"^\d{1,3}$")

DIST_BINS = ["<-2", "-2～-1", "-1～-0.5", "-0.5～0.5", "0.5～1", "1～2", ">2"]
TEMP_HEADER_KEYS = ("水温", "埋深")
PRECIP_GROUPS = {
    1: "东北平原",
    2: "黄淮海平原",
    3: "山西及西北诸省区",
    4: "长江中下游平原",
    5: "其他监控区",
}

# 浅层地下水埋深章节中的地貌单元（组, 名称, 正则别名）
SHALLOW_REGIONS: list[tuple[str, str, str]] = [
    ("东北平原", "三江平原", "三江平原"),
    ("东北平原", "穆棱兴凯平原", "穆棱兴凯平原"),
    ("东北平原", "松嫩平原", "松嫩平原"),
    ("东北平原", "辽河平原", "辽河平原"),
    ("黄淮海平原", "海河平原", "海河平原"),
    ("黄淮海平原", "黄淮平原", "黄淮平原"),
    ("山西及西北诸省区", "山西主要盆地", "主要盆地"),
    ("山西及西北诸省区", "呼包平原", "呼包平原"),
    ("山西及西北诸省区", "河套平原", "河套平原"),
    ("山西及西北诸省区", "关中平原", "关中平原"),
    ("山西及西北诸省区", "河西走廊平原", "河西走廊平原"),
    ("山西及西北诸省区", "银川卫宁平原", "银川卫宁平原"),
    ("山西及西北诸省区", "柴达木盆地", "柴达木盆地"),
    ("山西及西北诸省区", "塔里木盆地", "塔里木盆地"),
    ("山西及西北诸省区", "准噶尔盆地", "准噶尔盆地"),
    ("长江中下游平原", "江汉平原", "江汉平原"),
    ("长江中下游平原", "鄱阳湖平原", "鄱阳湖平原"),
    ("长江中下游平原", "长江三角洲平原", "长江三角洲平原"),
    ("长江中下游平原", "浙东沿海平原", "浙东沿海平原"),
    ("其他监控区", "河南省南襄山间平原", "南襄山间平原"),
    ("其他监控区", "成都平原", "成都平原"),
    ("其他监控区", "广东珠江三角洲平原", "珠江三角洲平原"),
    ("其他监控区", "雷州半岛平原", "雷州半岛平原"),
    ("其他监控区", "琼北台地平原", "琼北台地平原"),
]

# 山西主要盆地（表11）
SHANXI_BASINS = ["大同盆地", "忻定盆地", "长治盆地", "运城盆地", "临汾盆地", "太原盆地"]


# ---------------------------------------------------------------------------
# 文本 / 表格工具
# ---------------------------------------------------------------------------
def _clean_cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", "").replace("\r", "").strip()


def _to_float(value: Any) -> float | None:
    s = _clean_cell(value)
    if not s:
        return None
    s = s.replace("－", "-").replace("—", "-").replace("−", "-")
    s = s.replace("＜", "<").replace("＞", ">")
    if s in {"-", "/", "—", "–"}:
        return 0.0 if s == "/" else None
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    f = _to_float(value)
    return None if f is None else int(round(f))


def _junk_row(row: list[Any]) -> bool:
    cells = [_clean_cell(c) for c in row]
    joined = "".join(cells)
    if not joined:
        return True
    nonempty = [c for c in cells if c]
    # 被合并成大段正文的“行”
    if len(joined) > 120 and len(nonempty) <= 2:
        return True
    if any(len(c) > 60 for c in cells):
        return True
    if any("表" in c and re.search(r"表\s*\d", c) and len(c) > 12 for c in cells):
        return True
    return False


def _normalize_table(rows: list[list[Any]]) -> list[list[str]]:
    """去除全空列、全空行，返回字符串行。"""
    rows = [[_clean_cell(c) for c in row] for row in rows]
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return []
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    keep = [j for j in range(ncols) if any(r[j] for r in rows)]
    rows = [[r[j] for j in keep] for r in rows]
    if not rows:
        return []
    width = len(rows[0])
    out = []
    for r in rows:
        if _junk_row(r):
            continue
        out.append(r[:width] + [""] * max(0, width - len(r)))
    return out


def _caption_of(line: str) -> tuple[int, str] | None:
    m = CAPTION_RE.match(line.strip())
    if not m:
        return None
    no = int(m.group(1))
    if not 1 <= no <= 17:
        return None
    return no, m.group(2).strip()


def _rows_from_segment(page, y0: float, y1: float) -> list[list[str]]:
    if y1 - y0 < 8:
        return []
    box = (0, max(0.0, y0), page.width, min(page.height, y1))
    try:
        cropped = page.crop(box)
        tables = cropped.extract_tables()
    except Exception:  # noqa: BLE001 - 单页表格异常不应中断整期解析
        return []
    rows: list[list[str]] = []
    for table in tables:
        rows.extend(_normalize_table(table))
    return rows


def _page_lines(page) -> list[dict[str, Any]]:
    """抽取页面文本行（附带位置），并剔除页眉页脚。"""
    try:
        raw = page.extract_text_lines()
    except Exception:  # noqa: BLE001
        raw = []
    lines = []
    for ln in raw:
        text = (ln.get("text") or "").strip()
        if not text:
            continue
        top = float(ln.get("top") or 0)
        bottom = float(ln.get("bottom") or 0)
        if text == "地下水动态月报":
            continue
        if PAGE_NO_RE.match(text) and top > page.height - 80:
            continue
        if "年第" in text and "期" in text and top < 120:
            continue
        lines.append({"text": text, "top": top, "bottom": bottom, "page": page.page_number})
    return lines


HEADER_LINE_RE = re.compile(
    r"^(埋深变幅分区|埋深变幅级别|与上月相比|与去年同期相比|省级行?政区|地级行?政区|"
    r"站名|水位|含水介质|水温|埋深|变幅站点占比|平原名称|各省市平原区|平均降水量|"
    r"降水量距平|地貌单元|平均埋深|最大埋深|最小埋深|月平均流量|最大流量|最小流量|总站数)"
)


def _is_table_like_line(text: str) -> bool:
    """判断一行是否属于表格/图表标题，正文段落中应剔除，避免干扰叙述数据解析。"""
    if CAPTION_RE.match(text) or re.match(r"^图\s*\d+", text):
        return True
    if HEADER_LINE_RE.match(text):
        return True
    nums = re.findall(r"-?\d+(?:\.\d+)?", text)
    if not nums:
        return False
    # 纯表格行：数字多、没有句号，且不含逗号/顿号/分号这类句内标点
    if len(nums) >= 4 and "。" not in text and re.search(r"[，、；]", text) is None:
        return True
    # 纯表格行：短、无中文标点、含 2 个以上数字
    if len(text) <= 80 and re.search(r"[，。；：、]", text) is None and len(nums) >= 2:
        return True
    return False


def _sentence_slice(text: str, start: int, end: int) -> str:
    """取命中位置所在的一句话（用于 raw_sentence 展示）。"""
    left = max(0, start - 120)
    base = text.rfind("。", left, start)
    if base < 0:
        base = text.rfind("：", left, start)
    left = base + 1 if base >= 0 else max(0, start - 60)
    right = text.find("。", end)
    right = right + 1 if right >= 0 else min(len(text), end + 60)
    return text[left:right].strip()


# ---------------------------------------------------------------------------
# 各表解析
# ---------------------------------------------------------------------------
def _parse_precip(rows: list[list[str]], table_no: int, caption: str, period: str) -> tuple[list[dict], list[str]]:
    out, warns = [], []
    group = PRECIP_GROUPS.get(table_no, caption)
    current_province = ""
    for row in rows:
        if len(row) < 3:
            continue
        if any(k in row[0] for k in ("名称", "行政区", "平原区", "地貌单元")):
            continue
        if table_no == 3 and len(row) >= 4:
            province, unit, precip, anomaly = row[0], row[1], _to_float(row[2]), _to_float(row[3])
            if province:
                current_province = province
            province = current_province
        else:
            province, unit = "", row[0]
            precip, anomaly = _to_float(row[-2]), _to_float(row[-1])
        if precip is None or not unit:
            continue
        out.append(
            {
                "table_no": table_no,
                "group": group,
                "province": province,
                "unit": unit,
                "precip_mm": precip,
                "anomaly_pct": anomaly,
            }
        )
    if not out:
        warns.append(f"表{table_no} 未解析到降水量数据")
    return out, warns


def _parse_distribution(rows: list[list[str]], table_no: int, caption: str) -> tuple[dict | None, list[str]]:
    warns: list[str] = []
    bins = list(DIST_BINS)
    for row in rows:
        if row and row[0].startswith("埋深变幅级别"):
            vals = [c for c in row[1:] if c]
            if len(vals) >= 7:
                bins = vals[:7]
            break
    method_rows: dict[str, list[float | None]] = {}
    for row in rows:
        head = row[0] if row else ""
        if head.startswith("与上月相比") or head.startswith("较上月相比"):
            method_rows["prev_month"] = [_to_float(c) for c in row[1 : 1 + len(bins)]]
        elif head.startswith("与去年同期相比") or head.startswith("较去年同期相比"):
            method_rows["last_year"] = [_to_float(c) for c in row[1 : 1 + len(bins)]]
    if not method_rows:
        return None, [f"表{table_no} 未解析到埋深变幅分布"]
    region_label = re.split(r"\d+月份", caption, maxsplit=1)[0].strip()
    regions = [r for r in re.split(r"[和及、]", region_label) if r]
    return (
        {
            "table_no": table_no,
            "caption": caption,
            "region_label": region_label,
            "regions": regions,
            "bins": bins,
            "methods": {k: {"values_pct": v} for k, v in method_rows.items()},
        },
        warns,
    )


def _parse_shanxi(rows: list[list[str]], table_no: int, caption: str) -> tuple[list[dict], list[str]]:
    out: list[dict] = []
    header_found = False
    for row in rows:
        if not row:
            continue
        if row[0].startswith("地貌单元"):
            header_found = True
            continue
        if not header_found:
            continue
        if row[0] in SHANXI_BASINS or row[0].endswith("盆地"):
            if len(row) < 6:
                continue
            out.append(
                {
                    "basin": row[0],
                    "mean_depth_m": _to_float(row[1]),
                    "max_depth_m": _to_float(row[2]),
                    "min_depth_m": _to_float(row[3]),
                    "change_prev_month_m": _to_float(row[4]),
                    "change_last_year_m": _to_float(row[5]),
                }
            )
    return out, ([] if out else [f"表{table_no} 未解析到山西盆地数据"])


def _parse_deep(rows: list[list[str]], table_no: int) -> tuple[list[dict], list[str]]:
    out: list[dict] = []
    header_found = False
    for row in rows:
        if not row:
            continue
        if "总站数" in "".join(row):
            header_found = True
            continue
        if not header_found:
            continue
        if len(row) < 7:
            continue
        province = row[0]
        if not province or province.startswith("变幅") or "省级" in province:
            continue
        total = _to_int(row[1])
        if total is None:
            continue
        out.append(
            {
                "province": province,
                "total_stations": total,
                "up_gt2_pct": _to_float(row[2]),
                "up_0_5_2_pct": _to_float(row[3]),
                "stable_pct": _to_float(row[4]),
                "down_0_5_2_pct": _to_float(row[5]),
                "down_gt2_pct": _to_float(row[6]),
            }
        )
    return out, ([] if out else [f"表{table_no} 未解析到深层地下水数据"])


def _parse_water_stations(rows: list[list[str]], table_no: int) -> tuple[list[dict], list[str]]:
    out: list[dict] = []
    province = city = ""
    header_seen = False
    for row in rows:
        if not row:
            continue
        joined = "".join(row)
        if "含水介质" in joined:
            header_seen = True
            continue
        if len(row) < 7:
            continue
        prov, city_c, station, medium, level, chg_prev, chg_year = row[:7]
        if medium not in {"裂隙水", "岩溶水"}:
            continue
        if prov:
            province = prov
        if city_c:
            city = city_c
        level_f = _to_float(level)
        if level_f is None:
            continue
        out.append(
            {
                "province": province,
                "city": city,
                "station": station,
                "medium": medium,
                "water_level_m": level_f,
                "change_prev_month_m": _to_float(chg_prev),
                "change_last_year_m": _to_float(chg_year),
            }
        )
    return out, ([] if out else [f"表{table_no} 未解析到裂隙水/岩溶水重点站数据"])


def _parse_temp(rows: list[list[str]], table_no: int) -> tuple[list[dict], list[str]]:
    out: list[dict] = []
    for row in rows:
        if not row:
            continue
        joined = "".join(row)
        if "水温" in joined:
            continue
        if len(row) >= 9:
            prov, city1, st1, t1, d1, city2, st2, t2, d2 = row[:9]
            for prov_v, city, st, t, d in (
                (prov, city1, st1, t1, d1),
                (prov, city2, st2, t2, d2),
            ):
                t_f, d_f = _to_float(t), _to_float(d)
                if st:
                    out.append(
                        {
                            "province": prov_v,
                            "city": city,
                            "station": st,
                            "water_temp_c": t_f,
                            "depth_m": d_f,
                            "note": "本月缺测" if t_f is None or d_f is None else "",
                        }
                    )
        elif len(row) >= 5:
            prov, city, st, t, d = row[:5]
            t_f, d_f = _to_float(t), _to_float(d)
            if st:
                out.append(
                    {
                        "province": prov,
                        "city": city,
                        "station": st,
                        "water_temp_c": t_f,
                        "depth_m": d_f,
                        "note": "本月缺测" if t_f is None or d_f is None else "",
                    }
                )
    return out, ([] if out else [f"表{table_no} 未解析到水温重点站数据"])


def _parse_springs(rows: list[list[str]], table_no: int) -> tuple[list[dict], list[str]]:
    out: list[dict] = []
    province = ""
    city = ""
    for row in rows:
        if not row:
            continue
        if "月平均流量" in "".join(row):
            continue
        if len(row) < 6:
            continue
        prov, city_c, station, mean, mx, mn = row[:6]
        if not station:
            continue
        if prov:
            province = prov
        if city_c:
            city = city_c
        out.append(
            {
                "province": province,
                "city": city,
                "station": station,
                "mean_flow_m3s": _to_float(mean),
                "max_flow_m3s": _to_float(mx),
                "min_flow_m3s": _to_float(mn),
                "note": "" if _to_float(mean) is not None else mean,
            }
        )
    return out, ([] if out else [f"表{table_no} 未解析到泉流量数据"])


# ---------------------------------------------------------------------------
# 叙述性数据
# ---------------------------------------------------------------------------
def parse_change(window: str, keyword: str) -> dict[str, Any] | None:
    """从文本窗口中解析 “与上月/去年同期” 的埋深变化。

    兼容文本层换行/上标拆分造成的空格：如“较上 月减 2 少 0.7m”“增加 2 0.1m”。
    """
    # 去掉 km² 上标被拆成独立行后插入句子中间的 “2”
    cleaned = re.sub(r"(?<=[\u4e00-\u9fa5])\s+2\s+(?=[\u4e00-\u9fa5\d])", "", window)
    pattern = re.compile(
        keyword
        + r"[^。；;]{0,20}?(基本\s*持平|持\s*平|断流|"
        r"增\s*加\s*(?:\d+\s+)?([\d.]+)\s*m|"
        r"减\s*少\s*(?:\d+\s+)?([\d.]+)\s*m|"
        r"上\s*升\s*(?:\d+\s+)?([\d.]+)\s*m|"
        r"下\s*降\s*(?:\d+\s+)?([\d.]+)\s*m)"
    )
    m = pattern.search(cleaned)
    if not m:
        return None
    token = m.group(1)
    norm = re.sub(r"\s+", "", token)
    text = cleaned[max(0, m.start() - 12) : m.end()]
    if "持平" in norm:
        return {"text": text, "value": 0.0, "kind": "stable"}
    if norm.startswith("断流"):
        return {"text": text, "value": None, "kind": "dry"}
    if norm.startswith("增加") or norm.startswith("上升"):
        num = _to_float(m.group(2) or m.group(4))
        return {"text": text, "value": num, "kind": "increase"}
    num = _to_float(m.group(3) or m.group(5))
    return {"text": text, "value": -num if num is not None else None, "kind": "decrease"}


def _match_region(prefix: str) -> tuple[str, str, str] | None:
    """把 “塔里木盆地监控区”“浙东沿海一般平原” 之类前缀映射到规范地貌单元名。"""
    prefix = prefix.strip(" ：:，,。；;")
    normalized = prefix.replace("一般", "")
    if normalized.endswith("平原区"):
        normalized = normalized[: -1]
    best: tuple[str, str, str] | None = None
    for group, name, alias in SHALLOW_REGIONS:
        if alias in normalized or alias in prefix:
            if best is None or len(alias) > len(best[2]):
                best = (group, name, alias)
    return best


def extract_shallow_narrative(section_text: str) -> list[dict[str, Any]]:
    """按 “<地貌单元>…地下水平均埋深 X m” 的结构抽取叙述性埋深数据。

    先全局定位所有 “地下水平均埋深” 语句，再把语句前缀映射到规范地貌单元，
    避免同一段落中第二个地貌单元误取到第一个地貌单元的数值。
    """
    pat = re.compile(
        r"([\u4e00-\u9fa5（）]{2,30}?)\s*(?:监控区)?\s*(?:\d+\s*月份)?\s*地\s*下\s*水\s*平\s*均\s*埋\s*深\s*([\d.]+)\s*m"
    )
    matches = list(pat.finditer(section_text))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, m in enumerate(matches):
        region = _match_region(m.group(1))
        if region is None:
            continue
        group, name, alias = region
        if name in seen:
            continue
        seen.add(name)
        depth = float(m.group(2))
        tail_end = matches[i + 1].start() if i + 1 < len(matches) else len(section_text)
        window = section_text[m.end() : min(tail_end, m.end() + 320)]
        prev = parse_change(window, r"(?:与|较)?上\s*月")
        year = parse_change(window, r"(?:与|较)?(?:去年|上年)(?:\s*同\s*期)?")
        rec: dict[str, Any] = {
            "group": group,
            "region": name,
            "mean_depth_m": depth,
            "raw_sentence": _sentence_slice(section_text, m.start(), m.end()),
            "change_prev_month_text": prev["text"] if prev else "",
            "change_prev_month_m": prev["value"] if prev else None,
            "change_last_year_text": year["text"] if year else "",
            "change_last_year_m": year["value"] if year else None,
        }
        # 埋深小于 X m 的面积 / 占比
        area_m = re.search(r"埋深小于\s*([\d.]+)\s*m\s*的面积(?:有)?\s*([\d.]+)\s*万\s*km", window)
        share_m = re.search(r"占比\s*(\d+(?:\.\d+)?)\s*%", window)
        if area_m:
            rec["area_threshold_m"] = float(area_m.group(1))
            rec["area_km2"] = float(area_m.group(2)) * 10000
        if share_m:
            rec["area_share_pct"] = float(share_m.group(1))
        out.append(rec)
    # 保持既定排序
    order = {name: idx for idx, (_, name, _) in enumerate(SHALLOW_REGIONS)}
    out.sort(key=lambda r: order.get(r["region"], 999))
    return out


def extract_summary(section_text: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    m = re.search(r"共计\s*(\d+)\s*个地下水监测站", section_text)
    if m:
        out["station_total"] = int(m.group(1))
    m = re.search(r"省[（(]自治区、直辖市[）)]及新疆生产建设兵团共计\s*(\d+)\s*个监测站", section_text)
    if m:
        out["shallow_stations"] = int(m.group(1))
    # 深层监测站数：取“深层地下水水位变化”之后的“共计N个监测站”
    deep_part = section_text.split("深层地下水水位变化", 1)[-1]
    m = re.search(r"共计\s*(\d+)\s*个(?:深层地下水水位)?监测站", deep_part)
    if m:
        out["deep_stations"] = int(m.group(1))
    m = re.search(r"上升、稳定和下降的站点占比分别为\s*([\d.]+)%\s*、\s*([\d.]+)%\s*和\s*([\d.]+)%", section_text)
    if m:
        out["deep_up_pct"], out["deep_stable_pct"], out["deep_down_pct"] = (
            float(m.group(1)),
            float(m.group(2)),
            float(m.group(3)),
        )
    m = re.search(r"水位上升超过\s*2\s*m\s*的站点占比为\s*([\d.]+)%", section_text)
    if m:
        out["deep_up_gt2_pct"] = float(m.group(1))
    m = re.search(r"水位下降超过\s*2\s*m\s*的站点占比为\s*([\d.]+)%", section_text)
    if m:
        out["deep_down_gt2_pct"] = float(m.group(1))
    for key, kw in (("deep_up_top3", "上升超过"), ("deep_down_top3", "下降超过")):
        m = re.search(kw + r"[\s\S]{0,80}?三个省份分别是([^；;。]+)", section_text)
        if m:
            out[key] = m.group(1).strip()
    out["text"] = section_text.strip()
    return out


# ---------------------------------------------------------------------------
# 主解析流程
# ---------------------------------------------------------------------------
def parse_pdf(path: str | Path, period: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(path)
    meta = dict(meta or {})
    year, month = (int(x) for x in period.split("-"))
    result: dict[str, Any] = {
        "period": period,
        "year": year,
        "month": month,
        "title": meta.get("title") or f"《地下水动态月报》{year}年{month}月",
        "publish_date": meta.get("publish_date"),
        "detail_url": meta.get("detail_url"),
        "pdf_url": meta.get("pdf_url"),
        "source_pdf": path.name,
        "pages": 0,
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
        "sections": [],
        "page_texts": [],
        "warnings": [],
    }
    table_rows: dict[int, list[list[str]]] = {}
    table_captions: dict[int, str] = {}
    caption_pages: dict[int, int] = {}
    prev_caption: int | None = None
    section_name = "封面/目录"
    sections: dict[str, list[str]] = {}
    page_texts: list[dict[str, Any]] = []
    toc_pages: set[int] = set()

    with pdfplumber.open(str(path)) as pdf:
        result["pages"] = len(pdf.pages)
        for page in pdf.pages:
            lines = _page_lines(page)
            page_text = "\n".join(ln["text"] for ln in lines)
            if TOC_RE.search(page_text.split("\n")[0] if page_text else "") or "目 录" in page_text:
                toc_pages.add(page.page_number)
            captions: list[tuple[int, str, float]] = []
            for ln in lines:
                cap = _caption_of(ln["text"])
                if cap:
                    captions.append((cap[0], cap[1], ln["top"]))
            # 表格分段：页首→第一个标题（承接上一页表），标题之间，最后一个标题→页尾
            segments: list[tuple[float, float, int | None]] = []
            top_margin = 26.0
            bottom_margin = page.height - 40
            if captions:
                segments.append((top_margin, captions[0][2] - 3, prev_caption))
                for i, (no, _cap, top) in enumerate(captions):
                    end = captions[i + 1][2] - 3 if i + 1 < len(captions) else bottom_margin
                    segments.append((top - 2, end, no))
            else:
                segments.append((top_margin, bottom_margin, prev_caption))
            for y0, y1, cap_no in segments:
                if cap_no is None:
                    continue
                rows = _rows_from_segment(page, y0, y1)
                if rows:
                    table_rows.setdefault(cap_no, []).extend(rows)
            for no, cap, top in captions:
                table_captions.setdefault(no, cap)
                caption_pages.setdefault(no, page.page_number)
                prev_caption = no
            # 章节与正文
            for ln in lines:
                text = ln["text"]
                if page.page_number in toc_pages:
                    continue
                if SECTION_RE.match(text):
                    section_name = text
                    sections.setdefault(section_name, [])
                    continue
                if _is_table_like_line(text):
                    continue
                sections.setdefault(section_name, []).append(text)
            page_texts.append({"page": page.page_number, "text": page_text})
    result["tables"] = {
        str(no): {"caption": table_captions[no], "page": caption_pages.get(no), "rows": table_rows.get(no, [])}
        for no in sorted(table_rows)
    }

    # ---- 逐表解析 ----
    for no, rows in table_rows.items():
        cap = table_captions.get(no, "")
        if no in PRECIP_GROUPS:
            data, warns = _parse_precip(rows, no, cap, period)
            result["precipitation"].extend(data)
            result["warnings"].extend(warns)
        elif 6 <= no <= 13:
            if no == 11:
                data, warns = _parse_shanxi(rows, no, cap)
                result["shanxi_basins"] = data
                result["warnings"].extend(warns)
            else:
                dist, warns = _parse_distribution(rows, no, cap)
                result["shallow_distribution"].append(dist) if dist else result["warnings"].extend(warns)
        elif no == 14:
            data, warns = _parse_deep(rows, no)
            result["deep_provinces"] = data
            result["warnings"].extend(warns)
        elif no == 15:
            data, warns = _parse_water_stations(rows, no)
            result["water_stations"] = data
            result["warnings"].extend(warns)
        elif no == 16:
            data, warns = _parse_temp(rows, no)
            result["temperature_stations"] = data
            result["warnings"].extend(warns)
        elif no == 17:
            data, warns = _parse_springs(rows, no)
            result["springs"] = data
            result["warnings"].extend(warns)
        else:
            result["warnings"].append(f"表{no} 未识别的表类型：{cap}")

    # ---- 章节文本 ----
    for name, lines in sections.items():
        text = ""
        for ln in lines:
            if not ln:
                continue
            if text and not re.search(r"[。；;：:，,、（）()“”《》0-9A-Za-z%‰℃～]$", text):
                text += ln
            else:
                text += ln
        result["sections"].append({"heading": name, "text": text.strip(), "line_count": len(lines)})
    sec_map = {s["heading"]: s["text"] for s in result["sections"]}

    summary_text = ""
    shallow_text = ""
    deep_text = ""
    for heading, text in sec_map.items():
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
    result["page_texts"] = page_texts

    # ---- 完整性校验 ----
    expected = {
        "precipitation": 34,
        "shallow_distribution": 7,
        "shanxi_basins": 6,
        "deep_provinces": 15,
        "water_stations": 30,
        "temperature_stations": 50,
        "springs": 8,
        "shallow_narrative": 18,
    }
    for key, minimum in expected.items():
        got = len(result[key])
        if got < minimum:
            result["warnings"].append(f"{key} 解析数量偏少：{got} < 期望下限 {minimum}")
    return result


if __name__ == "__main__":
    import json
    import sys

    pdf_path = sys.argv[1]
    period = sys.argv[2]
    data = parse_pdf(pdf_path, period)
    print(json.dumps({k: v for k, v in data.items() if k not in {"page_texts", "sections", "tables"}}, ensure_ascii=False, indent=2)[:6000])
    print("\nWARNINGS:", data["warnings"])
