# -*- coding: utf-8 -*-
"""Fix stale example value 20.37 -> 20.31 in docs and refresh verification."""
from pathlib import Path

for name in ("docs/deploy.md", "docs/surface.md"):
    p = Path(name)
    t = p.read_text(encoding="utf-8")
    n = t.replace("20.37", "20.31")
    if n != t:
        p.write_text(n, encoding="utf-8")
        print("fixed", name)
