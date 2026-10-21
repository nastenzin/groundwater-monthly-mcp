# -*- coding: utf-8 -*-
"""Cross-check 公报 plain depths against 水文年报 year-end depths (2020-2022)."""
import sqlite3
from pathlib import Path

db = Path("src/groundwater_mcp/data/groundwater.db")
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
rows = list(c.execute("""
  SELECT b.plain, b.year AS bulletin_year, b.shallow_end_m AS bulletin_end,
         a.data_year, a.shallow_depth_m AS annual_depth
  FROM bulletin_plains b
  JOIN annual_groundwater a ON a.region = b.plain AND a.row_type='plain_basin'
  WHERE a.data_year = b.year
"""))
print(f"matched rows: {len(rows)}")
diffs = [abs(r["bulletin_end"] - r["annual_depth"]) for r in rows]
if diffs:
    print("max |diff| =", round(max(diffs), 2), "mean =", round(sum(diffs) / len(diffs), 2))
    bad = [dict(r) for r in rows if abs(r["bulletin_end"] - r["annual_depth"]) > 0.5]
    print("rows with diff > 0.5 m:", len(bad))
    for r in bad[:10]:
        print(r)
# also compare 月报 2023-12 where available
m = list(c.execute("""
  SELECT b.plain, b.shallow_end_m AS bulletin_2022, s.mean_depth_m AS monthly_2022_12
  FROM bulletin_plains b LEFT JOIN shallow_regions s
    ON s.region=b.plain AND s.period='2022-12'
  WHERE b.year=2022 AND s.mean_depth_m IS NOT NULL
"""))
print("vs monthly 2022-12 matched:", len(m))
Path("data/bulletin/probe/crosscheck.txt").write_text(
    "\n".join([f"matched={len(rows)} maxdiff={max(diffs) if diffs else None}"] + [str(dict(r)) for r in rows]),
    encoding="utf-8")
