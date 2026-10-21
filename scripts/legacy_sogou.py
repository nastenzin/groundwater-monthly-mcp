# -*- coding: utf-8 -*-
"""Sogou harvester: search queries, resolve redirect links, extract PDF/detail URLs."""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote, urljoin

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


def sogou_page(q, page=1):
    url = "https://www.sogou.com/web?query=" + quote(q) + (f"&page={page}" if page > 1 else "")
    try:
        r = S.get(url, timeout=45, headers={"Referer": "https://www.sogou.com/"})
    except Exception as e:  # noqa: BLE001
        print("ERR", repr(e)[:100])
        return None, []
    r.encoding = "utf-8"
    t = r.text
    if "请输入验证码" in t or "antispider" in t:
        print("  !! sogou captcha")
        return r, []
    res = []
    for m in re.finditer(r'<h3[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', t, re.S):
        href = urljoin("https://www.sogou.com", m.group(1))
        ttl = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        res.append((ttl, href))
    return r, res


def resolve(href, referer="https://www.sogou.com/web"):
    if "/link?url=" not in href:
        return href
    try:
        r = S.get(href, timeout=30, allow_redirects=True, headers={"Referer": referer})
        r.encoding = "utf-8"
        if r.url and "/link?url=" not in r.url:
            return r.url
        m = re.search(r'(?:URL|url)\s*=\s*([^"\'>\s]+)', r.text)
        if m:
            return m.group(1)
    except Exception:  # noqa: BLE001
        pass
    return href


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    queries = sys.argv[1:]
    all_rows = []
    for q in queries:
        print(f"===== {q}")
        for page in (1, 2):
            r, res = sogou_page(q, page)
            if not res:
                break
            for ttl, href in res:
                real = resolve(href)
                row = {"q": q, "title": ttl, "real": real}
                all_rows.append(row)
                mark = "PDF" if re.search(r"\.pdf", real, re.I) else "   "
                print(f"   [{mark}] {ttl[:62]} | {real[:150]}")
                time.sleep(0.15)
            time.sleep(0.6)
    (OUT / "sogou_results.json").write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("saved", len(all_rows))
