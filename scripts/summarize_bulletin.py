# -*- coding: utf-8 -*-
"""Summarise parsed bulletin PDF tables for review."""
import json
from pathlib import Path

d = json.loads(Path("data/bulletin/parsed/pdf_tables.json").read_text(encoding="utf-8"))
lines = []
for year in sorted(d, key=int):
    lines.append(f"===== {year}")
    for t in d[year]:
        lines.append(f"-- {t['kind']} p{t['page']} rows={len(t['rows'])} ncols={t['ncols']} problems={len(t['problems'])}")
        for r in t["rows"]:
            if t["kind"] == "supply":
                lines.append(f"   {r['name']:<12} ground={r.get('ground')} total={r.get('total_supply')} dom={r.get('domestic')} ind={r.get('industry')} agri={r.get('agri')} eco={r.get('eco')}")
            elif t["kind"] == "resources":
                lines.append(f"   {r['name']:<12} surface={r.get('surface')} ground={r.get('ground')} unrepeat={r.get('unrepeat')} total={r.get('total')}")
            else:
                lines.append(f"   {r['name']:<16} region={r.get('region')} area={r.get('area')} s_end={r.get('shallow_end')} s_prev={r.get('shallow_prev')} s_ch={r.get('shallow_change')} d_end={r.get('deep_end')}")
Path("data/bulletin/probe/summary.txt").write_text("\n".join(lines), encoding="utf-8")
print("lines", len(lines))
