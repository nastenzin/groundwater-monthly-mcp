# -*- coding: utf-8 -*-
"""Diagnose bulletin supply/resource table mappings for selected years."""
import sys

sys.path.insert(0, "scripts")
import parse_bulletin_pdf as P
import pymupdf

CASES = [
    (2015, "2015_P020251001647850218399.pdf", 9),
    (2016, "2016_P020251001647861405700.pdf", 6),
    (2020, "2020_P020251001647929257446.pdf", 15),
    (2022, "2022_P020251001647981493306.pdf", 28),
    (2024, "2024_P020251001648223173600.pdf", 27),
    (2024, "2024_P020251001648223173600.pdf", 17),
]
out = []
for year, fname, page_no in CASES:
    doc = pymupdf.open("data/bulletin/files/" + fname)
    page = doc[page_no - 1]
    out.append(f"=== {year} page {page_no}")
    for t in page.find_tables().tables:
        cap = P.caption_above(page, t.bbox[1])
        kind = P.classify(cap[0] if cap else "")
        out.append(f"  kind={kind} caption={cap[0] if cap else ''!r}")
        if kind not in ("supply", "resources"):
            continue
        cols, rows = P.table_rows(page, t, kind)
        recs = P.numeric_rows(rows, len(cols), 1)
        out.append(f"  cols={len(cols)} recs={len(recs)}")
        for r in recs[:3]:
            out.append(f"    {r['name']} {r['nums']}")
        mapped = P.map_supply(recs) if kind == "supply" else P.map_resources(recs)
        for r in mapped[:3]:
            out.append(f"    -> {r}")
        probs = P.validate(kind, mapped, year)
        out.append(f"  problems={len(probs)} sample={probs[:3]}")
    doc.close()
open("data/bulletin/probe/diag_supply.txt", "w", encoding="utf-8").write("\n".join(out))
print("written")
