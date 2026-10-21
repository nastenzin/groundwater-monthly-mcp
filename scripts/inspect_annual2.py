# -*- coding: utf-8 -*-
"""Check text layers across annual report PDFs."""
from pathlib import Path

from pypdf import PdfReader

for year in (2021, 2022, 2023, 2024, 2025):
    path = Path(f"data/annual/pdfs/{year}.pdf")
    reader = PdfReader(str(path))
    n = len(reader.pages)
    sample = []
    text_pages = 0
    for i in range(n):
        try:
            t = reader.pages[i].extract_text() or ""
        except Exception:  # noqa: BLE001
            t = ""
        if len(t.strip()) > 30:
            text_pages += 1
            if len(sample) < 2:
                sample.append((i + 1, t[:300].replace("\n", " ")))
    print(year, "pages", n, "text_pages", text_pages, "sample", sample[:1])
