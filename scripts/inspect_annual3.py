# -*- coding: utf-8 -*-
"""Check text extraction with PyMuPDF (handles some PDFs better than pypdf)."""
import pymupdf

for year in (2021, 2022, 2023, 2024, 2025):
    path = f"data/annual/pdfs/{year}.pdf"
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001
        print(year, "OPEN FAIL", repr(exc))
        continue
    n = doc.page_count
    nonempty = 0
    sample = None
    for i in range(n):
        t = doc[i].get_text("text")
        if len(t.strip()) > 50:
            nonempty += 1
            if sample is None:
                sample = (i + 1, t[:300].replace("\n", " "))
    print(year, "pages", n, "text_pages", nonempty, "sample", sample)
    doc.close()
