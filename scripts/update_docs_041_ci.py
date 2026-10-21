# -*- coding: utf-8 -*-
"""Docs: use CI (GitHub Actions) v0.4.1 asset hashes instead of local build hashes."""
from pathlib import Path

pairs = {
    "5,648,602": "5,648,307",
    "63a3aa325bd3e5b63613c231274cdf7a975a715ddbb86e120115d5789c89c045":
        "16f66d5d26c1996838a5570cacdfef6bfbad022a4d916aafd92fdc7004c77d0e",
    "5,655,415": "5,654,317",
    "4e6ddcefddea6e6cd799eb6b9c13c1fadf66a4f39538f93de87b24252f82b170":
        "bf247839a12d2d6af00af89f9b1ebfeb8534e925f010f831a1c19c4a188d35ec",
}
for name in ("README.md", "docs/deploy.md", "docs/release-notes-0.4.1.md"):
    p = Path(name)
    t = p.read_text(encoding="utf-8")
    n = t
    for old, new in pairs.items():
        n = n.replace(old, new)
    if n != t:
        p.write_text(n, encoding="utf-8")
        print("updated", name)
