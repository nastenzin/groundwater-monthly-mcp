# -*- coding: utf-8 -*-
"""Inspect components near a city label on the 海河 map to size the marker symbol."""
import sys
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

img = surf.imread_unicode(Path("data/surface/tmp/2025-12_f10_map.jpg"))
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
for thr in (120, 150, 180):
    _, dark = cv2.threshold(gray, thr, 255, cv2.THRESH_BINARY_INV)
    n, lab, stats, cents = cv2.connectedComponentsWithStats(dark, 8)
    print("thr", thr, "components", n)
res, _ = RapidOCR()(str(Path("data/surface/tmp/2025-12_f10_map.jpg")))
target = "北京市"
for box, text, score in res or []:
    if text.strip(".·•⊙ ") != target:
        continue
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    x0, x1, yc = min(xs), max(xs), (min(ys) + max(ys)) / 2
    print("box", x0, x1, yc)
    _, dark = cv2.threshold(gray, 160, 255, cv2.THRESH_BINARY_INV)
    n, lab, stats, cents = cv2.connectedComponentsWithStats(dark, 8)
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        cx, cy = cents[i]
        if not (x0 - 40 <= cx <= x1 + 40) or abs(cy - yc) > 25:
            continue
        print(f"  area={area:4d} w={w_:2d} h={h_:2d} cx={cx:7.1f} cy={cy:7.1f} "
              f"fill={area / max(1, w_ * h_):.2f}")
    break
