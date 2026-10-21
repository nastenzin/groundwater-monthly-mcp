# -*- coding: utf-8 -*-
"""Add the verified 2023-12 PDF (xxzx legacy attachment) to legacy_index.json."""
import json
from pathlib import Path

path = Path("data/legacy_index.json")
records = json.loads(path.read_text(encoding="utf-8"))
periods = {r["period"] for r in records}
if "2023-12" not in periods:
    records.append(
        {
            "period": "2023-12",
            "title": "《地下水动态月报》2023年12期",
            "detail_url": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202403/t20240302_1734366.html",
            "pdf_url": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202403/P020240302854010824506.pdf",
            "local_path": "data/legacy/pdfs/2023-12.pdf",
            "source": "水利部信息中心 xxzx.mwr.gov.cn（旧版残留 PDF 附件，202403 目录）",
            "pages": 33,
            "text_extractable": True,
            "note": "官方新版站点同名 PDF 已 404，此份为 xxzx 旧附件残留；pypdf 校验 33 页，含中文文本层。",
        }
    )
records.sort(key=lambda r: r["period"], reverse=True)
path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
print("legacy_index periods:", [(r["period"], bool(r.get("pdf_file") or r.get("local_path"))) for r in records])
