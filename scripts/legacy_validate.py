# -*- coding: utf-8 -*-
"""Validate data/legacy_index.json: paths, sizes, text richness."""
import json
import re
import sys
from pathlib import Path

INDEX = Path("data/legacy_index.json")
FAILS = Path("data/legacy_failures.json")


def has_cjk(s):
    return bool(re.search(r"[\u4e00-\u9fff]", s))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    idx = json.loads(INDEX.read_text(encoding="utf-8"))
    print(f"entries={len(idx)}")
    bad = 0
    for r in idx:
        p = Path(r["local_path"])
        if p.is_file():
            size = p.stat().st_size
            kind = "file"
            cjk_ok = r.get("text_extractable", False)
        elif p.is_dir():
            files = [f for f in p.rglob("*") if f.is_file()]
            size = sum(f.stat().st_size for f in files)
            kind = f"dir({len(files)} files)"
            cjk = 0
            for f in p.glob("page*.html"):
                if has_cjk(f.read_text(encoding="utf-8", errors="ignore")):
                    cjk += 1
            cjk_ok = cjk >= 5
        else:
            size, kind, cjk_ok = -1, "MISSING", False
        if size < 100_000 or not cjk_ok:
            bad += 1
        print(f"{r['period']} pages={r['pages']:>2} extract={r['text_extractable']} "
              f"size={size:>9} {kind:<16} cjk_ok={cjk_ok} {r['local_path']}")
    fails = json.loads(FAILS.read_text(encoding="utf-8"))
    print(f"failures={len(fails)} range={fails[0]['period']}..{fails[-1]['period']}")
    print(f"bad_entries={bad}")
