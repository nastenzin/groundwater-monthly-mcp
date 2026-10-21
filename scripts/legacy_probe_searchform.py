# -*- coding: utf-8 -*-
"""Find site search forms on mwr.gov.cn / xxzx.mwr.gov.cn / zzsc."""
import re
import sys
from pathlib import Path

import requests

HEAD = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
S = requests.Session()
S.headers.update(HEAD)
OUT = Path("data/legacy_probe")
OUT.mkdir(parents=True, exist_ok=True)


def get(url):
    try:
        r = S.get(url, timeout=45)
        r.encoding = "utf-8"
        return r
    except Exception as e:  # noqa: BLE001
        print("ERR", url, repr(e)[:100])
        return None


def find_forms(url, name):
    r = get(url)
    if not r:
        return
    t = r.text
    (OUT / name).write_text(t, encoding="utf-8")
    print(f"== {url} len={len(t)}")
    for m in re.finditer(r"<form[^>]*>", t, re.I):
        print("   FORM:", m.group(0)[:220])
    for m in re.finditer(r"(search[a-zA-Z0-9_\-\./]*\.(?:jsp|html|action|do)|/so/|so\.mwr|searchword|searchWord|q=)", t):
        s = m.group(0)
        if len(s) < 60:
            print("   HINT:", s)
    for m in re.finditer(r'href="([^"]*(?:search|so)[^"]*)"', t, re.I):
        print("   LINK:", m.group(1)[:150])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    find_forms("http://www.mwr.gov.cn/", "home_mwr.html")
    find_forms("http://xxzx.mwr.gov.cn/", "home_xxzx.html")
    find_forms("http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/", "newlist_home.html")
