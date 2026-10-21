# -*- coding: utf-8 -*-
"""Search engines (bing/baidu) + site search probes for 地下水动态月报."""
import re
import sys

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)


def fetch(url):
    try:
        r = S.get(url, timeout=40, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:120]}")
        return None
    print(f"[{r.status_code}] len={len(r.content)} {url}")
    return r


def bing(q, first=1):
    from urllib.parse import quote
    r = fetch(f"https://www.bing.com/search?q={quote(q)}&first={first}&setlang=zh-CN")
    if not r:
        return []
    t = r.text
    links = re.findall(r'<h2><a href="(http[^"]+)"[^>]*>(.*?)</a></h2>', t, re.S)
    out = []
    for u, ttl in links:
        ttl = re.sub(r"<[^>]+>", "", ttl)
        out.append((u, ttl))
        print("   ", ttl[:80], "|", u[:160])
    if not out:
        # fallback: any external hrefs
        cands = re.findall(r'href="(https?://(?!www\.bing)[^"]+)"', t)
        print("   raw links:", len(cands))
        for c in cands[:20]:
            print("    ", c[:160])
    return out


def baidu(q, pn=0):
    from urllib.parse import quote
    r = fetch(f"http://www.baidu.com/s?wd={quote(q)}&pn={pn}")
    if not r:
        return []
    t = r.text
    out = []
    for m in re.finditer(r'<h3[^>]*>.*?<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        u, ttl = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        out.append((u, ttl))
        print("   ", ttl[:80], "|", u[:160])
    if not out:
        print("   <no h3 links> len html", len(t))
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    q = sys.argv[2] if len(sys.argv) > 2 else "地下水动态月报 2019 pdf"
    if mode == "bing":
        bing(q)
    elif mode == "baidu":
        baidu(q)
    elif mode == "site":
        for u in [
            "http://www.mwr.gov.cn/so/",
            "http://so.mwr.gov.cn/",
            "http://www.mwr.gov.cn/search/",
            "http://xxzx.mwr.gov.cn/",
        ]:
            fetch(u)
