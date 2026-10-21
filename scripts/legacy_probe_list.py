# -*- coding: utf-8 -*-
"""Dump the xxzx list page raw HTML + pagination links for inspection."""
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
S = requests.Session()
S.headers.update(HEAD)
OUT = Path("data/legacy_probe")
OUT.mkdir(parents=True, exist_ok=True)


def get(url, tries=3, timeout=45):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, timeout=timeout)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)[:150]
    print(f"FAIL {url} :: {last}")
    return None


def detect_enc(r):
    """Return text using declared charset from headers/meta."""
    raw = r.content
    for enc in ("utf-8", "gb18030"):
        try:
            t = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if "charset=gb" in t[:2000].lower() or enc == "utf-8":
            return t, enc
    return raw.decode("gb18030", "replace"), "gb18030"


def main():
    base = "http://xxzx.mwr.gov.cn/xxgk/gbjb/dxsdtyb/"
    for suf in ["", "index_1.html", "index_2.html"]:
        url = base + suf
        r = get(url)
        if r is None:
            continue
        text, enc = detect_enc(r)
        name = (suf or "index.html").replace("/", "_")
        (OUT / f"xxzx_{name}").write_text(text, encoding="utf-8")
        s = BeautifulSoup(text, "html.parser")
        links = []
        for a in s.find_all("a"):
            t = a.get_text(strip=True)
            h = a.get("href") or ""
            links.append((t, h))
        print(f"== {url} enc={enc} bytes={len(r.content)} links={len(links)}")
        # page-number / pagination hints
        for t, h in links:
            if re.search(r"(index_\d+|下一页|尾页|totalpage|createPageHTML)", h + t):
                print(f"   PAGER: {t!r} -> {h}")
        m = re.findall(r"(createPageHTML\([^)]*\)|var\s+countPage\s*=\s*\d+|totalPage\s*=\s*\d+)", text)
        if m:
            print("   PAGERJS:", m[:5])
        for t, h in links:
                if "月报" in t or "地下水" in t or re.search(r"t\d{8}_\d+\.html", h):
                    print(f"   ITEM: {t} -> {h}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
