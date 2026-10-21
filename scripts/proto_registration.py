# -*- coding: utf-8 -*-
"""Diagnose registration: axis-aligned linear fit from city anchors, overlay polygons."""
import json
from pathlib import Path

import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from shapely.geometry import shape
from shapely.ops import transform

MAP = Path("data/recon/p7_img0_900x926.jpeg")
UNITS = Path("src/groundwater_mcp/data/geo/units.geojson")
CITIES = Path("src/groundwater_mcp/data/geo/china_cities.geojson")

img = cv2.imread(str(MAP))
h, w = img.shape[:2]
# OCR anchors
ocr = RapidOCR()
res, _ = ocr(str(MAP))
labels = {}
for box, text, score in res or []:
    t = text.strip(".·• ")
    if t.endswith("市") or t.endswith("县"):
        cx = sum(p[0] for p in box) / 4
        cy = sum(p[1] for p in box) / 4
        labels[t.replace("市", "").replace("县", "")] = (cx, cy, box)

city_geo = json.loads(CITIES.read_text(encoding="utf-8"))
city_pts = {}
for f in city_geo["features"]:
    name = f["properties"]["name"].replace("市", "").replace("地区", "")
    if f["geometry"] and f["geometry"]["type"] in ("Polygon", "MultiPolygon"):
        c = shape(f["geometry"]).centroid
        city_pts[name] = (c.x, c.y)
anchors = []
for name, (cx, cy, box) in labels.items():
    if name in city_pts:
        anchors.append((cx, cy, city_pts[name][0], city_pts[name][1], name))
print("anchors:", anchors)

if len(anchors) >= 2:
    xs = np.array([a[0] for a in anchors])
    ys = np.array([a[1] for a in anchors])
    lons = np.array([a[2] for a in anchors])
    lats = np.array([a[3] for a in anchors])
    # lon = a*x + b ; lat = c*y + d  (north-up, no rotation)
    A_lon = np.polyfit(xs, lons, 1)
    A_lat = np.polyfit(ys, lats, 1)
    print("lon(x) =", A_lon, " lat(y) =", A_lat)
    for a in anchors:
        plon = np.polyval(A_lon, a[0])
        plat = np.polyval(A_lat, a[1])
        print(a[4], "residual km:", round(abs(plon - a[2]) * 111 * np.cos(np.radians(a[3])), 2),
              round(abs(plat - a[3]) * 111, 2))

    def lonlat_to_pix(x, y):
        return ((x - A_lon[1]) / A_lon[0], (y - A_lat[1]) / A_lat[0])

    units = json.loads(UNITS.read_text(encoding="utf-8"))
    vis = img.copy()
    for f in units["features"]:
        if f["properties"]["id"] not in ("sanjiang", "muling_xingkai"):
            continue
        geom = shape(f["geometry"])
        parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
        for part in parts:
            pts = np.array([lonlat_to_pix(x, y) for x, y in part.exterior.coords], dtype=np.int32)
            cv2.polylines(vis, [pts], True, (0, 0, 255), 2)
        print("region", f["properties"]["name"], "bounds", geom.bounds)
    cv2.imwrite("data/recon/overlay_sanjiang.png", vis)
    print("saved data/recon/overlay_sanjiang.png")
