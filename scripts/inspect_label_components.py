# -*- coding: utf-8 -*-
"""List dark components near a city label to find the true marker dot."""
import sys
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

img = surf.imread_unicode(Path("data/surface/tmp/2025-12_f4_map.jpg"))
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
_, dark = cv2.threshold(gray, 110, 255, cv2.THRESH_BINARY_INV)
n, lab, stats, cents = cv2.connectedComponentsWithStats(dark, 8)
res, _ = RapidOCR()(str(Path("data/surface/tmp/2025-12_f4_map.jpg")))
for box, text, score in res or []:
    t = text.strip(".·•⊙ ")
    if t.rstrip("市") != "齐齐哈尔":
        continue
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    x0, x1, yc = min(xs), max(xs), (min(ys) + max(ys)) / 2
    print("box", x0, x1, yc, "text", text)
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        cx, cy = cents[i]
        if abs(cy - yc) > 14:
            continue
        if not (x0 - 30 <= cx <= x1 + 30):
            continue
        print(f"  comp area={area:4d} w={w_:2d} h={h_:2d} cx={cx:7.1f} cy={cy:7.1f} "
              f"rel_to_x0={cx - x0:6.1f} fill={area / max(1, w_ * h_):.2f}")
    # 保存裁剪
    crop = img[int(yc) - 18:int(yc) + 18, int(x0) - 35:int(x0) + 40]
    cv2.imwrite("data/recon/label_q.png", crop)
    print("crop saved")
