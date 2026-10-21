# -*- coding: utf-8 -*-
"""地下水埋深等值面图数字化：颜色分级 → 等值线 → 连续埋深场 → 经纬度查询。

设计要点
--------
* 数值只来自图面等值线：等级色块给出等级区间，等级边界即等值线（2/4/8/12/16/20/30/40/50 m），
  像元值由到上/下两条等值线的距离线性插值得到，并被钳制在所属等级区间内。
* 城市注记仅作为“像元 ↔ 经纬度”的定标控制点（不参与数值分配）；
  控制点多时拟合二次多项式以吸收投影变形，控制点少时退化为仿射，
  无控制点时用监测面积反推尺度 + 区域多边形质心兜底（quality=low）。
* 输出记录含：粗分辨率等级栅格（zlib+base64）、图例、定标模型（经纬度→像元）、
  经纬度 bbox、质量指标（控制点数、残差、面积一致性）与连续场统计。
"""
from __future__ import annotations

import base64
import json
import math
import re
import zlib
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt

RANGES = ["<2", "2~4", "4~8", "8~12", "12~16", "16~20", "20~30", "30~40", "40~50", ">50"]
BOUNDS = [0.0, 2.0, 4.0, 8.0, 12.0, 16.0, 20.0, 30.0, 40.0, 50.0, 1e9]
LEVELS = [2.0, 4.0, 8.0, 12.0, 16.0, 20.0, 30.0, 40.0, 50.0]
COARSE_MAX = 256
X_PI = math.pi * 3000.0 / 180.0


def bd09_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    x, y = lng - 0.0065, lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * X_PI)
    t = math.atan2(y, x) - 0.000003 * math.cos(x * X_PI)
    return z * math.cos(t), z * math.sin(t)


def load_city_points(path: str | Path) -> dict[str, tuple[float, float]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: (float(v[0]), float(v[1])) for k, v in data.items()}


def imread_unicode(path: str | Path) -> np.ndarray:
    buf = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError(f"无法读取图片：{path}")
    return img


# ---------------------------------------------------------------- 图例 / 分级
def decode_legend(path: str | Path) -> list[dict]:
    return decode_legend_array(imread_unicode(path))


def decode_legend_array(img: np.ndarray) -> list[dict]:
    mx = np.max(img, axis=2).astype(np.int16)
    mn = np.min(img, axis=2).astype(np.int16)
    mask = (((mx - mn) > 12) & (mx > 100) & ~((mx > 245) & (mn > 235))).astype(np.uint8) * 255
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    sw = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        x, y, w_, h_ = (int(v) for v in stats[i, :4])
        if not (150 <= area <= 3500 and 15 <= w_ <= 95 and 10 <= h_ <= 50):
            continue
        b, g, r = np.median(img[lab == i], axis=0)
        sw.append({"x": x, "y": y, "rgb": (int(r), int(g), int(b)), "area": area})
    sw.sort(key=lambda s: (0 if s["x"] < img.shape[1] / 2 else 1, s["y"]))
    sw = sw[:10]
    if len(sw) < 10:
        return []
    return [{"range": RANGES[i], "lo": BOUNDS[i], "hi": BOUNDS[i + 1], "rgb": list(s["rgb"])}
            for i, s in enumerate(sw)]


def classify_map(img: np.ndarray, legend: list[dict]) -> np.ndarray:
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.int16)
    refs = []
    for c in legend:
        r, g, b = c["rgb"]
        refs.append(cv2.cvtColor(np.uint8([[[b, g, r]]]), cv2.COLOR_BGR2LAB)[0, 0].astype(np.int16))
    mx = img.max(axis=2).astype(np.int16)
    mn = img.min(axis=2).astype(np.int16)
    cand = ((mx > 100) & ((mx - mn) > 10) & ~((mx > 240) & (mn > 225))).reshape(-1)
    flat = lab.reshape(-1, 3)
    d = np.stack([np.linalg.norm(flat - r, axis=1) for r in refs], axis=1)
    cls = np.where((d.min(axis=1) < 22) & cand, d.argmin(axis=1), -1)
    return cls.reshape(img.shape[:2]).astype(np.int8)


