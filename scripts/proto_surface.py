# -*- coding: utf-8 -*-
"""Prototype: 彩色等值面图 -> 等级栅格 -> 经纬度配准 -> 点查询/区域均值校验。"""
import json
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from shapely.geometry import Polygon, Point, shape
from shapely.ops import unary_union

MAP = Path("data/recon/p7_img0_900x926.jpeg")
LEGEND = Path("data/recon/p7_img1_345x232.jpeg")
UNITS = Path("src/groundwater_mcp/data/geo/units.geojson")
CITIES = Path("src/groundwater_mcp/data/geo/china_cities.geojson")

CLASSES = [
    ("<2", (55, 114, 206), 1.0),
    ("2~4", (117, 199, 247), 3.0),
    ("4~8", (189, 255, 176), 6.0),
    ("8~12", (255, 255, 165), 10.0),
    ("12~16", (243, 201, 247), 14.0),
    ("16~20", (192, 177, 220), 18.0),
    ("20~30", (239, 217, 144), 25.0),
    ("30~40", (235, 185, 136), 35.0),
    ("40~50", (223, 134, 118), 45.0),
    (">50", (169, 63, 65), 55.0),
]

img = cv2.imread(str(MAP))
h, w = img.shape[:2]
lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.int16)
legend_lab = [cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.int16)
              for _, (r, g, b), _ in CLASSES]
# 最近邻分类 + 阈值
flat = lab.reshape(-1, 3)
d = np.stack([np.linalg.norm(flat - L, axis=1) for L in legend_lab], axis=1)
idx = d.argmin(axis=1)
mind = d.min(axis=1)
cls = np.where(mind < 42, idx, -1).reshape(h, w).astype(np.int16)
mask = (cls >= 0).astype(np.uint8)
print("map", w, "x", h, "colored pixels", int(mask.sum()), f"({mask.mean()*100:.1f}%)")
print("class pixel share:", {CLASSES[i][0]: round(float((cls == i).mean() * 100), 1) for i in range(len(CLASSES)) if (cls == i).any()})

# 城市名 OCR
ocr = RapidOCR()
res, _ = ocr(str(MAP))
labels = []
for box, text, score in res or []:
    if any(k in text for k in ("市", "县", "区")) and len(text) <= 8:
        cx = sum(p[0] for p in box) / 4
        cy = sum(p[1] for p in box) / 4
        labels.append((text, cx, cy, score))
print("city-like OCR labels:", labels)

# 城市中心
city_geo = json.loads(CITIES.read_text(encoding="utf-8"))
city_pts = {}
for f in city_geo["features"]:
    name = f["properties"]["name"]
    geom = shape(f["geometry"])
    c = geom.centroid
    city_pts[name.replace("市", "")] = (c.x, c.y)

# 建立标签-坐标对应（标签框中心 vs 城市中心；地图中标签文本在点右侧，需用文本起点附近的圆点，先粗略用文本中心）
pairs = []
for text, cx, cy, score in labels:
    key = text.replace("市", "")
    for name, (lon, lat) in city_pts.items():
        if key and (key in name or name in key) and len(key) >= 2:
            pairs.append((cx, cy, lon, lat, text))
            break
print("anchor pairs:", pairs)

if len(pairs) >= 3:
    src = np.array([[p[0], p[1]] for p in pairs], dtype=np.float64)
    dst = np.array([[p[2], p[3]] for p in pairs], dtype=np.float64)
    # 仿射：pix -> lon/lat
    A, *_ = cv2.estimateAffine2D(src, dst, method=cv2.LMEDS)
    print("affine pix->lonlat:\n", A)
    if A is not None:
        pred = cv2.transform(src.reshape(-1, 1, 2), A).reshape(-1, 2)
        for (p, q, pair) in zip(pred, dst, pairs):
            print("residual deg:", pair[4], np.round(p - q, 4), "≈", round(float(np.linalg.norm((p - q) * 111)), 2), "km")
else:
    print("NOT ENOUGH ANCHORS; fallback needed")

# 区域均值校验：把像素点变换到经纬度后按区域多边形切分
units = json.loads(UNITS.read_text(encoding="utf-8"))
polys = {}
for f in units["features"]:
    if f["properties"]["id"] in ("sanjiang", "muling_xingkai"):
        polys[f["properties"]["name"]] = shape(f["geometry"])
print("regions:", {k: (round(v.bounds[0], 2), round(v.bounds[1], 2), round(v.bounds[2], 2), round(v.bounds[3], 2)) for k, v in polys.items()})

if len(pairs) >= 3 and A is not None:
    ys, xs = np.where(cls >= 0)
    sel = np.random.default_rng(0).choice(len(xs), size=min(40000, len(xs)), replace=False)
    px = np.stack([xs[sel], ys[sel]], axis=1).astype(np.float64)
    ll = cv2.transform(px.reshape(-1, 1, 2), A).reshape(-1, 2)
    cids = cls[ys[sel], xs[sel]]
    mid = np.array([c[2] for c in CLASSES])
    for name, poly in polys.items():
        inside = np.array([poly.contains(Point(x, y)) for x, y in ll])
        if inside.sum() > 50:
            print(name, "pixels", int(inside.sum()), "mean depth(m) ≈",
                  round(float(mid[cids[inside]].mean()), 2))
