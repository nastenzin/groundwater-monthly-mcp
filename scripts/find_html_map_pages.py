# -*- coding: utf-8 -*-
"""Find pages containing map figure captions in local HTML period folders."""
import re
from pathlib import Path

for period in ("2024-01", "2024-09"):
    d = Path("data/legacy/html") / period
    print("=====", period, "pages:", len(list(d.glob("page*.html"))))
    for p in sorted(d.glob("page*.html"), key=lambda x: int(re.sub(r"\D", "", x.stem) or 0)):
        t = p.read_text(encoding="utf-8", errors="ignore")
        if "埋深等值面图" in t:
            caps = re.findall(r"图\s*(\d+)[^\n]{0,60}埋深等值面图", t)
            print(p.stem, "caps:", caps[:4])