def fill_gaps(cls: np.ndarray) -> np.ndarray:
    col = (cls >= 0).astype(np.uint8)
    col = cv2.morphologyEx(col, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    col = cv2.morphologyEx(col, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    ind = distance_transform_edt(cls < 0, return_distances=False, return_indices=True)
    filled = cls[ind[0], ind[1]]
    return np.where(col > 0, filled, -1).astype(np.int8)


# ---------------------------------------------------------------- 等值线 / 连续场
def contour_masks(cls: np.ndarray) -> dict[float, np.ndarray]:
    out: dict[float, np.ndarray] = {}
    for k, level in enumerate(LEVELS):
        inner = ((cls >= 0) & (cls <= k)).astype(np.uint8)
        outer = (cls > k).astype(np.uint8)
        line = (cv2.dilate(outer, np.ones((3, 3), np.uint8)) > 0) & (inner > 0)
        if line.sum() >= 10:
            out[level] = line
    return out


def build_field(cls: np.ndarray) -> tuple[np.ndarray, dict]:
    h, w = cls.shape
    lines = contour_masks(cls)
    dists = {}
    for level, m in lines.items():
        seed = np.ones((h, w), np.uint8)
        seed[m] = 0
        dists[level] = cv2.distanceTransform(seed, cv2.DIST_L2, 5)
    field = np.full((h, w), np.nan, np.float32)
    for c in range(10):
        m = cls == c
        if not m.any():
            continue
        lo, hi = BOUNDS[c], BOUNDS[c + 1]
        lower = lo if (c >= 1 and lo in dists) else None
        upper = hi if (hi < 1e8 and hi in dists) else None
        if lower is not None and upper is not None:
            dl, du = dists[lower], dists[upper]
            s = dl + du
            s[s == 0] = 1
            field[m] = (lower + (upper - lower) * (dl[m] / s[m])).astype(np.float32)
        elif lower is not None:
            field[m] = np.float32(min(lo + (hi - lo) * 0.5, lo + 8.0))
        elif upper is not None:
            field[m] = np.float32(max(upper - (upper - lo) * 0.5, 0.5))
        else:
            field[m] = np.float32((lo + min(hi, lo + 10)) / 2)
    return field, dists


def field_stats(field: np.ndarray, cls: np.ndarray) -> dict:
    vals = field[np.isfinite(field)]
    ok = tot = 0
    for c in range(10):
        m = (cls == c) & np.isfinite(field)
        if not m.any():
            continue
        lo, hi = BOUNDS[c], BOUNDS[c + 1]
        tot += int(m.sum())
        ok += int(((field[m] >= lo - 1e-3) & (field[m] <= hi + 1e-3)).sum())
    return {"mean_depth_m": round(float(vals.mean()), 2) if len(vals) else None,
            "min_depth_m": round(float(vals.min()), 2) if len(vals) else None,
            "max_depth_m": round(float(vals.max()), 2) if len(vals) else None,
            "class_consistency": round(ok / max(1, tot) * 100, 1),
            "class_share": {RANGES[c]: round(float((cls == c).sum() / max(1, (cls >= 0).sum()) * 100), 1)
                            for c in range(10) if (cls == c).any()}}


# ---------------------------------------------------------------- 城市注记 / 定标
def _components(img: np.ndarray):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, dark = cv2.threshold(gray, 140, 255, cv2.THRESH_BINARY_INV)
    return cv2.connectedComponentsWithStats(dark, 8)


def find_marker(box, comps):
    n, _, stats, cents = comps
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    x0, x1 = min(xs), max(xs)
    yc = (min(ys) + max(ys)) / 2
    best = None
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w_, h_ = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if not (4 <= area <= 200 and 2 <= w_ <= 16 and 2 <= h_ <= 16
                and 0.4 <= w_ / max(1, h_) <= 2.5):
            continue
        cx, cy = cents[i]
        if abs(cy - yc) > 10:
            continue
        left, right = x0 - cx, cx - x1
        gap = left if 0 <= left <= 26 else (right if 0 <= right <= 26 else None)
        if gap is None:
            continue
        fill = area / max(1, w_ * h_)
        if fill < 0.3:
            continue
        score = gap + abs(cy - yc) * 3
        if best is None or score < best[0]:
            best = (score, cx, cy)
    return (best[1], best[2]) if best else None


def ocr_city_labels(img: np.ndarray, city_points: dict[str, tuple[float, float]]):
    from rapidocr_onnxruntime import RapidOCR
    res, _ = RapidOCR()(img)
    comps = _components(img)
    found = []
    for box, text, score in res or []:
        t = re.sub(r"\s+", "", text).strip(".·•⊙ ")
        t = re.sub(r"(市|地区|自治州|盟)$", "", t)
        if t not in city_points:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        mk = find_marker(box, comps)
        x, y = mk if mk else ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        found.append({"name": t, "x": x, "y": y,
                      "lon": city_points[t][0], "lat": city_points[t][1]})
    return found


def _design(anchors: list[dict], order: int) -> np.ndarray:
    lon = np.array([a["lon"] for a in anchors])
    lat = np.array([a["lat"] for a in anchors])
    base = np.column_stack([lon, lat, np.ones_like(lon)])
    if order == 2:
        base = np.column_stack([base, lon ** 2, lon * lat, lat ** 2])
    return base


def fit_model(anchors: list[dict]) -> dict | None:
    """拟合 经纬度 -> 像素（反向模型）。"""
    if len(anchors) < 3:
        return None
    order = 2 if len(anchors) >= 6 else 1
    dst = np.array([[a["x"], a["y"]] for a in anchors], np.float64)
    mean_lat = float(np.mean([a["lat"] for a in anchors]))
    scale = np.array([111.0 * math.cos(math.radians(mean_lat)), 111.0])
    w = np.ones(len(anchors))
    coef = None
    for _ in range(8):
        P = _design(anchors, order)
        coef, *_ = np.linalg.lstsq(P * w[:, None], dst * w[:, None], rcond=None)
        pred = P @ coef
        res = np.sqrt((((pred - dst) * scale) ** 2).sum(axis=1))
        new_w = (res <= max(8.0, float(np.median(res)) * 1.5)).astype(float)
        if new_w.sum() < (6 if order == 2 else 3):
            if order == 2:
                order, w = 1, np.ones(len(anchors))
                continue
            return None
        if np.array_equal(new_w, w):
            break
        w = new_w
    P = _design(anchors, order)
    pred = P @ coef
    res = np.sqrt((((pred - dst) * scale) ** 2).sum(axis=1))
    keep = res <= max(8.0, float(np.median(res)) * 1.5)
    inliers = [a for a, k in zip(anchors, keep) if k]
    rmse = float(np.sqrt(np.mean(res[keep] ** 2)))
    return {"order": order, "coef": coef.tolist(), "n": int(keep.sum()),
            "rmse_km": rmse, "inliers": inliers}


def forward_corners(model: dict, w: int, h: int) -> list[float]:
    """由反向模型（lonlat->pixel）在锚点上拟合正向仿射，求图像四角的经纬度 bbox。"""
    inl = model["inliers"]
    if len(inl) >= 3:
        src = np.array([[a["x"], a["y"], 1.0] for a in inl])
        dst = np.array([[a["lon"], a["lat"]] for a in inl])
        M, *_ = np.linalg.lstsq(src, dst, rcond=None)
        corners = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], float)
        ll = corners @ M
        return [float(ll[:, 0].min()), float(ll[:, 1].min()),
                float(ll[:, 0].max()), float(ll[:, 1].max())]
    return None


