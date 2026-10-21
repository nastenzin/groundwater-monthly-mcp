# -*- coding: utf-8 -*-
"""Legacy corpus crawler: recover 2024-01..2024-09 《地下水动态月报》 text from the
official mwr.gov.cn FlipBuilder HTML5 mobile player (search_config.js textForPages),
plus verify the one reachable legacy PDF (2021-03) on xxzx.mwr.gov.cn.

Outputs:
  data/legacy/html/<YYYY-MM>/pageN.html     recovered per-page text (page1-based)
  data/legacy/html/<YYYY-MM>/raw_*.js|html  original assets kept for provenance
  data/legacy/pdfs/<YYYY-MM>.pdf            PDF when downloadable
  data/legacy_index.json                    index of recovered issues
  data/legacy_failures.json                 months that could not be recovered
"""
import io
import json
import re
import time
from pathlib import Path

import requests

ROOT = Path("data")
LEG = ROOT / "legacy"
PDF_DIR = LEG / "pdfs"
HTML_DIR = LEG / "html"
for d in (PDF_DIR, HTML_DIR):
    d.mkdir(parents=True, exist_ok=True)

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Referer": "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/",
}
S = requests.Session()
S.headers.update(HEAD)

ZZ = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/"
DETAIL_TPL = "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/t20230328_{art}.html"
# 2024-month -> xxzx detail article id (from the full archive list)
ART = {
    "2024-01": "1737669", "2024-02": "1745368", "2024-03": "1747512",
    "2024-04": "1753800", "2024-05": "1759785", "2024-06": "1767321",
    "2024-07": "1769669", "2024-08": "1775328", "2024-09": "1779876",
}


def get(url, tries=3, timeout=60):
    last = None
    for i in range(tries):
        try:
            r = S.get(url, timeout=timeout)
            if r.status_code == 200 and not (len(r.content) == 394 and "error.html" in (r.url or "")):
                return r
            last = f"HTTP {r.status_code}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)[:120]
        time.sleep(1.2 * (i + 1))
    print(f"   FAIL {url} :: {last}")
    return None


def has_cjk(s):
    return bool(re.search(r"[\u4e00-\u9fff]", s))


def parse_text_for_pages(js_text):
    m = re.search(r"var\s+textForPages\s*=\s*(\[.*?\])\s*;", js_text, re.S)
    if not m:
        return None
    arr = m.group(1)
    try:
        return json.loads(arr)
    except json.JSONDecodeError:
        pass
    # fallback: split on "," boundaries between quoted strings
    items = re.findall(r'"((?:[^"\\]|\\.)*)"', arr, re.S)
    return [bytes(i, "utf-8").decode("unicode_escape") for i in items]


