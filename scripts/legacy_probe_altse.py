# -*- coding: utf-8 -*-
"""Query Mojeek / Yandex for 地下水动态月报 PDFs."""
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
S = requests.Session()
S.headers.update(HEAD)
OUT = Path("data/legacy_probe")
OUT.mkdir(parents=True, exist_ok=True)


def get(url, name=None):
    try:
        r = S.get(url, timeout=45, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:100]}")
        return None
    print(f"[{r.status_code}] len={len(r.content)} {r.url}")
    if name:
        (OUT / name).write_text(r.text, encoding="utf-8", errors="replace")
    return r


def mojeek(q):
    r = get("https://www.mojeek.com/search?q=" + quote(q), "mojeek.html")
    if not r:
        return []
    out = []
    for m in re.finditer(r'<a class="ob"[^>]*href="([^"]+)"', r.text):
        out.append(m.group(1))
    if not out:
        for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>', r.text):
            u = m.group(1)
            if "mojeek" not in u:
                out.append(u)
    for u in out[:25]:
        print("   ", u[:170])
    return out


def yandex(q):
    # yandex requires special handling; try lite version
    r = get("https://yandex.com/search/?text=" + quote(q) + "&lr=21461", "yandex.html")
    if not r:
        return []
    urls = re.findall(r'href="(https?://[^"]+)"', r.text)
    seen = set()
    for u in urls:
        if "yandex" in u:
            continue
        if u in seen:
            continue
        seen.add(u)
        print("   ", u[:170])
    return list(seen)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    engine = sys.argv[1]
    q = sys.argv[2]
    if engine == "mojeek":
        mojeek(q)
    elif engine == "yandex":
        yandex(q)
