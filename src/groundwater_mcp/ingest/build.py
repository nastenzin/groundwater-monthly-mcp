# -*- coding: utf-8 -*-
"""构建《地下水动态月报》结构化数据库。

输入：
  data/report_index.json   官方报告索引（由 scripts/crawl_index.py 生成）
  data/pdfs/<YYYY-MM>.pdf  报告原文
  data/legacy_index.json   可选，历史报告索引（由扩展语料流程生成）
输出：
  src/groundwater_mcp/data/groundwater.db  SQLite 数据库（随包分发）
  data/parsed/<YYYY-MM>.json               单期解析结果缓存
  data/dataset.json                        全量结构化数据（便于检查）
"""
from __future__ import annotations

import json
import sqlite3
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from groundwater_mcp.ingest.pdf_parse import parse_pdf  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"
PARSED = DATA / "parsed"
DB_OUT = ROOT / "src" / "groundwater_mcp" / "data" / "groundwater.db"

SCHEMA = """
DROP TABLE IF EXISTS reports;
DROP TABLE IF EXISTS sections;
DROP TABLE IF EXISTS precipitation;
DROP TABLE IF EXISTS shallow_regions;
DROP TABLE IF EXISTS shallow_basins;
DROP TABLE IF EXISTS shallow_distribution;
DROP TABLE IF EXISTS deep_provinces;
DROP TABLE IF EXISTS water_stations;
DROP TABLE IF EXISTS temperature_stations;
DROP TABLE IF EXISTS springs;
DROP TABLE IF EXISTS report_tables;
DROP TABLE IF EXISTS report_text;
DROP TABLE IF EXISTS annual_reports;
DROP TABLE IF EXISTS annual_groundwater;
DROP TABLE IF EXISTS bulletin_reports;
DROP TABLE IF EXISTS bulletin_national;
DROP TABLE IF EXISTS bulletin_regions;
DROP TABLE IF EXISTS bulletin_provinces;
DROP TABLE IF EXISTS bulletin_plains;

CREATE TABLE reports (
  period TEXT PRIMARY KEY,
  year INTEGER, month INTEGER,
  title TEXT, publish_date TEXT, detail_url TEXT, pdf_url TEXT,
  source_pdf TEXT, source_kind TEXT, pages INTEGER,
  station_total INTEGER, shallow_stations INTEGER, deep_stations INTEGER,
  deep_up_pct REAL, deep_stable_pct REAL, deep_down_pct REAL,
  deep_up_gt2_pct REAL, deep_down_gt2_pct REAL,
  deep_up_top3 TEXT, deep_down_top3 TEXT,
  summary_text TEXT
);
CREATE TABLE sections (
  period TEXT, seq INTEGER, heading TEXT, text TEXT,
  PRIMARY KEY (period, seq)
);
CREATE TABLE precipitation (
  period TEXT, table_no INTEGER, group_name TEXT, province TEXT, unit TEXT,
  precip_mm REAL, anomaly_pct REAL
);
CREATE TABLE shallow_regions (
  period TEXT, group_name TEXT, region TEXT,
  mean_depth_m REAL,
  change_prev_month_m REAL, change_prev_month_text TEXT,
  change_last_year_m REAL, change_last_year_text TEXT,
  area_threshold_m REAL, area_km2 REAL, area_share_pct REAL,
  raw_sentence TEXT
);
CREATE TABLE shallow_basins (
  period TEXT, basin TEXT, mean_depth_m REAL, max_depth_m REAL, min_depth_m REAL,
  change_prev_month_m REAL, change_last_year_m REAL
);
CREATE TABLE shallow_distribution (
  period TEXT, table_no INTEGER, region_label TEXT, method TEXT,
  bin_label TEXT, share_pct REAL
);
CREATE TABLE deep_provinces (
  period TEXT, province TEXT, total_stations INTEGER,
  up_gt2_pct REAL, up_0_5_2_pct REAL, stable_pct REAL,
  down_0_5_2_pct REAL, down_gt2_pct REAL
);
CREATE TABLE water_stations (
  period TEXT, province TEXT, city TEXT, station TEXT, medium TEXT,
  water_level_m REAL, change_prev_month_m REAL, change_last_year_m REAL
);
CREATE TABLE temperature_stations (
  period TEXT, province TEXT, city TEXT, station TEXT,
  water_temp_c REAL, depth_m REAL, note TEXT
);
CREATE TABLE springs (
  period TEXT, province TEXT, city TEXT, station TEXT,
  mean_flow_m3s REAL, max_flow_m3s REAL, min_flow_m3s REAL, note TEXT
);
CREATE TABLE report_tables (
  period TEXT, table_no INTEGER, caption TEXT, page INTEGER, rows_json TEXT,
  PRIMARY KEY (period, table_no)
);
CREATE TABLE report_text (
  period TEXT, page INTEGER, section TEXT, text TEXT
);
CREATE TABLE annual_reports (
  year INTEGER PRIMARY KEY, title TEXT, detail_url TEXT, pdf_url TEXT,
  pages INTEGER, table52_page INTEGER, table53_page INTEGER,
  data_years TEXT, source_kind TEXT
);
CREATE TABLE annual_groundwater (
  report_year INTEGER, data_year INTEGER, row_type TEXT,
  region TEXT, region_label TEXT, region_group TEXT,
  shallow_depth_m REAL, shallow_water_level_change_m REAL, shallow_depth_change_m REAL,
  deep_depth_m REAL, deep_water_level_change_m REAL, deep_depth_change_m REAL,
  source_table TEXT, source_page INTEGER
);
CREATE INDEX idx_annual_region ON annual_groundwater(region);
CREATE INDEX idx_precip_period ON precipitation(period);
CREATE INDEX idx_shallow_period ON shallow_regions(period);
CREATE INDEX idx_deep_period ON deep_provinces(period);
CREATE INDEX idx_text_period ON report_text(period);
CREATE TABLE bulletin_reports (
  year INTEGER PRIMARY KEY,
  title TEXT, detail_url TEXT, source_kind TEXT, pages INTEGER,
  coverage TEXT, note TEXT
);
CREATE TABLE bulletin_national (
  year INTEGER PRIMARY KEY,
  ground_resource_1e8m3 REAL, ground_supply_1e8m3 REAL, ground_share_pct REAL,
  total_supply_1e8m3 REAL, plain_resource_1e8m3 REAL,
  plain_storage_change_1e8m3 REAL, note TEXT
);
CREATE TABLE bulletin_regions (
  year INTEGER, region TEXT, region_group TEXT, scheme TEXT,
  ground_resource_1e8m3 REAL, surface_resource_1e8m3 REAL,
  unrepeat_1e8m3 REAL, total_resource_1e8m3 REAL,
  ground_supply_1e8m3 REAL, surface_supply_1e8m3 REAL, total_supply_1e8m3 REAL,
  ground_share_pct REAL, table_kind TEXT, source TEXT, page INTEGER
);
CREATE TABLE bulletin_provinces (
  year INTEGER, province TEXT,
  ground_resource_1e8m3 REAL, surface_resource_1e8m3 REAL,
  unrepeat_1e8m3 REAL, total_resource_1e8m3 REAL,
  ground_supply_1e8m3 REAL, surface_supply_1e8m3 REAL, total_supply_1e8m3 REAL,
  ground_share_pct REAL, table_kind TEXT, source TEXT, page INTEGER
);
CREATE TABLE bulletin_plains (
  year INTEGER, plain TEXT, region TEXT, monitor_area_1e4km2 REAL,
  shallow_end_m REAL, shallow_prev_m REAL, shallow_start_m REAL, shallow_change_m REAL,
  deep_end_m REAL, deep_prev_m REAL, deep_change_m REAL,
  source TEXT, page INTEGER
);
CREATE INDEX idx_bregion_year ON bulletin_regions(year);
CREATE INDEX idx_bprov_year ON bulletin_provinces(year);
CREATE INDEX idx_bplain_year ON bulletin_plains(year);

DROP TABLE IF EXISTS surface_maps;
CREATE TABLE surface_maps (
  period TEXT, figure INTEGER, page INTEGER,
  caption TEXT, regions TEXT,
  image_w INTEGER, image_h INTEGER,
  grid_w INTEGER, grid_h INTEGER, grid BLOB, field BLOB,
  legend TEXT, model TEXT, model_type TEXT,
  bbox TEXT, k_km_per_px REAL,
  method TEXT, quality TEXT, n_anchors INTEGER,
  anchor_rmse_km REAL, anchor_names TEXT,
  mean_depth_m REAL, min_depth_m REAL, max_depth_m REAL,
  class_consistency REAL, class_share TEXT,
  area_km2 REAL, expected_area_km2 REAL, area_ratio REAL,
  expected_mean_m REAL, mean_error_m REAL,
  source TEXT,
  PRIMARY KEY (period, figure)
);
CREATE INDEX idx_surface_period ON surface_maps(period);
"""


