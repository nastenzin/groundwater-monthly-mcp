# -*- coding: utf-8 -*-
"""Extract images from a report page and save PNGs for visual inspection."""
import sys
from pathlib import Path

import pymupdf

pdf = Path(sys.argv[1] if len(sys.argv) > 1 else "data/pdfs/2025-12.pdf")
pno = int(sys.argv[2] if len(sys.argv) > 2 else 7)
out = Path("data/recon")
out.mkdir(parents=True, exist_ok=True)
doc = pymupdf.open(pdf)
page = doc[pno - 1]
for idx, info in enumerate(page.get_images(full=True)):
    xref = info[0]
    base = doc.extract_image(xref)
    ext = base["ext"]
    f = out / f"p{pno}_img{idx}_{info[2]}x{info[3]}.{ext}"
    f.write_bytes(base["image"])
    print(f, bbox=page.get_image_bbox(info))
doc.close()
