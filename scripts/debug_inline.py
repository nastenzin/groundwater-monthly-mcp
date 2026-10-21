# -*- coding: utf-8 -*-
"""Debug inline supply parsing."""
import re
import sys
from pathlib import Path

sys.path.insert(0, "scripts")
import build_bulletin_dataset as B

text = Path("data/bulletin/text/2006.html.txt").read_text(encoding="utf-8")
names = ["全国", "南方四区", "北方六区", "松花江", "辽河", "海河", "黄河", "淮河",
         "长江", "珠江", "东南诸河", "西南诸河", "西北诸河", "太湖"]
pattern = "|".join(r"\s*".join(ch for ch in n) for n in names)
lines = []
for m in re.finditer(pattern, text):
    if B.canon_region(m.group(0)) != "全国":
        continue
    seg = text[m.end():m.end() + 260]
    if not re.match(r"\s*-?\d", seg):
        continue
    run = re.match(r"\s*((?:-?\d+(?:\.\d+)?\s*)+)", seg)
    vals = re.findall(r"-?\d+(?:\.\d+)?", run.group(1))
    lines.append(f"seg={seg[:120]!r}")
    lines.append(f"run={run.group(1)[:120]!r} n={len(vals)} vals={vals[:12]}")
Path("data/bulletin/probe/dbg_inline.txt").write_text("\n".join(lines), encoding="utf-8")
print("ok")
