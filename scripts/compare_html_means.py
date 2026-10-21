# -*- coding: utf-8 -*-
"""Compare HTML-thumbnail digitized means with narrative means."""
import json
import sqlite3
from pathlib import Path

c = sqlite3.connect("src/groundwater_mcp/data/groundwater.db")
c.row_factory = sqlite3.Row
for period in ("2024-09", "2024-01"):
    path = Path(f"data/surface/parsed/{period}.json")
    if not path.exists():
        continue
    rows = {r["region"]: r["mean_depth_m"] for r in c.execute(
        "SELECT region, mean_depth_m FROM shallow_regions WHERE period=?", (period,))}
    d = json.loads(path.read_text(encoding="utf-8"))
    errs = []
    for m in d["maps"]:
        if "error" in m:
            continue
        vals = [rows[r] for r in m["regions"] if rows.get(r) is not None]
        if not vals:
            continue
        exp = sum(vals) / len(vals)
        err = m["mean_depth_m"] - exp
        errs.append(abs(err))
        print(f"{period} f{m['figure']:>2} {m['regions'][0][:10]:<12} mean={m['mean_depth_m']:>6} "
              f"exp={exp:>6.2f} err={err:>+7.2f}")
    if errs:
        errs.sort()
        print(f"{period}: n={len(errs)} median={errs[len(errs)//2]:.2f} max={errs[-1]:.2f}")
