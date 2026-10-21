# -*- coding: utf-8 -*-
"""Debug: numeric block x/y clustering for a bulletin table."""
import sys

sys.path.insert(0, "scripts")
import parse_bulletin_pdf as P
import pymupdf

CASES = [(2015, "2015_P020251001647850218399.pdf", 1), (2022, "2022_P020251001647981493306.pdf", 0)]
out = []
for year, fname, tindex in CASES:
    doc = pymupdf.open("data/bulletin/files/" + fname)
    page = doc[8] if year == 2015 else doc[23]
    t = page.find_tables().tables[tindex]
    x0, y0, x1, y1 = t.bbox
    blocks = [b for b in P._lines(page) if x0 - 2 <= b[0] and b[2] <= x1 + 2 and y0 - 2 <= b[1] and b[3] <= y1 + 2]
    nums = [(b[0], b[1], b[2], b[3], P.norm(b[4])) for b in blocks if P.NUM.match(P.norm(b[4]))]
    out.append(f"=== {year} table{tindex + 1} blocks={len(blocks)} nums={len(nums)}")
    centers = sorted(round((n[0] + n[2]) / 2, 1) for n in nums)
    out.append("centers: " + ", ".join(str(c) for c in centers))
    rights = sorted(round(n[2], 1) for n in nums)
    out.append("rights: " + ", ".join(str(c) for c in rights))
    ys = sorted(round((n[1] + n[3]) / 2, 1) for n in nums)
    out.append("ys: " + ", ".join(str(c) for c in ys))
    doc.close()
open("data/bulletin/probe/dbg_cluster.txt", "w", encoding="utf-8").write("\n".join(out))
print("ok")
