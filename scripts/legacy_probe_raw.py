# -*- coding: utf-8 -*-
"""Raw fetch of specific URLs with status + snippet, to distinguish 404-page-from-200."""
import sys

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "http://xxzx.mwr.gov.cn/xxgk/gbjb/dxsdtyb/",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)


def show(url):
    try:
        r = S.get(url, timeout=45, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:150]}")
        return
    body = r.content
    note = ""
    if len(body) == 394:
        note = "  <<< 394-byte 404 page"
    print(f"[{r.status_code}] len={len(body)} final={r.url}{note}")
    print("   ", body[:260].decode("utf-8", "replace").replace("\n", " ")[:240])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    urls = [
        "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202012/files/basic-html/page2.html",
        "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202012/files/basic-html/page1.html",
        "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202012/",
        "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202406/",
        "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/",
        "http://xxzx.mwr.gov.cn/xxgk/gbjb/dxsdtyb/202411/t20241122_1779875.html",
    ]
    for u in urls:
        show(u)
