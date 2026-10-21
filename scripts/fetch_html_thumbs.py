# -*- coding: utf-8 -*-
"""Fetch thumbnail page images for HTML periods from the live flipbook."""
import re
import sys
import urllib.request
from pathlib import Path

PERIODS = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05",
           "2024-06", "2024-07", "2024-08", "2024-09"]
BASE = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/{yyyymm}/files/thumb/{page}.jpg"
OUT = Path("data/surface/html")

MAP_PAGES = [7, 9, 11, 13, 15, 18, 19, 21, 22, 23, 24, 25, 26, 27]


def fetch(url: str, dest: Path) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


def main() -> None:
    periods = sys.argv[1:] or PERIODS
    ok = 0
    for period in periods:
        yyyymm = period.replace("-", "")
        for page in MAP_PAGES:
            dest = OUT / period / f"p{page}.jpg"
            if dest.exists() and dest.stat().st_size > 5000:
                ok += 1
                continue
            try:
                n = fetch(BASE.format(yyyymm=yyyymm, page=page), dest)
                print(f"{period} p{page}: {n} B")
                ok += 1
            except Exception as exc:  # noqa: BLE001
                print(f"{period} p{page}: ERR {exc}")
    print("downloaded/kept:", ok)


if __name__ == "__main__":
    main()
