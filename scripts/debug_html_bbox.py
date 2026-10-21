# -*- coding: utf-8 -*-
"""Debug HTML period bbox/point query."""
import json
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
for r in c.execute("SELECT period, figure, regions, bbox, k_km_per_px, quality "
                   "FROM surface_maps WHERE period='2024-05' AND figure IN (1,4,7)"):
    print(dict(r))
print("expected bbox contains 哈尔滨?", )
row = c.execute("SELECT bbox FROM surface_maps WHERE period='2024-05' AND figure=4").fetchone()
b = json.loads(row["bbox"])
print("bbox", b, "contains", b[0] <= 126.63 <= b[2] and b[1] <= 45.75 <= b[3])
