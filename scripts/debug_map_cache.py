# -*- coding: utf-8 -*-
"""Debug map cache for HTML period."""
import json
import sqlite3

from groundwater_mcp import repository as repo
from groundwater_mcp import surface_query as sq

conn = repo.connect()
row = conn.execute("SELECT period, figure, field IS NOT NULL AS has_field, grid_w, grid_h "
                   "FROM surface_maps WHERE period='2024-05' AND figure=4").fetchone()
print("row:", dict(row) if row else None)
try:
    cached = sq._map_cached("2024-05", 4)
    print("cached:", None if cached is None else (cached[1], cached[2], len(cached[0])))
except Exception as exc:  # noqa: BLE001
    print("cache error:", repr(exc))
print("point_query:", json.dumps(sq.point_query(45.75, 126.63, period="2024-05"),
                                 ensure_ascii=False)[:300])
