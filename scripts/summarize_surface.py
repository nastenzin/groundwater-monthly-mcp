# -*- coding: utf-8 -*-
"""汇总等值面数字化结果的质量。"""
import json
from pathlib import Path

files = sorted(Path("data/surface/parsed").glob("*.json"))
tot = 0
errs = []
ratios = []
qual = {"high": 0, "medium": 0, "low": 0}
cons = []
periods = []
for f in files:
    d = json.loads(f.read_text(encoding="utf-8"))
    maps = [m for m in d["maps"] if "error" not in m]
    if not maps:
        continue
    periods.append((d["period"], len(maps)))
    for m in maps:
        tot += 1
        qual[m.get("quality", "low")] = qual.get(m.get("quality", "low"), 0) + 1
        if m.get("mean_error_m") is not None:
            errs.append(abs(m["mean_error_m"]))
        if m.get("area_ratio"):
            ratios.append(m["area_ratio"])
        cons.append(m.get("class_consistency", 0))
print("periods:", len(periods), "maps:", tot)
print("per period:", periods)
print("quality:", qual)
if errs:
    errs_sorted = sorted(errs)
    print(f"mean|error|: n={len(errs)} median={errs_sorted[len(errs)//2]:.2f} "
          f"p90={errs_sorted[int(len(errs)*0.9)]:.2f} max={max(errs):.2f} m")
if ratios:
    rs = sorted(ratios)
    print(f"area_ratio: median={rs[len(rs)//2]:.2f} min={min(rs):.2f} max={max(rs):.2f}")
print(f"class_consistency: min={min(cons):.1f} mean={sum(cons)/len(cons):.1f}")
