# -*- coding: utf-8 -*-
"""Download resolved 中国水资源公报 attachments."""
import json
import sys
import time
from pathlib import Path

import requests

HEAD = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0", "Referer": "http://www.mwr.gov.cn/sj/"}
OUT = Path("data/bulletin")
FILES = OUT / "files"
FILES.mkdir(parents=True, exist_ok=True)

idx = json.loads((OUT / "bulletin_index.json").read_text(encoding="utf-8"))


def fetch(url, dest):
    if dest.exists() and dest.stat().st_size > 20000:
        return dest.stat().st_size, False
    for attempt in range(3):
        try:
            with requests.get(url, timeout=300, headers=HEAD, stream=True) as r:
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
                tmp.replace(dest)
            return dest.stat().st_size, True
        except Exception as exc:  # noqa: BLE001
            print("  retry", attempt, repr(exc))
            time.sleep(3)
    return 0, False


def main(years):
    for rec in idx:
        if years and rec["year"] not in years:
            continue
        atts = rec.get("attachments") or []
        rec["local_files"] = []
        for u in atts:
            name = u.rsplit("/", 1)[-1]
            dest = FILES / f"{rec['year']}_{name}"
            size, new = fetch(u, dest)
            rec["local_files"].append({"url": u, "path": str(dest.as_posix()), "bytes": size})
            print(rec["year"], name, size, "new" if new else "cached")
    (OUT / "bulletin_index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    years = [int(x) for x in sys.argv[1:]]
    main(years)
