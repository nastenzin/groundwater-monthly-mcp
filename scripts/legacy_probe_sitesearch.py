# -*- coding: utf-8 -*-
"""Try xxzx POST search and mwr IRS full-text search."""
import re
import sys
from pathlib import Path

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)
OUT = Path("data/legacy_probe")
OUT.mkdir(parents=True, exist_ok=True)


def save(name, r):
    (OUT / name).write_text(r.text, encoding="utf-8", errors="replace")


def show_links(r, limit=40):
    for m in re.finditer(r'href="([^"]+)"', r.text):
        u = m.group(1)
        if re.search(r"(P0\d+\.pdf|t\d{8}_\d+\.html|\.pdf)", u):
            print("   LINK:", u[:180])


def xxzx_search(kw):
    url = "http://xxzx.mwr.gov.cn/WebSearch/action/Search/search"
    data = {
        "queryObj.siteid": "131",
        "queryObj.orderField": "date",
        "queryObj.orderFD": "0",
        "queryObj.keywords": kw,
    }
    try:
        r = S.post(url, data=data, timeout=60, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print("ERR xxzx", repr(e)[:120])
        return None
    print(f"[{r.status_code}] len={len(r.content)} final={r.url}")
    r.encoding = "utf-8"
    save("xxzx_search.html", r)
    print("   ", r.text[:400].replace("\n", " "))
    show_links(r)
    return r


def irs_search(kw, page=1):
    from urllib.parse import quote
    base = (
        "http://jsearch.mwr.gov.cn/irs-c-web/search.shtml"
        "?code=18703928938&dataTypeId=26264"
        f"&searchWord={quote(kw)}&page={page}"
    )
    try:
        r = S.get(base, timeout=60, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print("ERR irs", repr(e)[:120])
        return None
    print(f"[{r.status_code}] len={len(r.content)} final={r.url}")
    r.encoding = "utf-8"
    save("irs_search.html", r)
    print("   ", re.sub(r"<[^>]+>", " ", r.text)[:600].replace("\n", " "))
    show_links(r)
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    kw = sys.argv[2] if len(sys.argv) > 2 else "地下水动态月报"
    if sys.argv[1] == "xxzx":
        xxzx_search(kw)
    else:
        irs_search(kw)
