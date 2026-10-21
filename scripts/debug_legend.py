# -*- coding: utf-8 -*-
"""Debug legend swatch detection on the legend image."""
import cv2
import numpy as np

img = cv2.imread("data/recon/p7_img1_345x232.jpeg")
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
h, w = img.shape[:2]
b, g, r = cv2.split(img)
mx = np.max(img, axis=2).astype(np.int16)
mn = np.min(img, axis=2).astype(np.int16)
chroma = mx - mn
mask = ((chroma > 12) & (mx > 100) & ~((mx > 245) & (mn > 235))).astype(np.uint8) * 255
n, lab, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
print("blobs:", n - 1)
blobs = []
for i in range(1, n):
    area = stats[i, cv2.CC_STAT_AREA]
    x, y, w_, h_ = stats[i, :4]
    if area < 60:
        continue
    pix = img[lab == i]
    bb, gg, rr = np.median(pix, axis=0)
    blobs.append((int(x), int(y), int(w_), int(h_), int(area), (int(rr), int(gg), int(bb))))
blobs.sort(key=lambda t: (t[0] // 120, t[1]))
for bl in blobs:
    print(bl)
