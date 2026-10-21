# -*- coding: utf-8 -*-
"""Verify annual groundwater rows and vintages."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
print("annual rows", c.execute("SELECT COUNT(*) FROM annual_groundwater").fetchone()[0])
print("by data_year", [dict(r) for r in c.execute(
    "SELECT data_year, COUNT(*) n FROM annual_groundwater GROUP BY data_year"
)])
for region in ("三江平原", "松嫩平原", "辽河平原"):
    print(region)
    for r in c.execute(
        "SELECT report_year, data_year, region, shallow_depth_m, shallow_water_level_change_m, deep_depth_m FROM annual_groundwater WHERE region=? AND row_type='plain_basin' ORDER BY data_year",
        (region,),
    ):
        print("  ", dict(r))
print("reports", [dict(r) for r in c.execute(
    "SELECT year, data_years, source_kind FROM annual_reports ORDER BY year"
)])
