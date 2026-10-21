# -*- coding: utf-8 -*-
"""Fit affine vs quadratic pixel->lonlat on a map with many city labels."""
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

MAP = Path(sys.argv[1] if len(sys.argv) > 1 else "data/surface/tmp/2025-12_f10_map.jpg")
cities = surf.load_city_points(Path("src/groundwater_mcp/data/geo/city_points.json"))
img = surf.imread_unicode(MAP)
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
        if not (x0 - 4 <= cx <= x0 + 26) or abs(cy - yc) > 9:
            continue
        if area / max(1, w_ * h_) < 0.4:
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
print("anchors", len(anchors), [(a[0]) for a in anchors])
if len(anchors) >= 4:
    P = np.array([[a[1], a[2], 1.0] for a in anchors])
    T = np.array([[a[3], a[4]] for a in anchors])
    # 先用最小二乘 affine，再逐步剔除离群
    w = np.ones(len(anchors))
    for it in range(5):
        W = np.diag(w)
        beta, *_ = np.linalg.lstsq(P * w[:, None], T * w[:, None], rcond=None)
        pred = P @ beta
        res = np.sqrt(((pred - T) ** 2).sum(axis=1))
        w = (res <= max(3.0, np.median(res) * 1.5)).astype(float)
        if w.sum() < 4:
            break
    print("affine inliers", int(w.sum()), "rmse", round(float(np.sqrt((res[w > 0] ** 2).mean()) * 111), 2), "km")
    # 二次多项式（6 参数）
    Q = np.hstack([P, (P[:, 0] ** 2)[:, None], (P[:, 0] * P[:, 1])[:, None],
                   (P[:, 1] ** 2)[:, None]])
    w2 = np.ones(len(anchors))
    for it in range(8):
        W = np.diag(w2)
        beta2, *_ = np.linalg.lstsq(Q * w2[:, None], T * w2[:, None], rcond=None)
        pred2 = Q @ beta2
        res2 = np.sqrt(((pred2 - T) ** 2).sum(axis=1))
        w2 = (res2 <= max(2.0, np.median(res2) * 1.5)).astype(float)
        if w2.sum() < 8:
            break
    print("quad inliers", int(w2.sum()), "rmse", round(float(np.sqrt((res2[w2 > 0] ** 2).mean()) * 111), 2), "km")
    for a, r1, r2 in zip(anchors, res, res2):
        print(f"  {a[0]:>6} affine={r1 * 111:6.1f}km quad={r2 * 111:6.1f}km")
