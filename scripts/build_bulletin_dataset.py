# -*- coding: utf-8 -*-
"""Build the historical groundwater dataset from 《中国水资源公报》 1997-2024.

Sources:
  * 1997, 2010: HTML tables inside the bulletin article
  * 2006-2009: flattened region tables inside the HTML narrative
  * 2011-2014: DOCX/DOC attachments
  * 2015-2024: PDF tables (parsed by scripts/parse_bulletin_pdf.py)
  * national series + plain storage change: narrative regex (+ per-year overrides)
"""
import json
import re
from pathlib import Path

from docx import Document

OUT = Path("data/bulletin")
PARSED = OUT / "parsed"
TEXT = OUT / "text"

PROVINCES = [
    "北京", "天津", "河北", "山西", "内蒙古", "辽宁", "吉林", "黑龙江", "上海",
    "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南", "湖北", "湖南",
    "广东", "广西", "海南", "重庆", "四川", "贵州", "云南", "西藏", "陕西",
    "甘肃", "青海", "宁夏", "新疆",
]
REGION_ALIASES = {
    "全国": "全国", "北方6区": "北方6区", "北方六区": "北方6区",
    "南方4区": "南方4区", "南方四区": "南方4区",
    "松花江区": "松花江区", "松花江": "松花江区",
    "辽河区": "辽河区", "辽河": "辽河区",
    "海河区": "海河区", "海河": "海河区",
    "黄河区": "黄河区", "黄河": "黄河区",
    "淮河区": "淮河区", "淮河": "淮河区",
    "长江区": "长江区", "长江": "长江区",
    "珠江区": "珠江区", "珠江": "珠江区",
    "东南诸河区": "东南诸河区", "东南诸河": "东南诸河区",
    "西南诸河区": "西南诸河区", "西南诸河": "西南诸河区",
    "西北诸河区": "西北诸河区", "西北诸河": "西北诸河区",
    "太湖流域": "太湖流域", "太湖": "太湖流域",
    "松辽": "松辽片", "松辽片": "松辽片", "内陆河": "内陆河片",
    "松花江片": "松花江区", "辽河片": "辽河区", "海河片": "海河区",
    "黄河片": "黄河区", "淮河片": "淮河区", "长江片": "长江区", "珠江片": "珠江区",
}
SHORT_PLAINS = {
    "呼包平原": "内蒙古呼包平原", "河套平原": "内蒙古河套平原",
    "关中平原": "陕西关中平原", "银川卫宁平原": "宁夏银川卫宁平原",
    "河南省南襄山间平原区": "河南南襄山间平原区",
    "浙东沿海一般平原": "浙东沿海平原",
    "广东珠江三角洲一般平原": "广东珠江三角洲平原",
    "雷州半岛一般平原": "雷州半岛平原",
    "琼北台地一般平原": "琼北台地平原",
    "河西走廊平原": "甘肃河西走廊平原",
    "柴达木盆地": "青海柴达木盆地",
    "塔里木盆地": "新疆塔里木盆地",
    "准噶尔盆地": "新疆准噶尔盆地",
}
# Manual overrides where narrative wording defeats the regex (verified against the text)
NATIONAL_OVERRIDES = {
    1997: {"ground_resource": 6942.38, "ground_supply": 1031.49, "ground_share": 18.3,
           "total_supply": 5623.16, "plain_storage_change": -200.0, "plain_resource": 1325.0},
    1998: {"ground_share": None},
    2001: {"ground_resource": 8390.0, "ground_supply": None, "ground_share": 19.7,
           "total_supply": 5567.0, "plain_storage_change": -194.0},
    2002: {"ground_resource": 8697.0, "ground_share": 19.5, "plain_storage_change": -113.0},
    2003: {"ground_resource": 8299.0, "plain_storage_change": 167.0},
    2004: {"ground_resource": 7436.0, "plain_storage_change": -68.0},
    2005: {"ground_resource": 8091.0, "ground_supply": 1039.0, "ground_share": 18.4,
           "plain_storage_change": 2.0},
    2006: {"ground_resource": 7643.0, "ground_supply": 1066.0, "ground_share": 18.4,
           "plain_storage_change": -89.0},
    2007: {"ground_resource": 7617.0, "ground_supply": 1069.0, "ground_share": 18.4,
           "plain_storage_change": -86.0},
    2008: {"ground_resource": 8122.0, "ground_supply": None, "ground_share": 18.3,
           "plain_storage_change": -38.0},
    2009: {"ground_resource": 7267.0, "ground_supply": 1094.5, "ground_share": 18.4,
           "plain_storage_change": -16.6},
    2010: {"ground_resource": 8417.0, "ground_supply": 1107.3, "ground_share": 18.4,
           "plain_storage_change": -29.2},
}
NUM = re.compile(r"^-?\d+(?:\.\d+)?$")


