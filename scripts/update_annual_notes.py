# -*- coding: utf-8 -*-
"""Update annual index notes after OCR backfill."""
import json
from pathlib import Path

p = Path("data/annual/annual_index.json")
records = json.loads(p.read_text(encoding="utf-8"))
notes = {
    2021: "2021 卷为扫描版 PDF：表 5-3（2020/2021 年末）经 RapidOCR + 区域锚点重建，逐行埋深差校验通过；PDF 未随仓库保留，可用 pdf_url 重新下载。",
    2022: "2022 卷含文本层：表 5-2/5-3 已解析（2021/2022 年末，29 平原 + 11 重点区域）；PDF 未随仓库保留，可用 pdf_url 重新下载。",
    2023: "2023 卷为扫描版 PDF，未做 OCR，暂未入库。",
    2024: "2024 卷 PDF 存在字体编码问题，未入库（可后续 OCR/修复字体）。",
    2025: "2025 卷 PDF 存在字体编码问题，未入库（可后续 OCR/修复字体）。",
}
for rec in records:
    rec["local_path"] = None
    rec["note"] = notes.get(rec["year"], rec.get("note", ""))
p.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
print("ok", len(records))
