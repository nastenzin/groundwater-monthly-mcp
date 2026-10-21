# -*- coding: utf-8 -*-
"""List shallow region names for some periods."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
for period in ("2024-01", "2024-05", "2024-09"):
    rows = list(c.execute(
        "SELECT region, mean_depth_m, area_km2 FROM shallow_regions WHERE period=? "
        "ORDER BY region", (period,)))
    print(period, len(rows), [r["region"] for r in rows])
