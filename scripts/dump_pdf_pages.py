# -*- coding: utf-8 -*-
"""Dump PyMuPDF text blocks (sorted) for page range to a file for inspection."""
import sys
from pathlib import Path

import pymupdf

pdf = Path(sys.argv[1])
p0, p1 = int(sys.argv[2]), int(sys.argv[3])
out = Path(sys.argv[4] if len(sys.argv) > 4 else "data/bulletin/probe/pages.txt")
doc = pymupdf.open(pdf)
parts = []
for pno in range(p0 - 1, min(p1, doc.page_count)):
    page = doc[pno]
    parts.append(f"\n===== PAGE {pno + 1} =====")
    parts.append(page.get_text("text", sort=True))
doc.close()
out.write_text("".join(parts), encoding="utf-8")
print("written", out, out.stat().st_size)
