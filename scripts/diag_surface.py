# -*- coding: utf-8 -*-
"""列出等值面数字化结果中的异常图件。"""
import json
from pathlib import Path

for f in sorted(Path("data/surface/parsed").glob("*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    for m in d["maps"]:
        if "error" in m:
            print("ERR", d["period"], m)
            continue
        flags = []
        if (m.get("mean_error_m") is not None and abs(m["mean_error_m"]) > 2.0):
            flags.append(f"mean_err={m['mean_error_m']}")
        if (m.get("class_consistency") or 0) < 90:
            flags.append(f"cons={m.get('class_consistency')}")
        if not m.get("expected_mean_m"):
            flags.append("no_expected")
        if (m.get("area_ratio") or 1) < 0.8:
            flags.append(f"ratio={m.get('area_ratio')}")
        if flags:
            print(d["period"], m.get("figure"), m.get("regions"),
                  "mean", m.get("mean_depth_m"), "exp", m.get("expected_mean_m"), flags)
