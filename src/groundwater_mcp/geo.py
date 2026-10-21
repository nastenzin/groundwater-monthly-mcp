# -*- coding: utf-8 -*-
"""位置输入支持：行政区定位 + 地下水监测地貌单元解析。

纯 Python 标准库实现（射线法点在多边形内判断 + 等距圆柱近似距离），
不依赖 shapely / geopandas。

数据来源（全部为本包内离线文件，模块 import 时只读本地 geojson，绝不联网）:
    data/geo/china_provinces.geojson   省级行政区边界（阿里 DataV）
    data/geo/china_cities.geojson      地级行政区边界（阿里 DataV）
    data/geo/units.geojson             24 个地下水监测地貌单元（手工近似边界）

坐标约定
--------
- GeoJSON 文件内坐标一律 ``[lon, lat]``（经度在前，GeoJSON 标准）。
- 本模块所有公开函数入参一律 ``(lat, lon)``（纬度在前），内部完成转换。

重叠单元解析规则
----------------
相邻地貌单元（平原/盆地）允许互相重叠。当一个点同时落在多个单元内时：
1. 先按 ``properties.priority`` 升序（数值越小优先级越高）；
2. 同优先级时按 bbox 面积升序（面积更小的多边形更“贴切”）。
``units_at()`` 的返回列表已经按该规则排序，因此 ``units_at(lat, lon)[0]``
即该点的“主单元”。priority 由数据文件显式给出，便于人工修正误判。

全部公开函数对非法输入的处理：
- 纬度/经度越界、类型错误 -> 抛 ``ValueError``（信息可读）。
- 行政名 miss / 海域点 -> 返回空结果 ``{}``/``[]``，不抛异常。
- geojson 数据文件缺失或损坏 -> 抛 ``GeoDataError``（RuntimeError 子类）。
"""
from __future__ import annotations

import json
import math
from pathlib import Path

__all__ = [
    "GeoDataError",
    "UNITS",
    "locate_admin",
    "units_at",
    "units_for_admin",
    "nearest_units",
]

# ---------------------------------------------------------------------------
# 常量与数据加载
# ---------------------------------------------------------------------------

_GEO_DIR = Path(__file__).resolve().parent / "data" / "geo"

#: 每度纬度对应的公里数（球面近似）
_KM_PER_DEG_LAT = 110.574
#: 赤道上每度经度对应的公里数（随纬度乘 cos(lat)）
_KM_PER_DEG_LON_EQ = 111.320
#: nearby 判定的最大边界距离（公里）
NEARBY_RADIUS_KM = 120.0
#: units_at 最多返回的单元数
MAX_UNITS_AT = 5


class GeoDataError(RuntimeError):
    """本地 geojson 数据缺失/损坏时抛出。"""


_LOAD_ERROR: str | None = None
_PROVINCES: list[dict] = []
_CITIES: list[dict] = []
_UNITS: list[dict] = []
_UNITS_ORDERED: list[dict] = []

_ADMIN_SUFFIXES = (
    "特别行政区",
    "维吾尔自治区",
    "壮族自治区",
    "回族自治区",
    "自治区",
    "自治州",
    "地区",
    "省",
    "市",
    "盟",
)


def _short_name(name: str) -> str:
    """去掉行政区通名后缀：河北省->河北, 内蒙古自治区->内蒙古。"""
    name = str(name or "").strip()
    for suffix in _ADMIN_SUFFIXES:
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[: -len(suffix)]
    return name


def _geometry_bbox(geometry: dict) -> tuple[float, float, float, float] | None:
    """返回几何的 (min_lon, min_lat, max_lon, max_lat)，无有效坐标时 None。"""
    if not isinstance(geometry, dict):
        return None
    min_lon = min_lat = math.inf
    max_lon = max_lat = -math.inf
    found = False

    def visit(node) -> None:
        nonlocal min_lon, min_lat, max_lon, max_lat, found
        if not isinstance(node, (list, tuple)):
            return
        if (
            len(node) >= 2
            and isinstance(node[0], (int, float))
            and not isinstance(node[0], bool)
            and isinstance(node[1], (int, float))
            and not isinstance(node[1], bool)
        ):
            lon, lat = float(node[0]), float(node[1])
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
            found = True
            return
        for child in node:
            visit(child)

    visit(geometry.get("coordinates"))
    if not found:
        return None
    return (min_lon, min_lat, max_lon, max_lat)


