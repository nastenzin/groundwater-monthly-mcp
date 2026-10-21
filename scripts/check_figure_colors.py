# -*- coding: utf-8 -*-
"""检查月报“地下水埋深等值面图”页是否为彩色图（仅用于说明图件性质，不参与取数）。"""
from pathlib import Path

import pymupdf

pdf = Path("data/pdfs/2025-12.pdf")
doc = pymupdf.open(pdf)
page = doc[6]  # 第 7 页
pix = page.get_pixmap(dpi=60)
samples = pix.samples
n = pix.width * pix.height
colors = set()
for i in range(0, len(samples), pix.n * 7):
    colors.add(tuple(samples[i:i + 3]))
print("page", 7, "size", pix.width, pix.height, "sampled colors:", len(colors))
print("has_many_colors:", len(colors) > 50)
doc.close()
