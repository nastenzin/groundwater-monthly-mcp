# -*- coding: utf-8 -*-
"""Survey figure pages of one monthly report: caption, map image, legend image, extra strips."""
import re
from pathlib import Path

import pymupdf

pdf = Path("data/pdfs/2025-12.pdf")
doc = pymupdf.open(pdf)
for pno in range(doc.page_count):
    page = doc[pno]
    imgs = [(i[2], i[3], page.get_image_bbox(i)) for i in page.get_images(full=True)]
    caps = re.findall(r"图\s*(\d+)\s*([^\n]{0,45}等值面图[^\n]{0,15})", page.get_text("text"))
    if not caps and not imgs:
        continue
    print(f"p{pno+1}: caps={[c[0] for c in caps]}")
    for w, h, bb in imgs:
        kind = "legend" if 300 <= w <= 400 and 200 <= h <= 260 else ("map" if w * h > 100000 else "strip")
        print(f"   {kind}: {w}x{h} bbox={tuple(round(v,1) for v in bb)}")
    if caps:
        print("   caption text:", caps[0][1] if caps else "")
doc.close()
