# -*- coding: utf-8 -*-
"""Compare two dataset.json snapshots on numeric fields."""
import json
import sys
from pathlib import Path


def load(path):
    return {d["period"]: d for d in json.loads(Path(path).read_text(encoding="utf-8"))}


def main(old_path, new_path):
    old, new = load(old_path), load(new_path)
    diffs = []
    assert set(old) == set(new), (set(old) ^ set(new))
    for period in old:
        a, b = old[period], new[period]
        # 叙述埋深
        ra = {r["region"]: r for r in a["shallow_narrative"]}
        rb = {r["region"]: r for r in b["shallow_narrative"]}
        for key in sorted(set(ra) | set(rb)):
            x, y = ra.get(key, {}), rb.get(key, {})
            for field in ("mean_depth_m", "change_prev_month_m", "change_last_year_m"):
                if x.get(field) != y.get(field):
                    diffs.append(f"{period} {key} {field}: {x.get(field)} -> {y.get(field)}")
        # 降水
        pa = {(p["table_no"], p["unit"]): (p["precip_mm"], p["anomaly_pct"]) for p in a["precipitation"]}
        pb = {(p["table_no"], p["unit"]): (p["precip_mm"], p["anomaly_pct"]) for p in b["precipitation"]}
        for key in sorted(set(pa) | set(pb)):
            if pa.get(key) != pb.get(key):
                diffs.append(f"{period} precip {key}: {pa.get(key)} -> {pb.get(key)}")
        # 山西盆地
        ba = {x["basin"]: x for x in a["shanxi_basins"]}
        bb = {x["basin"]: x for x in b["shanxi_basins"]}
        for key in sorted(set(ba) | set(bb)):
            for field in ("mean_depth_m", "max_depth_m", "min_depth_m", "change_prev_month_m", "change_last_year_m"):
                if ba.get(key, {}).get(field) != bb.get(key, {}).get(field):
                    diffs.append(f"{period} basin {key} {field}: {ba.get(key, {}).get(field)} -> {bb.get(key, {}).get(field)}")
        # 分布
        da = {(d["table_no"], m, l): v for d in a["shallow_distribution"] for m, p in d["methods"].items() for l, v in zip(d["bins"], p["values_pct"])}
        db = {(d["table_no"], m, l): v for d in b["shallow_distribution"] for m, p in d["methods"].items() for l, v in zip(d["bins"], p["values_pct"])}
        if da != db:
            diffs.append(f"{period} distribution differs ({len(da)} vs {len(db)})")
        # 深层
        if a["deep_provinces"] != b["deep_provinces"]:
            diffs.append(f"{period} deep differs")
        # 重点站
        for key in ("water_stations", "temperature_stations", "springs"):
            if a[key] != b[key]:
                diffs.append(f"{period} {key} differs")
        # 综述统计
        sa = {k: v for k, v in a["summary"].items() if k != "text"}
        sb = {k: v for k, v in b["summary"].items() if k != "text"}
        if sa != sb:
            diffs.append(f"{period} summary differs: {sa} -> {sb}")
    print("numeric diffs:", len(diffs))
    for d in diffs[:50]:
        print(" -", d)
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
