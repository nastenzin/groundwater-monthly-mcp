# -*- coding: utf-8 -*-
"""Inspect colored components on a thumbnail page to isolate map vs legend."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

PALETTE = [[51, 116, 252], [112, 200, 252], [195, 252, 179], [255, 254, 175],
           [252, 196, 253], [190, 153, 253], [254, 208, 93], [253, 175, 102],
           [249, 118, 95], [242, 12, 17]]
legend = [{"range": surf.RANGES[i], "lo": surf.BOUNDS[i], "hi": surf.BOUNDS[i + 1],
           "rgb": PALETTE[i]} for i in range(10)]
img = surf.imread_unicode(Path("data/surface/html/2024-09/p7.jpg"))
up = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
cls = surf.classify_map(up, legend)
mask = (cls >= 0).astype(np.uint8)
n, lab, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
order = sorted(range(1, n), key=lambda i: -stats[i, cv2.CC_STAT_AREA])
for i in order[:8]:
    x, y, w, h, a = stats[i]
    print(f"comp area={a:7d} bbox=({x},{y},{w},{h}) centroid=({cents[i][0]:.0f},{cents[i][1]:.0f})")
print("page size", up.shape)
