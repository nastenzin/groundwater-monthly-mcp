# -*- coding: utf-8 -*-
"""Debug: dump detected columns, header text and first data rows for a table page."""
import sys

sys.path.insert(0, "scripts")
import parse_bulletin_pdf as P
import pymupdf

pdf, pno = sys.argv[1], int(sys.argv[2])
doc = pymupdf.open(pdf)
page = doc[pno - 1]
for t in page.find_tables().tables:
    cols, rows = P.table_rows(page, t)
    cap = P.caption_above(page, t.bbox[1])
    kind = P.classify(cap[0] if cap else "")
    print("bbox", t.bbox, "kind", kind, "cols", len(cols))
    print("cols", [(round(a, 1), round(b, 1)) for a, b in cols])
    for i, row in enumerate(rows[:8]):
        print(i, [c[:14] for c in row[2]])
doc.close()
