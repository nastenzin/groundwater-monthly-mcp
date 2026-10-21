# -*- coding: utf-8 -*-
"""Fetch flipbook main.js and search for page image path construction."""
import re
import urllib.request

URL = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202409/mobile/javascript/main.js"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=30) as r:
    text = r.read().decode("utf-8", "ignore")
print("len", len(text))
for pat in ("largePath", "normalPath", "thumbPath", "jpg", "files/"):
    idx = 0
    print("====", pat)
    for _ in range(4):
        idx = text.find(pat, idx)
        if idx < 0:
            break
        print("  ...", text[max(0, idx - 120):idx + 160].replace("\n", " "))
        idx += len(pat)
