# -*- coding: utf-8 -*-
"""Debug extraction for a failing bulletin table page."""
import sys

sys.path.insert(0, "scripts")
import parse_bulletin_pdf as P
import pymupdf

CASES = [(2020, "2020_P020251001647929257446.pdf", 15), (2021, "2021_P020251001647960160197.pdf", 20),
         (2019, "2019_P020251001647902770952.pdf", 10)]
lines = []
for year, fname, pno in CASES:
    doc = pymupdf.open("data/bulletin/files/" + fname)
    page = doc[pno - 1]
    lines.append(f"=== {year} p{pno}")
    tabs = page.find_tables().tables
    lines.append(f"tables={len(tabs)}")
    for t in tabs:
        lines.append(f" bbox={t.bbox} cells={len([c for c in t.cells if c])}")
        cap = P.caption_above(page, t.bbox[1])
        lines.append(f" cap={cap!r} kind={P.classify(cap[0] if cap else '')!r}")
        recs, colx = P.extract_table(page, t, P.classify(cap[0] if cap else "") or "supply")
        lines.append(f" recs={len(recs)} colx={[round(c, 1) for c in colx]}")
        for r in recs[:3]:
            lines.append(f"   {r!r}")
        blocks = [b for b in P._lines(page)
                  if b[0] >= t.bbox[0] - 3 and b[2] <= t.bbox[2] + 3 and b[1] >= t.bbox[1] - 3 and b[3] <= t.bbox[3] + 3]
        lines.append(f" blocks_in_bbox={len(blocks)}")
        numin = [b for b in blocks if P.NUM.match(P.norm(b[4]))]
        lines.append(f" nums_in_bbox={len(numin)} sample={[b[4] for b in numin[:10]]}")
    doc.close()
open("data/bulletin/probe/dbg_fail.txt", "w", encoding="utf-8").write("\n".join(lines))
print("ok")
