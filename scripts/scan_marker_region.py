# -*- coding: utf-8 -*-
"""Scan pixels around a label to locate the dot marker precisely."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

img = surf.imread_unicode(Path("data/surface/tmp/2025-12_f4_map.jpg"))
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
sub = gray[350:395, 245:300]
print("min/max:", sub.min(), sub.max())
for thr in (80, 110, 140, 170):
    ys, xs = np.where(sub < thr)
    print("thr", thr, "dark px", len(xs))
# 打印该区域的暗色连通域
roi = (gray < 160).astype(np.uint8)[350:395, 245:300]
n, lab, stats, cents = cv2.connectedComponentsWithStats(roi, 8)
for i in range(1, n):
    area = stats[i, cv2.CC_STAT_AREA]
    if area >= 2:
        print("comp", i, "area", area, "bbox", stats[i, :4], "centroid_global",
              (cents[i][0] + 245, cents[i][1] + 350),
              "mean_gray", int(gray[350 + (lab == i).nonzero()[0], 245 + (lab == i).nonzero()[1]].mean()))
cv2.imwrite("data/recon/label_q2.png", img[345:400, 240:320])
print("saved crop")
