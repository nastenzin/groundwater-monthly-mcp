# -*- coding: utf-8 -*-
"""Probe whether old mwr new-site article pages (2024 months) still exist by ID mapping."""
import re
import sys

import requests
from bs4 import BeautifulSoup

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/",
}
S = requests.Session()
S.headers.update(HEAD)


def check(url):
    try:
        r = S.get(url, timeout=45, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:90]}")
        return None
    bad = len(r.content) == 394 and "error.html" in (r.url or "")
    if bad:
        print(f"  404 {url}")
        return None
    r.encoding = "utf-8"
    t = BeautifulSoup(r.text, "html.parser")
    ttl = t.title.get_text(strip=True) if t.title else ""
    pdfs = [a.get("href") for a in t.find_all("a") if (a.get("href") or "").lower().endswith(".pdf")]
    print(f"  200 {url}")
    print(f"      title={ttl}  pdfs={pdfs}")
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cands = [
        # 2024-09 (xxzx id 1779875/1779876)
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202411/t20241122_1779875.html",
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202411/t20241122_1779874.html",
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202411/t20241122_1779877.html",
        # 2024-08
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202410/t20241022_1775327.html",
        # 2024-07
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202409/t20240912_1769668.html",
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202409/t20240912_1769669.html",
        # 2024-06
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202408/t20240821_1767320.html",
        # 2024-04
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202406/t20240627_1753798.html",
        # 2023-12
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202403/t20240302_1734366.html",
        # 2019-01
        "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/202303/t20230328_1675690.html",
    ]
    for u in cands:
        check(u)
