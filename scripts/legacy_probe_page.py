# -*- coding: utf-8 -*-
"""Fetch a page, save it, and print all links/iframes/script srcs."""
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "http://xxzx.mwr.gov.cn/xxgk/gbjb/dxsdtyb/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)
OUT = Path("data/legacy_probe")
OUT.mkdir(parents=True, exist_ok=True)


def fetch(url):
    r = S.get(url, timeout=45, allow_redirects=True)
    return r


def main(url, name):
    r = fetch(url)
    raw = r.content
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gb18030", "replace")
    (OUT / name).write_text(text, encoding="utf-8")
    print(f"== {url}\n   status={r.status_code} final={r.url} bytes={len(raw)}")
    s = BeautifulSoup(text, "html.parser")
    for tag in ("iframe", "frame", "embed", "object", "link", "script"):
        for el in s.find_all(tag):
            for attr in ("src", "href", "data"):
                v = el.get(attr)
                if v:
                    print(f"   {tag}.{attr}: {v}")
    print("   --- anchors ---")
    for a in s.find_all("a"):
        h = a.get("href") or ""
        t = a.get_text(strip=True)
        print(f"   a: {t!r} -> {h}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1], sys.argv[2])
