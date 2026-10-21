# -*- coding: utf-8 -*-
"""Fetch flipbook config.js and look for page image paths."""
import re
import urllib.request

BASE = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202409/mobile/"
for name in ("javascript/config.js", "javascript/search_config.js"):
    url = BASE + name
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        text = r.read().decode("utf-8", "ignore")
    print("====", name, len(text))
    print(text[:600].replace("\n", " "))
    hits = re.findall(r"[\w./-]*(?:jpg|jpeg|png)[\w./-]*", text)
    print("image refs:", hits[:20])
