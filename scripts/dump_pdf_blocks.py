# -*- coding: utf-8 -*-
"""Dump PyMuPDF text blocks with coordinates for given pages."""
import sys
from pathlib import Path

import pymupdf

pdf = Path(sys.argv[1])
p0, p1 = int(sys.argv[2]), int(sys.argv[3])
out = Path(sys.argv[4] if len(sys.argv) > 4 else "data/bulletin/probe/blocks.txt")
doc = pymupdf.open(pdf)
parts = []
for pno in range(p0 - 1, min(p1, doc.page_count)):
    page = doc[pno]
    parts.append(f"\n===== PAGE {pno + 1} size={page.rect} =====")
    d = page.get_text("dict")
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for line in b["lines"]:
            txt = "".join(s["text"] for s in line["spans"])
            if not txt.strip():
                continue
            x0, y0, x1, y1 = line["bbox"]
            parts.append(f"{x0:7.1f} {y0:7.1f} {x1:7.1f} {y1:7.1f}  {txt}")
doc.close()
out.write_text("\n".join(parts), encoding="utf-8")
print("written", out, out.stat().st_size)
