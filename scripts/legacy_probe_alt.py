# -*- coding: utf-8 -*-
"""Probe sogou / so.com / mofile for 地下水动态月报 PDFs."""
import re
import sys
from pathlib import Path
from urllib.parse import quote

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


def get(url, name=None):
    try:
        r = S.get(url, timeout=45, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:110]}")
        return None
    print(f"[{r.status_code}] len={len(r.content)} {r.url}")
    if name:
        (OUT / name).write_text(r.text, encoding="utf-8", errors="replace")
    return r


def parse_sogou(t):
    out = []
    for m in re.finditer(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        out.append((re.sub(r"<[^>]+>", "", m.group(2)).strip(), m.group(1)))
    return out


def parse_so(t):
    out = []
    for m in re.finditer(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        out.append((re.sub(r"<[^>]+>", "", m.group(2)).strip(), m.group(1)))
    return out


def parse_generic(t):
    """collect all hrefs with pdf"""
    urls = set()
    for m in re.finditer(r'href="([^"]+)"', t):
        u = m.group(1)
        if re.search(r"\.pdf($|\?|#)", u, re.I) or "P0" in u:
            urls.add(u)
    return urls


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    q = sys.argv[2] if len(sys.argv) > 2 else "地下水动态月报 pdf"
    if mode == "sogou":
        r = get("https://www.sogou.com/web?query=" + quote(q), "sogou_q.html")
        if r:
            r.encoding = "utf-8"
            for t, u in parse_sogou(r.text)[:20]:
                print("   ", t[:70], "|", u[:170])
            for u in list(parse_generic(r.text))[:10]:
                print("   PDF?", u[:170])
    elif mode == "so":
        r = get("https://www.so.com/s?q=" + quote(q), "so_q.html")
        if r:
            r.encoding = "utf-8"
            for t, u in parse_so(r.text)[:20]:
                print("   ", t[:70], "|", u[:170])
    elif mode == "mofile":
        for u in [
            "https://m.mofile.net/item/20519db2637a442fba950ebe64e7df5f.html",
            "https://m.mofile.net/item/656266f431e8463197a8196319d20aee.html",
        ]:
            get(u, "mofile_item.html")
        r = get("https://m.mofile.net/search?q=" + quote("地下水动态月报"), "mofile_search.html")
        if r:
            r.encoding = "utf-8"
            for m in re.finditer(r'href="(/item/[^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
                print("   ITEM:", m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()[:70])
