# -*- coding: utf-8 -*-
"""Review the assembled bulletin dataset: coverage + anomalies."""
import json
from collections import defaultdict
from pathlib import Path

d = json.loads(Path("data/bulletin/parsed/bulletin_dataset.json").read_text(encoding="utf-8"))
lines = []
by = defaultdict(lambda: defaultdict(list))
for r in d["regions"]:
    by[r["year"]][r.get("table", "res")].append(r)
lines.append("REGIONS by year")
for y in sorted(by):
    parts = []
    for t, rows in by[y].items():
        names = [r["name"] for r in rows]
        parts.append(f"{t}={len(rows)}")
    lines.append(f"  {y}: " + " ".join(parts))
lines.append("")
lines.append("PROVINCES by year")
byp = defaultdict(lambda: defaultdict(list))
for r in d["provinces"]:
    byp[r["year"]][r.get("table", "res")].append(r)
for y in sorted(byp):
    parts = [f"{t}={len(rows)}" for t, rows in byp[y].items()]
    lines.append(f"  {y}: " + " ".join(parts))
lines.append("")
lines.append("PLAINS by year")
bypl = defaultdict(list)
for r in d["plains"]:
    bypl[r["year"]].append(r["plain"])
for y in sorted(bypl):
    lines.append(f"  {y}: {len(bypl[y])} plains")
lines.append("")
lines.append("national 全国 ground resource / supply series (regions table)")
for y in sorted(by):
    nat = [r for r in by[y].get("resources", []) if r["name"] == "全国"]
    nat2 = [r for r in by[y].get("supply", []) if r["name"] == "全国"]
    g = nat[0]["ground"] if nat else None
    gs = nat2[0]["ground"] if nat2 else None
    lines.append(f"  {y}: ground={g} supply_ground={gs}")
Path("data/bulletin/probe/review.txt").write_text("\n".join(lines), encoding="utf-8")
print("ok")
