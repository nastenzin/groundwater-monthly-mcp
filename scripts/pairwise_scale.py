# -*- coding: utf-8 -*-
"""Pairwise scale consistency using inside-box marker detection."""
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

cities = surf.load_city_points(Path("src/groundwater_mcp/data/geo/city_points.json"))
img = surf.imread_unicode(Path("data/surface/tmp/2025-12_f4_map.jpg"))
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, dark = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)
n, lab, stats, cents = cv2.connectedComponentsWithStats(dark, 8)


def marker(box):
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    x0, x1, yc = min(xs), max(xs), (min(ys) + max(ys)) / 2
    best = None
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if not (3 <= area <= 40 and w_ <= 8 and h_ <= 8 and 0.4 <= w_ / max(1, h_) <= 2.5):
            continue
        cx, cy = cents[i]
        if not (x0 - 3 <= cx <= x0 + 26) or abs(cy - yc) > 9:
            continue
        fill = area / max(1, w_ * h_)
        if fill < 0.4:
            continue
        d = abs(cx - (x0 + 6)) + abs(cy - yc)
        if best is None or d < best[0]:
            best = (d, cx, cy)
    return best


res, _ = RapidOCR()(img)
anchors = []
for box, text, score in res or []:
    t = text.strip(".·•⊙ ").rstrip("市")
    if t in cities:
        mk = marker(box)
        if mk:
            anchors.append((t, mk[1], mk[2], *cities[t]))
for a in anchors:
    print(a[0], round(a[1], 1), round(a[2], 1), "->", a[3], a[4])
print("\npairwise k (km/px):")
ks = []
for i in range(len(anchors)):
    for j in range(i + 1, len(anchors)):
        a, b = anchors[i], anchors[j]
        pxd = math.hypot(a[1] - b[1], a[2] - b[2])
        if pxd < 60:
            continue
        km = math.hypot((b[3] - a[3]) * 111 * math.cos(math.radians((a[4] + b[4]) / 2)),
                        (b[4] - a[4]) * 111)
        ks.append(km / pxd)
        print(f"  {a[0]}-{b[0]}: px={pxd:6.1f} km={km:6.1f} k={km / pxd:.4f}")
print("median k", np.median(ks), "spread", np.std(ks) / np.mean(ks))
