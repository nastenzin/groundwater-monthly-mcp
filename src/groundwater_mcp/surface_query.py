# -*- coding: utf-8 -*-
"""等值面反演连续埋深场的查询层（运行时零第三方依赖：仅标准库）。

数据库里存的是数字化后的粗分辨率等级栅格（示意/取色）与连续场（uint16，0.01 m，
65535 表示图外）。查询时用定标模型把经纬度换算到栅格坐标，再做双线性取样。
连续场在构建时已按“等距线距离加权插值”生成，因此这里不需要 numpy/opencv。
"""
from __future__ import annotations

import json
import math
import sqlite3
import zlib
from array import array
from functools import lru_cache

from . import repository as repo

SENTINEL = 65535


def load_city_points(path) -> dict:
    """读取随包城市点位（WGS84）：{"北京": [lon, lat], ...}。纯标准库实现。"""
    import json as _json
    from pathlib import Path as _Path

    data = _json.loads(_Path(path).read_text(encoding="utf-8"))
    return {k: (float(v[0]), float(v[1])) for k, v in data.items()}


def _decode_u16(blob: bytes) -> array:
    a = array("H")
    a.frombytes(blob)
    return a


def decode_field(row: sqlite3.Row) -> array:
    return _decode_u16(zlib.decompress(row["field"]))


def decode_grid(row: sqlite3.Row) -> array:
    """返回等级（-1..9）；库里存 cls+1（0 图外）。"""
    a = array("B")
    a.frombytes(zlib.decompress(row["grid"]))
    return array("b", [int(v) - 1 for v in a])


@lru_cache(maxsize=24)
def _map_cached(period: str, figure: int):
    conn = repo.connect()
    try:
        row = conn.execute(
            "SELECT * FROM surface_maps WHERE period=? AND figure=?", (period, figure)
        ).fetchone()
    finally:
        conn.close()
    if not row or row["field"] is None:
        return None
    return decode_field(row), int(row["grid_w"]), int(row["grid_h"]), \
        json.loads(row["legend"]), dict(row)


def _sample(field: array, w: int, h: int, x: float, y: float) -> float | None:
    x = max(0.0, min(w - 1.0, x))
    y = max(0.0, min(h - 1.0, y))
    x0, y0 = int(math.floor(x)), int(math.floor(y))
    x1, y1 = min(x0 + 1, w - 1), min(y0 + 1, h - 1)
    fx, fy = x - x0, y - y0
    acc = 0.0
    wsum = 0.0
    for yy, xx, wgt in ((y0, x0, (1 - fx) * (1 - fy)), (y0, x1, fx * (1 - fy)),
                        (y1, x0, (1 - fx) * fy), (y1, x1, fx * fy)):
        v = field[yy * w + xx]
        if v != SENTINEL:
            acc += v / 100.0 * wgt
            wsum += wgt
    if wsum > 0:
        return acc / wsum
    # 最近非空像元兜底（最多 80 像元半径；用于落在图斑外但仍在 bbox 内的点）
    for rad in range(1, 81):
        for dy in range(-rad, rad + 1):
            for dx in range(-rad, rad + 1):
                if max(abs(dx), abs(dy)) != rad:
                    continue
                xx, yy = x0 + dx, y0 + dy
                if 0 <= xx < w and 0 <= yy < h:
                    v = field[yy * w + xx]
                    if v != SENTINEL:
                        return v / 100.0
    return None


def _class_of(legend: list[dict], value: float) -> dict | None:
    for c in legend:
        hi = c["hi"] if c["hi"] < 1e8 else float("inf")
        if c["lo"] <= value < hi:
            return {"range": c["range"], "lo": c["lo"], "hi": c["hi"]}
    return None


