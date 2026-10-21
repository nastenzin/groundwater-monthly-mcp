# -*- coding: utf-8 -*-
"""Probe the xxzx mirror list pages and the zzsc flipbook directories."""
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/",
}
S = requests.Session()
S.headers.update(HEAD)


def get(url, tries=2, timeout=45):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, timeout=timeout)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)[:120]
        time.sleep(1.5 * (i + 1))
    print(f"  FAIL {url} :: {last}")
    return None


def probe_lists():
    base = "http://xxzx.mwr.gov.cn/xxgk/gbjb/dxsdtyb/"
    suffixes = [""] + [f"index_{i}.html" for i in range(1, 10)]
    found = []
    for suf in suffixes:
        url = base + suf
        r = get(url)
        if r is None:
            continue
        s = BeautifulSoup(r.text, "html.parser")
        items = []
        for a in s.find_all("a"):
            t = a.get_text(strip=True)
            h = a.get("href") or ""
            m = re.search(r"(\d{4})年\s*(\d{1,2})月", t)
            if m and ("地下水" in t or "月报" in t):
                items.append((t, requests.compat.urljoin(url, h)))
        print(f"[list] {url} -> {len(items)} items")
        for t, u in items:
            print(f"   {t}  {u}")
        if not items:
            break
        found.extend(items)
        time.sleep(0.6)
    return found


def probe_dir():
    # probe the flipbook directory structure for a couple of known dirs
    dirs = ["202406", "202012", "202301", "201901", "201806"]
    names = [
        "book.xml",
        "javascript/config.js",
        "files/basic-html/page1.html",
        "files/basic-html/page2.html",
        "files/search/search.xml",
        "files/mobile/javascript/config.js",
    ]
    for d in dirs:
        root = f"http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/{d}/"
        print(f"[dir] {root}")
        for n in names:
            r = get(root + n, tries=1)
            print(f"   {'OK ' if r else 'no '} {n} len={len(r.content) if r else 0}")
        # try index listing
        r = get(root, tries=1)
        if r:
            s = BeautifulSoup(r.text, "html.parser")
            hrefs = [a.get("href") for a in s.find_all("a")][:20]
            print("   root links:", hrefs)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "list"):
        probe_lists()
    if what in ("all", "dir"):
        probe_dir()
