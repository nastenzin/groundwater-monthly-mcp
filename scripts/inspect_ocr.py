# -*- coding: utf-8 -*-
"""Inspect raw OCR boxes (including tiny marker boxes) for a map image."""
import sys
from pathlib import Path

from rapidocr_onnxruntime import RapidOCR

img = sys.argv[1] if len(sys.argv) > 1 else "data/recon/p9_img1_850x1000.jpeg"
res, _ = RapidOCR()(img)
rows = []
for box, text, score in res or []:
    x0 = min(p[0] for p in box); x1 = max(p[0] for p in box)
    y0 = min(p[1] for p in box); y1 = max(p[1] for p in box)
    rows.append((y0, x0, x1 - x0, y1 - y0, text, round(float(score), 2)))
rows.sort()
for r in rows:
    print(f"y={r[0]:7.1f} x={r[1]:7.1f} w={r[2]:5.1f} h={r[3]:5.1f} score={r[5]} {r[4]!r}")
