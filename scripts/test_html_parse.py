# -*- coding: utf-8 -*-
"""Test the HTML text-layer parser on saved pages."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from groundwater_mcp.ingest.html_parse import parse_html_report  # noqa: E402

index = json.loads(Path("data/legacy_index.json").read_text(encoding="utf-8"))
for rec in index:
    if not rec.get("local_path", "").startswith("data/legacy/html"):
        continue
    period = rec["period"]
    data = parse_html_report(Path(rec["local_path"]), period, rec)
    counts = {k: len(data[k]) for k in (
        "precipitation", "shallow_narrative", "shallow_distribution", "shanxi_basins",
        "deep_provinces", "water_stations", "temperature_stations", "springs")}
    print(period, counts, "tables", len(data["tables"]), "warnings", data["warnings"])
