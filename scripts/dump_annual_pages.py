# -*- coding: utf-8 -*-
"""Dump annual report pages to UTF-8 text file."""
import sys
from pathlib import Path

import pymupdf

year = int(sys.argv[1])
pages = [int(x) for x in sys.argv[2].split(",")]
out = Path(f"data/annual/pages_{year}_{pages[0]}-{pages[-1]}.txt")
doc = pymupdf.open(f"data/annual/pdfs/{year}.pdf")
chunks = []
for p in pages:
    chunks.append(f"{'=' * 25} PAGE {p}\n" + doc[p - 1].get_text("text"))
doc.close()
out.write_text("\n".join(chunks), encoding="utf-8")
print("wrote", out)
