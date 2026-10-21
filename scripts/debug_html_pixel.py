# -*- coding: utf-8 -*-
"""Debug pixel mapping for an HTML period query."""
import json
import sqlite3

from groundwater_mcp import surface_query as sq

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
row = c.execute("SELECT bbox, model, grid_w, grid_h FROM surface_maps "
                "WHERE period='2024-05' AND figure=4").fetchone()
coef = json.loads(row["model"])
print("coef", coef, "grid", row["grid_w"], row["grid_h"], "bbox", row["bbox"])
for lat, lon in ((45.75, 126.63), (43.85, 125.30), (46.0, 126.0)):
    px = coef[0][0] * lon + coef[0][1] * lat + coef[0][2]
    py = coef[1][0] * lon + coef[1][1] * lat + coef[1][2]
    print(lat, lon, "->", round(px, 1), round(py, 1))
print(sq.point_query(45.75, 126.63, period="2024-05"))
