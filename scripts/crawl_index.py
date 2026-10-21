# -*- coding: utf-8 -*-
"""Crawl the mwr.gov.cn 地下水动态月报 index and collect (title, month, detail URL, PDF URL)."""
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/"
HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
OUT = Path("data")
OUT.mkdir(exist_ok=True)
S = requests.Session()
S.headers.update(HEAD)


def get(url, tries=3, timeout=40):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, timeout=timeout)
            r.encoding = "utf-8"
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"FAILED {url}: {last}")


def month_of(title):
    m = re.search(r"(\d{4})年\s*(\d{1,2})月", title)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def main():
    reports = {}
    page = 0
    pages = [""] + [f"index_{i}.html" for i in range(1, 12)]
    for suffix in pages:
        url = BASE + suffix
        try:
            r = get(url)
        except RuntimeError as e:
            print("skip", e)
            continue
        s = BeautifulSoup(r.text, "html.parser")
        items = []
        for a in s.find_all("a"):
            t = a.get_text(strip=True)
            if re.match(r"《地下水动态月报》\s*\d{4}年", t):
                href = a.get("href")
                items.append((t, href))
        print(url, "items", len(items))
        if not items:
            break
        for t, href in items:
            key = month_of(t)
            if key is None:
                continue
            detail = requests.compat.urljoin(url, href)
            reports[key] = {"title": t, "detail_url": detail}
        page += 1
        time.sleep(0.6)

    print("reports found:", len(reports))
    # fetch detail pages for PDF link
    for key in sorted(reports, reverse=True):
        rec = reports[key]
        try:
            r = get(rec["detail_url"])
        except RuntimeError as e:
            print("detail fail", e)
            continue
        s = BeautifulSoup(r.text, "html.parser")
        pdf = None
        pub = None
        for a in s.find_all("a"):
            h = a.get("href") or ""
            if ".pdf" in h.lower():
                pdf = requests.compat.urljoin(rec["detail_url"], h)
                break
        m = re.search(r'name="PubDate" content="([^"]+)"', r.text)
        if m:
            pub = m.group(1)
        rec["pdf_url"] = pdf
        rec["publish_date"] = pub
        rec["period"] = f"{key[0]}-{key[1]:02d}"
        print(rec["period"], "pdf:", pdf, "pub:", pub)
        time.sleep(0.4)

    data = [
        {**v, "year": k[0], "month": k[1]}
        for k, v in sorted(reports.items(), reverse=True)
    ]
    (OUT / "report_index.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("wrote", len(data), "records")


if __name__ == "__main__":
    main()
