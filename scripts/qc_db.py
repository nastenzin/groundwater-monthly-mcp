# -*- coding: utf-8 -*-
"""DB-level quality checks for all periods."""
import sqlite3

conn = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
conn.row_factory = sqlite3.Row
periods = [r["period"] for r in conn.execute("SELECT period FROM reports ORDER BY period DESC")]
print("periods", len(periods), periods)

bad = []
seen = conn.execute("SELECT DISTINCT period, table_no, method FROM shallow_distribution").fetchall()
for row in seen:
    vals = [
        r["share_pct"]
        for r in conn.execute(
            "SELECT share_pct FROM shallow_distribution WHERE period=? AND table_no=? AND method=?",
            (row["period"], row["table_no"], row["method"]),
        )
    ]
    s = sum(v for v in vals if v is not None)
    if abs(s - 100.0) > 1.5:
        bad.append((row["period"], row["table_no"], row["method"], round(s, 1)))
print("distribution sum anomalies:", bad)

missing = [
    (r["period"], r["region"])
    for r in conn.execute(
        "SELECT period, region FROM shallow_regions WHERE change_prev_month_m IS NULL OR change_last_year_m IS NULL"
    )
]
print("null change rows:", len(missing), missing[:10])

for p in periods:
    total = conn.execute(
        "SELECT total_stations FROM deep_provinces WHERE period=? AND province='总计'", (p,)
    ).fetchone()[0]
    calc = conn.execute(
        "SELECT SUM(total_stations) FROM deep_provinces WHERE period=? AND province<>'总计'", (p,)
    ).fetchone()[0]
    if total != calc:
        print("deep total mismatch", p, total, calc)
print("done")
