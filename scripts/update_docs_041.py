# -*- coding: utf-8 -*-
"""Docs/verify: update 0.4.1 wheel+sdist numbers (local build)."""
from pathlib import Path

OLD = {
    "5,647,599": "5,648,602",
    "c9a87f5fe6f14153f6bac30ae73721ebb20f6a9c3fe0db5356a4d8002752dc7c":
        "63a3aa325bd3e5b63613c231274cdf7a975a715ddbb86e120115d5789c89c045",
    "5,653,126": "5,655,415",
    "c0beaaf13852c30d2a42a76dd979242d86cd48bc4d0f9987be5c6d816b1a0de1":
        "4e6ddcefddea6e6cd799eb6b9c13c1fadf66a4f39538f93de87b24252f82b170",
}
for name in ("README.md", "docs/deploy.md", "scripts/verify_all.py"):
    p = Path(name)
    t = p.read_text(encoding="utf-8")
    n = t
    for old, new in OLD.items():
        n = n.replace(old, new)
    n = (n.replace("groundwater_monthly_mcp-0.4.0-py3-none-any.whl",
                   "groundwater_monthly_mcp-0.4.1-py3-none-any.whl")
          .replace("groundwater_monthly_mcp-0.4.0.tar.gz",
                   "groundwater_monthly_mcp-0.4.1.tar.gz"))
    if n != t:
        p.write_text(n, encoding="utf-8")
        print("updated", name)
