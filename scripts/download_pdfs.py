# -*- coding: utf-8 -*-
"""Download report PDFs into data/pdfs/ and record metadata."""
import json
import time
from pathlib import Path

import requests

OUT = Path("data")
PDF_DIR = OUT / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)
HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/",
}
S = requests.Session()
S.headers.update(HEAD)


def download(url, dest, tries=3):
    if dest.exists() and dest.stat().st_size > 10000:
        return dest.stat().st_size
    last = None
    for i in range(tries):
        try:
            with S.get(url, timeout=60, stream=True) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
                tmp.replace(dest)
                return dest.stat().st_size
        except Exception as e:  # noqa: BLE001
            last = repr(e)
            time.sleep(2 + 2 * i)
    raise RuntimeError(f"{url}: {last}")


def main():
    records = json.loads((OUT / "report_index.json").read_text(encoding="utf-8"))
    for rec in records:
        dest = PDF_DIR / f"{rec['period']}.pdf"
        try:
            size = download(rec["pdf_url"], dest)
            rec["pdf_file"] = str(dest.as_posix())
            rec["pdf_bytes"] = size
            print(rec["period"], size)
        except Exception as e:  # noqa: BLE001
            print("FAIL", rec["period"], e)
        time.sleep(0.5)
    (OUT / "report_index.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
