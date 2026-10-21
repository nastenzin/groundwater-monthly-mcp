# -*- coding: utf-8 -*-
"""Dump PyMuPDF table cell bboxes for inspection."""
import sys
from pathlib import Path

import pymupdf

pdf = Path(sys.argv[1])
p0, p1 = int(sys.argv[2]), int(sys.argv[3])
out = Path(sys.argv[4] if len(sys.argv) > 4 else "data/bulletin/probe/cells.txt")
doc = pymupdf.open(pdf)
parts = []
for pno in range(p0 - 1, min(p1, doc.page_count)):
    page = doc[pno]
    tabs = page.find_tables()
    parts.append(f"\n===== PAGE {pno + 1} tables={len(tabs.tables)}")
    for ti, t in enumerate(tabs.tables):
        parts.append(f"-- table {ti + 1} bbox={t.bbox} row_count={t.row_count} col_count={t.col_count}")
        for ci, cell in enumerate(t.cells):
            if cell is None:
                continue
            x0, y0, x1, y1 = cell
            w = page.get_text("text", clip=pymupdf.Rect(x0, y0, x1, y1)).strip().replace("\n", " / ")
            parts.append(f"  {ci:3d} [{x0:6.1f},{y0:6.1f},{x1:6.1f},{y1:6.1f}] {w}")
doc.close()
out.write_text("\n".join(parts), encoding="utf-8")
print("written", out)
