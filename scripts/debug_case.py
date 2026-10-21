# -*- coding: utf-8 -*-
"""Debug specific bulletin tables (columns + row nums)."""
import sys

sys.path.insert(0, "scripts")
import parse_bulletin_pdf as P
import pymupdf

CASES = [(2022, "2022_P020251001647981493306.pdf", 28), (2024, "2024_P020251001648223173600.pdf", 17)]
lines = []
for year, fname, pno in CASES:
    doc = pymupdf.open("data/bulletin/files/" + fname)
    page = doc[pno - 1]
    for t in page.find_tables().tables:
        cap = P.caption_above(page, t.bbox[1])
        kind = P.classify(cap[0] if cap else "")
        lines.append(f"=== {year} p{pno} cap={cap[0] if cap else ''} kind={kind} bbox={t.bbox}")
        if not kind:
            continue
        recs, colx = P.extract_table(page, t, kind)
        lines.append(f"colx={[round(c, 1) for c in colx]}")
        for r in recs[:4]:
            lines.append(f"  {r['name']} {r['nums']}")
        mapped = P.map_supply(recs) if kind == "supply" else P.map_resources(recs)
        for r in mapped[:3]:
            lines.append(f"  -> {r}")
    doc.close()
open("data/bulletin/probe/dbg_case.txt", "w", encoding="utf-8").write("\n".join(lines))
print("ok")
