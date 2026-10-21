# -*- coding: utf-8 -*-
"""Validate color-class decoding by connected components (map lobes) vs narrative averages."""
import cv2
import numpy as np

CLASSES = [
    ("<2", (55, 114, 206), 1.0), ("2~4", (117, 199, 247), 3.0),
    ("4~8", (189, 255, 176), 6.0), ("8~12", (255, 255, 165), 10.0),
    ("12~16", (243, 201, 247), 14.0), ("16~20", (192, 177, 220), 18.0),
    ("20~30", (239, 217, 144), 25.0), ("30~40", (235, 185, 136), 35.0),
    ("40~50", (223, 134, 118), 45.0), (">50", (169, 63, 65), 55.0),
]

img = cv2.imread("data/recon/p7_img0_900x926.jpeg")
h, w = img.shape[:2]
lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.int16)
legend = [cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.int16)
          for _, (r, g, b), _ in CLASSES]
flat = lab.reshape(-1, 3)
d = np.stack([np.linalg.norm(flat - L, axis=1) for L in legend], axis=1)
cls = np.where(d.min(axis=1) < 42, d.argmin(axis=1), -1).reshape(h, w).astype(np.int16)
mask = (cls >= 0).astype(np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
n, labels_, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
mid = np.array([c[2] for c in CLASSES])
print("components >= 5000 px:")
comps = sorted([i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 5000],
               key=lambda i: -stats[i, cv2.CC_STAT_AREA])
for i in comps:
    comp_mask = labels_ == i
    vals = cls[comp_mask & (cls >= 0)]
    share = {CLASSES[k][0]: round(float((vals == k).mean() * 100), 1) for k in range(len(CLASSES)) if (vals == k).any()}
    print(f"  comp {i}: area={stats[i, cv2.CC_STAT_AREA]:6d} bbox={tuple(int(v) for v in stats[i][:4])} "
          f"mean_depth={mid[vals].mean():5.2f} m  share={share}")
