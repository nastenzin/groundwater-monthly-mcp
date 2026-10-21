# -*- coding: utf-8 -*-
"""Marker-dot detection test for city labels on a map."""
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

MAP = Path("data/surface/tmp/2025-12_f4_map.jpg")
cities = surf.load_city_points(Path("src/groundwater_mcp/data/geo/city_points.json"))
img = surf.imread_unicode(MAP)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, dark = cv2.threshold(gray, 110, 255, cv2.THRESH_BINARY_INV)
n, lab, stats, cents = cv2.connectedComponentsWithStats(dark, 8)


def markers_near(box):
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    x0, x1, yc = min(xs), max(xs), (min(ys) + max(ys)) / 2
    hgt = max(ys) - min(ys)
    best = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if not (2 <= area <= 60 and w_ <= 10 and h_ <= 10):
            continue
        cx, cy = cents[i]
        if abs(cy - yc) > hgt * 0.45:
            continue
        dist = min(abs(cx - x0), abs(cx - x1))
        if dist > 22:
            continue
        fill = area / max(1, w_ * h_)
        if fill < 0.4:
            continue
        best.append((dist + abs(cy - yc) * 2, cx, cy, area, w_, h_))
    best.sort()
    return best


res, _ = RapidOCR()(img)
anchors = []
for box, text, score in res or []:
    t = text.strip(".·•⊙ ")
    t2 = t.rstrip("市")
    if t2 not in cities:
        continue
    mk = markers_near(box)
    name = t2
    lon, lat = cities[name]
    print(name, "marker candidates", mk[:3])
    if mk:
        anchors.append((mk[0][1], mk[0][2], lon, lat, name))

print("\nanchors:", len(anchors))
# 尺度：城市对距离中位数
pairs = []
for i in range(len(anchors)):
    for j in range(i + 1, len(anchors)):
        a, b = anchors[i], anchors[j]
        pxd = math.hypot(a[0] - b[0], a[1] - b[1])
        if pxd < 80:
            continue
        km = math.hypot((b[2] - a[2]) * 111 * math.cos(math.radians((a[3] + b[3]) / 2)),
                        (b[3] - a[3]) * 111)
        pairs.append(km / pxd)
k = float(np.median(pairs)) if pairs else None
print("k=", k, "pairs=", len(pairs))
if k:
    mlat = float(np.mean([a[3] for a in anchors]))
    sx = k / (111 * math.cos(math.radians(mlat)))
    sy = k / 111
    # 平移：用中位偏移
    dlons = [a[2] - a[0] * sx for a in anchors]
    dlats = [a[3] + a[1] * sy for a in anchors]
    lon0, lat0 = float(np.median(dlons)), float(np.median(dlats))
    print("lon0,lat0=", lon0, lat0)
    for a in anchors:
        plon = lon0 + a[0] * sx
        plat = lat0 - a[1] * sy
        r = math.hypot((plon - a[2]) * 111 * math.cos(math.radians(a[3])),
                       (plat - a[3]) * 111)
        print(f"  {a[4]}: residual {r:.1f} km")