def _load_features(filename: str, kind: str) -> list[dict]:
    path = _GEO_DIR / filename
    if not path.exists():
        raise GeoDataError(
            f"缺少地理数据文件 {path}；请运行 scripts/geo_fetch.py "
            f"(行政区) 或 scripts/geo_build_units.py (地貌单元) 重新生成。"
        )
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise GeoDataError(f"地理数据文件 {path} 读取失败: {exc}") from exc

    features: list[dict] = []
    for feat in raw.get("features") or []:
        props = feat.get("properties") or {}
        geometry = feat.get("geometry") or {}
        bbox = _geometry_bbox(geometry)
        if bbox is None:
            continue
        item = {
            "name": props.get("name"),
            "adcode": props.get("adcode"),
            "province": props.get("province"),
            "level": props.get("level"),
            "geometry": geometry,
            "bbox": bbox,
        }
        if kind == "unit":
            item.update(
                id=props.get("id"),
                group=props.get("group"),
                provinces=list(props.get("provinces") or []),
                accuracy=props.get("accuracy"),
                priority=int(props["priority"]) if "priority" in props else 100,
            )
            # 用经纬度平面面积的余弦修正值做“贴切度” tie-break，仅用于排序
            mid_lat = math.radians((bbox[1] + bbox[3]) / 2.0)
            item["_area"] = (
                (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) * math.cos(mid_lat)
            )
        features.append(item)
    if not features:
        raise GeoDataError(f"地理数据文件 {path} 中没有有效要素。")
    return features


def _bootstrap() -> None:
    global _LOAD_ERROR, _PROVINCES, _CITIES, _UNITS, _UNITS_ORDERED
    try:
        _PROVINCES = _load_features("china_provinces.geojson", "province")
        _CITIES = _load_features("china_cities.geojson", "city")
        _UNITS = _load_features("units.geojson", "unit")
    except GeoDataError as exc:  # 延迟到调用时再抛，避免 import 直接崩
        _LOAD_ERROR = str(exc)
        return
    _UNITS_ORDERED = list(_UNITS)  # 保持数据文件中的分区顺序（供 UNITS 展示）
    # 主单元排序：priority 升序 -> bbox 面积升序
    _UNITS.sort(key=lambda u: (u["priority"], u["_area"]))
    _LOAD_ERROR = None


def _ensure_loaded() -> None:
    if _LOAD_ERROR:
        raise GeoDataError(_LOAD_ERROR)


_bootstrap()

#: 对外暴露的地貌单元清单（按任务清单的分区顺序，便于展示/枚举）
UNITS: list[dict] = [
    {
        "id": u["id"],
        "name": u["name"],
        "group": u["group"],
        "provinces": list(u["provinces"]),
        "bbox": [round(v, 3) for v in u["bbox"]],
        "accuracy": u["accuracy"],
    }
    for u in _UNITS_ORDERED
]

# 便于按行政名匹配的索引
_PROVINCE_BY_FULL = {f["name"]: f for f in _PROVINCES if f.get("name")}
_PROVINCE_BY_SHORT = {_short_name(f["name"]): f for f in _PROVINCES if f.get("name")}
_CITY_BY_FULL = {f["name"]: f for f in _CITIES if f.get("name")}

# ---------------------------------------------------------------------------
# 几何基础：射线法 + 距离
# ---------------------------------------------------------------------------


