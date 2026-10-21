# -*- coding: utf-8 -*-
"""Inspect decoded field/grid near a pixel (array based)."""
from groundwater_mcp import repository as repo
from groundwater_mcp import surface_query as sq

conn = repo.connect()
row = conn.execute("SELECT * FROM surface_maps WHERE period='2024-05' AND figure=4").fetchone()
w, h = int(row["grid_w"]), int(row["grid_h"])
grid = sq.decode_grid(row)
field = sq.decode_field(row)
print("size", w, h, "unique(classes)", sorted(set(grid)))
for y in range(28, 36):
    print("row", y, "grid", [grid[y * w + x] for x in range(25, 40)],
          "field", [field[y * w + x] for x in range(25, 40)])
print("sample:", sq._sample(field, w, h, 29.7, 33.1))
