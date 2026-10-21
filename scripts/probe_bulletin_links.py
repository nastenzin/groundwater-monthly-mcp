# -*- coding: utf-8 -*-
"""List all href/src and P0... strings for bulletin detail pages (raw)."""
import json
import re
from pathlib import Path

import requests

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}
idx = json.loads(Path("data/bulletin/bulletin_index.json").read_text(encoding="utf-8"))
OUT = Path("data/bulletin/probe")
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


def main(years):
    lines = []
    for rec in idx:
        if rec["year"] not in years:
            continue
        html = get(rec["detail_url"])
        lines.append(f"==== {rec['year']} {rec['detail_url']}")
        for m in re.finditer(r'(?:href|src)="([^"]+)"', html):
            h = m.group(1)
            if re.search(r"\.(pdf|docx?|xlsx?|zip|rar|jpg|png)$", h, re.I) or "P0" in h:
                lines.append(f"  ATTR {h}")
        for m in re.finditer(r"P0202\d+\.\w+", html):
            lines.append(f"  P0 {m.group(0)}")
        for m in re.finditer(r"(下载|附件)[^<]{0,40}", html):
            lines.append(f"  TXT {m.group(0)}")
    (OUT / "links.txt").write_text("\n".join(lines), encoding="utf-8")
    print("written", len(lines))


if __name__ == "__main__":
    import sys

    years = [int(x) for x in sys.argv[1:]] or list(range(1997, 2026))
    main(years)
