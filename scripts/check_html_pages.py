# -*- coding: utf-8 -*-
"""List pages with depth-map captions per HTML period and thumbnails present."""
import re
from pathlib import Path

for period in sorted(p.name for p in Path("data/legacy/html").iterdir()):
    pages = sorted(int(re.sub(r"\D", "", p.stem)) for p in (Path("data/legacy/html") / period).glob("page*.html"))
    hits = []
    for page in pages:
        t = (Path("data/legacy/html") / period / f"page{page}.html").read_text(encoding="utf-8", errors="ignore")
        if "埋深等值面图" in t:
            hits.append(page)
    thumbs = sorted(int(re.sub(r"\D", "", p.stem)) for p in (Path("data/surface/html") / period).glob("p*.jpg"))
    print(period, "caption_pages:", hits, "thumbs:", thumbs,
          "missing:", [p for p in hits if p not in thumbs])