def load_index() -> list[dict]:
    records: dict[str, dict] = {}
    for name in ("report_index.json", "legacy_index.json"):
        path = DATA / name
        if not path.exists():
            continue
        for rec in json.loads(path.read_text(encoding="utf-8")):
            period = rec.get("period")
            if not period or not (rec.get("pdf_file") or rec.get("local_path")):
                continue
            source = rec.get("pdf_file") or rec.get("local_path")
            path = Path(source)
            if not path.is_absolute():
                path = ROOT / path
            if not path.exists() and rec.get("local_path"):
                local = Path(rec["local_path"])
                if not local.is_absolute():
                    local = ROOT / local
                path = local
            rec = dict(rec)
            rec["kind"] = "pdf"
            if path.is_dir() and any(path.glob("page*.html")):
                rec["kind"] = "html"
                rec["local_path"] = str(path)
            elif path.suffix.lower() == ".pdf" and path.exists():
                rec["pdf_file"] = str(path)
                rec["local_path"] = str(path)
            else:
                continue
            records[period] = rec
    return [records[p] for p in sorted(records, reverse=True)]


QUALITY_GATE = {
    "precip": 30,
    "distribution": 6,
    "deep": 15,
    "water": 30,
    "temperature": 50,
    "springs": 6,
    "shallow": 18,
}
HTML_QUALITY_GATE = {
    "precip": 30,
    "distribution": 6,
    "deep": 15,
    "water": 30,
    "shallow": 18,
}


