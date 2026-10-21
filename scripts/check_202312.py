# -*- coding: utf-8 -*-
"""Check 2023-12 report rows in DB."""
import sqlite3

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
print("2023 periods:", [r[0] for r in c.execute(
    "SELECT period FROM reports WHERE period LIKE '2023%'")])
print("shallow rows:", c.execute(
    "SELECT COUNT(*) FROM shallow_regions WHERE period='2023-12'").fetchone()[0])
print("tables:", c.execute(
    "SELECT COUNT(*) FROM report_tables WHERE period='2023-12'").fetchone()[0])
print("text pages:", c.execute(
    "SELECT COUNT(*) FROM report_text WHERE period='2023-12'").fetchone()[0])
