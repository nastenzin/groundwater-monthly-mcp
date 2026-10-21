# -*- coding: utf-8 -*-
"""Prototype 3: city-dot anchors + Baidu->WGS84 city table -> affine calibration."""
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
import requests
from rapidocr_onnxruntime import RapidOCR

CACHE = Path("data/recon/city_geo.json")


def load_city_table():
    if CACHE.exists():
        return json.loads(CACHE.read_text(encoding="utf-8"))
    r = requests.get("https://cdn.jsdelivr.net/gh/88250/city-geo@master/data.json", timeout=90)
    rows = r.json()
    tbl = {}
    for row in rows:
        if row.get("area"):
            continue
        city = row["city"]
        if city == "市辖区":
            city = row["province"]
        for suffix in ("市", "地区", "自治州", "盟", "特别行政区"):
            if city.endswith(suffix):
                city = city[: -len(suffix)]
                break
        if not city:
            continue
        if not row.get("lng") or not row.get("lat"):
            continue
        tbl.setdefault(city, (float(row["lng"]), float(row["lat"])))
    CACHE.write_text(json.dumps(tbl, ensure_ascii=False, indent=1), encoding="utf-8")
    return tbl


X_PI = 3.14159265358979324 * 3000.0 / 180.0


def bd09_to_wgs84(lng, lat):
    x, y = lng - 0.0065, lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    return z * math.cos(theta), z * math.sin(theta)


def find_dots(img, box):
    """在文字框附近找小圆点标记，返回像素坐标。"""
    x0 = min(p[0] for p in box); x1 = max(p[0] for p in box)
    y0 = min(p[1] for p in box); y1 = max(p[1] for p in box)
    pad = 28
    H, W = img.shape[:2]
    xa, xb = max(0, int(x0 - pad)), min(W, int(x1 + pad))
    ya, yb = max(0, int(y0 - pad)), min(H, int(y1 + pad))
    roi = img[ya:yb, xa:xb]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)
    n, labels, stats, cents = cv2.connectedComponentsWithStats(th, 8)
    best = None
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if 4 <= area <= 60 and 0.4 <= w_ / max(1, h_) <= 2.5:
            d = abs(cents[i][0] + xa - (x0 + x1) / 2) + abs(cents[i][1] + ya - (y0 + y1) / 2)
            if best is None or d < best[0]:
                best = (d, cents[i][0] + xa, cents[i][1] + ya)
    return (best[1], best[2]) if best else None


def main():
    tbl = load_city_table()
    print("city table:", len(tbl))
    img = cv2.imread("data/recon/p9_img1_850x1000.jpeg")
    ocr = RapidOCR()
    res, _ = ocr("data/recon/p9_img1_850x1000.jpeg")
    labels = []
    for box, text, score in res or []:
        t = text.strip(".·• ")
        t = re.sub(r"(市|地区)$", "", t)
        if t in tbl:
            dot = find_dots(img, box)
            labels.append((t, box, dot, score))
    print("labels with city match:", [(l[0], l[2]) for l in labels])
    anchors = []
    for t, box, dot, score in labels:
        if not dot:
            continue
        lon, lat = bd09_to_wgs84(*tbl[t])
        anchors.append((dot[0], dot[1], lon, lat, t))
    print("anchors:", anchors)
    if len(anchors) >= 3:
        src = np.array([[a[0], a[1]] for a in anchors], np.float64)
        dst = np.array([[a[2], a[3]] for a in anchors], np.float64)
        A, mask = cv2.estimateAffine2D(src, dst, method=cv2.LMEDS)
        print("affine:\n", A)
        pred = cv2.transform(src.reshape(-1, 1, 2), A).reshape(-1, 2)
        for a, p in zip(anchors, pred):
            km = math.hypot((p[0] - a[2]) * 111 * math.cos(math.radians(a[3])), (p[1] - a[3]) * 111)
            print(f"  {a[4]} residual {km:.1f} km")
        # 检查比例尺是否各向异性
        print("px per deg lon:", 1 / abs(A[0, 0]), "px per deg lat:", 1 / abs(A[1, 1]))


if __name__ == "__main__":
    main()
