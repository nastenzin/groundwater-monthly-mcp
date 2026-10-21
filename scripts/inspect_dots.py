# -*- coding: utf-8 -*-
"""Inspect label crops and improve dot detection for anchor calibration."""
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

from proto_anchor import bd09_to_wgs84, load_city_table

IMG = Path("data/recon/p9_img1_850x1000.jpeg")
OUT = Path("data/recon/crops")
OUT.mkdir(parents=True, exist_ok=True)

tbl = load_city_table()
img = cv2.imread(str(IMG))
ocr = RapidOCR()
res, _ = ocr(str(IMG))


def dots_around(img, box):
    """在文字框左右两侧寻找圆形小标记。"""
    x0 = min(p[0] for p in box); x1 = max(p[0] for p in box)
    y0 = min(p[1] for p in box); y1 = max(p[1] for p in box)
    H, W = img.shape[:2]
    cands = []
    for xa, xb in ((x0 - 30, x0 + 4), (x1 - 4, x1 + 30)):
        xa, xb = max(0, int(xa)), min(W, int(xb))
        ya, yb = max(0, int(y0 - 6)), min(H, int(y1 + 6))
        roi = img[ya:yb, xa:xb]
        if roi.size == 0:
            continue
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 110, 255, cv2.THRESH_BINARY_INV)
        n, labels, stats, cents = cv2.connectedComponentsWithStats(th, 8)
        for i in range(1, n):
            area = stats[i, cv2.CC_STAT_AREA]
            w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
            if not (4 <= area <= 80):
                continue
            fill = area / max(1, w_ * h_)
            ar = w_ / max(1, h_)
            if fill >= 0.55 and 0.5 <= ar <= 2.0:
                cands.append((area, cents[i][0] + xa, cents[i][1] + ya, fill, ar))
    return cands


labels = []
for box, text, score in res or []:
    t = text.strip(".·• ")
    t2 = re.sub(r"(市|地区|自治州|盟)$", "", t)
    if t2 in tbl:
        cands = dots_around(img, box)
        labels.append((t, t2, box, cands))
        print(t, "score", round(float(score), 2), "cands", len(cands), cands[:3])
        # 保存文字附近裁剪用于目视
        x0 = int(min(p[0] for p in box)) - 35; x1 = int(max(p[0] for p in box)) + 35
        y0 = int(min(p[1] for p in box)) - 12; y1 = int(max(p[1] for p in box)) + 12
        crop = img[max(0, y0):y1, max(0, x0):x1]
        cv2.imwrite(str(OUT / f"{t2}.png"), crop)
print("saved crops to", OUT)