def norm(s):
    return re.sub(r"\s+", "", s or "").replace("−", "-").replace("－", "-")


def to_float(s):
    s = norm(s).replace(",", "")
    try:
        return float(s)
    except ValueError:
        return None


def canon_region(name):
    n = norm(name).lstrip("：:")
    if n.startswith("其中"):
        n = n[2:].lstrip("：:")
    return REGION_ALIASES.get(n, n)


def iter_docx_tables(path):
    doc = Document(path)
    out = []
    for tb in doc.tables:
        rows = [[norm(c.text) for c in row.cells] for row in tb.rows]
        out.append(rows)
    return out


def header_map(rows):
    known = set(REGION_ALIASES) | set(PROVINCES) | {"全 国", "全国"}
    data_start = None
    for i, row in enumerate(rows):
        if row and norm(row[0]) in known:
            data_start = i
            break
    if data_start is None:
        return None, None
    ncol = max(len(r) for r in rows)
    keys = []
    for ci in range(ncol):
        parts = []
        for row in rows[:data_start]:
            if ci < len(row):
                t = row[ci]
                if t and (not parts or parts[-1] != t):
                    parts.append(t)
        joined = "".join(parts)
        key = None
        for kw, k in [
            ("直流", None), ("不重复", "unrepeat"), ("地下", "ground"),
            ("地表", "surface"), ("其他", "other"), ("总供", "total_supply"),
            ("生活", "domestic"), ("工业", "industry"), ("农业", "agri"),
            ("生态", "eco"), ("总用", "total_use"), ("降水", "precip"),
        ]:
            if kw in joined:
                key = k
                break
        keys.append(key)
    return data_start, keys


def rows_to_records(rows, data_start, keys):
    out = []
    for row in rows[data_start:]:
        name = norm(row[0]) if row else ""
        if not name:
            continue
        rec = {"name": name}
        for ci in range(1, len(row)):
            k = keys[ci] if ci < len(keys) else None
            if not k:
                continue
            v = to_float(row[ci])
            if v is not None:
                rec.setdefault(k, v)
        if len(rec) > 1:
            out.append(rec)
    return out


def parse_docx_year(path):
    res = {"regions": {}, "provinces": {}}
    for rows in iter_docx_tables(path):
        ds, keys = header_map(rows)
        if ds is None:
            continue
        recs = rows_to_records(rows, ds, keys)
        is_province = any(norm(r[0]) in PROVINCES for r in rows[ds:] if r)
        is_supply = any(k == "total_supply" for k in keys if k)
        target = "provinces" if is_province else "regions"
        kind = "supply" if is_supply else "resources"
        for r in recs:
            n = norm(r["name"])
            if target == "regions":
                if n not in REGION_ALIASES and not n.startswith("其中"):
                    continue
                r["name"] = canon_region(n)
            else:
                if n not in PROVINCES and n != "全国":
                    continue
                r["name"] = n
            res[target].setdefault(kind, []).append(r)
    return res


