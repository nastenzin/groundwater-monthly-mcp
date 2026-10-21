# -*- coding: utf-8 -*-
"""数据库访问层：把 SQLite 中的数据组织成面向 MCP 工具的结构。"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from .paths import db_path

PERIOD_RE = re.compile(r"(\d{4})\D*(\d{1,2})")
METRICS = {
    "depth": ("mean_depth_m", "平均埋深(m)"),
    "change_prev": ("change_prev_month_m", "埋深较上月变化(m)"),
    "change_year": ("change_last_year_m", "埋深较去年同期变化(m)"),
    "precip": ("precip_mm", "月平均降水量(mm)"),
    "anomaly": ("anomaly_pct", "降水量距平(%)"),
}


class DataError(ValueError):
    """可读的数据查询错误（直接返回给调用方）。"""


def connect() -> sqlite3.Connection:
    path = db_path()
    if not path.exists():
        raise DataError(
            f"数据库不存在：{path}。请先运行 `python -m groundwater_mcp.ingest.build` 构建数据。"
        )
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def normalize_period(period: str | None) -> str | None:
    if period is None:
        return None
    text = str(period).strip()
    if text in {"", "latest", "最新", "最新一期"}:
        return None
    m = PERIOD_RE.search(text)
    if not m:
        raise DataError(f"无法识别的期号：{period!r}，请使用 YYYY-MM（如 2025-12）")
    year, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        raise DataError(f"月份不合法：{period!r}")
    return f"{year}-{month:02d}"


def _latest_period(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT period FROM reports ORDER BY period DESC LIMIT 1").fetchone()
    if not row:
        raise DataError("数据库中没有任何报告")
    return row["period"]


def resolve_period(conn: sqlite3.Connection, period: str | None) -> str:
    p = normalize_period(period)
    if p is None:
        return _latest_period(conn)
    row = conn.execute("SELECT period FROM reports WHERE period=?", (p,)).fetchone()
    if not row:
        periods = [r["period"] for r in conn.execute("SELECT period FROM reports ORDER BY period DESC")]
        raise DataError(f"没有 {p} 期数据。可用期号：{', '.join(periods)}")
    return p


def _rows(cursor: sqlite3.Cursor) -> list[dict[str, Any]]:
    return [dict(r) for r in cursor.fetchall()]


# ---------------------------------------------------------------------------
# 报告目录 / 元数据
# ---------------------------------------------------------------------------
def list_reports(conn: sqlite3.Connection, year: int | None = None, limit: int = 200) -> list[dict]:
    sql = (
        "SELECT period, year, month, title, publish_date, detail_url, pdf_url, pages, "
        "station_total, shallow_stations, deep_stations FROM reports"
    )
    params: list[Any] = []
    if year is not None:
        sql += " WHERE year=?"
        params.append(int(year))
    sql += " ORDER BY period DESC LIMIT ?"
    params.append(max(1, min(int(limit), 500)))
    return _rows(conn.execute(sql, params))


def get_report(conn: sqlite3.Connection, period: str | None) -> dict:
    p = resolve_period(conn, period)
    report = dict(conn.execute("SELECT * FROM reports WHERE period=?", (p,)).fetchone())
    sections = _rows(
        conn.execute("SELECT seq, heading, text FROM sections WHERE period=? ORDER BY seq", (p,))
    )
    report["sections"] = [
        {"heading": s["heading"], "chars": len(s["text"]), "text": s["text"]} for s in sections
    ]
    return report


# ---------------------------------------------------------------------------
# 各类数据
# ---------------------------------------------------------------------------
def get_precipitation(
    conn: sqlite3.Connection, period: str | None, group: str | None = None, unit: str | None = None
) -> dict:
    p = resolve_period(conn, period)
    sql = "SELECT * FROM precipitation WHERE period=?"
    params: list[Any] = [p]
    if group:
        sql += " AND (group_name LIKE ? OR province LIKE ? OR unit LIKE ?)"
        like = f"%{group}%"
        params += [like, like, like]
    sql += " ORDER BY table_no, rowid"
    rows = _rows(conn.execute(sql, params))
    if unit:
        rows = [r for r in rows if unit in r["unit"] or r["unit"] in unit or unit in (r["province"] or "")]
    return {"period": p, "count": len(rows), "rows": rows}


def get_shallow_groundwater(
    conn: sqlite3.Connection,
    period: str | None,
    region: str | None = None,
    group: str | None = None,
) -> dict:
    p = resolve_period(conn, period)
    sql = "SELECT * FROM shallow_regions WHERE period=?"
    params: list[Any] = [p]
    if region:
        sql += " AND (region LIKE ? OR group_name LIKE ?)"
        params += [f"%{region}%", f"%{region}%"]
    if group:
        sql += " AND group_name LIKE ?"
        params.append(f"%{group}%")
    rows = _rows(conn.execute(sql, params))
    basins = _rows(conn.execute("SELECT * FROM shallow_basins WHERE period=?", (p,)))
    dist = _rows(
        conn.execute(
            "SELECT table_no, region_label, method, bin_label, share_pct FROM shallow_distribution "
            "WHERE period=? ORDER BY table_no, method, rowid",
            (p,),
        )
    )
    result = {"period": p, "regions": rows}
    if region or group:
        # 只返回与筛选地貌单元相关的变幅分布
        names = {r["region"] for r in rows} | {r["group_name"] for r in rows}
        keep = []
        for d in dist:
            label = d["region_label"] or ""
            if any(n and n in label for n in names):
                keep.append(d)
        dist = keep
        basins = [b for b in basins if any(b["basin"] in (r.get("region") or "") for r in rows)] or basins
    result["distribution"] = dist
    result["shanxi_basins"] = basins
    result["notes"] = {
        "change_sign": "正值表示埋深增大（地下水水位下降），负值表示埋深减小（水位上升），单位 m",
        "distribution": "按面积统计的埋深变幅分级占比，method=prev_month 为与上月相比，last_year 为与去年同期相比",
    }
    return result


def get_deep_groundwater(
    conn: sqlite3.Connection, period: str | None, province: str | None = None
) -> dict:
    p = resolve_period(conn, period)
    sql = "SELECT * FROM deep_provinces WHERE period=?"
    params: list[Any] = [p]
    if province:
        sql += " AND province LIKE ?"
        params.append(f"%{province}%")
    rows = _rows(conn.execute(sql, params))
    total = next((r for r in rows if r["province"] == "总计"), None)
    if total is None:
        total = next(
            (
                r
                for r in _rows(conn.execute("SELECT * FROM deep_provinces WHERE period=?", (p,)))
                if r["province"] == "总计"
            ),
            None,
        )
    return {
        "period": p,
        "count": len(rows),
        "provinces": [r for r in rows if r["province"] != "总计"],
        "total": total,
        "notes": "占比为深层地下水水位较去年同期的变幅站点比例；上升=水位上升，下降=水位下降",
    }


def get_key_stations(conn: sqlite3.Connection, period: str | None, kind: str | None = None) -> dict:
    p = resolve_period(conn, period)
    kind = (kind or "all").lower()
    out: dict[str, Any] = {"period": p}
    if kind in {"all", "water", "fissure", "karst", "裂隙水", "岩溶水"}:
        rows = _rows(conn.execute("SELECT * FROM water_stations WHERE period=?", (p,)))
        if kind in {"fissure", "裂隙水"}:
            rows = [r for r in rows if r["medium"] == "裂隙水"]
        elif kind in {"karst", "岩溶水"}:
            rows = [r for r in rows if r["medium"] == "岩溶水"]
        out["water_stations"] = rows
    if kind in {"all", "temperature", "temp", "水温"}:
        out["temperature_stations"] = _rows(
            conn.execute("SELECT * FROM temperature_stations WHERE period=?", (p,))
        )
    if kind in {"all", "spring", "springs", "泉流量"}:
        out["springs"] = _rows(conn.execute("SELECT * FROM springs WHERE period=?", (p,)))
    return out


def get_table(conn: sqlite3.Connection, period: str | None, table_no: int) -> dict:
    p = resolve_period(conn, period)
    row = conn.execute(
        "SELECT caption, page, rows_json FROM report_tables WHERE period=? AND table_no=?",
        (p, int(table_no)),
    ).fetchone()
    if not row:
        available = [r["table_no"] for r in conn.execute(
            "SELECT table_no FROM report_tables WHERE period=? ORDER BY table_no", (p,)
        )]
        raise DataError(f"{p} 期没有表 {table_no}。可用表号：{available}")
    return {
        "period": p,
        "table_no": int(table_no),
        "caption": row["caption"],
        "page": row["page"],
        "rows": json.loads(row["rows_json"]),
    }


# ---------------------------------------------------------------------------
# 时间序列
# ---------------------------------------------------------------------------
def get_time_series(
    conn: sqlite3.Connection,
    metric: str,
    region: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    if metric not in METRICS:
        raise DataError(f"metric 必须是 {', '.join(METRICS)} 之一")
    start_p = normalize_period(start) if start else None
    end_p = normalize_period(end) if end else None
    points: list[dict[str, Any]] = []
    if metric in {"precip", "anomaly"}:
        field, label = METRICS[metric]
        sql = f"SELECT period, unit AS name, {field} AS value FROM precipitation WHERE 1=1"
        params: list[Any] = []
        if region:
            sql += " AND (unit LIKE ? OR province LIKE ?)"
            params += [f"%{region}%", f"%{region}%"]
        if start_p:
            sql += " AND period>=?"
            params.append(start_p)
        if end_p:
            sql += " AND period<=?"
            params.append(end_p)
        sql += " ORDER BY unit, period"
        for r in _rows(conn.execute(sql, params)):
            points.append({"period": r["period"], "name": r["name"], "value": r["value"]})
    else:
        field, label = METRICS[metric]
        sql = f"SELECT period, region AS name, {field} AS value FROM shallow_regions WHERE 1=1"
        params = []
        if region:
            sql += " AND (region LIKE ? OR group_name LIKE ?)"
            params += [f"%{region}%", f"%{region}%"]
        if start_p:
            sql += " AND period>=?"
            params.append(start_p)
        if end_p:
            sql += " AND period<=?"
            params.append(end_p)
        sql += " ORDER BY name, period"
        points = _rows(conn.execute(sql, params))
        # 山西主要盆地可细化为表11各盆地
    names = sorted({p["name"] for p in points})
    series = {name: [p for p in points if p["name"] == name] for name in names}
    return {
        "metric": metric,
        "metric_label": METRICS[metric][1],
        "series": series,
        "notes": "period 为 YYYY-MM；埋深类指标正值=埋深增大（水位下降），负值=埋深减小（水位上升）",
    }


def get_shanxi_basin_series(conn: sqlite3.Connection, basin: str) -> dict:
    rows = _rows(
        conn.execute(
            "SELECT period, basin, mean_depth_m, change_prev_month_m, change_last_year_m "
            "FROM shallow_basins WHERE basin LIKE ? ORDER BY period",
            (f"%{basin}%",),
        )
    )
    return {"basin": basin, "series": rows}


# ---------------------------------------------------------------------------
# 全文检索 / 原文
# ---------------------------------------------------------------------------
def search_text(
    conn: sqlite3.Connection, query: str, period: str | None = None, limit: int = 20
) -> dict:
    if not query or not query.strip():
        raise DataError("query 不能为空")
    limit = max(1, min(int(limit), 100))
    sql = (
        "SELECT period, page, text FROM report_text WHERE text LIKE ?"
    )
    params: list[Any] = [f"%{query.strip()}%"]
    p = normalize_period(period) if period else None
    if p:
        sql += " AND period=?"
        params.append(p)
    sql += " ORDER BY period DESC, page LIMIT ?"
    params.append(limit * 6)
    hits = []
    for row in conn.execute(sql, params):
        text = row["text"]
        idx = text.find(query.strip())
        snippet = text[max(0, idx - 60) : idx + len(query.strip()) + 90].replace("\n", "")
        hits.append({"period": row["period"], "page": row["page"], "snippet": snippet})
        if len(hits) >= limit:
            break
    return {"query": query, "count": len(hits), "hits": hits}


def get_report_text(
    conn: sqlite3.Connection,
    period: str | None,
    section: str | None = None,
    page_start: int | None = None,
    page_end: int | None = None,
    max_chars: int = 8000,
) -> dict:
    p = resolve_period(conn, period)
    if section:
        rows = _rows(
            conn.execute(
                "SELECT seq, heading, text FROM sections WHERE period=? AND heading LIKE ? ORDER BY seq",
                (p, f"%{section}%"),
            )
        )
        if not rows:
            raise DataError(f"{p} 期没有标题包含 {section!r} 的章节")
        text = "\n\n".join(f"## {r['heading']}\n{r['text']}" for r in rows)[:max_chars]
        return {"period": p, "section": rows[0]["heading"], "text": text}
    sql = "SELECT page, text FROM report_text WHERE period=?"
    params: list[Any] = [p]
    if page_start:
        sql += " AND page>=?"
        params.append(int(page_start))
    if page_end:
        sql += " AND page<=?"
        params.append(int(page_end))
    sql += " ORDER BY page"
    docs = _rows(conn.execute(sql, params))
    text = "\n\n".join(f"### 第{d['page']}页\n{d['text']}" for d in docs)[:max_chars]
    return {"period": p, "pages": [d["page"] for d in docs], "text": text}


# ---------------------------------------------------------------------------
# 供位置查询使用
# ---------------------------------------------------------------------------
def region_snapshot(conn: sqlite3.Connection, period: str, region: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM shallow_regions WHERE period=? AND region=?", (period, region)
    ).fetchone()
    if not row:
        row = conn.execute(
            "SELECT * FROM shallow_regions WHERE period=? AND region LIKE ?",
            (period, f"%{region}%"),
        ).fetchone()
    return dict(row) if row else None


def region_series(
    conn: sqlite3.Connection, region: str, end_period: str | None = None, limit: int = 12
) -> list[dict]:
    """返回该地貌单元截至 end_period（含）的最近若干期序列（时间升序）。"""
    sql = (
        "SELECT period, mean_depth_m, change_prev_month_m, change_last_year_m "
        "FROM shallow_regions WHERE region=?"
    )
    params: list[Any] = [region]
    if end_period:
        sql += " AND period<=?"
        params.append(end_period)
    sql += " ORDER BY period DESC LIMIT ?"
    params.append(int(limit))
    rows = _rows(conn.execute(sql, params))
    return list(reversed(rows))


def distribution_for(conn: sqlite3.Connection, period: str, region: str) -> list[dict]:
    rows = _rows(
        conn.execute(
            "SELECT table_no, region_label, method, bin_label, share_pct FROM shallow_distribution "
            "WHERE period=? AND region_label LIKE ? ORDER BY table_no, method, rowid",
            (period, f"%{region}%"),
        )
    )
    return rows


def precip_for(conn: sqlite3.Connection, period: str, name: str) -> dict | None:
    """按地貌单元/省名取降水记录，兼容不同年份的命名差异（如“一般平原”“河西走廊”）。"""
    candidates = [name]
    for base in (name.replace("一般", ""), name.replace("平原", ""), name.replace("一般", "").replace("平原", "")):
        if base and base not in candidates:
            candidates.append(base)
    for cand in candidates:
        row = conn.execute(
            "SELECT * FROM precipitation WHERE period=? AND unit=?", (period, cand)
        ).fetchone()
        if row:
            return dict(row)
    for cand in candidates:
        row = conn.execute(
            "SELECT * FROM precipitation WHERE period=? AND (unit LIKE ? OR province LIKE ?)",
            (period, f"%{cand}%", f"%{cand}%"),
        ).fetchone()
        if row:
            return dict(row)
    return None


def deep_for_province(conn: sqlite3.Connection, period: str, province: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM deep_provinces WHERE period=? AND province LIKE ?",
        (period, f"%{province}%"),
    ).fetchone()
    return dict(row) if row else None


def available_periods(conn: sqlite3.Connection) -> list[str]:
    return [r["period"] for r in conn.execute("SELECT period FROM reports ORDER BY period DESC")]


def db_stats(conn: sqlite3.Connection) -> dict:
    def count(table: str) -> int:
        return conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]

    return {
        "reports": count("reports"),
        "periods": available_periods(conn),
        "precipitation_rows": count("precipitation"),
        "shallow_regions": count("shallow_regions"),
        "deep_province_rows": count("deep_provinces"),
        "water_station_rows": count("water_stations"),
        "temperature_station_rows": count("temperature_stations"),
        "spring_rows": count("springs"),
        "tables": count("report_tables"),
        "annual_reports": count("annual_reports"),
        "annual_groundwater_rows": count("annual_groundwater"),
        "bulletin_reports": count("bulletin_reports"),
        "bulletin_national_rows": count("bulletin_national"),
        "bulletin_region_rows": count("bulletin_regions"),
        "bulletin_province_rows": count("bulletin_provinces"),
        "bulletin_plain_rows": count("bulletin_plains"),
        "bulletin_years": [
            r["year"] for r in conn.execute("SELECT year FROM bulletin_national ORDER BY year")
        ],
        "surface_maps": count("surface_maps"),
        "surface_periods": [
            r["period"] for r in conn.execute(
                "SELECT DISTINCT period FROM surface_maps ORDER BY period DESC")
        ],
        "db_path": str(db_path()),
        "db_size_kb": round(Path(db_path()).stat().st_size / 1024),
    }


# ---------------------------------------------------------------------------
# 年报（年末 12 月）数据：补齐 2023-12 之前的年际基准
# ---------------------------------------------------------------------------
def list_annual_reports(conn: sqlite3.Connection) -> list[dict]:
    rows = _rows(conn.execute("SELECT * FROM annual_reports ORDER BY year DESC"))
    for row in rows:
        try:
            row["data_years"] = json.loads(row["data_years"]) if row["data_years"] else []
        except json.JSONDecodeError:
            row["data_years"] = []
    return rows


def get_annual_groundwater(
    conn: sqlite3.Connection,
    year: int | None = None,
    data_year: int | None = None,
    region: str | None = None,
    row_type: str | None = None,
) -> dict:
    sql = "SELECT * FROM annual_groundwater WHERE 1=1"
    params: list[Any] = []
    if year is not None:
        sql += " AND report_year=?"
        params.append(int(year))
    if data_year is not None:
        sql += " AND data_year=?"
        params.append(int(data_year))
    if region:
        sql += " AND (region LIKE ? OR region_label LIKE ?)"
        params.extend([f"%{region}%", f"%{region}%"])
    if row_type and row_type != "all":
        sql += " AND row_type=?"
        params.append(row_type)
    sql += " ORDER BY data_year DESC, row_type, region"
    rows = _rows(conn.execute(sql, params))
    return {
        "count": len(rows),
        "rows": rows,
        "notes": {
            "row_type": "plain_basin=全国主要平原及盆地（表5-2）；key_region=重点区域（表5-3）",
            "sign": "water_level_change_m 为地下水位变幅（正=水位上升）；depth_change_m 为埋深变幅（正=埋深增大）",
            "coverage": "来自《中国水文年报》地下水章节的年末（12 月）数据，用于补齐月报序列之前的年际基准",
        },
    }


def annual_series_for_region(conn: sqlite3.Connection, region: str) -> list[dict]:
    rows = _rows(
        conn.execute(
            "SELECT report_year, data_year, region, shallow_depth_m, shallow_water_level_change_m, "
            "deep_depth_m, deep_water_level_change_m FROM annual_groundwater "
            "WHERE row_type='plain_basin' AND region=? ORDER BY data_year",
            (region,),
        )
    )
    return rows


# ---------------------------------------------------------------------------
# 历年《中国水资源公报》地下水数据（1997-2024）
# ---------------------------------------------------------------------------
BULLETIN_METRICS = {
    "national": {
        "ground_resource": ("ground_resource_1e8m3", "地下水资源量（亿m³）"),
        "ground_supply": ("ground_supply_1e8m3", "地下水供水量（亿m³）"),
        "ground_share": ("ground_share_pct", "地下水供水量占总供水比例（%）"),
        "total_supply": ("total_supply_1e8m3", "总供水量（亿m³）"),
        "plain_resource": ("plain_resource_1e8m3", "平原区地下水资源量（亿m³）"),
        "plain_storage_change": ("plain_storage_change_1e8m3", "北方平原区浅层地下水储存量较年初变化（亿m³）"),
    },
    "region": {
        "ground_resource": ("ground_resource_1e8m3", "地下水资源量（亿m³）"),
        "ground_supply": ("ground_supply_1e8m3", "地下水供水量（亿m³）"),
        "ground_share": ("ground_share_pct", "地下水供水量占总供水比例（%）"),
        "total_supply": ("total_supply_1e8m3", "总供水量（亿m³）"),
    },
    "province": {
        "ground_resource": ("ground_resource_1e8m3", "地下水资源量（亿m³）"),
        "ground_supply": ("ground_supply_1e8m3", "地下水供水量（亿m³）"),
        "ground_share": ("ground_share_pct", "地下水供水量占总供水比例（%）"),
        "total_supply": ("total_supply_1e8m3", "总供水量（亿m³）"),
    },
    "plain": {
        "shallow_end": ("shallow_end_m", "浅层地下水年末平均埋深（m）"),
        "shallow_change": ("shallow_change_m", "浅层地下水埋深年内变幅（m）"),
        "deep_end": ("deep_end_m", "深层地下水年末平均埋深（m）"),
        "deep_change": ("deep_change_m", "深层地下水埋深年内变幅（m）"),
    },
}

BULLETIN_LEVEL_TABLE = {
    "national": "bulletin_national",
    "region": "bulletin_regions",
    "province": "bulletin_provinces",
    "plain": "bulletin_plains",
}


def _bulletin_level(level: str | None) -> str:
    lv = (level or "national").strip().lower()
    aliases = {
        "全国": "national", "national": "national", "country": "national",
        "region": "region", "一级区": "region", "水资源一级区": "region",
        "province": "province", "省": "province", "省级行政区": "province",
        "plain": "plain", "plains": "plain", "平原": "plain", "盆地": "plain",
    }
    if lv not in aliases:
        raise DataError("level 必须是 national / region / province / plain 之一")
    return aliases[lv]


def list_bulletin_reports(conn: sqlite3.Connection) -> list[dict]:
    rows = _rows(conn.execute("SELECT * FROM bulletin_reports ORDER BY year"))
    for row in rows:
        row["coverage"] = [c for c in (row.get("coverage") or "").split(",") if c]
    return rows


def get_bulletin_national(conn: sqlite3.Connection, year: int | None = None) -> dict:
    sql = "SELECT * FROM bulletin_national"
    params: list[Any] = []
    if year is not None:
        sql += " WHERE year=?"
        params.append(int(year))
    sql += " ORDER BY year"
    rows = _rows(conn.execute(sql, params))
    if year is not None and not rows:
        raise DataError(f"《中国水资源公报》没有 {year} 年的地下水数据（1997、1998、2001-2024 中部分年份缺失）")
    for r in rows:
        r["note"] = r.get("note") or _bulletin_note(r["year"])
    return {
        "count": len(rows),
        "rows": rows,
        "metrics": {k: v[1] for k, v in BULLETIN_METRICS["national"].items()},
        "notes": {
            "source": "《中国水资源公报》历年地下水章节/附表（1997、1998、2001-2024）",
            "unit": "亿m³（埋深单位为 m）",
            "sign": "plain_storage_change 正值=储存量增加（水位上升），负值=减少（水位下降）",
        },
    }


def _bulletin_note(year: int) -> str:
    if year == 2023:
        return "2023 年卷为扫描版 PDF，未做 OCR，暂未入库"
    if year == 1998:
        return "1998 年卷在线版本仅给出叙述性比例，未给出可解析的绝对数值"
    if year in (1999, 2000):
        return "该年份公报未在水利部网站公开"
    return ""


def get_bulletin_regions(conn: sqlite3.Connection, year: int | None = None,
                         region: str | None = None) -> dict:
    sql = "SELECT * FROM bulletin_regions WHERE 1=1"
    params: list[Any] = []
    if year is not None:
        sql += " AND year=?"
        params.append(int(year))
    if region:
        sql += " AND region LIKE ?"
        params.append(f"%{region}%")
    sql += " ORDER BY year, CASE region_group WHEN '全国' THEN 0 WHEN '北方' THEN 1 " \
           "WHEN '南方' THEN 2 WHEN '一级区' THEN 3 ELSE 4 END, region"
    rows = _rows(conn.execute(sql, params))
    return {"count": len(rows), "rows": rows,
            "notes": "1997 年为九大流域片口径，2006 年起为 10 个水资源一级区口径；"
                     "单位亿m³；北方6区+南方4区=全国（一级区口径）"}


def get_bulletin_provinces(conn: sqlite3.Connection, year: int | None = None,
                           province: str | None = None) -> dict:
    sql = "SELECT * FROM bulletin_provinces WHERE province<>'全国'"
    params: list[Any] = []
    if year is not None:
        sql += " AND year=?"
        params.append(int(year))
    if province:
        sql += " AND province LIKE ?"
        params.append(f"%{province}%")
    sql += " ORDER BY year, province"
    rows = _rows(conn.execute(sql, params))
    return {"count": len(rows), "rows": rows,
            "notes": "省级行政区地下水数据来自公报附表（2011、2016-2024，部分年份无表）；单位亿m³"}


def get_bulletin_plains(conn: sqlite3.Connection, year: int | None = None,
                        plain: str | None = None) -> dict:
    sql = "SELECT * FROM bulletin_plains WHERE 1=1"
    params: list[Any] = []
    if year is not None:
        sql += " AND year=?"
        params.append(int(year))
    if plain:
        sql += " AND plain LIKE ?"
        params.append(f"%{plain}%")
    sql += " ORDER BY year, plain"
    rows = _rows(conn.execute(sql, params))
    return {"count": len(rows), "rows": rows,
            "notes": "2021/2022 年公报“主要平原及盆地浅层（深层）地下水动态”表；2021 年为年初/年末/变幅口径"}


def get_bulletin_series(
    conn: sqlite3.Connection,
    metric: str,
    level: str = "national",
    name: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict:
    lv = _bulletin_level(level)
    metrics = BULLETIN_METRICS[lv]
    if metric not in metrics:
        raise DataError(f"metric 必须是 {', '.join(metrics)} 之一（level={lv}）")
    field, label = metrics[metric]
    table = BULLETIN_LEVEL_TABLE[lv]
    key_col = {"national": None, "region": "region", "province": "province", "plain": "plain"}[lv]
    sql = f"SELECT * FROM {table} WHERE {field} IS NOT NULL"
    params: list[Any] = []
    if key_col and name:
        sql += f" AND {key_col} LIKE ?"
        params.append(f"%{name}%")
    if start_year is not None:
        sql += " AND year>=?"
        params.append(int(start_year))
    if end_year is not None:
        sql += " AND year<=?"
        params.append(int(end_year))
    order = "year" if key_col is None else f"{key_col}, year"
    sql += f" ORDER BY {order}"
    rows = _rows(conn.execute(sql, params))
    if not rows:
        raise DataError(f"没有匹配的《中国水资源公报》{label}数据（level={lv}, name={name!r}）")
    series: dict[str, list[dict]] = {}
    for r in rows:
        key = "全国" if key_col is None else r[key_col]
        series.setdefault(key, []).append({
            "year": r["year"], "value": r[field],
            "region_group": r.get("region_group") if lv == "region" else None,
        })
    return {"level": lv, "metric": metric, "metric_label": label,
            "count": len(rows), "series": series,
            "notes": "year 为公报年份（数据年份）；埋深类正值=埋深增大（水位下降）；储存量变化正值=增加"}


def bulletin_series_for_province(conn: sqlite3.Connection, province: str) -> list[dict]:
    return _rows(
        conn.execute(
            "SELECT year, ground_resource_1e8m3, ground_supply_1e8m3, ground_share_pct, "
            "total_supply_1e8m3 FROM bulletin_provinces WHERE province=? ORDER BY year",
            (province,),
        )
    )


def bulletin_series_for_plain(conn: sqlite3.Connection, plain: str) -> list[dict]:
    rows = _rows(
        conn.execute(
            "SELECT year, shallow_end_m, shallow_change_m, deep_end_m, deep_change_m "
            "FROM bulletin_plains WHERE plain=? ORDER BY year",
            (plain,),
        )
    )
    if not rows:
        rows = _rows(
            conn.execute(
                "SELECT year, shallow_end_m, shallow_change_m, deep_end_m, deep_change_m "
                "FROM bulletin_plains WHERE plain LIKE ? ORDER BY year",
                (f"%{plain}%",),
            )
        )
    return rows
