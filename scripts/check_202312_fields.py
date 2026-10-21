# -*- coding: utf-8 -*-
"""Inspect 2023-12 shallow region fields."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
for r in c.execute("SELECT region, mean_depth_m, area_km2, area_share_pct "
                   "FROM shallow_regions WHERE period='2023-12' LIMIT 6"):
    print(dict(r))