def parse_html_dump(year):
    p = OUT / "htmltables" / f"{year}.txt"
    res = {"regions": {}}
    if not p.exists():
        return res
    tables = []
    cur = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.startswith("##### TABLE"):
            cur = []
            tables.append(cur)
            continue
        if cur is not None and "|" in line:
            cur.append(line.split("|"))
    for rows in tables:
        dstart = None
        for i, row in enumerate(rows):
            if row and canon_region(row[0]) in REGION_ALIASES.values():
                dstart = i
                break
        if dstart is None:
            continue
        ncols = max(len(r) - 1 for r in rows[dstart:] if r)
        kind = "resources" if ncols == 5 else "supply"
        for row in rows[dstart:]:
            name = canon_region(row[0])
            if name not in REGION_ALIASES.values():
                continue
            nums = [to_float(c) if c.strip() else None for c in row[1:]]
            if len(nums) != ncols:
                continue
            rec = {"name": name}
            if kind == "resources":
                rec.update(dict(zip(["precip", "surface", "ground", "unrepeat", "total"], nums)))
            else:
                if ncols == 8:
                    rec.update(dict(zip(["surface", "ground", "other", "total_supply",
                                         "agri", "industry", "domestic", "total_use"], nums)))
                elif ncols == 9:
                    rec.update(dict(zip(["surface", "ground", "other", "total_supply",
                                         "domestic", "industry", "agri", "eco", "total_use"], nums)))
            res["regions"].setdefault(kind, []).append(rec)
    return res


def parse_inline_regions(year, text):
    """Parse the flattened region tables of 2006-2009.

    The HTML pages contain table rows as plain text: region label followed by
    numbers. Only occurrences whose payload starts with a number are table rows.
    A leading run of 5 numbers is a water-resources row, 9 numbers a supply row.
    """
    names = ["全国", "南方四区", "北方六区", "松花江", "辽河", "海河", "黄河", "淮河",
             "长江", "珠江", "东南诸河", "西南诸河", "西北诸河", "太湖"]
    pattern = "|".join(r"\s*".join(ch for ch in n) for n in names)
    res = {"regions": {}}
    seen = {"resources": set(), "supply": set()}
    for m in re.finditer(pattern, text):
        seg = text[m.end():m.end() + 260]
        if not re.match(r"\s*-?\d", seg):
            continue
        run = re.match(r"\s*((?:-?\d+(?:\.\d+)?\s*)+)", seg)
        if not run:
            continue
        vals = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", run.group(1))]
        while len(vals) > 9:
            vals.pop()
        name = canon_region(m.group(0))
        if len(vals) == 5 and name not in seen["resources"]:
            seen["resources"].add(name)
            rec = {"name": name}
            rec.update(dict(zip(["precip", "surface", "ground", "unrepeat", "total"], vals)))
            res["regions"].setdefault("resources", []).append(rec)
        elif len(vals) == 9 and name not in seen["supply"]:
            seen["supply"].add(name)
            rec = {"name": name}
            rec.update(dict(zip(["surface", "ground", "other", "total_supply",
                                 "domestic", "industry", "agri", "eco", "total_use"], vals)))
            res["regions"].setdefault("supply", []).append(rec)
    return res


