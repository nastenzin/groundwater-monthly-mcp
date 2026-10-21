# -*- coding: utf-8 -*-
"""Probe the new-site pdf folder for older months + find site search."""
import re
import sys

import requests
from bs4 import BeautifulSoup

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)


def probe(url, snippet=150):
    try:
        r = S.get(url, timeout=45, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:110]}")
        return None
    bad = len(r.content) == 394 and "error.html" in (r.url or "")
    print(f"[{r.status_code}] len={len(r.content)} {'BAD(404-page) ' if bad else ''}{r.url}")
    if not bad:
        print("   ", r.content[:snippet].decode("utf-8", "replace").replace("\n", " ")[:snippet])
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    if mode == "oldpdf":
        for u in [
            "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202012/P020210107610029685570.pdf",
            "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202012/",
            "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/index_1.html",
            "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/index_2.html",
            "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202012/t20210107_1500000.html",
            "http://www.mwr.gov.cn/sj/tjgb/",
        ]:
            probe(u)
    elif mode == "search":
        r = probe("http://www.mwr.gov.cn/", 4000)
        if r:
            t = r.content.decode("utf-8", "replace")
            for m in re.finditer(r'(action="[^"]*"|so\.mwr[^"\']*|search[^"\']{0,60})', t, re.I):
                print("   ", m.group(0)[:150])
