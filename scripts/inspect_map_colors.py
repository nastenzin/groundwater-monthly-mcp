# -*- coding: utf-8 -*-
"""Inspect dominant colors of the map image vs legend swatch colors."""
import cv2
import numpy as np

img = cv2.imread("data/recon/p7_img0_900x926.jpeg")
h, w = img.shape[:2]
flat = img.reshape(-1, 3).astype(np.float32)
# 排除白底和深色文字/线条
mx = flat.max(axis=1); mn = flat.min(axis=1)
keep = (~((mx > 240) & (mn > 225))) & (mx > 120) & ((mx - mn) > 10)
px = flat[keep]
print("colored-ish pixels:", len(px), f"({len(px) / (h * w) * 100:.1f}%)")
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
K = 14
best = None
for seed in range(3):
    cv2.setRNGSeed(seed)
    compact, lab, centers = cv2.kmeans(px, K, None, criteria, 5, cv2.KMEANS_PP_CENTERS)
    if best is None or compact < best[0]:
        best = (compact, centers, lab)
compact, centers, lab = best
counts = np.bincount(lab.ravel(), minlength=K)
order = np.argsort(-counts)
legend = [
    ("<2", (51, 116, 252)), ("2~4", (112, 200, 252)), ("4~8", (195, 252, 179)),
    ("8~12", (255, 254, 175)), ("12~16", (252, 196, 253)), ("16~20", (190, 153, 253)),
    ("20~30", (254, 208, 93)), ("30~40", (253, 175, 102)), ("40~50", (249, 118, 95)),
    (">50", (242, 12, 17)),
]
lab_legend = []
for name, (r, g, b) in legend:
    bgr = np.uint8([[[b, g, r]]])
    lab_legend.append((name, cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)))
for i in order:
    b, g, r = centers[i]
    bl = cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.float32)
    ds = sorted(((np.linalg.norm(bl - L), name) for name, L in lab_legend))[:2]
    print(f"{counts[i] / len(px) * 100:5.1f}%  rgb=({r:5.0f},{g:5.0f},{b:5.0f})  "
          f"nearest: {ds[0][1]} d={ds[0][0]:.1f}  | {ds[1][1]} d={ds[1][0]:.1f}")
