# -*- coding: utf-8 -*-
"""Explore mofile.net: item page structure, download links, uploader collection, search paging."""
import re
import sys
from pathlib import Path
from urllib.parse import quote, urljoin

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)
OUT = Path("data/legacy_probe")
OUT.mkdir(parents=True, exist_ok=True)


def get(url, name=None, snippet=0):
    try:
        r = S.get(url, timeout=45, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:110]}")
        return None
    print(f"[{r.status_code}] len={len(r.content)} {r.url}")
    if name:
        (OUT / name).write_text(r.text, encoding="utf-8", errors="replace")
    r.encoding = "utf-8"
    if snippet:
        t = re.sub(r"<script.*?</script>", " ", r.text, flags=re.S)
        t = re.sub(r"<style.*?</style>", " ", t, flags=re.S)
        t = re.sub(r"<[^>]+>", " ", t)
        t = re.sub(r"\s+", " ", t)
        print("   TXT:", t[:snippet])
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    if mode == "item":
        r = get(
            "https://m.mofile.net/item/20519db2637a442fba950ebe64e7df5f.html",
            "mofile_item_2019_01.html",
        )
        if r:
            for m in re.finditer(r'(href|src|action)="([^"]+)"', r.text):
                u = m.group(2)
                if re.search(r"(down|pdf|file|item|user|api|convert|preview)", u, re.I):
                    print("   ", m.group(1), u[:170])
            for m in re.finditer(r"(https?://[^\"'\s<>]+\.pdf[^\"'\s<>]*)", r.text):
                print("   PDFURL:", m.group(1)[:200])
            for m in re.finditer(r"(var\s+\w+\s*=\s*['\"][^'\"]{10,200}['\"])", r.text):
                print("   JSVAR:", m.group(1)[:200])
    elif mode == "search":
        q = sys.argv[2] if len(sys.argv) > 2 else "地下水动态月报"
        for page in (1, 2, 3):
            u = f"https://m.mofile.net/search?q={quote(q)}&page={page}"
            r = get(u, f"mofile_search_{page}.html")
            if not r:
                continue
            for m in re.finditer(r'href="(/item/[^"]+)"[^>]*>(.*?)</a>', r.text, re.S):
                t = re.sub(r"<[^>]+>", "", m.group(2))
                t = re.sub(r"\s+", " ", t).strip()
                print("   ITEM:", m.group(1), t[:60])
