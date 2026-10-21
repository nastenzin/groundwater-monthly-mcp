# -*- coding: utf-8 -*-
"""等值面图数字化原型：图例解码 -> 颜色分级 -> 城市锚点定标 -> 面积校验。

用法: python scripts/surface_proto.py <map.jpg> <legend.jpg> <region1,region2> [period]
"""
import json
import math
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from shapely.geometry import shape
from shapely.ops import unary_union

CITY_TABLE = Path("data/recon/city_geo.json")
UNITS = Path("src/groundwater_mcp/data/geo/units.geojson")
RANGES = ["<2", "2~4", "4~8", "8~12", "12~16", "16~20", "20~30", "30~40", "40~50", ">50"]
MIDS = [1.0, 3.0, 6.0, 10.0, 14.0, 18.0, 25.0, 35.0, 45.0, 55.0]

BD09 = 0.0065, 0.006
X_PI = math.pi * 3000.0 / 180.0


def bd09_to_wgs84(lng, lat):
    x, y = lng - BD09[0], lat - BD09[1]
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    t = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    return z * math.cos(t), z * math.sin(t)


def city_lookup():
    raw = json.loads(CITY_TABLE.read_text(encoding="utf-8"))
    return {k: bd09_to_wgs84(*v) for k, v in raw.items()}


def decode_legend(path):
    img = cv2.imread(str(path))
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]
    mask = ((sat > 60) & (val > 100)).astype(np.uint8) * 255
    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    swatches = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if area < 80 or w_ < 10 or h_ < 8:
            continue
        if not (0.8 <= w_ / max(1, h_) <= 6):
            continue
        pix = img[lab == i]
        b, g, r = np.median(pix, axis=0)
        swatches.append({"bbox": [int(stats[i, 0]), int(stats[i, 1]), int(w_), int(h_)],
                         "rgb": [int(r), int(g), int(b)], "area": int(area)})
    # 排序：先按列（x），再按行（y）
    swatches.sort(key=lambda s: (round(s["bbox"][0] / (img.shape[1] / 2)), s["bbox"][1]))
    if len(swatches) < 10:
        raise RuntimeError(f"图例色块不足：{len(swatches)}")
    return swatches[:10]


def classify(map_img, legend_rgb):
    lab = cv2.cvtColor(map_img, cv2.COLOR_BGR2LAB).astype(np.int16)
    ref = []
    for rgb in legend_rgb:
        bgr = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
        ref.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[0, 0].astype(np.int16))
    flat = lab.reshape(-1, 3)
    d = np.stack([np.linalg.norm(flat - r, axis=1) for r in ref], axis=1)
    cls = np.where(d.min(axis=1) < 40, d.argmin(axis=1), -1).reshape(map_img.shape[:2]).astype(np.int8)
    return cls


def unit_polys(names):
    feats = json.loads(UNITS.read_text(encoding="utf-8"))["features"]
    want = set(names)
    polys = [shape(f["geometry"]) for f in feats if f["properties"]["name"] in want]
    return unary_union(polys) if polys else None


def ocr_cities(img_path, cities):
    res, _ = RapidOCR()(str(img_path))
    found = []
    for box, text, score in res or []:
        t = text.strip(".·•⊙ ")
        t = re.sub(r"(市|地区|自治州|盟)$", "", t)
        if t in cities:
            xs = [p[0] for p in box]; ys = [p[1] for p in box]
            found.append({"name": t, "x": (min(xs) + max(xs)) / 2,
                          "y": (min(ys) + max(ys)) / 2, "score": float(score)})
    return found


