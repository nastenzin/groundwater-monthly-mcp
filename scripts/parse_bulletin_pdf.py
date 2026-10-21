# -*- coding: utf-8 -*-
"""Parse tables out of 《中国水资源公报》 PDFs (2015-2025) into structured JSON.

Strategy: ruling-line table bbox + text-line blocks. Numeric blocks are clustered
into columns (x centres) and rows (y centres); labels left of the first numeric
column give row names. Semantics come from numeric consistency checks, not from
the (merged, partially ruled) header cells.
"""
import json
import re
import sys
from pathlib import Path

import pymupdf

OUT = Path("data/bulletin")
NUM = re.compile(r"^[-−－]?\d+(?:\.\d+)?$")

REGIONS = [
    "全国", "北方6区", "南方4区", "松花江区", "辽河区", "海河区", "黄河区",
    "淮河区", "长江区", "珠江区", "东南诸河区", "西南诸河区", "西北诸河区",
    "太湖流域", "太湖",
]
REGION_SUFFIX = ("区",)

PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西",
    "甘肃", "青海", "宁夏", "新疆",
]

PLAINS = [
    "三江平原", "松嫩平原", "穆棱兴凯平原", "辽河平原", "海河平原", "大同盆地",
    "忻定盆地", "长治盆地", "黄淮平原", "运城盆地", "临汾盆地", "太原盆地",
    "内蒙古呼包平原", "内蒙古河套平原", "陕西关中平原", "宁夏银川卫宁平原",
    "江汉平原", "鄱阳湖平原", "长江三角洲平原", "河南南襄山间平原区",
    "成都平原", "浙东沿海平原", "广东珠江三角洲平原", "雷州半岛平原",
    "琼北台地平原", "甘肃河西走廊平原", "青海柴达木盆地", "新疆塔里木盆地",
    "新疆准噶尔盆地",
]


def norm(s):
    s = re.sub(r"\s+", "", s or "")
    return s.replace("−", "-").replace("－", "-").replace("—", "-")


def seg_centers(centers, gap):
    centers = sorted(centers)
    segs = [[centers[0]]]
    for c in centers[1:]:
        if c - segs[-1][-1] > gap:
            segs.append([c])
        else:
            segs[-1].append(c)
    return [sum(s) / len(s) for s in segs]


def _lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for line in b["lines"]:
            txt = "".join(s["text"] for s in line["spans"]).strip()
            if not txt:
                continue
            x0, y0, x1, y1 = line["bbox"]
            out.append((x0, y0, x1, y1, txt))
    return out


def caption_above(page, y):
    cands = [ln for ln in _lines(page) if ln[3] <= y + 3 and re.match(r"^表\s*\d+", ln[4])]
    if not cands:
        return None
    best = max(cands, key=lambda ln: ln[3])
    ymid = (best[1] + best[3]) / 2
    same = sorted([ln for ln in _lines(page) if abs((ln[1] + ln[3]) / 2 - ymid) < 6], key=lambda ln: ln[0])
    return (" ".join(ln[4] for ln in same), best[3])


def classify(caption):
    if not caption:
        return None
    c = norm(caption)
    if "平原" in c and ("地下水动态" in c or "埋深" in c):
        return "plain"
    if "供用水" in c or ("供水量" in c and "用水量" in c):
        return "supply"
    if "水资源量" in c or "水资源总量" in c:
        return "resources"
    return None


def _words(page):
    out = []
    for x0, y0, x1, y1, txt, *_ in page.get_text("words"):
        txt = txt.strip()
        if not txt:
            continue
        out.append((x0, y0, x1, y1, txt))
    return out


