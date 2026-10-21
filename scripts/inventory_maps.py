# -*- coding: utf-8 -*-
"""Inventory of 等值面图 (iso-surface maps) across monthly reports (PDF + HTML)."""
import re
from pathlib import Path

import pymupdf

rows = []
for pdf in sorted(Path("data/pdfs").glob("*.pdf")):
    doc = pymupdf.open(pdf)
    caps = []
    for i, page in enumerate(doc):
        text = page.get_text("text")
        for m in re.finditer(r"图\s*(\d+)\s*([^\n]{0,50}等值面图[^\n]{0,20})", text):
            caps.append((i + 1, m.group(1), m.group(2).strip()))
    rows.append((pdf.stem, doc.page_count, len(caps), caps[:6]))
    doc.close()
for r in rows:
    print(r[0], "pages", r[1], "maps", r[2], r[3])

# HTML periods
html_dirs = sorted(Path("data/legacy/html").glob("*"))
print("\nHTML dirs:", [d.name for d in html_dirs][:15])
