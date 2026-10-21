# -*- coding: utf-8 -*-
"""Probe directory listings, sogou/so search, mofile doc site."""
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


def get(url, snippet=200, save=None):
    try:
        r = S.get(url, timeout=45, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:110]}")
        return None
    print(f"[{r.status_code}] len={len(r.content)} {r.url}")
    if save:
        (OUT / save).write_text(r.text, encoding="utf-8", errors="replace")
    if snippet:
        print("   ", r.content[:snippet].decode("utf-8", "replace").replace("\n", " ")[:snippet])
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    if mode == "dirs":
        for u in [
            "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/",
            "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202103/",
            "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202001/",
            "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/201910/",
            "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/index.html",
            "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/t20230328_1675747.pdf",
        ]:
            get(u, 250)
    elif mode == "sogou":
        from urllib.parse import quote
        q = sys.argv[2]
        r = get("https://www.sogou.com/web?query=" + quote(q), 0, "sogou.html")
        if r:
            t = r.text
            print("   vrwrap:", t.count("vrwrap"))
            for m in re.finditer(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
                print("   ", re.sub(r"<[^>]+>", "", m.group(2))[:70], "|", m.group(1)[:160])
    elif mode == "so":
        from urllib.parse import quote
        q = sys.argv[2]
        r = get("https://www.so.com/s?q=" + quote(q), 0, "so.html")
        if r:
            t = r.text
            print("   res-list:", t.count("res-list"))
            for m in re.finditer(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
                print("   ", re.sub(r"<[^>]+>", "", m.group(2))[:70], "|", m.group(1)[:160])
    elif mode == "mofile":
        for u in [
            "https://m.mofile.net/item/20519db2637a442fba950ebe64e7df5f.html",
            "https://m.mofile.net/item/656266f431e8463197a8196319d20aee.html",
        ]:
            get(u, 300)