def extract_table(page, t, kind):
    x0, y0, x1, y1 = t.bbox
    blocks = [b for b in _words(page)
              if b[0] >= x0 - 3 and b[2] <= x1 + 3 and b[1] >= y0 - 3 and b[3] <= y1 + 3]
    nums, labels = [], []
    for bx0, by0, bx1, by1, txt in blocks:
        rec = {"tx0": bx0, "ty0": by0, "tx1": bx1, "ty1": by1,
               "cx": (bx0 + bx1) / 2, "cy": (by0 + by1) / 2, "text": txt}
        if NUM.match(norm(txt)):
            rec["value"] = float(norm(txt))
            nums.append(rec)
        else:
            labels.append(rec)
    if len(nums) < 5:
        return [], []
    colx = seg_centers([n["cx"] for n in nums], 12)
    # rows by y clustering
    rows = []
    cur = [nums[0]]
    for n in sorted(nums, key=lambda r: r["cy"]):
        if n["cy"] - cur[-1]["cy"] > 7:
            rows.append(cur)
            cur = [n]
        else:
            cur.append(n)
    rows.append(cur)
    first_y = min(sum(n["cy"] for n in g) / len(g) for g in rows)
    labels = [lb for lb in labels if lb["cy"] > first_y - 5]
    # attach labels: name = label with x1 left of first numeric column
    name_x = colx[0] - 8
    recs = []
    for g in rows:
        yc = sum(n["cy"] for n in g) / len(g)
        vals = [None] * len(colx)
        for n in g:
            ci = min(range(len(colx)), key=lambda i: abs(colx[i] - n["cx"]))
            if abs(colx[ci] - n["cx"]) < 13 and vals[ci] is None:
                vals[ci] = n["value"]
        if sum(v is not None for v in vals) < 2:
            continue
        near = [lb for lb in labels if abs(lb["cy"] - yc) <= 7 and lb["tx1"] <= name_x + 30]
        near.sort(key=lambda lb: (lb["ty0"], lb["tx0"]))
        recs.append({"yc": yc, "nums": vals, "labels": near,
                     "raw": [n["text"] for n in g]})
    used = set()
    for r in recs:
        for lb in r["labels"]:
            used.add(id(lb))
    for lb in labels:
        if id(lb) in used:
            continue
        if lb["tx1"] > name_x + 30:
            continue
        cand = [r for r in recs if 0 < lb["cy"] - r["yc"] <= 20]
        if cand:
            r = max(cand, key=lambda r: r["yc"])
            r["labels"].append(lb)
            used.add(id(lb))
    out = []
    plain_kw = ("平原", "盆地", "三角洲", "台地", "山间", "绿洲", "塬", "灌区")

    def is_region(n):
        if n in REGIONS:
            return True
        if any(n.startswith(p) for p in ("东南", "西北", "黄河区、", "黄河区,", "其中")):
            return True
        if "区" in n and not any(k in n for k in plain_kw):
            return True
        return False

    for r in recs:
        labs = sorted(r["labels"], key=lambda lb: (lb["ty0"], lb["tx0"]))
        name_parts, region = [], None
        for lb in labs:
            n = norm(lb["text"])
            if kind == "plain" and is_region(n):
                region = (region + n) if region else n
            else:
                name_parts.append(n)
        out.append({"name": "".join(name_parts), "region": region, "nums": r["nums"]})
    # drop columns that are empty for every row (stray numeric fragments in label area)
    if out:
        ncol = len(out[0]["nums"])
        keep = [ci for ci in range(ncol) if any(r["nums"][ci] is not None for r in out)]
        if len(keep) < ncol:
            for r in out:
                r["nums"] = [r["nums"][ci] for ci in keep]
            colx = [colx[ci] for ci in keep]
    return out, colx


def map_resources(recs):
    out = []
    for r in recs:
        v = r["nums"]
        if all(x is not None for x in v) and len(v) == 5:
            rec = dict(zip(["precip", "surface", "ground", "unrepeat", "total"], v))
        elif len(v) == 5:
            rec = dict(zip(["precip", "surface", "ground", "unrepeat", "total"], v))
        elif len(v) == 4:
            rec = dict(zip(["surface", "ground", "unrepeat", "total"], v))
        else:
            continue
        # fix ambiguity: if surface+unrepeat != total but shifted by one
        if rec.get("total") and rec.get("surface") is not None and rec["unrepeat"] is not None:
            if abs(rec["surface"] + rec["unrepeat"] - rec["total"]) > 0.6:
                # try 5-col layout where first column was precip in mm
                if len(v) == 5:
                    rec = dict(zip(["precip", "surface", "ground", "unrepeat", "total"], v[1:] + [None]))
        out.append({"name": r["name"], **rec})
    return out


