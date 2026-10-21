# -*- coding: utf-8 -*-
"""Dump text of a text-extractable annual report and locate groundwater sections."""
import re
import sys
from pathlib import Path

import pymupdf

year = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
path = Path(f"data/annual/pdfs/{year}.pdf")
doc = pymupdf.open(str(path))
texts = [doc[i].get_text("text") for i in range(doc.page_count)]
out = Path(f"data/annual/{year}.txt")
out.write_text("\n\n".join(f"########## PAGE {i + 1} ##########\n{t}" for i, t in enumerate(texts)), encoding="utf-8")
print("pages", doc.page_count, "wrote", out)

# TOC
for i, t in enumerate(texts[:10]):
    if "目" in t and "录" in t:
        print(f"--- TOC page {i + 1} ---")
        print(t[:2500])

print("\n=== pages mentioning 地下水 ===")
for i, t in enumerate(texts):
    if "地下水" in t:
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        hits = [ln for ln in lines if "地下水" in ln]
        print(f"p{i + 1}:", " | ".join(hits[:6])[:300])
doc.close()
