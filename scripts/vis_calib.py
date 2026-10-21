# -*- coding: utf-8 -*-
"""Visualize calibration: city points back-projected onto the map image."""
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

period = "2025-12"
fig = 4
d = json.loads(Path(f"data/surface/parsed/{period}.json").read_text(encoding="utf-8"))
rec = next(m for m in d["maps"] if m["figure"] == fig)
img = surf.imread_unicode(Path(f"data/surface/tmp/{period}_f{fig}_map.jpg"))
cities = surf.load_city_points(Path("src/groundwater_mcp/data/geo/city_points.json"))
A = np.array(rec["affine"], np.float32)
# 逆变换：经纬度 -> 像素
Ai = cv2.invertAffineTransform(A)
vis = img.copy()
h, w = img.shape[:2]
for name, (lon, lat) in cities.items():
    # 只画落在图像范围内的
    px = cv2.transform(np.array([[[lon, lat]]], np.float64), Ai)[0, 0]
    x, y = float(px[0]), float(px[1])
    if -50 <= x <= w + 50 and -50 <= y <= h + 50:
        cv2.circle(vis, (int(x), int(y)), 4, (0, 0, 255), -1)
        cv2.putText(vis, name, (int(x) + 5, int(y)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                    (0, 0, 128), 1, cv2.LINE_AA)
out = Path(f"data/recon/calib_overlay_f{fig}.png")
cv2.imwrite(str(out), vis)
print("saved", out)
print("affine", A.tolist(), "k", rec["k_km_per_px"], "quality", rec["quality"])
