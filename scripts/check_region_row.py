# -*- coding: utf-8 -*-
"""Check narrative rows for a region across periods."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
for p in ("2024-10", "2024-11", "2025-01", "2025-12"):
    r = c.execute(
        "SELECT region, mean_depth_m, area_km2, area_share_pct, raw_sentence "
        "FROM shallow_regions WHERE period=? AND region LIKE ?", (p, "%河西%")).fetchone()
    print(p, dict(r) if r else None)
