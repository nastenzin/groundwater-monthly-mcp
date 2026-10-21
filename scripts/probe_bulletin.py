# -*- coding: utf-8 -*-
"""Probe MWR water-resources-bulletin / yearbook index pages."""
import re
import sys

import requests
from bs4 import BeautifulSoup

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}


def get(url):
    r = requests.get(url, timeout=40, headers=HEAD)
    r.raise_for_status()
    raw = r.content
    for enc in ("utf-8", "gb18030"):
        try:
            text = raw.decode(enc)
            if text.count("\ufffd") < 5:
                return text
        except UnicodeDecodeError:
            continue
    return raw.decode("gb18030", "replace")


def main(url):
    html = get(url)
    print("URL", url, "len", len(html))
    s = BeautifulSoup(html, "html.parser")
    for a in s.find_all("a"):
        href = a.get("href") or ""
        txt = a.get_text(" ", strip=True)
        if not txt:
            continue
        if re.search(r"(公报|年鉴|20\d\d|19\d\d)", txt) or re.search(r"(szygb|zgsljn|zgswnb|tjgb)", href):
            print(repr(txt)[:80], "->", href)


if __name__ == "__main__":
    for u in sys.argv[1:]:
        main(u)
