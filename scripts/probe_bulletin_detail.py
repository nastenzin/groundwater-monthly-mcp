# -*- coding: utf-8 -*-
"""Inspect bulletin detail pages: dump links + main HTML to files."""
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}
OUT = Path("data/bulletin/probe")
OUT.mkdir(parents=True, exist_ok=True)
idx = json.loads(Path("data/bulletin/bulletin_index.json").read_text(encoding="utf-8"))


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


def main(years):
    for rec in idx:
        if rec["year"] not in years:
            continue
        url = rec["detail_url"]
        html = get(url)
        s = BeautifulSoup(html, "html.parser")
        lines = [f"URL {url}", f"len {len(html)}"]
        for a in s.find_all("a"):
            h = (a.get("href") or "").strip()
            t = a.get_text(" ", strip=True)
            if h and (re.search(r"\.(pdf|docx?|xlsx?|zip|rar)$", h, re.I) or "P0" in h):
                lines.append(f"LINK {t} -> {h}")
        # candidate containers
        for sel in ["#zoom", "#content", ".TRS_Editor", ".article", "#article", ".content", ".v_news_content", "#text", ".pages_content"]:
            node = s.select_one(sel)
            if node:
                txt = node.get_text("\n", strip=True)
                lines.append(f"--- SEL {sel} len {len(txt)}")
                lines.append(txt[:200000])
        body = s.body.get_text("\n", strip=True) if s.body else ""
        lines.append(f"--- BODY len {len(body)}")
        lines.append(body[:200000])
        (OUT / f"{rec['year']}.txt").write_text("\n".join(lines), encoding="utf-8")
        print(rec["year"], "ok", len(html))


if __name__ == "__main__":
    import sys

    years = [int(x) for x in sys.argv[1:]] or [1997, 2001, 2010, 2014]
    main(years)