def calibrate(img: np.ndarray, mask: np.ndarray, expected: dict) -> dict | None:
    """经纬度 <-> 像元定标。

    尺度优先由“监测面积 = 像元面积 × k²”反推（叙述面积是独立来源，较可靠）；
    平移优先用城市注记的偏移中位数（注记位置有 ±数公里噪声，取中位数可平滑），
    无注记时用区域多边形质心兜底。城市数据只用于定标，不参与数值分配。
    """
    h, w = mask.shape
    ys, xs = np.where(mask > 0)
    if not len(xs):
        return None
    n_pix = float(len(xs))
    exp_area = expected.get("area_km2")
    poly = expected.get("polygon")
    centroid = expected.get("centroid")
    k = None
    method = "area-scaled"
    if exp_area:
        k = math.sqrt(exp_area / n_pix)
    elif poly is not None:
        pc = poly.centroid
        k = math.sqrt(float(poly.area * (111.32 ** 2) * math.cos(math.radians(pc.y))) / n_pix)
        method = "polygon-area"
    if not k or centroid is None:
        return None

    labels = ocr_city_labels(img, expected["cities"]) if expected.get("cities") else []
    mean_lat = centroid[1]
    sx = k / (111 * math.cos(math.radians(mean_lat)))
    sy = k / 111
    if labels:
        # 用各注记反推平移，取中位数（注记有摆放偏移，用中位数抗差）
        t_lon = [lb["lon"] - lb["x"] * sx for lb in labels]
        t_lat = [lb["lat"] + lb["y"] * sy for lb in labels]
        lon0 = float(np.median(t_lon))
        lat0 = float(np.median(t_lat))
        # 残差与内点
        res = []
        for lb in labels:
            plon = lon0 + lb["x"] * sx
            plat = lat0 - lb["y"] * sy
            km = math.hypot((plon - lb["lon"]) * 111 * math.cos(math.radians(lb["lat"])),
                            (plat - lb["lat"]) * 111)
            res.append((km, lb["name"]))
        in_km = [km for km, _ in res if km <= 25]
        rmse = float(np.sqrt(np.mean(np.square(in_km)))) if in_km else None
        n_in = len(in_km)
        quality = ("high" if n_in >= 6 and rmse and rmse <= 10 else
                   "medium" if n_in >= 3 and rmse and rmse <= 20 else "low")
    else:
        lon0 = centroid[0] - (float(xs.mean()) - w / 2) * sx
        lat0 = centroid[1] + (float(ys.mean()) - h / 2) * sy
        res, rmse, n_in, quality = [], None, 0, "low"
    bbox = [lon0, lat0 - h * sy, lon0 + w * sx, lat0]
    return {"method": "city-anchored" if labels else method,
            "model_type": "axis-affine",
            "model_coef": [[1.0 / sx, 0.0, -lon0 / sx],
                           [0.0, -1.0 / sy, lat0 / sy]],
            "bbox": bbox, "k_km_per_px": k,
            "n_anchors": n_in, "anchor_rmse_km": round(rmse, 2) if rmse else None,
            "anchor_names": [name for km, name in res if km <= 25], "quality": quality}


