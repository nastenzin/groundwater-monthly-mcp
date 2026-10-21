# -*- coding: utf-8 -*-
"""Fit similarity/affine transforms on city markers and inspect residual patterns."""
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
_, dark = cv2.threshold(gray, 110, 255, cv2.THRESH_BINARY_INV)
n, lab, stats, cents = cv2.connectedComponentsWithStats(dark, 8)


def marker(box):
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    x0, x1, yc = min(xs), max(xs), (min(ys) + max(ys)) / 2
    best = None
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if not (4 <= area <= 20 and w_ <= 6 and h_ <= 6):
            continue
        cx, cy = cents[i]
        if not (x0 - 2 <= cx <= x0 + 25) or abs(cy - yc) > 10:
            continue
        fill = area / max(1, w_ * h_)
        if fill < 0.5:
            continue
        d = abs(cx - (x0 + 6)) + abs(cy - yc)
        if best is None or d < best[0]:
            best = (d, cx, cy)
    return best


res, _ = RapidOCR()(img)
pairs = []
for box, text, score in res or []:
    t = text.strip(".·•⊙ ").rstrip("市")
    if t not in cities:
        continue
    mk = marker(box)
    if mk:
        lon, lat = cities[t]
        pairs.append((mk[1], mk[2], lon, lat, t))
print("pairs:", [(p[4], round(p[0]), round(p[1])) for p in pairs])
if len(pairs) >= 3:
    src = np.array([[p[0], p[1]] for p in pairs], np.float64)
    dst = np.array([[p[2], p[3]] for p in pairs], np.float64)
    # similarity (scale, rotation, tx, ty) via umeyama
    mu_s, mu_d = src.mean(0), dst.mean(0)
    S = src - mu_s
    D = dst - mu_d
    cov = D.T @ S / len(src)
    U, d_, Vt = np.linalg.svd(cov)
    R = (U @ Vt).T
    scale = d_.sum() / (S ** 2).sum() * len(src)
    t = mu_d - scale * (R @ mu_s)
    print("similarity scale(deg/px):", scale, "R:", R, "t:", t)
    pred = (scale * (R @ (src - mu_s).T).T) + mu_d
    for p, pr in zip(pairs, pred):
        km = math.hypot((pr[0] - p[2]) * 111 * math.cos(math.radians(p[3])),
                        (pr[1] - p[3]) * 111)
        print(f"  {p[4]}: residual {km:.1f} km  pred=({pr[0]:.3f},{pr[1]:.3f}) true=({p[2]:.3f},{p[3]:.3f})")
    A, _ = cv2.estimateAffine2D(src, dst)
    pred2 = cv2.transform(src.reshape(-1, 1, 2), A).reshape(-1, 2)
    print("affine A:", A.tolist())
    for p, pr in zip(pairs, pred2):
        km = math.hypot((pr[0] - p[2]) * 111 * math.cos(math.radians(p[3])),
                        (pr[1] - p[3]) * 111)
        print(f"  affine {p[4]}: residual {km:.1f} km")
