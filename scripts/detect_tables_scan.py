# -*- coding: utf-8 -*-
"""Detect table-heavy pages in scanned annual report by counting horizontal ruling lines."""
from pathlib import Path

import numpy as np
from PIL import Image

for path in sorted(Path("data/annual/scan2021").glob("p*.png")):
    img = Image.open(path).convert("L")
    arr = np.asarray(img)
    h, w = arr.shape
    dark = arr < 160
    row_frac = dark.mean(axis=1)
    long_rows = int((row_frac > 0.5).sum())
    # 去掉上下页边
    body = dark[int(h * 0.08) : int(h * 0.92), :]
    body_rows = int((body.mean(axis=1) > 0.5).sum())
    if body_rows >= 8:
        print(path.name, "hlines", body_rows, "size", img.size)