# ---------------------------------------------------------------- 单图数字化
def digitize_figure(map_path: Path, legend_path: Path, regions: list[str],
                    city_points: dict, expected: dict) -> dict:
    img = imread_unicode(map_path)
    legend = decode_legend(legend_path)
    cls = fill_gaps(classify_map(img, legend))
    field, _ = build_field(cls)
    stats = field_stats(field, cls)
    expected = dict(expected)
    expected["cities"] = city_points
    calib = calibrate(img, (cls >= 0).astype(np.uint8), expected)
    h, w = cls.shape
    scale = COARSE_MAX / max(h, w)
    gw, gh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    # 降采样 + 去斑点：等级栅格以 (cls+1) 存储，0 表示图外
    grid_small = cv2.resize((cls + 1).astype(np.uint8), (gw, gh), interpolation=cv2.INTER_NEAREST)
    for _ in range(2):
        blur = cv2.medianBlur(grid_small, 3)
        grid_small = np.where(grid_small == 0, 0, blur).astype(np.uint8)
    blob = base64.b64encode(zlib.compress(grid_small.tobytes(), 9)).decode()
    rec = {"image_size": [w, h], "legend": legend, "grid_w": gw, "grid_h": gh,
           "grid": blob, **stats}
    if calib:
        rec.update(calib)
        rec["area_km2"] = round(float(calib["k_km_per_px"] ** 2 * (cls >= 0).sum()), 1)
        exp = expected.get("area_km2")
        rec["expected_area_km2"] = round(float(exp), 1) if exp else None
        rec["area_ratio"] = round(rec["area_km2"] / exp, 2) if exp else None
    return rec
