# -*- coding: utf-8 -*-
"""Probe flipbook page image naming under .../202409/files/."""
import urllib.request

BASE = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202409/files/"
names = ["thumb/1.jpg", "page/1.jpg", "page/1.png", "large/1.png", "page/2.jpg",
         "page/3.jpg", "page/5.jpg", "normal/1.jpg", "large/1.jpg",
         "page/1.jpg?1", "large/1.jpg?1", "page/01.jpg", "page/1.jpeg",
         "page/1.webp", "thumb/1.png"]
for n in names:
    url = BASE + n
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            d = r.read(3000)
            ct = r.headers.get("Content-Type")
            print(f"{r.status} {len(d):6d} {ct:20s} {n}")
            if ct and ct.startswith("text/html"):
                print("   body:", d[:200])
    except Exception as exc:  # noqa: BLE001
        print(f"ERR {getattr(exc, 'code', '?')} {n} {exc}")
