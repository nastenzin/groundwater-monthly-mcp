# -*- coding: utf-8 -*-
"""Explore xxzx 地下水监测评价 (dxsjcpj) channel and other candidate paths."""
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)


def get(url, tries=2, timeout=45):
    for i in range(tries):
        try:
            r = S.get(url, timeout=timeout)
            if r.status_code == 200 and not (len(r.content) == 394 and "error.html" in r.url):
                r.encoding = r.apparent_encoding or "utf-8"
                return r
            if r.status_code == 200:
                return None
        except Exception as e:  # noqa: BLE001
            msg = repr(e)[:90]
        time.sleep(1.2 * (i + 1))
    return None


def walk_channel(base):
    all_items = []
    for suf in [""] + [f"index_{i}.html" for i in range(1, 12)]:
        url = base + suf
        r = get(url)
        if r is None:
            print(f"  [{suf or 'index.html'}] MISS")
            continue
        s = BeautifulSoup(r.text, "html.parser")
        items = []
        for a in s.find_all("a"):
            t = a.get_text(strip=True)
            h = a.get("href") or ""
            if re.search(r"(月报|地下水)", t):
                items.append((t, requests.compat.urljoin(url, h)))
        print(f"  [{suf or 'index.html'}] ok len={len(r.content)} items={len(items)}")
        if suf and not items:
            break
        for t, u in items:
            print(f"      {t} -> {u}")
        all_items.extend(items)
        time.sleep(0.5)
    return all_items


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    bases = [
        "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/",
        "http://xxzx.mwr.gov.cn/swszyjcpj/",
    ]
    for b in bases:
        print("==", b)
        walk_channel(b)
