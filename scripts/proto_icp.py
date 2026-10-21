# -*- coding: utf-8 -*-
"""Prototype 2: shape-based (ICP) calibration of a colored isosurface map + validation."""
import json
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, Point, shape
from shapely.ops import unary_union

MAP = Path("data/recon/p7_img0_900x926.jpeg")
UNITS = Path("src/groundwater_mcp/data/geo/units.geojson")

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
flat = lab.reshape(-1, 3)
d = np.stack([np.linalg.norm(flat - L, axis=1) for L in legend_lab], axis=1)
mind = d.min(axis=1)
cls = np.where(mind < 42, d.argmin(axis=1), -1).reshape(h, w).astype(np.int16)
mask = (cls >= 0).astype(np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
if n > 1:
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    mask = (labels == biggest).astype(np.uint8)
cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
contour = max(cnts, key=cv2.contourArea).reshape(-1, 2).astype(np.float64)
print("mask area px", int(mask.sum()), "boundary pts", len(contour))

units = json.loads(UNITS.read_text(encoding="utf-8"))
polys = []
for f in units["features"]:
    if f["properties"]["id"] in ("sanjiang", "muling_xingkai"):
        polys.append(shape(f["geometry"]))
target = unary_union(polys)
# 目标边界点
tb = []
for part in (target.geoms if target.geom_type == "MultiPolygon" else [target]):
    for x, y in part.exterior.coords:
        tb.append((x, y))
tb = np.array(tb)
poly_iou_ref = target

# 初始变换：bbox 对齐（x->lon, y->lat 线性）
minx, miny, maxx, maxy = target.bounds
px0, py0 = contour[:, 0].min(), contour[:, 1].min()
px1, py1 = contour[:, 0].max(), contour[:, 1].max()
A = np.array([[ (maxx - minx) / (px1 - px0), 0, minx - px0 * (maxx - minx) / (px1 - px0)],
              [0, -(maxy - miny) / (py1 - py0), maxy + py0 * (maxy - miny) / (py1 - py0)]])
print("init A:", A)

tree = cKDTree(tb)
src = contour.copy()
for it in range(60):
    dst = cv2.transform(src.reshape(-1, 1, 2), A.reshape(2, 3)).reshape(-1, 2)
    dist, idx = tree.query(dst)
    keep = dist < 0.6
    if keep.sum() < 20:
        break
    S = src[keep]
    D = tb[idx[keep]]
    # 最小二乘仿射 S->D
    M = np.hstack([S, np.ones((len(S), 1))])
    sol, *_ = np.linalg.lstsq(M, D, rcond=None)
    A_new = sol.T  # 2x3
    delta = np.abs(A_new - A).max()
    A = A_new
    if delta < 1e-7:
        break
print("final A:\n", A, "\niter", it, "delta", delta)

# 质量：把 mask 轮廓投影回经纬度，计算 IoU（多边形近似）
dst = cv2.transform(contour.reshape(-1, 1, 2), A.reshape(2, 3)).reshape(-1, 2)
try:
    mask_poly = Polygon(dst).buffer(0)
    iou = mask_poly.intersection(poly_iou_ref).area / mask_poly.union(poly_iou_ref).area
    print("IoU(map shape vs units polygons) =", round(float(iou), 3))
except Exception as exc:  # noqa: BLE001
    print("polygon build failed", exc)

# 区域均值校验
ys, xs = np.where(cls >= 0)
sel = np.random.default_rng(0).choice(len(xs), size=min(60000, len(xs)), replace=False)
px = np.stack([xs[sel], ys[sel]], axis=1).astype(np.float64)
ll = cv2.transform(px.reshape(-1, 1, 2), A.reshape(2, 3)).reshape(-1, 2)
cids = cls[ys[sel], xs[sel]]
mid = np.array([c[2] for c in CLASSES])
polys = {}
for f in units["features"]:
    if f["properties"]["id"] in ("sanjiang", "muling_xingkai"):
        polys[f["properties"]["name"]] = shape(f["geometry"])
for name, poly in polys.items():
    inside = np.array([poly.contains(Point(x, y)) for x, y in ll])
    if inside.sum() > 30:
        print(name, "pixels", int(inside.sum()), "mean depth ≈", round(float(mid[cids[inside]].mean()), 2))

# 可视化
vis = img.copy()
cv2.polylines(vis, [contour.astype(np.int32)], True, (0, 0, 0), 1)
def ll2pix(x, y):
    M = np.hstack([np.array([[x, y, 1.0]]), np.zeros((1, 3))])
    # 逆变换
    Ai = cv2.invertAffineTransform(A.reshape(2, 3))
    return cv2.transform(np.array([[[x, y]]], dtype=np.float64), Ai)[0, 0]
for part in (target.geoms if target.geom_type == "MultiPolygon" else [target]):
    pts = np.array([ll2pix(x, y) for x, y in part.exterior.coords], dtype=np.int32)
    cv2.polylines(vis, [pts], True, (0, 0, 255), 2)
cv2.imwrite("data/recon/overlay_icp.png", vis)
print("saved data/recon/overlay_icp.png")
