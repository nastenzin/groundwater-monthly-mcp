# -*- coding: utf-8 -*-
"""Probe flipbook dirs: which months exist, and what assets live inside."""
import re
import sys
import time

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "http://xxzx.mwr.gov.cn/xxgk/gbjb/dxsdtyb/",
}
S = requests.Session()
S.headers.update(HEAD)
ZZ = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/"


def get(url, tries=2, timeout=40):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, timeout=timeout, allow_redirects=True)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)[:100]
        time.sleep(1.2 * (i + 1))
    print(f"   ERR {url} :: {last}")
    return None


def exists(url):
    r = get(url, tries=1)
    if r is None:
        return False, 0, r
    n = len(r.content)
    if n == 394 and "error.html" in (r.url or ""):
        return False, n, r
    if n == 394:
        return False, n, r
    return True, n, r


def probe_assets(months):
    names = [
        "book.xml",
        "xml/book.xml",
        "files/book.xml",
        "flash/book.xml",
        "javascript/book.xml",
        "js/fbscript.js",
        "js/fbendscript.js",
        "book.swf",
        "files/basic-html/page1.html",
        "files/basic-html/page2.html",
        "files/basic-html/index.html",
        "files/mobile/index.html",
        "files/thumb/1.jpg",
    ]
    for m in months:
        root = f"{ZZ}{m}/"
        ok, n, r = exists(root)
        print(f"[{m}] root exists={ok} bytes={n}")
        if not ok:
            continue
        for nm in names:
            ok2, n2, _ = exists(root + nm)
            if ok2:
                print(f"    OK {nm} bytes={n2}")


def probe_months():
    existing = []
    years = range(2019, 2025)
    for y in years:
        for mth in range(1, 13):
            if y == 2024 and mth > 9:
                continue
            key = f"{y}{mth:02d}"
            ok, n, _ = exists(f"{ZZ}{key}/")
            print(f"[{key}] exists={ok} bytes={n}")
            if ok:
                existing.append((key, n))
    print("EXISTING:", existing)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    what = sys.argv[1]
    if what == "months":
        probe_months()
    else:
        probe_assets(sys.argv[2].split(","))
