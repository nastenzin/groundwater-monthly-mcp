# -*- coding: utf-8 -*-
"""Debug surface query internals."""
import json
import sqlite3

from groundwater_mcp import repository as repo
from groundwater_mcp import surface_query as sq

conn = repo.connect()
row = conn.execute(
    "SELECT period, figure, bbox, model, grid_w, grid_h, quality, regions "
    "FROM surface_maps WHERE period='2025-12' AND figure=4").fetchone()
print("row:", dict(row) if row else None)
try:
    cached = sq._field_cached("2025-12", 4)
    print("cached:", None if cached is None else (cached[0].shape, cached[1].shape))
except Exception as exc:  # noqa: BLE001
    print("cache ERR", repr(exc))
print("maps total:", conn.execute("SELECT COUNT(*) FROM surface_maps").fetchone()[0])
