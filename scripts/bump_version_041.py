# -*- coding: utf-8 -*-
"""版本号升级：0.4.0 -> 0.4.1（纯文本，无 BOM）。"""
from pathlib import Path

files = ["pyproject.toml", "server.json", "src/groundwater_mcp/__init__.py",
         "src/groundwater_mcp/server.py", "Dockerfile"]
for name in files:
    p = Path(name)
    text = p.read_text(encoding="utf-8")
    new = text.replace("0.4.0", "0.4.1")
    if new != text:
        p.write_text(new, encoding="utf-8")
        print("bumped", name)
    else:
        print("unchanged", name)
