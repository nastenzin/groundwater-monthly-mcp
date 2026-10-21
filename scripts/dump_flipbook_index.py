# -*- coding: utf-8 -*-
"""Fetch live flipbook index.html and list scripts / asset references."""
import re
import urllib.request

URL = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202409/mobile/index.html"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    text = r.read().decode("utf-8", "ignore")
print("len", len(text))
for m in re.findall(r'(?:src|href)="([^"]+)"', text):
    print("ref:", m)
print("--- body snippet ---")
i = text.find("<body")
print(text[i:i + 1500])
