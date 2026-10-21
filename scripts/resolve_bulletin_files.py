# -*- coding: utf-8 -*-
"""Resolve per-year attachment (pdf/docx/jpg) for 中国水资源公报 and download."""
import argparse
import json
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}
OUT = Path("data/bulletin")
PDF_DIR = OUT / "files"
PDF_DIR.mkdir(parents=True, exist_ok=True)


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


def resolve(rec):
    html = get(rec["detail_url"])
    s = BeautifulSoup(html, "html.parser")
    links = []
    for a in s.find_all("a"):
        h = (a.get("href") or "").strip()
        if re.search(r"\.(pdf|docx?|xlsx?|zip|rar)$", h, re.I):
            links.append(requests.compat.urljoin(rec["detail_url"], h))
    if not links:
        for m in re.finditer(r'href="([^"]+\.pdf)"', html):
            links.append(requests.compat.urljoin(rec["detail_url"], m.group(1)))
    imgs = [requests.compat.urljoin(rec["detail_url"], m.group(1)) for m in re.finditer(r'(?:src|href)="\.?/?(W0202\d+\.jpg)"', html)]
    # de-dup keep order
    out = []
    for u in links + imgs:
        if u not in out:
            out.append(u)
    return out


def head_size(url):
    try:
        r = requests.head(url, timeout=30, headers=HEAD, allow_redirects=True)
        return int(r.headers.get("Content-Length") or 0)
    except Exception:  # noqa: BLE001
        return 0


def main():
    idx = json.loads((OUT / "bulletin_index.json").read_text(encoding="utf-8"))
    for rec in idx:
        if rec.get("attachments") is None:
            try:
                rec["attachments"] = resolve(rec)
            except Exception as exc:  # noqa: BLE001
                print("resolve fail", rec["year"], repr(exc))
                rec["attachments"] = []
            for u in rec["attachments"]:
                print(rec["year"], u, head_size(u))
    (OUT / "bulletin_index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
