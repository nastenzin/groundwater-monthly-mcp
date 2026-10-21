# -*- coding: utf-8 -*-
"""Fill GitHub owner placeholders with the real account name."""
from pathlib import Path

OWNER = "nastenzin"
files = ["pyproject.toml", "server.json", "Dockerfile", "README.md",
         "docs/deploy.md", "smithery.yaml", "scripts/package_check.py"]
for name in files:
    p = Path(name)
    if not p.exists():
        continue
    text = p.read_text(encoding="utf-8")
    new = (text.replace("REPLACE_WITH_GITHUB_OWNER", OWNER)
               .replace("io.github.replace-me/", f"io.github.{OWNER}/")
               .replace("io.github.<owner>/", f"io.github.{OWNER}/")
               .replace("<owner>", OWNER)
               .replace("<你的 GitHub 用户名或组织>", OWNER)
               .replace("<你的 GitHub 用户名/组织>", OWNER))
    if new != text:
        p.write_text(new, encoding="utf-8")
        print("updated", name)
