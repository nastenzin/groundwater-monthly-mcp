# -*- coding: utf-8 -*-
"""Update wheel/sdist size+sha references after owner metadata change."""
from pathlib import Path

OLD_WHEEL_SHA = "60e98571a9aa8c99b97b0d046709c881a3eee437fbf21b2f0e6bff83bc279830"
NEW_WHEEL_SHA = "24ae8fea9a8e270661c8d36f9f97a0335f9ce635610733bac3a3283c3f1ec9c4"
OLD_SDIST_SHA = "567af2f33320a0feffa21acf31fb1bf843b2463ae3758a217aed24d0aeb1b747"
NEW_SDIST_SHA = "caa6d32cc320d163408d10fffec800da7f7de2fe9ba3246ad0e77d356101b694"

files = ["README.md", "docs/deploy.md", "docs/release-notes-0.4.0.md",
         "scripts/verify_all.py", "data/verification_report.json", "docs/verification.md"]
for name in files:
    p = Path(name)
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    n = (t.replace(OLD_WHEEL_SHA, NEW_WHEEL_SHA)
           .replace(OLD_SDIST_SHA, NEW_SDIST_SHA)
           .replace("5,646,895", "5,647,891")
           .replace("5,654,048", "5,654,026")
           .replace("5.39 MB", "5.39 MB"))
    if n != t:
        p.write_text(n, encoding="utf-8")
        print("updated", name)
