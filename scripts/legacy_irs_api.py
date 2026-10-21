# -*- coding: utf-8 -*-
"""Download IRS search JS bundles and extract API endpoint patterns."""
import re
import sys

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "http://jsearch.mwr.gov.cn/",
}
S = requests.Session()
S.headers.update(HEAD)

URLS = [
    "http://jsearch.mwr.gov.cn/irs-c-web/irs/app-js/app.js",
    "http://jsearch.mwr.gov.cn/irs-c-web/theme.js",
]

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for u in URLS:
        try:
            r = S.get(u, timeout=40)
        except Exception as e:  # noqa: BLE001
            print("ERR", u, repr(e)[:100])
            continue
        print(f"== {u} status={r.status_code} len={len(r.content)}")
        t = r.text
        hits = set()
        for m in re.finditer(r"""['"](/[A-Za-z0-9_\-/\.]{4,120})['"]""", t):
            p = m.group(1)
            if re.search(r"(search|api|result|json|ajax|query|list)", p, re.I):
                hits.add(p)
        for p in sorted(hits)[:80]:
            print("   ", p)
        # also print "url:" assignments
        for m in re.finditer(r"(url\s*[:=]\s*['\"][^'\"]{3,120}['\"])", t):
            print("   ASSIGN:", m.group(1)[:140])
