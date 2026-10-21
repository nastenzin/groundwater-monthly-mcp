# -*- coding: utf-8 -*-
"""《地下水动态月报》MCP 服务器。

数据来源：水利部公开发布的《地下水动态月报》PDF（2019—2025 年多期，随本仓库分发）。
位置输入支持三种方式：经纬度、选择行政区、地图选点。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from mcp.server.mcpserver import MCPServer

from . import repository as repo
from . import surface_query as sq
from .paths import PACKAGE_DIR

INSTRUCTIONS = (
    "本服务器提供《地下水动态月报》的结构化数据查询：报告目录、综述、降水量、浅层地下水埋深及变化、"
    "深层地下水水位变幅、裂隙水/岩溶水重点站、水温、泉流量，以及全文检索与 17 张原始统计表。"
    "另有《中国水文年报》地下水数据（各平原/盆地每年 12 月埋深与同比水位变幅），用于补齐月报序列之前的年际基准，"
    "可用 get_annual_groundwater / list_annual_reports 查询。"
    "还把历年《中国水资源公报》地下水数据入库（1997、1998、2001-2024）：全国地下水资源量/供水量/占比、"
    "北方平原区浅层地下水储存量变化、10 个水资源一级区与省级行政区的地下水资源量与供水量，"
    "可用 list_bulletin_reports / get_bulletin_groundwater / get_bulletin_series 查询。"
    "月报数据来源为水利部公开发布的月报（2024-10 及以后为原生 PDF，2024-01~09 为官方 HTML5 文本层，2023-12 为旧版残留 PDF）。"
    "此外，月报中的彩色“地下水埋深等值面图”已被数字化为连续埋深场：从图例颜色提取等级区间与等值线，"
    "在相邻等值线之间按距离插值，可查询任意经纬度点的连续埋深（get_depth_at_point / get_city_depth），"
    "或查看图件反演结果（list_surface_maps / get_depth_surface）；城市点位仅用于图件定标与取坐标，"
    "数值只来自等值线，不按城市归类分配。"
    "位置查询支持三种输入方式：1) 经纬度 locate_by_coordinates(lat, lon)；"
    "2) 行政区 locate_by_administrative_region(province, city)；"
    "3) 地图选点 locate_by_map_point(lat, lon)（先用 get_map_picker 在浏览器地图上点击取得坐标，"
    "再把坐标传回来）。也可以用统一的 query_by_location 按 mode 自动分派。"
    "地貌单元边界是近似范围，定位结果含 relation/confidence 字段，请结合原文使用；"
    "所有数值均来自月报原文，引用时请注明期号与来源链接。"
)

mcp = MCPServer(
    name="groundwater-monthly",
    title="地下水动态月报数据",
    instructions=INSTRUCTIONS,
    version="0.4.1",
)

# 黄淮海/山西等区域的降水量表按省或盆地统计，需要从地貌单元映射到表内名称
PRECIP_ALIASES: dict[str, list[str]] = {
    "海河平原": ["北京", "天津", "河北"],
    "黄淮平原": ["河南", "山东", "江苏", "安徽"],
    "山西主要盆地": ["大同盆地", "忻定盆地", "长治盆地", "运城盆地", "临汾盆地", "太原盆地"],
    # 2023 年及更早的报告使用过不同写法
    "河西走廊平原": ["河西走廊平原", "河西走廊"],
    "银川卫宁平原": ["银川卫宁平原", "银川平原", "卫宁平原"],
    "浙东沿海平原": ["浙东沿海平原", "浙东沿海一般平原"],
    "广东珠江三角洲平原": ["广东珠江三角洲平原", "广东珠江三角洲一般平原"],
    "雷州半岛平原": ["雷州半岛平原", "雷州半岛"],
    "琼北台地平原": ["琼北台地平原", "琼北台地"],
}

PROVINCE_SUFFIXES = [
    "维吾尔自治区", "壮族自治区", "回族自治区", "特别行政区", "自治区",
    "省", "市",
]


def _short_province(name: str | None) -> str:
    if not name:
        return ""
    out = name.strip()
    for suffix in PROVINCE_SUFFIXES:
        if out.endswith(suffix):
            out = out[: -len(suffix)]
            break
    return out


def _geo():
    try:
        from . import geo  # 延迟导入，便于未安装地理数据时仍可使用其他工具
    except Exception as exc:  # noqa: BLE001
        raise repo.DataError(
            f"地理定位模块不可用（{exc}）。请确认已随仓库分发 src/groundwater_mcp/geo.py 与 data/geo/*.geojson。"
        ) from exc
    return geo


@lru_cache(maxsize=1)
def _city_points():
    """随包城市点位（WGS84），仅用于把城市名换算成坐标，不参与数值分配。"""
    return sq.load_city_points(PACKAGE_DIR / "data" / "geo" / "city_points.json")


def _source_of(conn, period: str) -> dict:
    row = conn.execute(
        "SELECT detail_url, pdf_url, title, publish_date FROM reports WHERE period=?", (period,)
    ).fetchone()
    return dict(row) if row else {}


def _unit_snapshot(
    conn, period: str, unit: dict, include_series: bool = True
) -> dict:
    name = unit["name"]
    snap = repo.region_snapshot(conn, period, name)
    precip: list[dict] = []
    names = PRECIP_ALIASES.get(name, [name])
    for alias in names:
        row = repo.precip_for(conn, period, alias)
        if row and row not in precip:
            precip.append(row)
    distribution = repo.distribution_for(conn, period, name) if snap else []
    entry = {
        "unit": name,
        "group": unit.get("group"),
        "relation": unit.get("relation") or "administrative",
        "distance_km": unit.get("distance_km"),
        "shallow_depth": snap,
        "precipitation": precip,
        "distribution": distribution,
    }
    if include_series and snap:
        entry["series"] = repo.region_series(conn, name, end_period=period)
        annual = repo.annual_series_for_region(conn, name)
        if annual:
            entry["annual_series"] = annual
        bulletin = repo.bulletin_series_for_plain(conn, name)
        if bulletin:
            entry["bulletin_series"] = bulletin
    return entry


def _location_payload(
    conn,
    period: str | None,
    mode: str,
    input_info: dict,
    admin: dict,
    units: list[dict],
    include_series: bool = True,
) -> dict:
    p = repo.resolve_period(conn, period)
    payload: dict[str, Any] = {
        "mode": mode,
        "input": input_info,
        "period": p,
        "resolved_admin": admin,
        "matched_units": [
            {k: u.get(k) for k in ("id", "name", "group", "relation", "distance_km", "reason")}
            for u in units
        ],
        "data": {"units": [_unit_snapshot(conn, p, u, include_series) for u in units]},
        "source": _source_of(conn, p),
        "disclaimer": (
            "地貌单元边界为基于公开地理信息的近似范围（approximate），仅用于把位置映射到月报中的监测区；"
            "定位结果中的 relation（inside/nearby）与 distance_km 可用于判断可靠程度。数值以月报原文为准。"
        ),
    }
    province = _short_province(admin.get("province"))
    if mode == "administrative":
        payload["resolution_confidence"] = "high" if units else "none"
    else:
        relations = [u.get("relation") for u in units]
        if "inside" in relations:
            payload["resolution_confidence"] = "high"
        elif units:
            dists = [u.get("distance_km") for u in units if u.get("distance_km") is not None]
            payload["resolution_confidence"] = "medium" if dists and min(dists) <= 50 else "low"
            if payload["resolution_confidence"] == "low":
                payload["note"] = (
                    "该坐标未落入任何监测区，仅返回最近的地貌单元（距离较远），定位可靠性低；"
                    "建议改用行政区查询或结合 distance_km 判断。"
                )
        else:
            payload["resolution_confidence"] = "none"
    if province and province not in {"", "None"}:
        deep = repo.deep_for_province(conn, p, province)
        if deep and deep.get("province") != "总计":
            payload["data"]["province_deep"] = deep
        # 该省/市在降水量表中的记录（表2/表3 按省或盆地统计）
        prec = _rows_precip_by_admin(conn, p, province, admin.get("city"))
        if prec:
            payload["data"]["province_precipitation"] = prec
        hist = repo.bulletin_series_for_province(conn, province)
        if hist:
            payload["data"]["province_groundwater_history"] = {
                "source": "《中国水资源公报》历年附表（2011、2016-2024）",
                "unit": "亿m³ / %",
                "series": hist,
            }
    if not units:
        payload["note"] = (
            "该位置未落入月报覆盖的平原/盆地监测区。可改用附近的行政区查询，或查看 province_deep / "
            "province_precipitation 中的省级汇总数据。"
        )
    lat_in, lon_in = input_info.get("lat"), input_info.get("lon")
    if lat_in is not None and lon_in is not None:
        try:
            payload["data"]["surface_depth"] = sq.point_query(
                float(lat_in), float(lon_in), period=p
            )
        except Exception:  # noqa: BLE001 - 等值面数据缺失时不影响主查询
            payload["data"]["surface_depth"] = {"count": 0, "hits": []}
    return payload


def _rows_precip_by_admin(conn, period: str, province: str, city: str | None = None) -> list[dict]:
    rows = [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM precipitation WHERE period=? AND (province LIKE ? OR unit LIKE ?)",
            (period, f"%{province}%", f"%{province}%"),
        )
    ]
    return rows


# ---------------------------------------------------------------------------
# 基础数据工具
# ---------------------------------------------------------------------------
@mcp.tool()
def describe_dataset() -> dict:
    """返回随包分发的数据集概况：期数、期号列表、各表行数、数据库位置。"""
    conn = repo.connect()
    try:
        stats = repo.db_stats(conn)
    finally:
        conn.close()
    stats["coverage"] = {
        "note": "月报条目来自水利部公开月报（原生 PDF 或官方 HTML5 文本层）；年报条目来自《中国水文年报》地下水章节；"
                "公报条目来自《中国水资源公报》历年地下水章节与附表",
        "latest": stats["periods"][0] if stats["periods"] else None,
        "earliest": stats["periods"][-1] if stats["periods"] else None,
        "annual_reports": stats.get("annual_reports", 0),
        "annual_rows": stats.get("annual_groundwater_rows", 0),
        "bulletin_reports": stats.get("bulletin_reports", 0),
        "bulletin_years": stats.get("bulletin_years", []),
        "bulletin_rows": (
            stats.get("bulletin_national_rows", 0)
            + stats.get("bulletin_region_rows", 0)
            + stats.get("bulletin_province_rows", 0)
            + stats.get("bulletin_plain_rows", 0)
        ),
        "surface_maps": stats.get("surface_maps", 0),
        "surface_periods": stats.get("surface_periods", []),
        "surface_note": "surface_maps 为彩色埋深等值面图数字化的结果：颜色分级→等值线→连续场，"
                        "可用 get_depth_at_point / get_depth_surface / get_city_depth 查询",
    }
    return stats


@mcp.tool()
def list_reports(year: int | None = None, limit: int = 50) -> dict:
    """列出可用报告期号（按时间倒序）。

    Args:
        year: 可选，只列某一年，如 2025。
        limit: 最多返回条数，默认 50。
    """
    conn = repo.connect()
    try:
        rows = repo.list_reports(conn, year=year, limit=limit)
    finally:
        conn.close()
    return {"count": len(rows), "reports": rows}


@mcp.tool()
def get_report(period: str | None = None) -> dict:
    """获取某一期月报的元数据、综述统计（站网数、深层水位变幅占比）与章节结构。

    Args:
        period: 期号 YYYY-MM（如 2025-11）；省略时取最新一期。
    """
    conn = repo.connect()
    try:
        report = repo.get_report(conn, period)
    finally:
        conn.close()
    return report


@mcp.tool()
def get_precipitation(period: str | None = None, group: str | None = None, unit: str | None = None) -> dict:
    """查询降水量表（表1–表5）：各平原区/省/盆地的月平均降水量与距平百分比。

    Args:
        period: 期号 YYYY-MM，省略取最新。
        group: 按大区过滤，如“东北平原”“黄淮海平原”“山西及西北诸省区”“长江中下游平原”“其他监控区”。
        unit: 按地貌单元或省名过滤，如“松嫩平原”“北京”。
    """
    conn = repo.connect()
    try:
        result = repo.get_precipitation(conn, period, group=group, unit=unit)
    finally:
        conn.close()
    result["notes"] = "降水量距平为相对常年同期（1981—2010 年）的百分比"
    return result


@mcp.tool()
def get_shallow_groundwater(
    period: str | None = None, region: str | None = None, group: str | None = None
) -> dict:
    """查询浅层地下水埋深及变化：各平原/盆地平均埋深、与上月和去年同期变化、面积占比，以及变幅分级分布。

    Args:
        period: 期号 YYYY-MM，省略取最新。
        region: 地貌单元名（支持模糊匹配），如“三江平原”“海河平原”“山西主要盆地”。
        group: 大区名，如“东北平原”。
    """
    conn = repo.connect()
    try:
        result = repo.get_shallow_groundwater(conn, period, region=region, group=group)
    finally:
        conn.close()
    return result


@mcp.tool()
def get_deep_groundwater(period: str | None = None, province: str | None = None) -> dict:
    """查询深层地下水水位较去年同期的变幅站点占比（表14），可按省过滤。

    Args:
        period: 期号 YYYY-MM，省略取最新。
        province: 省级行政区简称或全称，如“河北”“山西省”。
    """
    conn = repo.connect()
    try:
        result = repo.get_deep_groundwater(conn, period, province=_short_province(province))
    finally:
        conn.close()
    return result


@mcp.tool()
def get_key_stations(period: str | None = None, kind: str = "all") -> dict:
    """查询重点监测站数据：裂隙水/岩溶水水位（表15）、水温（表16）、泉流量（表17）。

    Args:
        period: 期号 YYYY-MM，省略取最新。
        kind: all / water / temperature / spring；也可用“裂隙水”“岩溶水”“水温”“泉流量”。
    """
    conn = repo.connect()
    try:
        result = repo.get_key_stations(conn, period, kind=kind)
    finally:
        conn.close()
    return result


@mcp.tool()
def get_time_series(
    metric: str = "depth",
    region: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """获取某一指标的时间序列（跨多个期号）。

    Args:
        metric: depth（平均埋深 m）/ change_prev（埋深较上月变化 m）/ change_year（埋深较去年同期变化 m）/
                precip（月降水量 mm）/ anomaly（降水距平 %）。
        region: 地貌单元名（埋深类）或省/盆地名（降水类），支持模糊匹配；省略时返回全部。
        start: 起始期号 YYYY-MM，可选。
        end: 结束期号 YYYY-MM，可选。
    """
    conn = repo.connect()
    try:
        result = repo.get_time_series(conn, metric, region=region, start=start, end=end)
    finally:
        conn.close()
    return result


@mcp.tool()
def search_report_text(query: str, period: str | None = None, limit: int = 20) -> dict:
    """在月报原文中全文检索，返回命中页与上下文片段。

    Args:
        query: 检索词，如“松嫩平原”“蓄变量”“泉水断流”。
        period: 限定期号 YYYY-MM，省略则检索全部期。
        limit: 最多返回条数，默认 20。
    """
    conn = repo.connect()
    try:
        result = repo.search_text(conn, query, period=period, limit=limit)
    finally:
        conn.close()
    return result


@mcp.tool()
def get_report_text(
    period: str | None = None,
    section: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    max_chars: int = 8000,
) -> dict:
    """读取月报原文（按章节或页码），用于核对数值或引用原文。

    Args:
        period: 期号 YYYY-MM，省略取最新。
        section: 章节标题关键字，如“综述”“降水量”“浅层地下水”“重点站”。
        page_start/page_end: 页码范围（1 起）。
        max_chars: 返回文本上限，默认 8000 字符。
    """
    conn = repo.connect()
    try:
        result = repo.get_report_text(
            conn, period, section=section, page_start=page_start, page_end=page_end, max_chars=max_chars
        )
    finally:
        conn.close()
    return result


@mcp.tool()
def list_tables(period: str | None = None) -> dict:
    """列出某一期月报中解析出的 17 张表（表号、标题、所在页码、行数）。"""
    conn = repo.connect()
    try:
        p = repo.resolve_period(conn, period)
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT table_no, caption, page, rows_json FROM report_tables WHERE period=? ORDER BY table_no",
                (p,),
            )
        ]
    finally:
        conn.close()
    return {
        "period": p,
        "tables": [
            {
                "table_no": r["table_no"],
                "caption": r["caption"],
                "page": r["page"],
                "row_count": len(json.loads(r["rows_json"])),
            }
            for r in rows
        ],
    }


@mcp.tool()
def get_table(period: str | None = None, table_no: int = 1) -> dict:
    """获取某一期某张统计表的原始行（rows 为二维数组，表头在第一行）。

    Args:
        period: 期号 YYYY-MM，省略取最新。
        table_no: 表号 1–17（可用 list_tables 查看含义）。
    """
    conn = repo.connect()
    try:
        result = repo.get_table(conn, period, table_no)
    finally:
        conn.close()
    return result


# ---------------------------------------------------------------------------
# 位置输入：经纬度 / 行政区 / 地图选点
# ---------------------------------------------------------------------------
def _resolve_coords(lat: float, lon: float) -> tuple[dict, list[dict], str]:
    geo = _geo()
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError) as exc:
        raise repo.DataError("经纬度必须是数字") from exc
    if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
        raise repo.DataError("经纬度超出合法范围：lat∈[-90,90]，lon∈[-180,180]")
    admin = geo.locate_admin(lat_f, lon_f)
    units = geo.units_at(lat_f, lon_f)
    inside = [u for u in units if u.get("relation") == "inside"]
    if inside:
        # 有明确命中时不再返回远处的“nearby”单元，避免噪声
        units = inside
        method_note = "坐标命中监测区多边形；relation=inside 表示点在近似边界内"
    else:
        nearest = geo.nearest_units(lat_f, lon_f, k=3)
        units = [
            {**u, "relation": "nearby", "distance_km": u.get("distance_km")} for u in nearest
        ]
        method_note = "坐标未落入已知监测区多边形，返回最近的地貌单元（距离见 distance_km）"
    return admin, units, method_note


@mcp.tool()
def locate_by_coordinates(
    lat: float, lon: float, period: str | None = None, include_series: bool = True
) -> dict:
    """按经纬度查询该位置所属监测区的地下水数据（三种位置输入方式之一）。

    Args:
        lat: 纬度，如 39.90。
        lon: 经度，如 116.40。
        period: 期号 YYYY-MM，省略取最新。
        include_series: 是否附带近 12 期时间序列。
    """
    conn = repo.connect()
    try:
        admin, units, note = _resolve_coords(lat, lon)
        payload = _location_payload(
            conn, period, "coordinates", {"lat": float(lat), "lon": float(lon)},
            admin, units, include_series=include_series,
        )
    finally:
        conn.close()
    payload["resolution_note"] = note
    return payload


@mcp.tool()
def locate_by_administrative_region(
    province: str,
    city: str | None = None,
    period: str | None = None,
    include_series: bool = True,
) -> dict:
    """按行政区查询相关监测区的地下水数据（三种位置输入方式之一）。

    Args:
        province: 省级行政区全称或简称，如“河北省”“河北”。
        city: 可选，地级行政区名，如“衡水市”“石家庄市”；给出后会优先匹配该市所在的监测区。
        period: 期号 YYYY-MM，省略取最新。
        include_series: 是否附带近 12 期时间序列。
    """
    geo = _geo()
    conn = repo.connect()
    try:
        units = geo.units_for_admin(province=province, city=city)
        admin = {"province": province, "city": city}
        payload = _location_payload(
            conn, period, "administrative", {"province": province, "city": city},
            admin, units, include_series=include_series,
        )
    finally:
        conn.close()
    if not units:
        payload["resolution_note"] = (
            f"行政区 {province}{city or ''} 不在月报的平原/盆地监测区内，未匹配到地貌单元"
        )
    else:
        payload["resolution_note"] = "按行政区与监测区的地理关系匹配（含近似匹配）"
    return payload


@mcp.tool()
def locate_by_map_point(
    lat: float, lon: float, period: str | None = None, include_series: bool = True
) -> dict:
    """按地图选点查询地下水数据：先用 get_map_picker 打开地图点选，再把坐标传回本工具。

    Args:
        lat: 地图上点选位置的纬度。
        lon: 地图上点选位置的经度。
        period: 期号 YYYY-MM，省略取最新。
        include_series: 是否附带近 12 期时间序列。
    """
    conn = repo.connect()
    try:
        admin, units, note = _resolve_coords(lat, lon)
        payload = _location_payload(
            conn, period, "map_point", {"lat": float(lat), "lon": float(lon), "picked_on": "map"},
            admin, units, include_series=include_series,
        )
    finally:
        conn.close()
    payload["resolution_note"] = note
    payload["map_picker"] = {
        "how_to": "打开 get_map_picker 返回的 picker_path（浏览器），在地图上点击即可得到经纬度，再把坐标传给本工具",
        "resource_uri": "groundwater://map/picker",
    }
    return payload


@mcp.tool()
def query_by_location(
    period: str | None = None,
    mode: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    province: str | None = None,
    city: str | None = None,
    include_series: bool = True,
) -> dict:
    """统一的位置查询入口：按 mode 自动分派到经纬度/行政区/地图选点三种方式。

    Args:
        period: 期号 YYYY-MM，省略取最新。
        mode: coordinates（经纬度）/ administrative（行政区）/ map_point（地图选点）；
              省略时按参数自动判断：有 province 走行政区，否则有经纬度走 coordinates。
        lat/lon: mode=coordinates 或 map_point 时必填。
        province/city: mode=administrative 时必填 province。
        include_series: 是否附带近 12 期时间序列。
    """
    chosen = (mode or "").strip().lower()
    if chosen in {"", "auto"}:
        chosen = "administrative" if province else "coordinates"
    if chosen in {"coordinates", "coordinate", "latlon", "经纬度", "coords"}:
        if lat is None or lon is None:
            raise repo.DataError("经纬度模式需要同时提供 lat 和 lon")
        return locate_by_coordinates(lat, lon, period=period, include_series=include_series)
    if chosen in {"administrative", "admin", "region", "行政区"}:
        if not province:
            raise repo.DataError("行政区模式需要提供 province（可选 city）")
        return locate_by_administrative_region(
            province, city=city, period=period, include_series=include_series
        )
    if chosen in {"map_point", "map", "map-pick", "地图选点", "地图"}:
        if lat is None or lon is None:
            raise repo.DataError("地图选点模式需要同时提供 lat 和 lon")
        return locate_by_map_point(lat, lon, period=period, include_series=include_series)
    raise repo.DataError("mode 必须是 coordinates / administrative / map_point 之一")


@mcp.tool()
def list_annual_reports() -> dict:
    """列出已入库的《中国水文年报》年份与地下水章节数据范围（用于补齐月报之前的历史基准）。"""
    conn = repo.connect()
    try:
        reports = repo.list_annual_reports(conn)
    finally:
        conn.close()
    return {
        "count": len(reports),
        "reports": reports,
        "note": "年报提供每年 12 月的各平原/盆地平均埋深与同比水位变幅，作为月报序列（2023-12 起）之前的年际基准",
    }


@mcp.tool()
def get_annual_groundwater(
    year: int | None = None,
    data_year: int | None = None,
    region: str | None = None,
    row_type: str = "all",
) -> dict:
    """查询《中国水文年报》地下水数据：各平原/盆地与重点区域每年 12 月的埋深及同比水位变幅。

    Args:
        year: 年报年份（如 2022），省略则返回全部已入库年报。
        data_year: 数据年份（如 2020/2021/2022），省略则返回全部年份。
        region: 地貌单元或重点区域名（模糊匹配），如“三江平原”“华北地区”。
        row_type: all / plain_basin（全国主要平原及盆地）/ key_region（重点区域）。
    """
    conn = repo.connect()
    try:
        result = repo.get_annual_groundwater(
            conn, year=year, data_year=data_year, region=region, row_type=row_type
        )
    finally:
        conn.close()
    return result


@mcp.tool()
def list_bulletin_reports() -> dict:
    """列出已入库的《中国水资源公报》年份、来源形式与数据覆盖（用于查询 1997 年以来的历史地下水数据）。"""
    conn = repo.connect()
    try:
        rows = repo.list_bulletin_reports(conn)
    finally:
        conn.close()
    return {
        "count": len(rows),
        "reports": rows,
        "note": "公报数据为年度口径（地下水资源量、地下水供水量、占比、北方平原储存量变化），"
                "与月报的逐月埋深、水文年报的年末埋深互补；1997 年为九大流域片口径，2006 年起为 10 个水资源一级区口径",
    }


@mcp.tool()
def get_bulletin_groundwater(
    year: int | None = None,
    level: str = "national",
    name: str | None = None,
) -> dict:
    """查询《中国水资源公报》历年地下水数据（1997、1998、2001-2024）。

    Args:
        year: 公报年份（数据年份），如 2010；省略时返回全部年份。
        level: national（全国，默认）/ region（水资源一级区）/ province（省级行政区）/ plain（主要平原及盆地年末埋深）。
        name: 在 region/province/plain 级别下按名称模糊过滤，如“海河区”“河北”“三江平原”。
    """
    conn = repo.connect()
    try:
        lv = repo._bulletin_level(level)
        if lv == "national":
            result = repo.get_bulletin_national(conn, year=year)
        elif lv == "region":
            result = repo.get_bulletin_regions(conn, year=year, region=name)
        elif lv == "province":
            result = repo.get_bulletin_provinces(conn, year=year, province=name)
        else:
            result = repo.get_bulletin_plains(conn, year=year, plain=name)
    finally:
        conn.close()
    result["level"] = lv
    result["unit"] = "亿m³；plain 级别的埋深单位为 m"
    return result


@mcp.tool()
def get_bulletin_series(
    metric: str = "ground_supply",
    level: str = "national",
    name: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    """获取《中国水资源公报》某一指标的历史时间序列（1997-2024）。

    Args:
        metric: national/region/province 级别：ground_resource（地下水资源量）、ground_supply（地下水供水量）、
            ground_share（地下水占总供水比例%）、total_supply（总供水量）；
            national 另有 plain_resource（平原区地下水资源量）、plain_storage_change（北方平原浅层储存量变化）；
            plain 级别：shallow_end / shallow_change / deep_end / deep_change（埋深及变幅）。
        level: national（默认）/ region / province / plain。
        name: region/province/plain 级别的对象名，如“河北”“海河区”“三江平原”。
        start_year: 起始年份（含）。
        end_year: 结束年份（含）。
    """
    conn = repo.connect()
    try:
        result = repo.get_bulletin_series(
            conn, metric=metric, level=level, name=name,
            start_year=start_year, end_year=end_year,
        )
    finally:
        conn.close()
    return result


@mcp.tool()
def list_surface_maps(period: str | None = None) -> dict:
    """列出已数字化的“地下水埋深等值面图”（连续场反演结果）：期号、图号、覆盖区域、定标质量。

    Args:
        period: 期号 YYYY-MM，省略则返回全部已处理期次。
    """
    return sq.surface_maps(period)


@mcp.tool()
def get_depth_at_point(lat: float, lon: float, period: str | None = None) -> dict:
    """按经纬度从等值面图反演任意点的连续地下水埋深（不是按行政区/城市归类取值）。

    结果来自图面等值线：先由颜色等级提取等值线，再在上下两条等值线之间按距离插值，
    因此可返回非分级边界上的连续值（如 5.7 m）。城市/行政区数据只用于图件定标，不参与取值。

    Args:
        lat: 纬度，如 45.75。
        lon: 经度，如 126.63。
        period: 期号 YYYY-MM，省略则在全部已数字化期次中查询（返回各期结果）。
    """
    return sq.point_query(lat, lon, period=period)


@mcp.tool()
def get_depth_surface(
    period: str,
    figure: int | None = None,
    region: str | None = None,
    include_grid: bool = False,
) -> dict:
    """查看某一期等值面图的数字化结果：图例、定标模型、连续场统计、等级占比。

    Args:
        period: 期号 YYYY-MM。
        figure: 图号（可用 list_surface_maps 查）；省略时按 region 过滤列出概要。
        region: 地貌单元名（如“松嫩平原”），用于筛选覆盖该区域的图。
        include_grid: 是否返回粗分辨率等级栅格（二维整数数组，-1 表示图外）。
    """
    if figure is not None:
        return sq.surface_detail(period, int(figure), include_grid=include_grid)
    data = sq.surface_maps(period)
    if region:
        data["maps"] = [m for m in data["maps"] if region in "".join(m.get("regions") or [])]
        data["count"] = len(data["maps"])
    return data


@mcp.tool()
def get_city_depth(city: str, period: str | None = None) -> dict:
    """按城市名查询该城市点位由等值面反演的连续埋深（城市点位仅作坐标使用）。

    Args:
        city: 城市名（不含“市”），如“哈尔滨”“石家庄”。
        period: 期号 YYYY-MM，省略则在全部已数字化期次中查询。
    """
    pts = _city_points()
    return sq.city_depth(city, pts, period=period)


@mcp.tool()
def get_map_picker() -> dict:
    """获取“地图选点”用的本地交互地图：返回 HTML 文件路径与使用说明，可在浏览器打开后点击取坐标。"""
    picker = PACKAGE_DIR / "data" / "map" / "map_picker.html"
    return {
        "picker_path": str(picker),
        "exists": picker.exists(),
        "how_to": [
            "用浏览器打开 picker_path（file:// 路径）",
            "在地图上点击目标位置，页面会显示经纬度，可点按钮复制 lat, lon 或 JSON",
            "把经纬度传给 locate_by_map_point(lat, lon, period=...) 或 query_by_location(mode='map_point', ...)",
        ],
        "resource_uri": "groundwater://map/picker",
        "note": (
            "Leaflet 已随包分发（data/map/leaflet.js|css），离线也能加载页面并取坐标；"
            "底图默认高德（GCJ-02 选点后自动转换为 WGS84，与 MCP 数据一致），"
            "可切换 OSM/Esri/无底图；底图瓦片需要联网，离线时切换“无底图”仍可取坐标。"
            "地图仅用于取坐标，不参与数据计算。"
        ),
    }


# ---------------------------------------------------------------------------
# 资源
# ---------------------------------------------------------------------------
@mcp.resource("groundwater://catalog", name="报告目录", mime_type="application/json")
def catalog_resource() -> str:
    """全部可用期号与元数据（JSON）。"""
    conn = repo.connect()
    try:
        rows = repo.list_reports(conn, limit=500)
    finally:
        conn.close()
    return json.dumps({"count": len(rows), "reports": rows}, ensure_ascii=False, indent=2)


@mcp.resource("groundwater://report/{period}", name="单期报告元数据", mime_type="application/json")
def report_resource(period: str) -> str:
    """某一期的元数据、综述与章节结构（JSON）。"""
    conn = repo.connect()
    try:
        report = repo.get_report(conn, period)
    finally:
        conn.close()
    return json.dumps(report, ensure_ascii=False, indent=2)


@mcp.resource("groundwater://map/picker", name="地图选点页面", mime_type="text/html")
def map_picker_resource() -> str:
    """可点击取经纬度的交互地图 HTML（保存为 .html 后用浏览器打开）。"""
    picker = PACKAGE_DIR / "data" / "map" / "map_picker.html"
    if picker.exists():
        return picker.read_text(encoding="utf-8")
    return "<html><body><h1>地图选点页面缺失</h1></body></html>"


@mcp.prompt(name="region_groundwater_brief", description="生成某监测区某期的地下水动态摘要")
def region_prompt(region: str, period: str = "最新") -> str:
    return (
        f"请基于 groundwater-monthly 服务器中的数据，为“{region}”{period} 期《地下水动态月报》生成简报：\n"
        "1) 先调用 get_shallow_groundwater(region=...) 获取平均埋深、较上月/去年同期变化与变幅分布；\n"
        "2) 调用 get_precipitation 获取该区降水及距平；如为山西盆地可结合 get_shanxi_basin_series；\n"
        "3) 调用 get_time_series 概述近 12 期趋势；\n"
        "4) 引用时注明期号与来源 PDF 链接，说明埋深变化符号含义（正=埋深增大/水位下降）。"
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
