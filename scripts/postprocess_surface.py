# -*- coding: utf-8 -*-
"""补全等值面记录的期望均值（无面积时用简单平均）与校验标记。"""
import json
import sqlite3
from pathlib import Path

DB = Path("src/groundwater_mcp/data/groundwater.db")
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
cache = {}


def means(period):
    if period in cache:
        return cache[period]
    rows = conn.execute(
        "SELECT region, mean_depth_m FROM shallow_regions WHERE period=?", (period,)).fetchall()
    cache[period] = {r["region"]: r["mean_depth_m"] for r in rows if r["mean_depth_m"] is not None}
    return cache[period]


n = 0
suspects = 0
rejected = 0
for path in sorted(Path("data/surface/parsed").glob("*.json")):
    doc = json.loads(path.read_text(encoding="utf-8"))
    period = doc["period"]
    table = means(period)
    for m in doc.get("maps", []):
        if "error" in m:
            continue
        regions = m.get("regions") or []
        vals = [table.get(r) for r in regions]
        vals = [v for v in vals if v is not None]
        if vals:
            exp = sum(vals) / len(vals)
            m["expected_mean_m"] = round(exp, 2)
            if m.get("mean_depth_m") is not None:
                err = round(m["mean_depth_m"] - exp, 2)
                m["mean_error_m"] = err
                # 图斑裁切明显失败：均值方向性偏离超过 10m 且量级差异 >1.8 倍/0.4 倍
                if abs(err) > 10 and (m["mean_depth_m"] > 1.8 * exp
                                      or m["mean_depth_m"] < 0.4 * exp):
                    m["error"] = "图斑提取异常（分页/裁切失败，已剔除）"
                    m["rejected_reason"] = m.pop("mean_error_m", None)
                    rejected += 1
                    n += 1
                    continue
                if abs(err) > 5:
                    m["validation"] = "suspect"
                    suspects += 1
                else:
                    m.pop("validation", None)
        n += 1
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
conn.close()
print("maps", n, "suspect", suspects, "rejected", rejected)
