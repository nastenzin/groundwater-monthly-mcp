# -*- coding: utf-8 -*-
"""Test PyMuPDF table finder on bulletin PDF pages."""
import sys
from pathlib import Path

import pymupdf

pdf = Path(sys.argv[1])
p0 = int(sys.argv[2])
p1 = int(sys.argv[3])
doc = pymupdf.open(pdf)
print("pages", doc.page_count, "version", pymupdf.__doc__)
for pno in range(p0 - 1, min(p1, doc.page_count)):
    page = doc[pno]
    tabs = page.find_tables()
    print(f"==== page {pno + 1} tables={len(tabs.tables)}")
    for ti, t in enumerate(tabs.tables):
        rows = t.extract()
        print(f"-- table {ti + 1} rows={len(rows)} bbox={t.bbox}")
        for row in rows[:30]:
            print(" | ".join((c or "").replace("\n", " ").strip() for c in row))
doc.close()
