# -*- coding: utf-8 -*-
"""Docs: bump 0.4.0 -> 0.4.1 (excluding historical release notes)."""
from pathlib import Path

files = ["README.md", "docs/deploy.md", "docs/surface.md", "smithery.yaml"]
for name in files:
    p = Path(name)
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    n = t.replace("0.4.0", "0.4.1").replace("v0.4.0", "v0.4.1")
    if n != t:
        p.write_text(n, encoding="utf-8")
        print("bumped", name)