def quality_ok(data: dict, kind: str = "pdf") -> tuple[bool, dict]:
    counts = {
        "precip": len(data["precipitation"]),
        "distribution": len(data["shallow_distribution"]),
        "deep": len(data["deep_provinces"]),
        "water": len(data["water_stations"]),
        "temperature": len(data["temperature_stations"]),
        "springs": len(data["springs"]),
        "shallow": len(data["shallow_narrative"]),
    }
    gate = HTML_QUALITY_GATE if kind == "html" else QUALITY_GATE
    bad = {k: (counts[k], v) for k, v in gate.items() if counts[k] < v}
    return (not bad), {"counts": counts, "below_gate": bad}


def _parser_signature() -> str:
    import hashlib

    digest = hashlib.sha256()
    for name in ("pdf_parse.py", "html_parse.py"):
        path = Path(__file__).with_name(name)
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def parse_all(records: list[dict]) -> list[dict]:
    PARSED.mkdir(parents=True, exist_ok=True)
    sig_file = PARSED / "_parser_signature.txt"
    sig = _parser_signature()
    old_sig = sig_file.read_text(encoding="utf-8").strip() if sig_file.exists() else ""
    if old_sig != sig:
        print("parser changed, invalidating parse cache")
        for cache in PARSED.glob("*.json"):
            cache.unlink()
        sig_file.write_text(sig, encoding="utf-8")
    out = []
    skips = []
    for rec in records:
        period = rec["period"]
        kind = rec.get("kind", "pdf")
        cache = PARSED / f"{period}.json"
        source_path = Path(rec.get("local_path") or rec["pdf_file"])
        if cache.exists() and source_path.exists() and cache.stat().st_mtime >= source_path.stat().st_mtime:
            data = json.loads(cache.read_text(encoding="utf-8"))
        elif kind == "html":
            from groundwater_mcp.ingest.html_parse import parse_html_report

            data = parse_html_report(source_path, period, rec)
            cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        else:
            data = parse_pdf(Path(rec["pdf_file"]), period, rec)
            cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        ok, quality = quality_ok(data, kind)
        if not ok:
            print(
                period,
                "SKIPPED (quality gate):",
                quality["below_gate"],
            )
            skips.append({"period": period, "source": str(source_path), "kind": kind, "quality": quality})
            continue
        out.append(data)
        print(
            period,
            "pages", data["pages"],
            "tables", len(data["tables"]),
            "precip", len(data["precipitation"]),
            "shallow", len(data["shallow_narrative"]),
            "deep", len(data["deep_provinces"]),
            "warn", len(data["warnings"]),
        )
    (DATA / "quality_skips.json").write_text(
        json.dumps(skips, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out


def insert(conn: sqlite3.Connection, data: dict) -> None:
    s = data["summary"]
    conn.execute(
        """INSERT OR REPLACE INTO reports VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            data["period"], data["year"], data["month"], data["title"],
            data.get("publish_date"), data.get("detail_url"), data.get("pdf_url"),
            data.get("source_pdf"), data.get("source_kind", "pdf"), data.get("pages"),
            s.get("station_total"), s.get("shallow_stations"), s.get("deep_stations"),
            s.get("deep_up_pct"), s.get("deep_stable_pct"), s.get("deep_down_pct"),
            s.get("deep_up_gt2_pct"), s.get("deep_down_gt2_pct"),
            s.get("deep_up_top3"), s.get("deep_down_top3"), s.get("text"),
        ),
    )
    for seq, sec in enumerate(data["sections"]):
        conn.execute(
            "INSERT INTO sections VALUES (?,?,?,?)",
            (data["period"], seq, sec["heading"], sec["text"]),
        )
    for p in data["precipitation"]:
        conn.execute(
            "INSERT INTO precipitation VALUES (?,?,?,?,?,?,?)",
            (
                data["period"], p["table_no"], p["group"], p["province"], p["unit"],
                p["precip_mm"], p["anomaly_pct"],
            ),
        )
    for r in data["shallow_narrative"]:
        conn.execute(
            "INSERT INTO shallow_regions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                data["period"], r["group"], r["region"], r["mean_depth_m"],
                r["change_prev_month_m"], r["change_prev_month_text"],
                r["change_last_year_m"], r["change_last_year_text"],
                r.get("area_threshold_m"), r.get("area_km2"), r.get("area_share_pct"),
                r["raw_sentence"],
            ),
        )
    for b in data["shanxi_basins"]:
        conn.execute(
            "INSERT INTO shallow_basins VALUES (?,?,?,?,?,?,?)",
            (
                data["period"], b["basin"], b["mean_depth_m"], b["max_depth_m"],
                b["min_depth_m"], b["change_prev_month_m"], b["change_last_year_m"],
            ),
        )
    for d in data["shallow_distribution"]:
        for method, payload in d["methods"].items():
            for label, value in zip(d["bins"], payload["values_pct"]):
                conn.execute(
                    "INSERT INTO shallow_distribution VALUES (?,?,?,?,?,?)",
                    (data["period"], d["table_no"], d["region_label"], method, label, value),
                )
    for p in data["deep_provinces"]:
        conn.execute(
            "INSERT INTO deep_provinces VALUES (?,?,?,?,?,?,?,?)",
            (
                data["period"], p["province"], p["total_stations"],
                p["up_gt2_pct"], p["up_0_5_2_pct"], p["stable_pct"],
                p["down_0_5_2_pct"], p["down_gt2_pct"],
            ),
        )
    for w in data["water_stations"]:
        conn.execute(
            "INSERT INTO water_stations VALUES (?,?,?,?,?,?,?,?)",
            (
                data["period"], w["province"], w["city"], w["station"], w["medium"],
                w["water_level_m"], w["change_prev_month_m"], w["change_last_year_m"],
            ),
        )
    for t in data["temperature_stations"]:
        conn.execute(
            "INSERT INTO temperature_stations VALUES (?,?,?,?,?,?,?)",
            (
                data["period"], t["province"], t["city"], t["station"],
                t["water_temp_c"], t["depth_m"], t.get("note", ""),
            ),
        )
    for sp in data["springs"]:
        conn.execute(
            "INSERT INTO springs VALUES (?,?,?,?,?,?,?,?)",
            (
                data["period"], sp["province"], sp["city"], sp["station"],
                sp["mean_flow_m3s"], sp["max_flow_m3s"], sp["min_flow_m3s"], sp["note"],
            ),
        )
    for table_no, table in data["tables"].items():
        conn.execute(
            "INSERT INTO report_tables VALUES (?,?,?,?,?)",
            (
                data["period"], int(table_no), table["caption"], table.get("page"),
                json.dumps(table["rows"], ensure_ascii=False),
            ),
        )
    for page in data["page_texts"]:
        conn.execute(
            "INSERT INTO report_text VALUES (?,?,?,?)",
            (data["period"], page["page"], "", page["text"]),
        )


def insert_annual(conn: sqlite3.Connection) -> int:
    """把年报解析结果（data/annual/parsed/*.json）写入数据库。"""
    annual_dir = DATA / "annual" / "parsed"
    count = 0
    if not annual_dir.exists():
        return 0
    for path in sorted(annual_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        years = data.get("data_years") or []
        conn.execute(
            "INSERT OR REPLACE INTO annual_reports VALUES (?,?,?,?,?,?,?,?,?)",
            (
                data["report_year"], data.get("title"), data.get("detail_url"),
                data.get("pdf_url"), data.get("pages"), data.get("table52_page"),
                data.get("table53_page"), json.dumps(years, ensure_ascii=False),
                data.get("source_kind", "pdf-text-layer"),
            ),
        )
        for row_type, rows in (
            ("plain_basin", data.get("plains", [])),
            ("key_region", data.get("key_regions", [])),
        ):
            for row in rows:
                for idx, data_year in enumerate(years):
                    if idx == 0:
                        shallow, deep = row.get("shallow_first"), row.get("deep_first")
                        swl = dwl = None
                    else:
                        shallow, deep = row.get("shallow_second"), row.get("deep_second")
                        swl, dwl = row.get("shallow_change"), row.get("deep_change")
                    sdchg = -swl if swl is not None else None
                    ddchg = -dwl if dwl is not None else None
                    conn.execute(
                        "INSERT INTO annual_groundwater VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            data["report_year"], data_year, row_type,
                            row.get("region"), row.get("region_label"), row.get("region_group"),
                            shallow, swl, sdchg, deep, dwl, ddchg,
                            data.get("table_name") or ("表5-2" if row_type == "plain_basin" else "表5-3"),
                            data.get("table_page") or data.get("table52_page"),
                        ),
                    )
                    count += 1
    # 同一数据年份可能出现在多份年报（后续年报会修订前一年值）：
    # 优先取“当年年报”（report_year == data_year）的版本，否则取最新年报版本。
    conn.execute(
        """
        DELETE FROM annual_groundwater
        WHERE rowid NOT IN (
            SELECT rowid FROM annual_groundwater a
            WHERE rowid = (
                SELECT b.rowid FROM annual_groundwater b
                WHERE b.data_year = a.data_year AND b.row_type = a.row_type AND b.region = a.region
                ORDER BY (b.report_year = b.data_year) DESC, b.report_year DESC
                LIMIT 1
            )
        )
        """
    )
    return conn.execute("SELECT COUNT(*) FROM annual_groundwater").fetchone()[0]


def _bulletin_report_note(year: int) -> str:
    if year == 2023:
        return "2023 年卷为扫描版 PDF，未做 OCR，暂未入库"
    if year == 1998:
        return "1998 年卷在线版本仅给出叙述性比例，未给出可解析的绝对数值"
    if year in (1999, 2000):
        return "该年份公报未在水利部网站公开"
    return ""


def insert_bulletin(conn: sqlite3.Connection) -> int:
    """把《中国水资源公报》历史地下水数据写入数据库。"""
    path = DATA / "bulletin" / "parsed" / "bulletin_dataset.json"
    if not path.exists():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    index_path = DATA / "bulletin" / "bulletin_index.json"
    index = {}
    if index_path.exists():
        for rec in json.loads(index_path.read_text(encoding="utf-8")):
            index[int(rec["year"])] = rec
    # coverage per year
    cov: dict[int, set] = {}
    for rec in data.get("national", []):
        if any(v is not None for k, v in rec.items() if k not in ("year", "source")):
            cov.setdefault(rec["year"], set()).add("national")
    for rec in data.get("regions", []):
        cov.setdefault(rec["year"], set()).add("regions")
    for rec in data.get("provinces", []):
        cov.setdefault(rec["year"], set()).add("provinces")
    for rec in data.get("plains", []):
        cov.setdefault(rec["year"], set()).add("plains")
    for year, rec in sorted(index.items()):
        kinds = ",".join(sorted(cov.get(year, []))) or "unavailable"
        files = rec.get("local_files") or []
        source_kind = "pdf" if any(f["path"].endswith(".pdf") for f in files) else (
            "docx" if any(f["path"].endswith((".doc", ".docx")) for f in files) else "html")
        conn.execute(
            "INSERT OR REPLACE INTO bulletin_reports VALUES (?,?,?,?,?,?,?)",
            (year, rec.get("title"), rec.get("detail_url"), source_kind,
             len(files) or None, kinds, rec.get("note") or _bulletin_report_note(year)),
        )
    for rec in data.get("national", []):
        conn.execute(
            "INSERT OR REPLACE INTO bulletin_national VALUES (?,?,?,?,?,?,?,?)",
            (rec["year"], rec.get("ground_resource"), rec.get("ground_supply"),
             rec.get("ground_share"), rec.get("total_supply"),
             rec.get("plain_resource"), rec.get("plain_storage_change"), rec.get("note")),
        )
    for rec in data.get("regions", []):
        name = rec["name"]
        if name == "全国":
            group = "全国"
        elif name in ("北方6区", "南方4区"):
            group = name[:2]
        elif "太湖" in name:
            group = "太湖"
        elif rec["year"] == 1997:
            group = "流域片"
        else:
            group = "一级区"
        scheme = "流域片(1997)" if rec["year"] == 1997 else "水资源一级区"
        conn.execute(
            "INSERT INTO bulletin_regions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec["year"], name, group, scheme,
             rec.get("ground"), rec.get("surface"), rec.get("unrepeat"), rec.get("total"),
             rec.get("ground") if rec.get("table") == "supply" else None,
             rec.get("surface") if rec.get("table") == "supply" else None,
             rec.get("total_supply") if rec.get("table") == "supply" else None,
             rec.get("ground_share"), rec.get("table"), rec.get("source"), rec.get("page")),
        )
    # region table has both kinds; ground resource and supply live in separate rows,
    # merge them into one row per (year, region)
    conn.execute(
        """
        UPDATE bulletin_regions SET
          ground_supply_1e8m3 = (SELECT b.ground_supply_1e8m3 FROM bulletin_regions b
             WHERE b.year=bulletin_regions.year AND b.region=bulletin_regions.region
               AND b.table_kind='supply'),
          surface_supply_1e8m3 = (SELECT b.surface_supply_1e8m3 FROM bulletin_regions b
             WHERE b.year=bulletin_regions.year AND b.region=bulletin_regions.region
               AND b.table_kind='supply'),
          total_supply_1e8m3 = (SELECT b.total_supply_1e8m3 FROM bulletin_regions b
             WHERE b.year=bulletin_regions.year AND b.region=bulletin_regions.region
               AND b.table_kind='supply')
        WHERE table_kind='resources'
        """
    )
    conn.execute(
        "DELETE FROM bulletin_regions WHERE table_kind='supply' AND EXISTS ("
        "SELECT 1 FROM bulletin_regions r WHERE r.year=bulletin_regions.year "
        "AND r.region=bulletin_regions.region AND r.table_kind='resources')"
    )
    conn.execute(
        "UPDATE bulletin_regions SET ground_share_pct = ROUND(ground_supply_1e8m3 * 100.0 / "
        "total_supply_1e8m3, 1) WHERE total_supply_1e8m3 > 0 AND ground_supply_1e8m3 IS NOT NULL"
    )
    for rec in data.get("provinces", []):
        conn.execute(
            "INSERT INTO bulletin_provinces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec["year"], rec["name"],
             rec.get("ground") if rec.get("table") == "resources" else None,
             rec.get("surface") if rec.get("table") == "resources" else None,
             rec.get("unrepeat"), rec.get("total"),
             rec.get("ground") if rec.get("table") == "supply" else None,
             rec.get("surface") if rec.get("table") == "supply" else None,
             rec.get("total_supply"), rec.get("ground_share"),
             rec.get("table"), rec.get("source"), rec.get("page")),
        )
    conn.execute(
        """
        UPDATE bulletin_provinces SET
          ground_supply_1e8m3 = (SELECT b.ground_supply_1e8m3 FROM bulletin_provinces b
             WHERE b.year=bulletin_provinces.year AND b.province=bulletin_provinces.province
               AND b.table_kind='supply'),
          surface_supply_1e8m3 = (SELECT b.surface_supply_1e8m3 FROM bulletin_provinces b
             WHERE b.year=bulletin_provinces.year AND b.province=bulletin_provinces.province
               AND b.table_kind='supply'),
          total_supply_1e8m3 = (SELECT b.total_supply_1e8m3 FROM bulletin_provinces b
             WHERE b.year=bulletin_provinces.year AND b.province=bulletin_provinces.province
               AND b.table_kind='supply')
        WHERE table_kind='resources'
        """
    )
    conn.execute(
        "DELETE FROM bulletin_provinces WHERE table_kind='supply' AND EXISTS ("
        "SELECT 1 FROM bulletin_provinces r WHERE r.year=bulletin_provinces.year "
        "AND r.province=bulletin_provinces.province AND r.table_kind='resources')"
    )
    conn.execute(
        "UPDATE bulletin_provinces SET ground_share_pct = ROUND(ground_supply_1e8m3 * 100.0 / "
        "total_supply_1e8m3, 1) WHERE total_supply_1e8m3 > 0 AND ground_supply_1e8m3 IS NOT NULL"
    )
    for rec in data.get("plains", []):
        conn.execute(
            "INSERT INTO bulletin_plains VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (rec["year"], rec["plain"], rec.get("region"), rec.get("area"),
             rec.get("shallow_end"), rec.get("shallow_prev"), rec.get("shallow_start"),
             rec.get("shallow_change"), rec.get("deep_end"), rec.get("deep_prev"),
             rec.get("deep_change"), rec.get("source"), rec.get("page")),
        )
    return conn.execute("SELECT COUNT(*) FROM bulletin_national").fetchone()[0]


def insert_surface(conn: sqlite3.Connection) -> int:
    """把等值面数字化结果（data/surface/parsed/*.json）写入数据库。"""
    src = DATA / "surface" / "parsed"
    if not src.exists():
        return 0
    import base64

    import numpy as np

    from groundwater_mcp.ingest import surface as surf

    count = 0
    for path in sorted(src.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        period = doc.get("period") or path.stem
        for m in doc.get("maps", []):
            if "error" in m or not m.get("grid"):
                continue
            # 粗栅格（cls+1，0=图外）
            raw = zlib.decompress(base64.b64decode(m["grid"]))
            grid = np.frombuffer(raw, dtype=np.uint8).reshape(m["grid_h"], m["grid_w"])
            cls = grid.astype(np.int16) - 1
            # 构建连续场并量化为 uint16（0.01 m），65535 表示图外
            field, _ = surf.build_field(cls)
            q = np.where(np.isfinite(field), np.round(field * 100.0), 65535).astype("<u2")
            field_blob = zlib.compress(q.tobytes(), 9)
            # 定标模型按“全分辨率像元”给出，入库前换算到粗栅格坐标
            coef = m.get("model_coef")
            iw, ih = (m.get("image_size") or [None, None])[:2]
            gw, gh = m.get("grid_w"), m.get("grid_h")
            if coef and iw and ih and gw and gh:
                rx, ry = gw / iw, gh / ih
                coef = [[coef[0][0] * rx, coef[0][1] * rx, coef[0][2] * rx],
                        [coef[1][0] * ry, coef[1][1] * ry, coef[1][2] * ry]]
            conn.execute(
                "INSERT OR REPLACE INTO surface_maps VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    period, m.get("figure"), m.get("page"), m.get("caption"),
                    json.dumps(m.get("regions") or [], ensure_ascii=False),
                    m.get("image_size", [None, None])[0], m.get("image_size", [None, None])[1],
                    m.get("grid_w"), m.get("grid_h"), zlib_b64(m.get("grid")), field_blob,
                    json.dumps(m.get("legend"), ensure_ascii=False),
                    json.dumps(coef), m.get("model_type"),
                    json.dumps(m.get("bbox")), m.get("k_km_per_px"),
                    m.get("method"), m.get("quality"), m.get("n_anchors"),
                    m.get("anchor_rmse_km"),
                    json.dumps(m.get("anchor_names") or [], ensure_ascii=False),
                    m.get("mean_depth_m"), m.get("min_depth_m"), m.get("max_depth_m"),
                    m.get("class_consistency"),
                    json.dumps(m.get("class_share") or {}, ensure_ascii=False),
                    m.get("area_km2"), m.get("expected_area_km2"), m.get("area_ratio"),
                    m.get("expected_mean_m"), m.get("mean_error_m"),
                    m.get("source", "pdf"),
                ),
            )
            count += 1
    return count


def zlib_b64(value: str | None) -> bytes | None:
    """JSON 中存的是 base64(zlib(grid))，入库后仍保持 zlib 压缩（BLOB）。"""
    import base64

    if not value:
        return None
    return base64.b64decode(value)


def main() -> None:
    records = load_index()
    if not records:
        raise SystemExit("没有可用的报告索引，请先运行 scripts/crawl_index.py / download_pdfs.py")
    datasets = parse_all(records)
    DB_OUT.parent.mkdir(parents=True, exist_ok=True)
    if DB_OUT.exists():
        DB_OUT.unlink()
    conn = sqlite3.connect(DB_OUT)
    try:
        conn.executescript(SCHEMA)
        for data in datasets:
            insert(conn, data)
        annual_rows = insert_annual(conn)
        bulletin_rows = insert_bulletin(conn)
        surface_rows = insert_surface(conn)
        conn.commit()
    finally:
        conn.close()
    (DATA / "dataset.json").write_text(
        json.dumps(datasets, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nDB: {DB_OUT} ({DB_OUT.stat().st_size / 1024:.0f} KB), reports={len(datasets)}, "
          f"annual_rows={annual_rows}, bulletin_national_years={bulletin_rows}, "
          f"surface_maps={surface_rows}")


if __name__ == "__main__":
    main()
