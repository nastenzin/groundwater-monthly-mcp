# -*- coding: utf-8 -*-
"""Inspect annual hydrological report PDFs: pages, TOC, groundwater pages."""
import re
import sys
from pathlib import Path

from pypdf import PdfReader

YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2023
path = Path(f"data/annual/pdfs/{YEAR}.pdf")
reader = PdfReader(str(path))
print("year", YEAR, "pages", len(reader.pages), "bytes", path.stat().st_size)
print("=== first pages text ===")
for i in range(min(8, len(reader.pages))):
    text = reader.pages[i].extract_text() or ""
    print(f"--- page {i + 1} len {len(text)}")
    print(text[:800])
