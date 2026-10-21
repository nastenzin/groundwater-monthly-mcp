# -*- coding: utf-8 -*-
"""Dump narrative text of 中国水资源公报 HTML pages (1997-2014 era)."""
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}
OUT = Path("data/bulletin/text")
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


def main():
    for rec in idx:
        dest = OUT / f"{rec['year']}.html.txt"
        if dest.exists() and dest.stat().st_size > 500:
            continue
        html = get(rec["detail_url"])
        s = BeautifulSoup(html, "html.parser")
        nodes = s.select(".TRS_Editor") or s.select("#zoom") or [s.body]
        parts = []
        for node in nodes:
            for el in node.find_all(["p", "div", "td", "h1", "h2", "h3", "h4", "table", "tr"]):
                if el.name == "table":
                    continue
                txt = el.get_text(" ", strip=True).replace("\u3000", " ")
                if txt:
                    parts.append(txt)
        # fallback: whole text
        body = "\n".join(parts)
        if len(body) < 300:
            body = s.body.get_text("\n", strip=True)
        dest.write_text(body, encoding="utf-8")
        print(rec["year"], len(body))


if __name__ == "__main__":
    main()
