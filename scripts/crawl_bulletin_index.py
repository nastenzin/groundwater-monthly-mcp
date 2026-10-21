# -*- coding: utf-8 -*-
"""Crawl MWR annual water-resources bulletin index and collect PDF links."""
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}
BASE = "http://www.mwr.gov.cn/sj/tjgb/szygb/"
OUT = Path("data/bulletin")
OUT.mkdir(parents=True, exist_ok=True)


def get(url):
    r = requests.get(url, timeout=40, headers=HEAD)
    r.raise_for_status()
    raw = r.content
    try:
        t = raw.decode("utf-8")
        if t.count("\ufffd") < 5:
            return t
    except UnicodeDecodeError:
        pass
    return raw.decode("gb18030", "replace")


def index_pages():
    """Return list of index page URLs (index_N.html style pagination)."""
    urls = [BASE]
    html = get(BASE)
    s = BeautifulSoup(html, "html.parser")
    n = 1
    for a in s.find_all("a"):
        href = a.get("href") or ""
        m = re.search(r"(index_(\d+)\.html)", href)
        if m:
            n = max(n, int(m.group(2)))
    print("max page", n)
    for i in range(1, n + 1):
        urls.append(BASE + f"index_{i}.html")
    return urls


def entries():
    found = {}
    for url in index_pages():
        try:
            html = get(url)
        except Exception as exc:  # noqa: BLE001
            print("idx fail", url, repr(exc))
            continue
        s = BeautifulSoup(html, "html.parser")
        for a in s.find_all("a"):
            txt = a.get_text(" ", strip=True)
            href = a.get("href") or ""
            m = re.match(r"(\d{4})年中国水资源公报", txt)
            if m and href.endswith(".html"):
                year = int(m.group(1))
                found.setdefault(year, requests.compat.urljoin(url, href))
        time.sleep(0.4)
    return found


def pdf_for(detail_url):
    html = get(detail_url)
    s = BeautifulSoup(html, "html.parser")
    for a in s.find_all("a"):
        href = a.get("href") or ""
        if ".pdf" in href.lower():
            return requests.compat.urljoin(detail_url, href)
    # some pages embed iframe / script links
    for m in re.finditer(r"(https?://[^\"'\s]+\.pdf|P0[0-9A-Za-z]+\.pdf)", html):
        return requests.compat.urljoin(detail_url, m.group(1))
    return None


def main():
    found = entries()
    print("years", sorted(found))
    index_path = OUT / "bulletin_index.json"
    old = {}
    if index_path.exists():
        old = {r["year"]: r for r in json.loads(index_path.read_text(encoding="utf-8"))}
    records = []
    for year in sorted(found):
        url = found[year]
        rec = old.get(year, {})
        if rec.get("pdf_url"):
            records.append(rec)
            continue
        rec = {"year": year, "title": f"{year}年中国水资源公报", "detail_url": url}
        try:
            rec["pdf_url"] = pdf_for(url)
        except Exception as exc:  # noqa: BLE001
            print("pdf fail", year, repr(exc))
            rec["pdf_url"] = None
        print(year, rec["pdf_url"])
        records.append(rec)
        time.sleep(0.4)
    index_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
