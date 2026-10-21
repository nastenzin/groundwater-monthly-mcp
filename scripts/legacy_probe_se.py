# -*- coding: utf-8 -*-
"""Probe search engines (bing/sogou/so.com) and TRS RSS/search endpoints."""
import re
import sys
from pathlib import Path

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)
OUT = Path("data/legacy_probe")
OUT.mkdir(parents=True, exist_ok=True)


def get(url, snippet=0):
    try:
        r = S.get(url, timeout=45, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:110]}")
        return None
    print(f"[{r.status_code}] len={len(r.content)} {r.url}")
    if snippet:
        print("   ", r.content[:snippet].decode("utf-8", "replace").replace("\n", " ")[:snippet])
    return r


def bing_probe(q):
    from urllib.parse import quote
    r = get("https://cn.bing.com/search?q=" + quote(q) + "&setlang=zh-CN&ensearch=0")
    if not r:
        return
    t = r.text
    (OUT / "bing_test.html").write_text(t, encoding="utf-8")
    print("   b_algo:", t.count("b_algo"))
    blocks = re.findall(r'<li class="b_algo"(.*?)</li>', t, re.S)
    print("   blocks:", len(blocks))
    for b in blocks[:15]:
        a = re.search(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if a:
            ttl = re.sub(r"<[^>]+>", "", a.group(2))
            print("   ", ttl[:70], "|", a.group(1)[:170])


def sogou_probe(q):
    from urllib.parse import quote
    r = get("https://www.sogou.com/web?query=" + quote(q))
    if not r:
        return
    t = r.text
    (OUT / "sogou_test.html").write_text(t, encoding="utf-8")
    print("   vrwrap:", t.count("vrwrap"), "rb:", t.count('class="rb"'))
    for m in re.finditer(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        print("   ", re.sub(r"<[^>]+>", "", m.group(2))[:70], "|", m.group(1)[:170])


def so_probe(q):
    from urllib.parse import quote
    r = get("https://www.so.com/s?q=" + quote(q))
    if not r:
        return
    t = r.text
    (OUT / "so_test.html").write_text(t, encoding="utf-8")
    print("   res-list:", t.count("res-list"))
    for m in re.finditer(r'<h3[^>]*class="res-title[^"]*"[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        print("   ", re.sub(r"<[^>]+>", "", m.group(2))[:70], "|", m.group(1)[:170])


def trs_probe():
    bases = [
        "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/",
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/",
    ]
    tails = ["rss.xml", "index.xml", "atom.xml", "rss.rss", "index.rss"]
    for b in bases:
        for t in tails:
            get(b + t, 100)
    for u in [
        "http://www.mwr.gov.cn/search/",
        "http://www.mwr.gov.cn/so/",
        "http://xxzx.mwr.gov.cn/search/",
        "http://so.mwr.gov.cn/",
    ]:
        get(u, 300)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    q = sys.argv[2] if len(sys.argv) > 2 else "地下水动态月报"
    if mode == "bing":
        bing_probe(q)
    elif mode == "sogou":
        sogou_probe(q)
    elif mode == "so":
        so_probe(q)
    elif mode == "trs":
        trs_probe()