def calibrate(map_path, map_img, cls, legends, cities, region_names):
    h, w = cls.shape
    mask = (cls >= 0).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ys, xs = np.where(mask > 0)
    cx, cy = xs.mean(), ys.mean()
    # 1) 城市锚点：像素位置
    labels = ocr_cities(map_path, cities)
    # 2) 尺度 k (km/px)：用城市对距离中位数
    pairs = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = labels[i], labels[j]
            pxd = math.hypot(a["x"] - b["x"], a["y"] - b["y"])
            if pxd < 80:
                continue
            lon1, lat1 = cities[a["name"]]
            lon2, lat2 = cities[b["name"]]
            km = math.hypot((lon2 - lon1) * 111 * math.cos(math.radians((lat1 + lat2) / 2)),
                            (lat2 - lat1) * 111)
            pairs.append(km / pxd)
    k = float(np.median(pairs)) if pairs else None
    method = "city-pairs"
    poly = unit_polys(region_names)
    poly_area_km2 = None
    if poly is not None:
        pc = poly.centroid
        poly_area_km2 = float(poly.area * (111.32 ** 2) * math.cos(math.radians(pc.y)))
    # 3) 无锚点时用区域多边形面积反推尺度
    if k is None and poly_area_km2:
        k = math.sqrt(poly_area_km2 / float(mask.sum()))
        method = "polygon-area"
    if not k:
        return None
    mean_lat = poly.centroid.y if poly is not None else 45.0
    if labels:
        ref = labels[0]
        lon0, lat0 = cities[ref["name"]]
        sx = k / (111 * math.cos(math.radians(lat0)))
        sy = k / 111
        resids = []
        for lb in labels:
            plon = lon0 + (lb["x"] - ref["x"]) * sx
            plat = lat0 - (lb["y"] - ref["y"]) * sy
            clon, clat = cities[lb["name"]]
            resids.append(math.hypot((plon - clon) * 111 * math.cos(math.radians(clat)),
                                     (plat - clat) * 111))
        rmse = float(np.sqrt(np.mean(np.square(resids))))
        dlon = float(np.mean([(cities[lb["name"]][0] - (lon0 + (lb["x"] - ref["x"]) * sx)) for lb in labels]))
        dlat = float(np.mean([(cities[lb["name"]][1] - (lat0 - (lb["y"] - ref["y"]) * sy)) for lb in labels]))
        lon0 += dlon
        lat0 += dlat
    else:
        pc = poly.centroid
        mean_lat = pc.y
        lon0 = pc.x - (cx - w / 2) * k / (111 * math.cos(math.radians(mean_lat)))
        lat0 = pc.y + (cy - h / 2) * k / 111
        sx = k / (111 * math.cos(math.radians(mean_lat)))
        sy = k / 111
        rmse = None
        ref = {"x": w / 2, "y": h / 2}
    # 以 (ref.x, ref.y) 为参考像素
    rx, ry = ref["x"], ref["y"]
    area_km2 = float(mask.sum()) * k * k
    bbox = [lon0 - rx * sx, lat0 - (h - ry) * sy, lon0 + (w - rx) * sx, lat0 + ry * sy]
    out = {"k_km_per_px": k, "method": method, "n_anchors": len(labels),
           "anchor_rmse_km": round(rmse, 2) if rmse is not None else None,
           "lon0": lon0, "lat0": lat0, "ref_px": [rx, ry], "sx": sx, "sy": sy,
           "map_area_km2": area_km2,
           "poly_area_km2": poly_area_km2,
           "area_ratio": round(area_km2 / poly_area_km2, 2) if poly_area_km2 else None,
           "bbox": bbox}
    return out


if __name__ == "__main__":
    MAP_PATH = sys.argv[1]
    LEGEND_PATH = sys.argv[2]
    regions = sys.argv[3].split(",")
    swatches = decode_legend(LEGEND_PATH)
    legends = [s["rgb"] for s in swatches]
    print("legend rgb:", legends)
    img = cv2.imread(MAP_PATH)
    cls = classify(img, legends)
    cities = city_lookup()
    calib = calibrate(img, cls, legends, cities, regions)
    print(json.dumps(calib, ensure_ascii=False, indent=1))
    # 分级占比
    vals = cls[cls >= 0]
    print("class share:", {RANGES[i]: round(float((vals == i).mean() * 100), 1)
                           for i in range(10) if (vals == i).any()})
    mid = np.array(MIDS)
    print("mean depth:", round(float(mid[vals].mean()), 2))
