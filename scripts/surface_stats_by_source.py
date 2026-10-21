# -*- coding: utf-8 -*-
"""Surface rows by source and error stats."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
print("by source:", [dict(r) for r in c.execute(
    "SELECT source, COUNT(*) n FROM surface_maps GROUP BY source")])
print("periods:", c.execute("SELECT COUNT(DISTINCT period) FROM surface_maps").fetchone()[0])
print("rows:", c.execute("SELECT COUNT(*) FROM surface_maps").fetchone()[0])
for src in ("pdf", "html-thumbnail"):
    rows = [abs(r[0]) for r in c.execute(
        "SELECT mean_error_m FROM surface_maps WHERE source=? AND mean_error_m IS NOT NULL",
        (src,))]
    rows.sort()
    if rows:
        print(src, "n=", len(rows), "median=", round(rows[len(rows) // 2], 2),
              "p90=", round(rows[int(len(rows) * 0.9)], 2), "max=", round(rows[-1], 2))
print("suspects>5:", c.execute(
    "SELECT COUNT(*) FROM surface_maps WHERE ABS(mean_error_m)>5").fetchone()[0])
