# -*- coding: utf-8 -*-
"""OCR the 2021 annual report groundwater table page."""
import sys
from pathlib import Path

import pymupdf
from rapidocr_onnxruntime import RapidOCR

page_no = int(sys.argv[1]) if len(sys.argv) > 1 else 67
pdf = "data/annual/pdfs/2021.pdf"
out = Path(f"data/annual/scan2021/ocr_p{page_no:03d}.png")
doc = pymupdf.open(pdf)
pix = doc[page_no - 1].get_pixmap(dpi=300)
pix.save(str(out))
doc.close()
ocr = RapidOCR()
result, _ = ocr(str(out))
items = []
for box, text, score in result or []:
    xs = [pt[0] for pt in box]
    ys = [pt[1] for pt in box]
    items.append(
        {
            "text": text.strip(),
            "x": round(sum(xs) / 4, 1),
            "y": round(sum(ys) / 4, 1),
            "score": round(float(score), 2),
        }
    )
items.sort(key=lambda it: (it["y"], it["x"]))
for it in items:
    print(f'{it["y"]:8.1f} {it["x"]:8.1f} {it["score"]:.2f} {it["text"]}')
Path(f"data/annual/scan2021/ocr_p{page_no:03d}.json").write_text(
    __import__("json").dumps(items, ensure_ascii=False, indent=1), encoding="utf-8"
)
print("count", len(items))
