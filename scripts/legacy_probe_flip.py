# -*- coding: utf-8 -*-
"""Deep probe flipbook dirs 2024 for assets: page images, search xml, html5, download pdf."""
import re
import sys

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "http://xxzx.mwr.gov.cn/xxgk/gbjb/dxsdtyb/",
}
S = requests.Session()
S.headers.update(HEAD)
ZZ = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/"

NAMES = [
    "files/search/search.xml",
    "files/search/1.xml",
    "files/page/1.jpg",
    "files/pages/1.jpg",
    "files/page1.jpg",
    "files/1.jpg",
    "files/shot.jpg",
    "files/thumb/1.jpg",
    "files/pdf/1.pdf",
    "files/download/1.pdf",
    "download/1.pdf",
    "files/mobile/index.html",
    "mobile/index.html",
    "html5/index.html",
    "files/html5/index.html",
    "bookContent.swf",
    "P0202.pdf",
]


def get(url, timeout=40):
    try:
        r = S.get(url, timeout=timeout, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        return None, repr(e)[:60]
    return r, None


def probe(root):
    r, err = get(root)
    if r is None:
        print(f"ERR {root} {err}")
        return
    n = len(r.content)
    print(f"[root] {root} len={n} final={r.url}")
    if n == 58:
        print("   BODY58:", r.content.decode("utf-8", "replace"))
        return
    if n == 394:
        print("   404-page")
        return
    for nm in NAMES:
        rr, err = get(root + nm)
        if rr is None:
            continue
        if len(rr.content) == 394 and "error.html" in (rr.url or ""):
            continue
        print(f"   OK {nm} len={len(rr.content)}")
        if nm.endswith(".xml"):
            print("      ", rr.content[:600].decode("utf-8", "replace").replace("\n", " ")[:600])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for mth in sys.argv[1].split(","):
        probe(ZZ + mth + "/")
