# -*- coding: utf-8 -*-
"""Dump all tables from a docx with caption context."""
import sys
from pathlib import Path

from docx import Document
import json

path = Path(sys.argv[1])
doc = Document(path)
out = []
for ti, tb in enumerate(doc.tables):
    out.append(f"##### TABLE {ti + 1} rows={len(tb.rows)} cols={len(tb.columns)}")
    for row in tb.rows:
        cells = [c.text.replace("\n", " ").strip() for c in row.cells]
        out.append("|".join(cells))
dest = Path(sys.argv[2])
dest.write_text("\n".join(out), encoding="utf-8")
print("written", dest, len(doc.tables))
