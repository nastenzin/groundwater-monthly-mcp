# -*- coding: utf-8 -*-
"""Probe xxzx GET search, robots/sitemap, and flipbook 2024 coverage + SWF text check."""
import io
import re
import sys
import zlib
from pathlib import Path

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)
OUT = Path("data/legacy_probe")
OUT.mkdir(parents=True, exist_ok=True)


def get(url, timeout=60):
    try:
        r = S.get(url, timeout=timeout, allow_redirects=True)
    except Exception as e:  # noqa: BLE001
        print(f"ERR {url} :: {repr(e)[:100]}")
        return None
    bad = len(r.content) == 394 and "error.html" in (r.url or "")
    print(f"[{r.status_code}] len={len(r.content)} {'BAD ' if bad else ''}{r.url}")
    return r


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    if mode == "misc":
        for u in [
            "http://xxzx.mwr.gov.cn/robots.txt",
            "http://xxzx.mwr.gov.cn/sitemap.xml",
            "http://www.mwr.gov.cn/robots.txt",
            "http://www.mwr.gov.cn/sitemap.xml",
        ]:
            r = get(u)
            if r and len(r.content) < 5000:
                print("   ", r.text[:800].replace("\n", " "))
    elif mode == "getsearch":
        from urllib.parse import quote
        kw = quote("地下水动态月报")
        for u in [
            f"http://xxzx.mwr.gov.cn/WebSearch/action/Search/search?queryObj.keywords={kw}&queryObj.siteid=131",
            f"http://xxzx.mwr.gov.cn/WebSearch/action/Search/search?queryObj.keywords={kw}",
        ]:
            r = get(u, timeout=120)
            if r:
                (OUT / "xxzx_getsearch.html").write_text(r.text, encoding="utf-8", errors="replace")
                for m in re.finditer(r'href="([^"]+)"', r.text):
                    u2 = m.group(1)
                    if re.search(r"(P0\d+\.pdf|t\d{8}_\d+\.html)", u2):
                        print("   LINK:", u2[:170])
    elif mode == "zz2024":
        ZZ = "http://www.mwr.gov.cn/zzsc/tjgb/dxsdtyb/"
        for mth in range(1, 13):
            key = f"2024{mth:02d}"
            r = get(ZZ + key + "/")
            if r and not (len(r.content) == 394):
                print(f"   {key} EXISTS {len(r.content)}")
    elif mode == "swftext":
        b = Path("data/legacy_probe/swf/bookContent_dec.swf").read_bytes()
        print("bytes", len(b))
        # JPEG markers
        print("JPEG SOI count:", b.count(b"\xff\xd8\xff"))
        # look for UTF-8 chinese sequences
        cnt = len(re.findall(rb"[\xe4-\xe9][\x80-\xbf]{2}", b))
        print("utf8-cjk candidate bytes:", cnt)
        for kw in ["地下水".encode(), "月报".encode(), "水位".encode()]:
            print(kw.decode(errors="replace"), "->", b.count(kw))
        # also check strings with .jpg
        for m in re.finditer(rb"[ -~]{5,60}\.jpg", b):
            print("   jpg ref:", m.group(0)[:80])
