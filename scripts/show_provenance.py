# -*- coding: utf-8 -*-
"""展示数据血缘：每条数据的来源类型（表格单元格/正文句子/OCR/HTML 文本层）。"""
import json
import sqlite3
from pathlib import Path

db = Path("src/groundwater_mcp/data/groundwater.db")
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
out = []


def show(title, sql, params=()):
    out.append(f"\n## {title}")
    for r in c.execute(sql, params):
        d = dict(r)
        for k, v in list(d.items()):
            if isinstance(v, str) and len(v) > 160:
                d[k] = v[:160] + "…"
        out.append(json.dumps(d, ensure_ascii=False))


show("月报原始表（report_tables，rows_json 为单元格文本）",
     "SELECT period, table_no, caption, page, substr(rows_json,1,220) AS rows FROM report_tables "
     "WHERE period='2025-12' AND table_no=6")
show("月报浅层叙述（shallow_regions：raw_sentence 为原文句子）",
     "SELECT period, region, mean_depth_m, change_prev_month_m, raw_sentence FROM shallow_regions "
     "WHERE period='2025-12' AND region='三江平原'")
show("月报降水（precipitation：来自表 1-5 单元格）",
     "SELECT period, table_no, unit, precip_mm, anomaly_pct FROM precipitation "
     "WHERE period='2025-12' AND unit='松嫩平原'")
show("水文年报（annual_reports.source_kind / annual_groundwater.source_table）",
     "SELECT year, source_kind, data_years FROM annual_reports")
show("水文年报行来源", "SELECT report_year, data_year, region, shallow_depth_m, source_table, source_page "
                       "FROM annual_groundwater WHERE region='三江平原' AND row_type='plain_basin' ORDER BY data_year")
show("公报全国（source 标注 html/pdf 表格）", "SELECT year, ground_resource_1e8m3, ground_supply_1e8m3 FROM bulletin_national "
                                           "WHERE year IN (1997,2010,2022) ORDER BY year")
show("公报一级区来源", "SELECT year, region, ground_resource_1e8m3, source, page FROM bulletin_regions "
                        "WHERE year=2010 AND region='海河区'")
show("公报平原埋深来源", "SELECT year, plain, shallow_end_m, shallow_change_m, source, page FROM bulletin_plains "
                          "WHERE year=2022 AND plain='三江平原'")
c.close()
Path("data/provenance_report.md").write_text("\n".join(out), encoding="utf-8")
print("written data/provenance_report.md")
