# -*- coding: utf-8 -*-
"""Check 河西 maps across periods."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
for r in c.execute(
        "SELECT period, figure, mean_depth_m, expected_mean_m, mean_error_m, source "
        "FROM surface_maps WHERE regions LIKE ? ORDER BY period", ("%河西走廊%",)):
    print(dict(r))
