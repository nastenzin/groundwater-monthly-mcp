# -*- coding: utf-8 -*-
"""Dump sqlite schema + row counts of the bundled dataset."""
import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1] if len(sys.argv) > 1 else "src/groundwater_mcp/data/groundwater.db")
c = sqlite3.connect(db)
lines = []
for name, sql in c.execute("select name, sql from sqlite_master where type in ('table','index') order by name"):
    lines.append(f"### {name}\n{sql}")
    if sql and sql.upper().startswith("CREATE TABLE"):
        try:
            n = c.execute(f"select count(*) from '{name}'").fetchone()[0]
            lines.append(f"rows: {n}")
        except Exception as exc:  # noqa: BLE001
            lines.append(f"rows: err {exc}")
Path("data/db_schema.txt").write_text("\n\n".join(lines), encoding="utf-8")
print("ok", len(lines))
