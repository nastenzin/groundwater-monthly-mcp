# -*- coding: utf-8 -*-
"""Prepare annual parsed JSONs: convert 2022 keys, add OCR-derived 2021 data."""
import json
from pathlib import Path

annual = Path("data/annual")
index = {r["year"]: r for r in json.loads((annual / "annual_index.json").read_text(encoding="utf-8"))}

# 1) 2022: rename row keys to generic first/second
p2022 = annual / "parsed" / "2022.json"
data2022 = json.loads(p2022.read_text(encoding="utf-8"))
for section in ("plains", "key_regions"):
    for row in data2022.get(section, []):
        for old, new in (
            ("shallow_2021", "shallow_first"),
            ("shallow_2022", "shallow_second"),
            ("deep_2021", "deep_first"),
            ("deep_2022", "deep_second"),
        ):
            if old in row:
                row[new] = row.pop(old)
data2022["source_kind"] = "pdf-text-layer"
data2022["table_name"] = "表5-2"
data2022["table_page"] = data2022.get("table52_page")
p2022.write_text(json.dumps(data2022, ensure_ascii=False, indent=2), encoding="utf-8")
print("2022 rows", len(data2022["plains"]), len(data2022["key_regions"]))

# 2) 2021: OCR-derived table 5-3 (2020/2021 year-end)
rows = json.loads((annual / "scan2021" / "table2021.json").read_text(encoding="utf-8"))
meta = index.get(2021, {})
data2021 = {
    "report_year": 2021,
    "title": meta.get("title") or "2021中国水文年报",
    "detail_url": meta.get("detail_url"),
    "pdf_url": meta.get("pdf_url"),
    "pages": 105,
    "data_years": [2020, 2021],
    "table52_page": 67,
    "table53_page": None,
    "table_name": "表5-3",
    "table_page": 67,
    "source_kind": "pdf-scan-ocr",
    "plains": rows,
    "key_regions": [],
    "warnings": [
        "2021 年报 PDF 为扫描件，表5-3 由 OCR 坐标重建（region-anchored），"
        "并用“埋深差=水位变幅”逐行校验，29/29 一致；2021 年列与 2022 年报重叠值仅作比对，入库以更新年报版本为准。",
    ],
}
(annual / "parsed" / "2021.json").write_text(
    json.dumps(data2021, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("2021 rows", len(rows))
