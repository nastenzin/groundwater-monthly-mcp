# -*- coding: utf-8 -*-
"""Diagnose figure page structure for a period with 0 digitized maps."""
import re
import sys
from pathlib import Path

import pymupdf

period = sys.argv[1] if len(sys.argv) > 1 else "2024-10"
doc = pymupdf.open(Path("data/pdfs") / f"{period}.pdf")
print("pages", doc.page_count)
for pno in range(doc.page_count):
    page = doc[pno]
    text = page.get_text("text")
    caps = re.findall(r"图\s*[0-9]+\s*[^\n]{0,80}", text)
    imgs = [(i[2], i[3], tuple(round(v, 1) for v in page.get_image_bbox(i)))
            for i in page.get_images(full=True)]
    if caps or imgs:
        print(f"p{pno + 1}: caps={caps[:2]}")
        print("   images:", imgs)
doc.close()
