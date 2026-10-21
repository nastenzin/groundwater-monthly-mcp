# -*- coding: utf-8 -*-
"""Baidu search with redirect resolution: hunt for PDF URLs of 地下水动态月报 issues."""
import re
import sys
import time
from urllib.parse import quote

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "http://www.baidu.com/",
}
S = requests.Session()
S.headers.update(HEAD)


def baidu_results(kw, pn=0):
    url = f"http://www.baidu.com/s?wd={quote(kw)}&pn={pn}&ie=utf-8"
    try:
        r = S.get(url, timeout=45)
    except Exception as e:  # noqa: BLE001
        print("ERR", repr(e)[:100])
        return []
    r.encoding = "utf-8"
    t = r.text
    if "百度安全验证" in t or "wappass" in t:
        print("  !! baidu captcha")
        return []
    out = []
    # each result block: <h3 ...><a href="http://www.baidu.com/link?url=...">
    for m in re.finditer(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        href, ttl = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        out.append((ttl, href))
    # realurl hints sometimes present
    for m in re.finditer(r'"realurl"\s*:\s*"([^"]+)"', t):
        print("  realurl:", m.group(1)[:160])
    return out


def resolve(href):
    if "baidu.com/link" not in href:
        return href
    try:
        r = S.get(href, timeout=25, allow_redirects=False)
        loc = r.headers.get("Location")
        if loc:
            return loc
        # meta refresh fallback
        m = re.search(r'URL=([^"\'>]+)', r.text)
        if m:
            return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    return href


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    keywords = sys.argv[1:]
    for kw in keywords:
        print(f"===== {kw}")
        for ttl, href in baidu_results(kw):
            real = resolve(href)
            print(f"   {ttl[:60]} | {real[:170]}")
            time.sleep(0.2)
