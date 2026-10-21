# -*- coding: utf-8 -*-
"""Remove machine-specific paths from public docs/scripts/metadata."""
import json
from pathlib import Path

# 1) docs/deploy.md：示例中的本机解释器与仓库路径改为通用写法
p = Path("docs/deploy.md")
t = p.read_text(encoding="utf-8")
t = (t.replace("D:\\\\Anaconda\\\\python.exe", "python")
      .replace("D:\\Anaconda\\python.exe", "python")
      .replace("D:\\\\MCP服务器", "<repo>")
      .replace("D:\\MCP服务器", "<repo>")
      .replace("D:/MCP服务器", "<repo>"))
p.write_text(t, encoding="utf-8")
print("deploy fixed")

# 2) scripts/geo_check.py：用法注释
p = Path("scripts/geo_check.py")
t = p.read_text(encoding="utf-8")
t = t.replace("D:\\\\Anaconda\\\\python.exe scripts\\\\geo_check.py",
              "python scripts/geo_check.py")
t = t.replace("D:\\Anaconda\\python.exe scripts\\geo_check.py",
              "python scripts/geo_check.py")
p.write_text(t, encoding="utf-8")
print("geo_check fixed")

# 3) data/quality_skips.json：source 路径改为仓库相对路径
p = Path("data/quality_skips.json")
if p.exists():
    rows = json.loads(p.read_text(encoding="utf-8"))
    for row in rows:
        src = row.get("source")
        if src:
            row["source"] = src.replace("D:\\MCP服务器\\", "").replace("\\", "/")
    p.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("quality_skips sanitized")
