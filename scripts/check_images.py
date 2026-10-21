# -*- coding: utf-8 -*-
"""检查月报 PDF 中图片/图件页分布，确认数据仅来自表格与文字。"""
import re
from pathlib import Path

import pymupdf

pdfs = sorted(Path("data/pdfs").glob("*.pdf"))
print("pdf files:", len(pdfs))
sample = [p for p in pdfs if p.stem in ("2025-12", "2024-07", "2023-12", "2024-11")] or pdfs[:3]
for p in sample:
    doc = pymupdf.open(p)
    img_pages, cap_figs = [], []
    for i, page in enumerate(doc):
        n = len(page.get_images(full=True))
        if n:
            img_pages.append((i + 1, n))
        for m in re.finditer(r"图\s*\d+[^\n]{0,40}", page.get_text("text")):
            cap_figs.append((i + 1, m.group(0).strip()[:50]))
    print(f"\n{p.stem}: pages={doc.page_count}, image_pages={img_pages[:12]}, n_img_pages={len(img_pages)}")
    print("  figure captions:", cap_figs[:8])
    doc.close()
