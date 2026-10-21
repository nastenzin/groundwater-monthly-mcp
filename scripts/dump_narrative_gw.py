# -*- coding: utf-8 -*-
"""Dump groundwater-related narrative sentences of 中国水资源公报 HTML years."""
import re
from pathlib import Path

OUT = Path("data/bulletin/probe")
lines = []
for year in range(1997, 2011):
    p = Path(f"data/bulletin/text/{year}.html.txt")
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8")
    # split into sentences around groundwater keywords
    sents = re.split(r"[。\n]", text)
    hits = [s.strip() for s in sents if "地下" in s or "浅层" in s]
    lines.append(f"===== {year} hits={len(hits)}")
    for s in hits:
        lines.append("  " + s[:400])
Path(OUT / "narrative_gw.txt").write_text("\n".join(lines), encoding="utf-8")
print("ok")
