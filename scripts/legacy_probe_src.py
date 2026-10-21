# -*- coding: utf-8 -*-
"""Check alternate sources: wayback availability API, xxzx other channels."""
import sys

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)


def show(url, snippet=300):
    try:
        r = S.get(url, timeout=50, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:140]}")
        return None
    body = r.content
    print(f"[{r.status_code}] len={len(body)} final={r.url}")
    print("   ", body[:snippet].decode("utf-8", "replace").replace("\n", " ")[:snippet])
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    if mode == "wayback":
        for u in [
            "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202301/",
            "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/202012/",
            "http://xxzx.mwr.gov.cn/xxgk/gbjb/dxsdtyb/",
        ]:
            show("http://archive.org/wayback/available?url=" + requests.utils.quote(u, safe=""))
    elif mode == "channels":
        for u in [
            "http://xxzx.mwr.gov.cn/xxgk/gbjb/",
            "http://www.mwr.gov.cn/sj/tjgb/",
            "http://www.mwr.gov.cn/zzsc/tjgb/",
            "http://www.mwr.gov.cn/zzsc/",
        ]:
            show(u)
