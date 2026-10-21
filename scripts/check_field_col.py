# -*- coding: utf-8 -*-
"""Check null field/grid in surface_maps."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
print("null field:", c.execute("SELECT COUNT(*) FROM surface_maps WHERE field IS NULL").fetchone()[0])
print("null grid:", c.execute("SELECT COUNT(*) FROM surface_maps WHERE grid IS NULL").fetchone()[0])
print("html field lengths:", c.execute(
    "SELECT length(field) FROM surface_maps WHERE source='html-thumbnail' LIMIT 3").fetchall())
print("pdf field lengths:", c.execute(
    "SELECT length(field) FROM surface_maps WHERE source='pdf' LIMIT 3").fetchall())
