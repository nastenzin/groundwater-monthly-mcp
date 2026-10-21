# -*- coding: utf-8 -*-
"""Inspect dxsjcpj detail pages across years: find iframe, pdf links, attachments."""
import re
import sys

import requests
from bs4 import BeautifulSoup

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/",
}
S = requests.Session()
S.headers.update(HEAD)

CASES = {
    "2019-01": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/t20230328_1675690.html",
    "2020-12": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/t20230328_1675744.html",
    "2022-01": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/t20230328_1675774.html",
    "2023-01": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/t20230328_1675786.html",
    "2024-01": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202403/t20240328_1737669.html",
    "2024-09": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202411/t20241122_1779876.html",
}


def get(url):
    try:
        r = S.get(url, timeout=50)
        r.encoding = "utf-8"
        return r
    except Exception as e:  # noqa: BLE001
        print("ERR", url, repr(e)[:120])
        return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for period, url in CASES.items():
        r = get(url)
        if r is None:
            continue
        s = BeautifulSoup(r.text, "html.parser")
        title = s.title.get_text(strip=True) if s.title else ""
        ifr = [f.get("src") for f in s.find_all("iframe")]
        frames = [f.get("src") for f in s.find_all("frame")]
        pdfs = [a.get("href") for a in s.find_all("a") if (a.get("href") or "").lower().endswith(".pdf")]
        embeds = [(e.name, e.get("src") or e.get("data")) for e in s.find_all(["embed", "object"])]
        print(f"== {period} status={r.status_code} bytes={len(r.content)} title={title}")
        print(f"   iframe={ifr} frame={frames} embed={embeds}")
        print(f"   pdfs={pdfs}")
        # body text snippet around 附件/下载
        body = s.get_text(" ", strip=True)
        for kw in ("附件", "下载", "点击"):
            i = body.find(kw)
            if i >= 0:
                print(f"   ...{body[max(0, i-40):i+80]}...")
                break
        # all links containing zzsc or files
        for a in s.find_all("a"):
            h = a.get("href") or ""
            if "zzsc" in h or "files/" in h:
                print("   LINK:", h)
