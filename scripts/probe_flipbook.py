# -*- coding: utf-8 -*-
"""Probe flipbook image URL patterns on mwr.gov.cn for HTML periods."""
import urllib.request

BASE = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202409/mobile/"
CANDIDATES = [
    "files/large/1.jpg", "files/normal/1.jpg", "files/page/1.jpg", "files/thumb/1.jpg",
    "files/large/7.jpg", "files/normal/7.jpg", "files/page/7.jpg",
    "large/1.jpg", "normal/1.jpg", "page/1.jpg", "images/1.jpg",
    "files/1.jpg", "book/files/large/1.jpg", "javascript/config.js", "javascript/main.js",
]
for c in CANDIDATES:
    url = BASE + c
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read(2000)
            print(f"OK  {r.status} {len(data):6d}B {r.headers.get('Content-Type')}  {c}")
    except Exception as exc:  # noqa: BLE001
        print(f"ERR {getattr(exc, 'code', '?')}  {c}  {exc}")
