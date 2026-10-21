# -*- coding: utf-8 -*-
"""Inspect shallow_regions rows used as calibration expectations."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
rows = list(c.execute(
    "SELECT region, group_name, mean_depth_m, area_km2, area_share_pct "
    "FROM shallow_regions WHERE period='2025-12' ORDER BY region"))
print(len(rows))
for r in rows:
    print(dict(r))