def parse_national(year, text):
    rec = {"year": year}
    t = re.sub(r"\s+", "", text)
    m = re.search(r"地下水资源量[^。]{0,40}?([0-9]+(?:\.[0-9]+)?)亿", t)
    if m:
        rec["ground_resource"] = float(m.group(1))
    m = re.search(r"地下水源供水量(?:为)?[^0-9]{0,10}([0-9]+(?:\.[0-9]+)?)亿", t)
    if m:
        rec["ground_supply"] = float(m.group(1))
    m = re.search(r"地下水源供水量占[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)%", t)
    if m:
        rec["ground_share"] = float(m.group(1))
    m = re.search(r"全国总供水量(?:为)?([0-9]+(?:\.[0-9]+)?)亿", t)
    if m:
        rec["total_supply"] = float(m.group(1))
    m = re.search(r"平原区地下水资源量(?:为)?([0-9]+(?:\.[0-9]+)?)亿", t)
    if m:
        rec["plain_resource"] = float(m.group(1))
    m = re.search(r"浅层地下水储存量比(?:年初|上年同期|上年)(增加|减少|下降|上升)约?([0-9]+(?:\.[0-9]+)?)亿", t)
    if m:
        sig = 1 if m.group(1) in ("增加", "上升") else -1
        rec["plain_storage_change"] = sig * float(m.group(2))
    return rec


