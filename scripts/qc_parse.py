# -*- coding: utf-8 -*-
"""Quality checks across all parsed reports."""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from groundwater_mcp.ingest.pdf_parse import parse_pdf  # noqa: E402

index = {r["period"]: r for r in json.loads(Path("data/report_index.json").read_text(encoding="utf-8"))}
problems = []
for period in sorted(index, reverse=True):
    meta = index[period]
    data = parse_pdf(Path(meta["pdf_file"]), period, meta)
    s = data["summary"]
    for key in ("station_total", "shallow_stations", "deep_stations", "deep_up_pct", "deep_down_pct"):
        if s.get(key) is None:
            problems.append(f"{period}: summary.{key} missing")
    if len(data["precipitation"]) != 34:
        problems.append(f"{period}: precipitation={len(data['precipitation'])}")
    if len(data["shallow_narrative"]) != 24:
        problems.append(f"{period}: shallow_narrative={len(data['shallow_narrative'])}")
    for r in data["shallow_narrative"]:
        if r["mean_depth_m"] is None:
            problems.append(f"{period}: {r['region']} depth None")
        if r["change_prev_month_text"] == "" and r["change_last_year_text"] == "":
            problems.append(f"{period}: {r['region']} 无变化描述")
    for d in data["shallow_distribution"]:
        for method, payload in d["methods"].items():
            vals = payload["values_pct"]
            total = sum(v for v in vals if v is not None)
            if abs(total - 100.0) > 1.5:
                problems.append(f"{period}: 表{d['table_no']} {method} sum={total}")
    if len(data["shanxi_basins"]) != 6:
        problems.append(f"{period}: shanxi={len(data['shanxi_basins'])}")
    dp = data["deep_provinces"]
    total_row = [p for p in dp if p["province"] == "总计"]
    if len(dp) != 20 or not total_row:
        problems.append(f"{period}: deep rows={len(dp)}")
    else:
        calc = sum(p["total_stations"] for p in dp if p["province"] != "总计")
        if calc != total_row[0]["total_stations"]:
            problems.append(f"{period}: deep total {calc} != {total_row[0]['total_stations']}")
        for p in dp:
            for k in ("up_gt2_pct", "up_0_5_2_pct", "stable_pct", "down_0_5_2_pct", "down_gt2_pct"):
                if p[k] is None:
                    problems.append(f"{period}: {p['province']} {k} None")
    if len(data["water_stations"]) < 36:
        problems.append(f"{period}: water_stations={len(data['water_stations'])}")
    tc = Counter(r["province"] for r in data["temperature_stations"])
    if len(data["temperature_stations"]) < 63:
        problems.append(f"{period}: temperature_stations={len(data['temperature_stations'])}")
    if len(data["springs"]) != 9:
        problems.append(f"{period}: springs={len(data['springs'])}")
    # 温度缺测站
    missing = [(r["province"], r["station"]) for r in data["temperature_stations"] if r["water_temp_c"] is None]
    print(period, "temp", len(data["temperature_stations"]), "missing", missing, "warn", len(data["warnings"]))

print("\nPROBLEMS", len(problems))
for p in problems:
    print(" -", p)
