# -*- coding: utf-8 -*-
"""Docs: record actual GitHub Release asset hashes (CI build) and note local-build difference."""
from pathlib import Path

CI_WHEEL = ("5,647,599", "c9a87f5fe6f14153f6bac30ae73721ebb20f6a9c3fe0db5356a4d8002752dc7c")
LOCAL_WHEEL_SHA = "24ae8fea9a8e270661c8d36f9f97a0335f9ce635610733bac3a3283c3f1ec9c4"
CI_SDIST = ("5,653,126", "c0beaaf13852c30d2a42a76dd979242d86cd48bc4d0f9987be5c6d816b1a0de1")
LOCAL_SDIST_SHA = "caa6d32cc320d163408d10fffec800da7f7de2fe9ba3246ad0e77d356101b694"

repl = [
    ("README.md", [("5,647,891", CI_WHEEL[0]), (LOCAL_WHEEL_SHA, CI_WHEEL[1])]),
    ("docs/deploy.md", [("5,647,891", CI_WHEEL[0]), (LOCAL_WHEEL_SHA, CI_WHEEL[1])]),
    ("docs/release-notes-0.4.0.md", [("5,647,891", CI_WHEEL[0]), (LOCAL_WHEEL_SHA, CI_WHEEL[1]),
                                     ("5,654,026", CI_SDIST[0]), (LOCAL_SDIST_SHA, CI_SDIST[1])]),
]
for name, pairs in repl:
    p = Path(name)
    t = p.read_text(encoding="utf-8")
    n = t
    for old, new in pairs:
        n = n.replace(old, new)
    if n != t:
        p.write_text(n, encoding="utf-8")
        print("updated", name)