def _validate_lat_lon(lat, lon) -> tuple[float, float]:
    """校验并规范化 (lat, lon)；非法输入抛可读 ValueError。"""
    for label, value, bound in (("lat", lat, 90.0), ("lon", lon, 180.0)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{label} 必须是数字，收到 {type(value).__name__}: {value!r}")
        if not math.isfinite(float(value)):
            raise ValueError(f"{label} 必须是有限数值，收到 {value!r}")
        if not -bound <= float(value) <= bound:
            raise ValueError(f"{label} 超出取值范围 [-{bound:g}, {bound:g}]：{value!r}")
    return float(lat), float(lon)


def _point_in_ring(lat: float, lon: float, ring: list) -> bool:
    """射线法：点是否在单个环内（环坐标为 [lon, lat]）。"""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = float(ring[i][0]), float(ring[i][1])
        xj, yj = float(ring[j][0]), float(ring[j][1])
        if (yi > lat) != (yj > lat):
            x_cross = (xj - xi) * (lat - yi) / (yj - yi) + xi
            if lon < x_cross:
                inside = not inside
        j = i
    return inside


def _iter_polygons(geometry: dict):
    """Polygon/MultiPolygon -> 逐块产出 rings 列表（ring[0] 为外环）。"""
    gtype = geometry.get("type")
    coords = geometry.get("coordinates") or []
    if gtype == "Polygon":
        yield coords
    elif gtype == "MultiPolygon":
        for poly in coords:
            yield poly


def _point_in_polygon(lat: float, lon: float, rings: list) -> bool:
    """点在环组内：先判外环，再排除洞。"""
    if not rings:
        return False
    if not _point_in_ring(lat, lon, rings[0]):
        return False
    for hole in rings[1:]:
        if _point_in_ring(lat, lon, hole):
            return False
    return True


def _bbox_contains(bbox: tuple, lat: float, lon: float) -> bool:
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def _bbox_intersects(a: tuple, b: tuple) -> bool:
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def _bbox_center(bbox: tuple) -> tuple[float, float]:
    """bbox -> (lat, lon) 中心点。"""
    return ((bbox[1] + bbox[3]) / 2.0, (bbox[0] + bbox[2]) / 2.0)


def _geometry_centroid(geometry: dict) -> tuple[float, float] | None:
    """几何最大块的面积质心 -> (lat, lon)；无有效面积时 None。"""
    best_abs_area = 0.0
    best: tuple[float, float] | None = None
    for rings in _iter_polygons(geometry):
        if not rings:
            continue
        ring = rings[0]
        n = len(ring)
        if n < 3:
            continue
        area2 = 0.0
        cx = 0.0
        cy = 0.0
        for i in range(n):
            x0, y0 = float(ring[i][0]), float(ring[i][1])
            x1, y1 = float(ring[(i + 1) % n][0]), float(ring[(i + 1) % n][1])
            cross = x0 * y1 - x1 * y0
            area2 += cross
            cx += (x0 + x1) * cross
            cy += (y0 + y1) * cross
        if abs(area2) < 1e-12:
            continue
        area = area2 / 2.0
        if abs(area) > best_abs_area:
            best_abs_area = abs(area)
            best = (cy / (6.0 * area), cx / (6.0 * area))  # (lat, lon)
    return best


def _point_in_geometry(lat: float, lon: float, geometry: dict) -> bool:
    for rings in _iter_polygons(geometry):
        if _point_in_polygon(lat, lon, rings):
            return True
    return False


def _seg_distance_km(
    lat: float, lon: float, ax: float, ay: float, bx: float, by: float
) -> float:
    """点到线段距离（公里），等距圆柱近似，局部以该点纬度为基准。"""
    kx = _KM_PER_DEG_LON_EQ * math.cos(math.radians(lat))
    ky = _KM_PER_DEG_LAT
    axk, ayk = (ax - lon) * kx, (ay - lat) * ky
    bxk, byk = (bx - lon) * kx, (by - lat) * ky
    dx, dy = bxk - axk, byk - ayk
    if dx == 0.0 and dy == 0.0:
        return math.hypot(axk, ayk)
    t = -(axk * dx + ayk * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    return math.hypot(axk + t * dx, ayk + t * dy)


def _distance_to_polygon_km(lat: float, lon: float, rings: list) -> float:
    if _point_in_polygon(lat, lon, rings):
        return 0.0
    best = math.inf
    for ring in rings:
        n = len(ring)
        if n < 2:
            continue
        for i in range(n):
            ax, ay = float(ring[i][0]), float(ring[i][1])
            bx, by = float(ring[(i + 1) % n][0]), float(ring[(i + 1) % n][1])
            best = min(best, _seg_distance_km(lat, lon, ax, ay, bx, by))
    return best


def _distance_to_geometry_km(lat: float, lon: float, geometry: dict) -> float:
    best = math.inf
    for rings in _iter_polygons(geometry):
        best = min(best, _distance_to_polygon_km(lat, lon, rings))
    return best


def _segments_intersect(a: tuple, b: tuple, c: tuple, d: tuple) -> bool:
    """线段 ab 与 cd 是否相交（含端点接触）。"""
    eps = 1e-9

    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    def on_segment(p, q, r):  # q 是否落在线段 pr 上（已知共线）
        return (
            min(p[0], r[0]) - eps <= q[0] <= max(p[0], r[0]) + eps
            and min(p[1], r[1]) - eps <= q[1] <= max(p[1], r[1]) + eps
        )

    o1 = orient(a, b, c)
    o2 = orient(a, b, d)
    o3 = orient(c, d, a)
    o4 = orient(c, d, b)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0):
        return True
    if abs(o1) <= eps and on_segment(a, c, b):
        return True
    if abs(o2) <= eps and on_segment(a, d, b):
        return True
    if abs(o3) <= eps and on_segment(c, a, d):
        return True
    if abs(o4) <= eps and on_segment(c, b, d):
        return True
    return False


def _polygons_intersect(rings_a: list, rings_b: list) -> bool:
    """两个多边形（rings 列表）是否相交：顶点包含 + 边界相交。"""
    for rings_x, rings_y in ((rings_a, rings_b), (rings_b, rings_a)):
        outer = rings_x[0]
        for pt in outer:
            if _point_in_polygon(pt[1], pt[0], rings_y):
                return True
    for ring_a in rings_a:
        n_a = len(ring_a)
        for ring_b in rings_b:
            n_b = len(ring_b)
            if n_a < 2 or n_b < 2:
                continue
            for i in range(n_a):
                a = ring_a[i]
                b = ring_a[(i + 1) % n_a]
                for j in range(n_b):
                    c = ring_b[j]
                    d = ring_b[(j + 1) % n_b]
                    if _segments_intersect(a, b, c, d):
                        return True
    return False


def _geometries_intersect(geom_a: dict, geom_b: dict) -> bool:
    """Polygon/MultiPolygon 几何是否相交。"""
    for rings_a in _iter_polygons(geom_a):
        for rings_b in _iter_polygons(geom_b):
            if _polygons_intersect(rings_a, rings_b):
                return True
    return False


def _match_province(name: str) -> dict | None:
    name = str(name or "").strip()
    if not name:
        return None
    return _PROVINCE_BY_FULL.get(name) or _PROVINCE_BY_SHORT.get(_short_name(name))


def _match_city(name: str, province_feature: dict | None = None) -> dict | None:
    """按全名/去后缀短名/短名前缀匹配地级要素；可限定省份。"""
    name = str(name or "").strip()
    if not name:
        return None
    short = _short_name(name)
    candidates: list[dict] = []
    exact = _CITY_BY_FULL.get(name)
    if exact is not None:
        candidates.append(exact)
    for feat in _CITIES:
        if feat.get("name") and _short_name(feat["name"]) == short and feat is not exact:
            candidates.append(feat)
    if not candidates and len(short) >= 2:  # 允许短前缀，如 延边 -> 延边朝鲜族自治州
        for feat in _CITIES:
            if _short_name(feat.get("name") or "").startswith(short) and feat is not exact:
                candidates.append(feat)
    if province_feature is not None:
        pname = province_feature.get("name")
        candidates = [f for f in candidates if f.get("province") == pname]
    if not candidates:
        return None
    # 同名城市优先取与短名完全相等的
    for feat in candidates:
        if feat.get("name") == name or _short_name(feat.get("name") or "") == short:
            return feat
    return candidates[0]


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def _unit_public(unit: dict, relation: str, distance_km: float | None) -> dict:
    return {
        "id": unit["id"],
        "name": unit["name"],
        "group": unit["group"],
        "relation": relation,
        "distance_km": distance_km,
    }


def locate_admin(lat: float, lon: float) -> dict:
    """按经纬度定位行政区（省 / 地级市）。

    参数
    ----
    lat, lon : float
        纬度、经度（十进制度，WGS84/GCJ02 差异对本用途可忽略）。

    返回
    ----
    ``{"province": str | None, "city": str | None}``

    - 点落在中国境内：返回省名与地级市名；直辖市/特别行政区返回
      ``city`` 与 ``province`` 相同（数据里以省代市）。
    - 点落在境外/海上：返回 ``{"province": None, "city": None}``。
    - 非法输入（越界/非数字）：抛 ``ValueError``。
    """
    lat, lon = _validate_lat_lon(lat, lon)
    _ensure_loaded()

    for feat in _CITIES:
        if _bbox_contains(feat["bbox"], lat, lon) and _point_in_geometry(
            lat, lon, feat["geometry"]
        ):
            province = feat.get("province") or feat["name"]
            return {"province": province, "city": feat["name"]}

    for feat in _PROVINCES:
        if _bbox_contains(feat["bbox"], lat, lon) and _point_in_geometry(
            lat, lon, feat["geometry"]
        ):
            return {"province": feat["name"], "city": None}

    return {"province": None, "city": None}


def units_at(lat: float, lon: float) -> list[dict]:
    """返回该点所在或邻近（边界距离 <= 120km）的地貌单元，最多 5 个。

    返回元素为
    ``{"id", "name", "group", "relation": "inside"|"nearby", "distance_km"}``。

    - ``inside``（点在单元内）排在前，按单元优先级排序（见模块 docstring），
      并满足 ``units_at(...)[0]`` 即“主单元”；inside 时 ``distance_km`` 为 0.0。
    - ``nearby`` 按边界距离升序，``distance_km`` 为到最近边界的近似公里数。
    - 海域/无邻近单元时返回 ``[]``；非法输入抛 ``ValueError``。
    """
    lat, lon = _validate_lat_lon(lat, lon)
    _ensure_loaded()

    inside: list[dict] = []
    nearby: list[tuple[float, dict]] = []
    for unit in _UNITS:
        if _bbox_contains(unit["bbox"], lat, lon) and _point_in_geometry(
            lat, lon, unit["geometry"]
        ):
            inside.append(_unit_public(unit, "inside", 0.0))
        else:
            # 单元只有 24 个且顶点很少，直接算边界距离即可（不受 bbox 限制，
            # 这样 bbox 边缘外的“近邻”点也能正确返回 nearby）。
            dist = _distance_to_geometry_km(lat, lon, unit["geometry"])
            if dist <= NEARBY_RADIUS_KM:
                nearby.append((dist, unit))

    nearby.sort(key=lambda item: (item[0], item[1]["priority"], item[1]["_area"]))
    result = list(inside)
    for dist, unit in nearby:
        result.append(_unit_public(unit, "nearby", round(dist, 1)))
    return result[:MAX_UNITS_AT]


def units_for_admin(province: str | None = None, city: str | None = None) -> list[dict]:
    """按行政区返回相关地貌单元。

    参数
    ----
    province : str | None
        省名，支持全名或去后缀短名（``河北``/``河北省``、``内蒙古`` 等）。
    city : str | None
        地级市名，支持全名或短名（``石家庄``/``石家庄市``）。

    返回
    ----
    ``[{"id", "name", "group", "reason"}]``，按单元优先级排序。

    - 只给 ``province``：返回该省覆盖的单元，reason 说明“省份匹配”。
    - 给 ``city``：先按单元 provinces 列表收窄，再判断单元几何与城市边界是否
      真实相交（城市代表点落在单元内或边界相交，reason 说明“城市范围相交”）；
      此时 ``province`` 仅用于同名城市消歧，不做整省展开。
    - 省名/市名 miss、两者都为空、或城市与省份不匹配时返回 ``[]``。
    - 参数类型非法（非字符串）抛 ``ValueError``。
    """
    if province is None and city is None:
        raise ValueError("province 与 city 至少需要提供一个")
    if province is not None and not isinstance(province, str):
        raise ValueError(f"province 必须是字符串或 None，收到 {type(province).__name__}")
    if city is not None and not isinstance(city, str):
        raise ValueError(f"city 必须是字符串或 None，收到 {type(city).__name__}")
    _ensure_loaded()

    province_feat = _match_province(province) if province else None
    if province and province_feat is None:
        return []

    city_feat = None
    if city:
        city_feat = _match_city(city, province_feat)
        if city_feat is None:
            return []
        if province_feat is None:
            province_feat = _match_province(city_feat.get("province") or "")

    province_name = province_feat.get("name") if province_feat else None
    # 城市模式下用城市的“代表点”（bbox 中心 + 最大块面积质心）判断相关性，
    # 避免只用 bbox 相交导致相距很远的单元被误判为相关；此时 province
    # 仅用于消歧（同名城市跨省），不再做整省展开。
    city_probes: list[tuple[float, float]] = []
    if city_feat is not None:
        city_probes.append(_bbox_center(city_feat["bbox"]))
        centroid = _geometry_centroid(city_feat["geometry"])
        if centroid is not None:
            city_probes.append(centroid)

    results: list[dict] = []
    for unit in _UNITS:
        reasons: list[str] = []
        if city_feat is None:
            if province_name and province_name in unit["provinces"]:
                reasons.append(f"单元所属省份包含{province_name}")
        else:
            city_province = city_feat.get("province") or ""
            # 先按省份收窄（单元 provinces 列表是权威范围），再做真实几何相交判断
            if city_province and city_province in unit["provinces"]:
                hit = any(
                    _point_in_geometry(plat, plon, unit["geometry"])
                    for plat, plon in city_probes
                ) or (
                    _bbox_intersects(unit["bbox"], city_feat["bbox"])
                    and _geometries_intersect(unit["geometry"], city_feat["geometry"])
                )
                if hit:
                    reasons.append(f"单元范围与{city_feat['name']}相交")
        if reasons:
            results.append(
                {
                    "id": unit["id"],
                    "name": unit["name"],
                    "group": unit["group"],
                    "reason": "；".join(reasons),
                }
            )
    return results


def nearest_units(lat: float, lon: float, k: int = 3) -> list[dict]:
    """返回距离该点最近的 k 个地貌单元（含 distance_km）。

    返回元素为 ``{"id", "name", "group", "distance_km", "relation"}``；
    点在单元内时 distance_km 为 0.0、relation 为 ``"inside"``，否则为
    ``"outside"``。k 必须是正整数；非法输入抛 ``ValueError``。
    """
    lat, lon = _validate_lat_lon(lat, lon)
    if isinstance(k, bool) or not isinstance(k, int):
        raise ValueError(f"k 必须是正整数，收到 {type(k).__name__}: {k!r}")
    if k <= 0:
        raise ValueError(f"k 必须是正整数，收到 {k!r}")
    _ensure_loaded()

    scored: list[tuple[float, dict]] = []
    for unit in _UNITS:
        if _point_in_geometry(lat, lon, unit["geometry"]):
            scored.append((0.0, unit))
        else:
            scored.append((_distance_to_geometry_km(lat, lon, unit["geometry"]), unit))
    scored.sort(key=lambda item: (item[0], item[1]["priority"], item[1]["_area"]))
    return [
        {
            "id": unit["id"],
            "name": unit["name"],
            "group": unit["group"],
            "distance_km": round(dist, 1),
            "relation": "inside" if dist == 0.0 else "outside",
        }
        for dist, unit in scored[:k]
    ]