def main():
    PARSED.mkdir(parents=True, exist_ok=True)
    pdf_tables = json.loads((PARSED / "pdf_tables.json").read_text(encoding="utf-8"))
    dataset = {"reports": [], "national": [], "regions": [], "provinces": [], "plains": [],
               "warnings": []}

    def add_region(year, kind, rec, source, page=None):
        name = rec.get("name")
        if not name:
            return
        out = {"year": year, "level": "region", "name": name, "table": kind, "source": source}
        if page:
            out["page"] = page
        for k, v in rec.items():
            if k != "name" and (isinstance(v, (int, float)) or v is None):
                out[k] = v
        dataset["regions"].append(out)

    def add_province(year, kind, rec, source, page=None):
        out = {"year": year, "level": "province", "name": rec["name"], "table": kind, "source": source}
        if page:
            out["page"] = page
        for k, v in rec.items():
            if k != "name" and (isinstance(v, (int, float)) or v is None):
                out[k] = v
        dataset["provinces"].append(out)

    # --- PDF years 2015-2024
    for year in sorted(pdf_tables, key=int):
        y = int(year)
        for t in pdf_tables[year]:
            kind = t["kind"]
            if kind in ("resources", "supply"):
                is_prov = any(r["name"] in PROVINCES for r in t["rows"])
                for r in t["rows"]:
                    name = norm(r["name"])
                    if is_prov:
                        nn = "全国" if name == "全国" else name
                        if nn != "全国" and nn not in PROVINCES:
                            continue
                        add_province(y, kind, {**r, "name": nn}, "pdf", t["page"])
                    else:
                        nn = canon_region(name)
                        if nn not in REGION_ALIASES.values() and "太湖" not in nn:
                            continue
                        add_region(y, kind, {**r, "name": nn}, "pdf", t["page"])
            elif kind == "plain":
                for r in t["rows"]:
                    name = SHORT_PLAINS.get(norm(r["name"]), norm(r["name"]))
                    rec = {"year": y, "plain": name, "source": "pdf", "page": t["page"],
                           "region": r.get("region")}
                    for k, v in r.items():
                        if k in ("name", "region"):
                            continue
                        rec[k] = v
                    dataset["plains"].append(rec)
    # --- DOCX years
    for year in (2011, 2012, 2013, 2014):
        if year in (2011, 2012):
            src = TEXT / f"{year}.doc.converted.docx"
        else:
            cand = list((OUT / "files").glob(f"{year}_*.docx"))
            src = cand[0] if cand else None
        if not src or not src.exists():
            dataset["warnings"].append(f"{year}: docx missing")
            continue
        res = parse_docx_year(str(src))
        for kind, recs in res["regions"].items():
            for r in recs:
                add_region(year, kind, r, "docx")
        for kind, recs in res["provinces"].items():
            for r in recs:
                add_province(year, kind, r, "docx")
    # --- HTML table years
    for year in (1997, 2010):
        res = parse_html_dump(year)
        for kind, recs in res["regions"].items():
            for r in recs:
                add_region(year, kind, r, "html-table")
    # --- inline region tables 2006-2009 are present in the HTML only as a
    # duplicated flattened dump; parsing them reliably is not worth the risk,
    # so those years keep national figures only (documented in README).
    # --- national narrative
    for year in range(1997, 2025):
        candidates = [TEXT / f"{year}.pdf.txt", TEXT / f"{year}.doc.txt",
                      TEXT / f"{year}.docx.txt", TEXT / f"{year}.html.txt"]
        text = None
        for c in candidates:
            if c.exists() and c.stat().st_size > 3000:
                text = c.read_text(encoding="utf-8")
                if year >= 2015 and c.name.endswith("pdf.txt"):
                    break
                if 2011 <= year <= 2014 and ("doc" in c.name):
                    break
        if text is None:
            dataset["warnings"].append(f"{year}: no text for national")
            continue
        rec = parse_national(year, text)
        rec.update(NATIONAL_OVERRIDES.get(year, {}))
        rec["source"] = "narrative"
        dataset["national"].append(rec)
    # --- merge national ground resource / supply from region tables when available
    nat_map = {}
    for r in dataset["regions"]:
        if r["name"] == "全国":
            nat_map.setdefault(r["year"], {})[r["table"]] = r
    for rec in dataset["national"]:
        y = rec["year"]
        tm = nat_map.get(y, {})
        if "resources" in tm and tm["resources"].get("ground") is not None:
            rec["ground_resource"] = tm["resources"]["ground"]
        if "supply" in tm and tm["supply"].get("ground") is not None:
            rec["ground_supply"] = tm["supply"]["ground"]
        if tm.get("supply", {}).get("total_supply"):
            rec["total_supply"] = tm["supply"]["total_supply"]
            if rec.get("ground_supply"):
                rec["ground_share"] = round(rec["ground_supply"] / rec["total_supply"] * 100, 1)
    (PARSED / "bulletin_dataset.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
    # --- QC: aggregates vs national, region sums vs north+south
    qc = []
    for year in sorted({r["year"] for r in dataset["regions"]}):
        rows = [r for r in dataset["regions"] if r["year"] == year]
        res = {r["name"]: r for r in rows if r["table"] == "resources"}
        sup = {r["name"]: r for r in rows if r["table"] == "supply"}
        for label, table, field in (("resources", res, "ground"), ("supply", sup, "total_supply")):
            if "全国" in table and "北方6区" in table and "南方4区" in table:
                nat = table["全国"].get(field)
                ns = table["北方6区"].get(field)
                ss = table["南方4区"].get(field)
                if None not in (nat, ns, ss) and abs(nat - ns - ss) > 1.0:
                    qc.append(f"{year} {label} 北方+南方≠全国 ({ns}+{ss}!={nat})")
        if "全国" in sup and sup["全国"].get("ground") and sup["全国"].get("total_supply"):
            g = sup["全国"]["ground"]
            if g > sup["全国"]["total_supply"]:
                qc.append(f"{year} supply 地下水>总供水")
        for prov_rows in ([r for r in dataset["provinces"] if r["year"] == year],):
            if not prov_rows:
                continue
            s = [r for r in prov_rows if r["table"] == "supply"]
            if s:
                tot = sum(r.get("ground") or 0 for r in s if r["name"] != "全国")
                nat = next((r for r in s if r["name"] == "全国"), None)
                if nat and nat.get("ground") and abs(tot - nat["ground"]) > 2.0:
                    qc.append(f"{year} 省级地下水供水量之和={tot:.1f} ≠ 全国{nat['ground']}")
    dataset["qc"] = qc
    (PARSED / "bulletin_dataset.json").write_text(
        json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")
    print("regions", len(dataset["regions"]), "provinces", len(dataset["provinces"]),
          "plains", len(dataset["plains"]), "national", len(dataset["national"]),
          "warnings", len(dataset["warnings"]), "qc", len(qc))
    for w in dataset["warnings"]:
        print(" WARN", w)
    for w in qc:
        print(" QC", w)


if __name__ == "__main__":
    main()
