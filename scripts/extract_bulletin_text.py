# -*- coding: utf-8 -*-
"""Extract text from 中国水资源公报 attachments (pdf/docx/doc) to text dumps."""
import glob
import json
import subprocess
import sys
from pathlib import Path

OUT = Path("data/bulletin")
TXT = OUT / "text"
TXT.mkdir(parents=True, exist_ok=True)
idx = json.loads((OUT / "bulletin_index.json").read_text(encoding="utf-8"))


def dump_pdf(path, dest):
    import fitz

    doc = fitz.open(path)
    parts = []
    for i, page in enumerate(doc):
        parts.append(f"\n===== PAGE {i + 1} =====\n")
        parts.append(page.get_text("text"))
    doc.close()
    dest.write_text("".join(parts), encoding="utf-8")
    return len(parts)


def dump_docx(path, dest):
    from docx import Document

    doc = Document(path)
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.oxml.ns import qn

    def iter_block(parent):
        body = parent.element.body
        for child in body.iterchildren():
            if child.tag == qn("w:p"):
                yield Paragraph(child, parent)
            elif child.tag == qn("w:tbl"):
                yield Table(child, parent)

    parts = []
    for block in iter_block(doc):
        if isinstance(block, Table):
            parts.append("\n[TABLE]")
            for row in block.rows:
                cells = []
                for c in row.cells:
                    cells.append(c.text.replace("\n", " ").strip())
                parts.append("|".join(cells))
            parts.append("[/TABLE]\n")
        else:
            t = block.text.strip()
            if t:
                parts.append(t)
    dest.write_text("\n".join(parts), encoding="utf-8")
    return len(parts)


def dump_doc(path, dest):
    """Convert .doc to .docx with Word COM, then reuse docx dumper."""
    import win32com.client  # type: ignore

    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        d = word.Documents.Open(str(Path(path).resolve()), ReadOnly=True)
        tmp = dest.with_suffix(".converted.docx")
        d.SaveAs2(str(tmp.resolve()), FileFormat=16)
        d.Close(False)
    finally:
        word.Quit()
    return dump_docx(str(tmp), dest)


def main(years):
    for rec in idx:
        if years and rec["year"] not in years:
            continue
        for f in rec.get("local_files") or []:
            p = Path(f["path"])
            ext = p.suffix.lower()
            dest = TXT / f"{rec['year']}{ext}.txt"
            if ext == ".pdf":
                n = dump_pdf(p, dest)
            elif ext == ".docx":
                n = dump_docx(p, dest)
            elif ext == ".doc":
                try:
                    n = dump_doc(p, dest)
                except Exception as exc:  # noqa: BLE001
                    print("doc fail", rec["year"], repr(exc))
                    continue
            else:
                continue
            print(rec["year"], p.name, dest.name, "blocks", n, "chars", dest.stat().st_size)


if __name__ == "__main__":
    main([int(x) for x in sys.argv[1:]])
