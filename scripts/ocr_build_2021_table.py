# -*- coding: utf-8 -*-
"""Rebuild 2021 annual groundwater table from OCR boxes (region-anchored).

输出 data/annual/scan2021/table2021.json，字段为通用 first/second（2020/2021）。
"""
import json
from pathlib import Path

ITEMS = json.loads(Path("data/annual/scan2021/ocr_p067.json").read_text(encoding="utf-8"))
ITEMS = [it for it in ITEMS if it["y"] > 930]

COLUMN_RANGES = [
    ("group", 0, 500),
    ("region", 500, 1000),
    ("shallow_first", 1000, 1250),
    ("shallow_second", 1250, 1430),
    ("shallow_change", 1430, 1620),
    ("deep_first", 1620, 1800),
    ("deep_second", 1800, 1990),
    ("deep_change", 1990, 2300),
]

CANONICAL = {
    "三江平原": "三江平原",
    "松嫩平原": "松嫩平原",
    "穆棱兴凯平原": "穆棱兴凯平原",
    "辽河平原": "辽河平原",
    "海河平原": "海河平原",
    "大同盆地": "大同盆地",
    "忻定盆地": "忻定盆地",
    "长治盆地": "长治盆地",
    "黄淮平原": "黄淮平原",
    "运城盆地": "运城盆地",
    "临汾盆地": "临汾盆地",
    "太原盆地": "太原盆地",
    "内蒙古呼包平原": "呼包平原",
    "内蒙古河套平原": "河套平原",
    "陕西关中平原": "关中平原",
    "宁夏银川卫宁平原": "银川卫宁平原",
    "江汉平原": "江汉平原",
    "鄱阳湖平原": "鄱阳湖平原",
    "长江三角洲平原": "长江三角洲平原",
    "河南南襄山间平原区": "河南省南襄山间平原",
    "成都平原": "成都平原",
    "浙东沿海一般平原": "浙东沿海平原",
    "广东珠江三角洲一般平原": "广东珠江三角洲平原",
    "雷州半岛一般平原": "雷州半岛平原",
    "琼北台地一般平原": "琼北台地平原",
    "甘肃河西走廊平原": "河西走廊平原",
    "青海柴达木盆地": "柴达木盆地",
    "新疆塔里木盆地": "塔里木盆地",
    "新疆准噶尔盆地": "准噶尔盆地",
}


def norm_num(text: str) -> str:
    return text.replace("—", "-").replace("−", "-").replace(" ", "")


def as_float(text: str):
    text = norm_num(text).rstrip(".")
    if text in {"", "-", "/"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


region_items = []
group_items = []
numeric_items = []
for it in ITEMS:
    x = it["x"]
    if 500 <= x < 1000:
        region_items.append(it)
    elif x < 500:
        group_items.append(it)
    else:
        numeric_items.append(it)

region_items.sort(key=lambda it: it["y"])
anchors = region_items


def nearest_anchor(y: float, max_dist: float = 40.0):
    best = None
    best_d = 1e9
    for it in anchors:
        d = abs(it["y"] - y)
        if d < best_d:
            best, best_d = it, d
    return best if best_d <= max_dist else None


rows: dict[int, dict] = {}
for idx, it in enumerate(anchors):
    rows[idx] = {"region_label": it["text"], "region_group": "", "values": {}}

for it in numeric_items:
    col = None
    for name, lo, hi in COLUMN_RANGES:
        if lo <= it["x"] < hi and name not in {"group", "region"}:
            col = name
            break
    if col is None:
        continue
    anchor = nearest_anchor(it["y"], max_dist=45)
    if anchor is None:
        continue
    idx = anchors.index(anchor)
    rows[idx]["values"][col] = rows[idx]["values"].get(col, "") + norm_num(it["text"])

for it in group_items:
    anchor = nearest_anchor(it["y"], max_dist=60)
    if anchor is None:
        continue
    idx = anchors.index(anchor)
    if rows[idx]["region_group"]:
        continue
    rows[idx]["region_group"] = it["text"]

out = []
for idx in sorted(rows):
    row = rows[idx]
    label = row["region_label"]
    canonical = CANONICAL.get(label)
    if not canonical:
        print("WARN unknown region:", label)
        canonical = label
    values = row["values"]
    rec = {
        "region": canonical,
        "region_label": label,
        "region_group": row["region_group"],
        "shallow_first": as_float(values.get("shallow_first", "")),
        "shallow_second": as_float(values.get("shallow_second", "")),
        "shallow_change": as_float(values.get("shallow_change", "")),
        "deep_first": as_float(values.get("deep_first", "")),
        "deep_second": as_float(values.get("deep_second", "")),
        "deep_change": as_float(values.get("deep_change", "")),
    }
    out.append(rec)

print("rows", len(out))
problems = []
for rec in out:
    print(rec)
    for key in ("shallow", "deep"):
        first, second, chg = (
            rec[f"{key}_first"],
            rec[f"{key}_second"],
            rec[f"{key}_change"],
        )
        if first is not None and second is not None and chg is not None:
            diff = round(first - second, 1)
            if abs(diff - chg) > 0.15:
                problems.append((rec["region"], key, diff, chg))
print("consistency problems:", problems)
Path("data/annual/scan2021/table2021.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
