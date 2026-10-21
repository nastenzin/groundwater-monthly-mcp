# -*- coding: utf-8 -*-
"""Finalize the legacy corpus: add the verified 2023-12 PDF, rebuild index/failures, print stats."""
import io
import json
import shutil
from pathlib import Path

from pypdf import PdfReader

ROOT = Path("data")
LEG = ROOT / "legacy"
PDF_DIR = LEG / "pdfs"
INDEX = ROOT / "legacy_index.json"
FAILS = ROOT / "legacy_failures.json"
PROBE = ROOT / "legacy" / "probe"


def has_cjk(s):
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def add_pdf(src: Path, period: str, title: str, pdf_url: str, detail_url: str, source: str, note: str):
    dst = PDF_DIR / f"{period}.pdf"
    if src.exists():
        shutil.copyfile(src, dst)
    if not dst.exists():
        return None
    data = dst.read_bytes()
    rd = PdfReader(io.BytesIO(data))
    pages = len(rd.pages)
    extractable = False
    sample = ""
    for i in range(1, min(5, pages)):
        t = rd.pages[i].extract_text() or ""
        if has_cjk(t):
            extractable = True
            sample = sample or t[:60].replace("\n", " ")
    return {
        "period": period,
        "title": title,
        "detail_url": detail_url,
        "pdf_url": pdf_url,
        "local_path": str(dst).replace("\\", "/"),
        "source": source,
        "pages": pages,
        "text_extractable": extractable,
        "note": f"pypdf 校验页数={pages}，抽查含中文={extractable}；样例：{sample}。{note}",
    }


def main():
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    index = [r for r in index if r["period"] != "2023-12"]

    rec = add_pdf(
        PROBE / "p202403.pdf",
        "2023-12",
        "《地下水动态月报》2023年12期",
        "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202403/P020240302854010824506.pdf",
        "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202403/t20240302_1734366.html",
        "水利部信息中心 xxzx.mwr.gov.cn（残留官方 PDF 附件，目录 202403/，上传日 2024-03-02 对应 2023年12期）",
        "官方新版站点同名 PDF 已 404，此份为 xxzx 旧附件残留。",
    )
    if rec:
        index.append(rec)

    index.sort(key=lambda r: r["period"])
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

    if FAILS.exists():
        failures = json.loads(FAILS.read_text(encoding="utf-8"))
    else:
        failures = []
    have = {r["period"] for r in index}
    failures = [f for f in failures if f["period"] not in have]
    # record every unrecovered month of the 2019-01..2024-09 target window
    y, m = 2019, 1
    while (y, m) <= (2024, 9):
        p = f"{y}-{m:02d}"
        if p not in have and not any(f["period"] == p for f in failures):
            failures.append({
                "period": p,
                "reason": "官方原始资源已下线：zzsc flipbook 目录统一 404、新版站点 PDF 目录已删除、旧 PDF 附件文件名不可枚举",
                "tried": [
                    f"http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/{y}{m:02d}/",
                    f"http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/{y}{m:02d}/",
                    "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/ (详情页仅剩 iframe，附件目录无索引)",
                ],
            })
        m += 1
        if m > 12:
            m = 1
            y += 1
    failures.sort(key=lambda f: f["period"])
    FAILS.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")

    # stats
    years = {}
    pdf_sizes = []
    for r in index:
        years[r["period"][:4]] = years.get(r["period"][:4], 0) + 1
        p = Path(r["local_path"])
        if p.is_file():
            pdf_sizes.append(p.stat().st_size)
        elif p.is_dir():
            pdf_sizes.append(sum(f.stat().st_size for f in p.rglob("*") if f.is_file()))
    ext = sum(1 for r in index if r.get("text_extractable"))
    print("index entries:", len(index), "failures:", len(failures))
    print("per year:", dict(sorted(years.items())))
    print("text_extractable:", ext, "/", len(index))
    print("total bytes:", sum(pdf_sizes))
    print("pages:", {r["period"]: r["pages"] for r in index})


if __name__ == "__main__":
    main()
