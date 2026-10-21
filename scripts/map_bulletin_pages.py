# -*- coding: utf-8 -*-
"""Map bulletin PDF pages -> table captions detected on each page."""
import json
import re
import sys
from pathlib import Path

import pymupdf

OUT = Path("data/bulletin")
idx = json.loads((OUT / "bulletin_index.json").read_text(encoding="utf-8"))


def main(years):
    lines = []
    for rec in idx:
        if years and rec["year"] not in years:
            continue
        pdfs = [f["path"] for f in rec.get("local_files") or [] if f["path"].endswith(".pdf")]
        for p in pdfs:
            doc = pymupdf.open(p)
            lines.append(f"==== {rec['year']} {Path(p).name} pages={doc.page_count}")
            for pno in range(doc.page_count):
                page = doc[pno]
                text = page.get_text("text", sort=True)
                caps = re.findall(r"表\s*\d+[^\n]{0,50}", text)
                nt = len(page.find_tables().tables)
                if caps or nt:
                    lines.append(f"  p{pno + 1} tables={nt} caps={caps[:4]}")
            doc.close()
    dest = OUT / "probe" / "page_map.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines), encoding="utf-8")
    print("written", dest)


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]])