def parse_total_pages(cfg_text):
    m = re.search(r"totalPageCount\s*:\s*(\[[^\]]*\])", cfg_text)
    if m:
        try:
            arr = json.loads(m.group(1))
            if arr:
                return int(arr[0])
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def crawl_flipbook(period):
    ym = period.replace("-", "")
    base = f"{ZZ}{ym}/mobile/"
    idx = get(base + "index.html")
    if idx is None:
        return None
    idx_text = idx.content.decode("utf-8", "replace")
    m = re.search(r"<title>([^<]+)</title>", idx_text)
    title = m.group(1).strip() if m else f"《地下水动态月报》{period}"

    assets = {}
    for name in ("javascript/config.js", "javascript/search_config.js", "javascript/bookmark_config.js"):
        r = get(base + name)
        if r is not None:
            assets[name] = r.content.decode("utf-8", "replace")
        time.sleep(0.3)
    if "javascript/search_config.js" not in assets:
        return None
    pages = parse_text_for_pages(assets["javascript/search_config.js"])
    if not pages:
        return None
    total = parse_total_pages(assets.get("javascript/config.js", "")) or len(pages)

    outdir = HTML_DIR / period
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "index.html").write_text(idx_text, encoding="utf-8")
    for name, body in assets.items():
        (outdir / ("raw_" + Path(name).name)).write_text(body, encoding="utf-8")

    page_files = []
    for i, text in enumerate(pages, start=1):
        text = text or ""
        html = (
            '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="utf-8" />\n'
            f"<title>{title} 第{i}页</title>\n"
            '<meta name="legacy-source" content="'
            f"{base}javascript/search_config.js" '" />\n'
            "</head>\n<body>\n"
            f'<div class="page" data-page="{i}">\n{text}\n</div>\n'
            "</body>\n</html>\n"
        )
        p = outdir / f"page{i}.html"
        p.write_text(html, encoding="utf-8")
        page_files.append(p)

    ok_pages = sum(1 for t in pages if t and has_cjk(t))
    return {
        "period": period,
        "title": title,
        "detail_url": DETAIL_TPL.format(art=ART[period]),
        "pdf_url": "",
        "local_path": str(outdir).replace("\\", "/"),
        "source": f"mwr.gov.cn FlipBuilder HTML5 移动版文本层 ({base}javascript/search_config.js)",
        "pages": len(pages),
        "total_pages_declared": total,
        "text_extractable": ok_pages > 0 and ok_pages >= max(1, len(pages) // 2),
        "note": f"官方原始 PDF/flipbook 目录仍在线但仅提供 HTML5 播放器；页面文字取自播放器搜索文本层，共 {ok_pages}/{len(pages)} 页含中文。",
        "files": [str(p).replace("\\", "/") for p in page_files],
    }


def grab_pdf_2021_03():
    """The one legacy PDF verified reachable (2021年第03期)."""
    url = "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/P020230328612580584223.pdf"
    r = None
    for i in range(3):
        try:
            r = S.get(url, timeout=120)
            if r.status_code == 200 and r.content[:4] == b"%PDF":
                break
            r = None
        except Exception:  # noqa: BLE001
            r = None
        time.sleep(2 * (i + 1))
    if r is None:
        return None
    out = PDF_DIR / "2021-03.pdf"
    out.write_bytes(r.content)
    pages = None
    extractable = False
    sample = ""
    try:
        from pypdf import PdfReader
        rd = PdfReader(io.BytesIO(r.content))
        pages = len(rd.pages)
        for i in range(1, min(4, pages)):
            t = rd.pages[i].extract_text() or ""
            if has_cjk(t):
                extractable = True
                sample = sample or t[:80].replace("\n", " ")
    except Exception as e:  # noqa: BLE001
        print("   pypdf err", repr(e)[:120])
    return {
        "period": "2021-03",
        "title": "《地下水动态月报》2021年3期",
        "detail_url": DETAIL_TPL.format(art=1675747),
        "pdf_url": url,
        "local_path": str(out).replace("\\", "/"),
        "source": "水利部信息中心 xxzx.mwr.gov.cn（残留官方 PDF 附件）",
        "pages": pages,
        "text_extractable": extractable,
        "note": f"官方 xxzx 文章目录下残留 PDF 附件，pypdf 校验页数={pages}，抽查含中文={extractable}；样例：{sample[:60]}",
    }


def main():
    index = []
    failures = []
    for month in range(1, 10):
        period = f"2024-{month:02d}"
        print(f"== {period}")
        rec = crawl_flipbook(period)
        if rec:
            print(f"   OK pages={rec['pages']} extractable={rec['text_extractable']} {rec['title']}")
            index.append(rec)
        else:
            failures.append({
                "period": period,
                "reason": "官方 flipbook 已删除（zzsc 目录 404）或文本层缺失",
                "tried": [f"{ZZ}{period.replace('-', '')}/mobile/javascript/search_config.js"],
            })

    rec = grab_pdf_2021_03()
    if rec:
        print(f"== 2021-03 PDF ok pages={rec['pages']} extractable={rec['text_extractable']}")
        index.append(rec)
    else:
        failures.append({"period": "2021-03", "reason": "PDF 下载失败", "tried": [
            "http://xxzx.mwr.gov.cn/swszyjcpj/dxsjcpj/202303/P020230328612580584223.pdf"]})

    index.sort(key=lambda r: r["period"])
    (ROOT / "legacy_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "legacy_failures.json").write_text(
        json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote index={len(index)} failures={len(failures)}")


if __name__ == "__main__":
    main()
