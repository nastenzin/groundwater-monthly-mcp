# -*- coding: utf-8 -*-
"""Inspect 2024-05 surface rows."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
for r in c.execute("SELECT period, figure, source, regions FROM surface_maps "
                   "WHERE period='2024-05' ORDER BY figure"):
    print(dict(r))
