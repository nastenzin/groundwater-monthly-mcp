# -*- coding: utf-8 -*-
"""Dump groundwater chapter pages of an annual report."""
import sys

import pymupdf

year = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
pages = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [77, 78, 81, 82]
doc = pymupdf.open(f"data/annual/pdfs/{year}.pdf")
for p in pages:
    print("=" * 25, "PAGE", p)
    print(doc[p - 1].get_text("text"))
doc.close()