def map_supply(recs):
    found = None
    ncol = max(len(r["nums"]) for r in recs)
    for i in range(1, ncol - 1):
        for j in range(i + 1, ncol):
            ok = tot = 0
            for r in recs:
                w = r["nums"]
                if len(w) != ncol or w[i] is None or w[j] is None:
                    continue
                tot += 1
                supply_sum = sum(x for x in w[:i] if x is not None)
                if abs(w[i] - w[j]) < 0.35 and abs(supply_sum - w[i]) < 0.7:
                    ok += 1
            if tot > 5 and ok >= 0.8 * tot:
                if found is None or ok > found[0]:
                    found = (ok, i, j)
    if not found:
        return []
    _, i, j = found
    out = []
    for r in recs:
        v = r["nums"]
        if len(v) != ncol:
            continue
        supply_cols = v[:i]
        use_cols = [x for x in v[i + 1:j]]
        rec = {"name": r["name"],
               "surface": supply_cols[0] if len(supply_cols) > 0 else None,
               "ground": supply_cols[1] if len(supply_cols) > 1 else None,
               "other": sum(x for x in supply_cols[2:] if x is not None) if len(supply_cols) > 2 else 0.0,
               "total_supply": v[i], "total_use": v[j]}
        u = [x for x in use_cols if x is not None]
        if len(u) == 4:
            rec.update(dict(zip(["domestic", "industry", "agri", "eco"], u)))
        elif len(u) == 5:
            rec.update({"domestic": u[0], "industry": u[1], "dc_thermal": u[2], "agri": u[3], "eco": u[4]})
        out.append(rec)
    return out


def map_plain(recs):
    out = []
    for r in recs:
        v = r["nums"]
        if len(v) < 3:
            continue
        if len(v) >= 7:
            keys = ["area", "shallow_end", "shallow_prev", "shallow_change",
                    "deep_end", "deep_prev", "deep_change"]
        elif len(v) == 6:
            keys = ["shallow_end", "shallow_prev", "shallow_change",
                    "deep_end", "deep_prev", "deep_change"]
        elif len(v) == 4:
            keys = ["area", "shallow_end", "shallow_prev", "shallow_change"]
        else:
            keys = ["shallow_start", "shallow_end", "shallow_change"]
        rec = {"name": r["name"], "region": r.get("region")}
        rec.update({k: v[idx] for idx, k in enumerate(keys) if idx < len(v)})
        out.append(rec)
    return out


def validate(kind, recs):
    problems = []
    if kind == "resources":
        for r in recs:
            if r.get("surface") is not None and r.get("unrepeat") is not None and r.get("total") is not None:
                if abs(r["surface"] + r["unrepeat"] - r["total"]) > 0.6:
                    problems.append(f"resources {r['name']}")
    if kind == "supply":
        for r in recs:
            if r.get("surface") is not None and r.get("ground") is not None and r.get("total_supply"):
                if abs(r["surface"] + r["ground"] + (r.get("other") or 0) - r["total_supply"]) > 0.8:
                    problems.append(f"supply {r['name']} 供水项")
            if r.get("total_use") and r.get("domestic") is not None:
                s = sum(r.get(k) or 0 for k in ("domestic", "industry", "agri", "eco"))
                if abs(s - r["total_use"]) > 0.8:
                    problems.append(f"supply {r['name']} 用水项")
    if kind == "plain":
        for r in recs:
            if r.get("shallow_change") is None:
                continue
            base = r.get("shallow_prev")
            if base is None:
                base = r.get("shallow_start")
            if base is not None and r.get("shallow_end") is not None:
                if abs((r["shallow_end"] - base) - r["shallow_change"]) > 0.15:
                    problems.append(f"plain {r['name']} 变幅")
    return problems


def parse_pdf(path, year):
    doc = pymupdf.open(path)
    tables = []
    for pno in range(doc.page_count):
        page = doc[pno]
        for t in page.find_tables().tables:
            cap = caption_above(page, t.bbox[1])
            cap_txt = cap[0] if cap else ""
            kind = classify(cap_txt)
            if not kind:
                continue
            recs, colx = extract_table(page, t, kind)
            if len(recs) < 3:
                continue
            if kind == "resources":
                mapped = map_resources(recs)
            elif kind == "supply":
                mapped = map_supply(recs)
            else:
                mapped = map_plain(recs)
            tables.append({"page": pno + 1, "caption": cap_txt, "kind": kind,
                           "ncols": len(colx), "rows": mapped, "problems": validate(kind, mapped)})
    doc.close()
    return tables


def main(years):
    idx = json.loads((OUT / "bulletin_index.json").read_text(encoding="utf-8"))
    result = {}
    dest = OUT / "parsed" / "pdf_tables.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        result = json.loads(dest.read_text(encoding="utf-8"))
    for rec in idx:
        if years and rec["year"] not in years:
            continue
        for f in rec.get("local_files") or []:
            if not f["path"].endswith(".pdf"):
                continue
            tables = parse_pdf(f["path"], rec["year"])
            result[str(rec["year"])] = tables
            print(rec["year"], [(t["kind"], t["page"], len(t["rows"]), len(t["problems"])) for t in tables])
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]])
