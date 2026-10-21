# -*- coding: utf-8 -*-
"""Dump HTML tables from old 中国水资源公报 detail pages."""
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}
OUT = Path("data/bulletin/htmltables")
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
        if years and rec["year"] not in years:
            continue
        html = get(rec["detail_url"])
        s = BeautifulSoup(html, "html.parser")
        tables = s.find_all("table")
        lines = [f"YEAR {rec['year']} tables={len(tables)}"]
        for ti, tb in enumerate(tables):
            lines.append(f"\n##### TABLE {ti + 1}")
            for tr in tb.find_all("tr"):
                cells = []
                for td in tr.find_all(["td", "th"]):
                    txt = td.get_text(" ", strip=True).replace("\u3000", " ")
                    cells.append(txt)
                if any(cells):
                    lines.append("|".join(cells))
        (OUT / f"{rec['year']}.txt").write_text("\n".join(lines), encoding="utf-8")
        print(rec["year"], "tables", len(tables))


if __name__ == "__main__":
    import sys

    main([int(x) for x in sys.argv[1:]] or [1997, 2010])
