# -*- coding: utf-8 -*-
"""Fix README traceability paragraph (raw archives are not shipped in this repo)."""
from pathlib import Path

p = Path("README.md")
t = p.read_text(encoding="utf-8")
old = ("- 每期数据均可回溯：原生 PDF 期次随仓库分发（`data/pdfs/`、`data/legacy/pdfs/`），"
       "HTML5 文本层期次逐页\n  存档（`data/legacy/html/<YYYY-MM>/pageN.html`），"
       "数据库中每个数值都能对应到期号、页码/表号与")
new = ("- 每期数据均可回溯：原始 PDF/HTML 归档因体积较大不随 Git 仓库分发"
       "（可用 `scripts/download_pdfs.py`、\n  `scripts/legacy_crawl.py` 等重新下载），"
       "数据库中每个数值都能对应到期号、页码/表号与")
if old in t:
    t = t.replace(old, new)
    p.write_text(t, encoding="utf-8")
    print("fixed")
else:
    print("NOT FOUND")
    i = t.find("每期数据均可回溯")
    print(repr(t[i - 5:i + 200]))
