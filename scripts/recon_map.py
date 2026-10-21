# -*- coding: utf-8 -*-
"""Recon: 月报等值面图页的构成（图片/矢量/文本/图例/坐标标注）。"""
import re
from pathlib import Path

import pymupdf

pdf = Path("data/pdfs/2025-12.pdf")
doc = pymupdf.open(pdf)
page = doc[6]
print("page rect", page.rect)
print("images:", [(i[0], i[2], i[3]) for i in page.get_images(full=True)])
drawings = page.get_drawings()
print("drawings:", len(drawings))
if drawings:
    fills = [d.get("fill") for d in drawings[:20]]
    print("first fills:", fills)
text = page.get_text("text")
print("---- text ----")
print(text[:2000])
print("---- image bbox ----")
for img in page.get_images(full=True):
    print(page.get_image_bbox(img))
Path("data/recon").mkdir(exist_ok=True)
pix = page.get_pixmap(dpi=200)
pix.save("data/recon/2025-12_p7.png")
print("saved", pix.width, pix.height)
doc.close()
