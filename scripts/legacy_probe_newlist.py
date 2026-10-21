# -*- coding: utf-8 -*-
"""Check pagination on the new-site dxsdtyb column + old detail raw html for attachment links."""
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)
OUT = Path("data/legacy_probe")
OUT.mkdir(parents=True, exist_ok=True)


def get(url):
    try:
        r = S.get(url, timeout=45)
        r.encoding = "utf-8"
        return r
    except Exception as e:  # noqa: BLE001
        print("ERR", url, repr(e)[:110])
        return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    if mode == "list":
        for suf in ["", "index_1.html", "index_2.html", "index_3.html"]:
            url = "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/" + suf
            r = get(url)
            if r is None:
                continue
            bad = "error.html" in (r.url or "")
            t = r.text
            (OUT / f"newlist_{suf or 'index.html'}").write_text(t, encoding="utf-8")
            s = BeautifulSoup(t, "html.parser")
            items = [
                (a.get_text(strip=True), a.get("href"))
                for a in s.find_all("a")
                if re.search(r"地下水动态月报|月报", a.get_text(strip=True))
            ]
            print(f"== {url} len={len(t)} bad={bad} items={len(items)}")
            for t2, h in items[:25]:
                print("   ", t2, "|", h)
            for m in re.findall(r"(createPageHTML\([^)]*\)|countPage\s*=\s*\d+)", t):
                print("   PAGER:", m)
    elif mode == "detail":
        url = sys.argv[2]
        r = get(url)
        if r:
            print(f"== {url} len={len(r.content)} final={r.url}")
            t = r.text
            for m in re.finditer(r'[^"\'\s]*P0\d+\.pdf[^"\'\s]*', t):
                print("   PDFREF:", m.group(0))
            for m in re.finditer(r"(附件|download|P0\d{10})", t):
                print("   HIT:", m.group(0))
            # any script vars with urls
            for m in re.finditer(r"(iframe[^>]*>|src\s*=\s*[\"'][^\"']+[\"'])", t):
                print("   SRC:", m.group(0)[:160])