def point_query(lat: float, lon: float, period: str | None = None,
                max_results: int = 6) -> dict:
    """查询任意经纬度点的等值面反演埋深（可跨期）。"""
    conn = repo.connect()
    try:
        sql = ("SELECT period, figure, page, caption, regions, bbox, model, "
               "quality, n_anchors, anchor_rmse_km, legend, method, mean_depth_m, "
               "area_km2, expected_area_km2, area_ratio, mean_error_m, source "
               "FROM surface_maps")
        params: list = []
        if period:
            p = repo.normalize_period(period)
            if p:
                sql += " WHERE period=?"
                params.append(p)
        rows = repo._rows(conn.execute(sql, params))
    finally:
        conn.close()
    hits = []
    for row in rows:
        bbox = json.loads(row["bbox"]) if row["bbox"] else None
        if not bbox or not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
            continue
        cached = _map_cached(row["period"], row["figure"])
        if cached is None:
            continue
        field, w, h, legend, _ = cached
        coef = json.loads(row["model"])
        px = coef[0][0] * lon + coef[0][1] * lat + coef[0][2]
        py = coef[1][0] * lon + coef[1][1] * lat + coef[1][2]
        if not (0 <= px <= w - 1 and 0 <= py <= h - 1):
            continue
        value = _sample(field, w, h, px, py)
        if value is None:
            continue
        ix = min(w - 1, max(0, int(px)))
        iy = min(h - 1, max(0, int(py)))
        hits.append({
            "period": row["period"], "figure": row["figure"], "page": row["page"],
            "regions": json.loads(row["regions"]) if row["regions"] else [],
            "caption": row["caption"],
            "depth_m": round(value, 2),
            "class_range": _class_of(legend, value),
            "quality": row["quality"], "n_anchors": row["n_anchors"],
            "anchor_rmse_km": row["anchor_rmse_km"], "method": row["method"],
            "surface_mean_depth_m": row["mean_depth_m"],
            "surface_mean_error_m": row["mean_error_m"],
            "area_ratio": row["area_ratio"],
            "source_kind": row["source"] if "source" in row.keys() else "pdf",
            "source": "等值面图数字化（等值线连续场插值）",
            "off_surface": field[iy * w + ix] == SENTINEL,
        })
    hits.sort(key=lambda r: (r["anchor_rmse_km"] if r["anchor_rmse_km"] is not None else 99))
    return {"lat": lat, "lon": lon, "period": period, "count": len(hits),
            "hits": hits[:max_results],
            "notes": {
                "method": "由等值线距离加权插值得到连续埋深；等级区间来自图例",
                "uncertainty": "误差主要来自图例等级宽度（1~10 m）与图件定标（城市注记控制点残差，"
                               "见 anchor_rmse_km；无控制点时为区域质心兜底）",
            }}


def surface_maps(period: str | None = None) -> dict:
    conn = repo.connect()
    try:
        sql = ("SELECT period, figure, page, caption, regions, grid_w, grid_h, model_type, "
               "quality, n_anchors, anchor_rmse_km, method, mean_depth_m, min_depth_m, "
               "max_depth_m, class_consistency, class_share, area_km2, expected_area_km2, "
               "area_ratio, expected_mean_m, mean_error_m, k_km_per_px, source "
               "FROM surface_maps")
        params = []
        if period:
            p = repo.normalize_period(period)
            if p:
                sql += " WHERE period=?"
                params.append(p)
        sql += " ORDER BY period DESC, figure"
        rows = repo._rows(conn.execute(sql, params))
    finally:
        conn.close()
    for r in rows:
        for k in ("regions", "class_share"):
            if r.get(k):
                try:
                    r[k] = json.loads(r[k])
                except (TypeError, json.JSONDecodeError):
                    pass
    return {"count": len(rows), "maps": rows}


def surface_detail(period: str, figure: int, include_grid: bool = False) -> dict:
    conn = repo.connect()
    try:
        row = conn.execute(
            "SELECT * FROM surface_maps WHERE period=? AND figure=?", (period, figure)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise repo.DataError(f"没有 {period} 第 {figure} 幅等值面图")
    legend = json.loads(row["legend"]) if row["legend"] else []
    out = {"period": period, "figure": figure, "page": row["page"],
           "caption": row["caption"], "regions": json.loads(row["regions"] or "[]"),
           "legend": legend, "grid_size": [int(row["grid_w"]), int(row["grid_h"])],
           "model": json.loads(row["model"]), "bbox": json.loads(row["bbox"] or "null"),
           "quality": row["quality"], "n_anchors": row["n_anchors"],
           "source_kind": row["source"] if "source" in row.keys() else "pdf",
           "anchor_rmse_km": row["anchor_rmse_km"], "method": row["method"],
           "stats": {"mean_depth_m": row["mean_depth_m"], "min_depth_m": row["min_depth_m"],
                     "max_depth_m": row["max_depth_m"],
                     "class_consistency": row["class_consistency"],
                     "area_km2": row["area_km2"],
                     "expected_area_km2": row["expected_area_km2"],
                     "area_ratio": row["area_ratio"],
                     "expected_mean_m": row["expected_mean_m"],
                     "mean_error_m": row["mean_error_m"]},
           "class_share": json.loads(row["class_share"] or "{}"),
           "notes": "连续场由等值线距离加权插值生成；网格坐标为粗分辨率（长边≤160）"}
    if include_grid:
        grid = decode_grid(row)
        out["grid"] = [list(grid[i * int(row["grid_w"]):(i + 1) * int(row["grid_w"])])
                       for i in range(int(row["grid_h"]))]
    return out


def city_depth(city: str, city_points: dict, period: str | None = None) -> dict:
    if city not in city_points:
        raise repo.DataError(f"未知城市：{city}（内置 {len(city_points)} 个城市点位）")
    lon, lat = city_points[city]
    res = point_query(lat, lon, period=period)
    return {"city": city, "lon": lon, "lat": lat, **res}
