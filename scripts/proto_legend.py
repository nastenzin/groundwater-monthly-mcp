# -*- coding: utf-8 -*-
"""Prototype: decode legend colors + classify one map + register to lon/lat."""
import json
from pathlib import Path

from PIL import Image
import numpy as np

# 1) legend decode: legend image p7_img1_345x232.jpeg
img = Image.open("data/recon/p7_img1_345x232.jpeg").convert("RGB")
arr = np.asarray(img)
print("legend image size", img.size)

# print coarse grid of colors to locate swatches
h, w, _ = arr.shape
for y in range(0, h, 24):
    row = []
    for x in range(0, w, 45):
        r, g, b = arr[y, x]
        row.append(f"({r:3d},{g:3d},{b:3d})")
    print(y, " ".join(row))
