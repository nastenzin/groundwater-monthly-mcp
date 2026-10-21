# -*- coding: utf-8 -*-
"""Probe annual hydrological report detail pages and collect PDF links."""
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}
PAGES = {
    2025: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202607/t20260724_2135937.html",
    2024: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202510/t20251001_2037173.html",
    2023: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202510/t20251001_2037172.html",
    2022: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202510/t20251001_2037171.html",
    2021: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202510/t20251001_2037170.html",
}
for year, url in PAGES.items():
    r = requests.get(url, timeout=40, headers=HEAD)
    r.encoding = "utf-8"
    print("=" * 20, year, r.status_code, len(r.text))
    pdfs = re.findall(r'href="([^"]*\.pdf)"', r.text)
    print(" pdf:", pdfs[:5])
    for a in BeautifulSoup(r.text, "html.parser").find_all("a"):
        h = a.get("href") or ""
        if ".pdf" in h.lower() or ".html" in h.lower() and "files" in h:
            print("  A:", a.get_text(strip=True)[:40], h)
