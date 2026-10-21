# -*- coding: utf-8 -*-
"""Test pdfplumber table extraction on a bulletin PDF page range."""
import sys
from pathlib import Path

import pdfplumber

pdf = Path(sys.argv[1])
p0 = int(sys.argv[2])
p1 = int(sys.argv[3])
with pdfplumber.open(pdf) as doc:
    print("pages", len(doc.pages))
    for pno in range(p0 - 1, min(p1, len(doc.pages))):
        page = doc.pages[pno]
        tabs = page.extract_tables({
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "intersection_tolerance": 5,
        })
        print(f"==== page {pno + 1} tables={len(tabs)}")
        for ti, t in enumerate(tabs):
            print(f"-- table {ti + 1} rows={len(t)}")
            for row in t[:40]:
                print(" | ".join((c or "").replace("\n", " ").strip() for c in row))
