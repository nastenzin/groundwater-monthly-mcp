# -*- coding: utf-8 -*-
"""Download《中国水文年报》(annual hydrological report) PDFs from mwr.gov.cn."""
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}
PAGES = {
    2025: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202607/t20260724_2135937.html",
    2024: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202510/t20251001_2037173.html",
    2023: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202510/t20251001_2037172.html",
    2022: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202510/t20251001_2037171.html",
    2021: "http://www.mwr.gov.cn/sj/tjgb/zgswnb/202510/t20251001_2037170.html",
}
OUT = Path("data/annual")
PDF_DIR = OUT / "pdfs"
OUT.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)


def main():
    records = []
    for year, url in PAGES.items():
        r = requests.get(url, timeout=40, headers=HEAD)
        r.encoding = "utf-8"
        s = BeautifulSoup(r.text, "html.parser")
        title = s.title.get_text(strip=True) if s.title else f"{year}中国水文年报"
        pdf = None
        for a in s.find_all("a"):
            h = a.get("href") or ""
            if ".pdf" in h.lower():
                pdf = requests.compat.urljoin(url, h)
                break
        if not pdf:
            print("NO PDF", year, url)
            continue
        dest = PDF_DIR / f"{year}.pdf"
        if not (dest.exists() and dest.stat().st_size > 1_000_000):
            for attempt in range(3):
                try:
                    with requests.get(pdf, timeout=180, headers=HEAD, stream=True) as resp:
                        resp.raise_for_status()
                        tmp = dest.with_suffix(".part")
                        with open(tmp, "wb") as f:
                            for chunk in resp.iter_content(1 << 16):
                                f.write(chunk)
                        tmp.replace(dest)
                    break
                except Exception as exc:  # noqa: BLE001
                    print("retry", year, attempt, repr(exc))
                    time.sleep(3)
        size = dest.stat().st_size if dest.exists() else 0
        print(year, title, pdf, size)
        records.append(
            {
                "year": year,
                "title": title,
                "detail_url": url,
                "pdf_url": pdf,
                "local_path": str(dest.as_posix()),
                "bytes": size,
            }
        )
        time.sleep(1)
    (OUT / "annual_index.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
