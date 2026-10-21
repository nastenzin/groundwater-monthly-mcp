# -*- coding: utf-8 -*-
"""Enumerate captured URLs via Common Crawl index (works without archive.org)."""
import json
import sys

import requests

HEAD = {"User-Agent": "legacy-corpus-research/1.0 (+contact: local)"}
S = requests.Session()
S.headers.update(HEAD)
BASE = "https://index.commoncrawl.org/"


def collections():
    r = S.get(BASE + "collinfo.json", timeout=60)
    data = r.json()
    return [c["id"] for c in data]


def query(coll, url, limit=1000, page=0, page_size=5):
    params = {
        "url": url,
        "output": "json",
        "limit": limit,
    }
    if page:
        params["page"] = page
        params["pageSize"] = page_size
    r = S.get(f"{BASE}{coll}-index", params=params, timeout=120)
    if r.status_code != 200:
        return r.status_code, r.text[:200]
    rows = []
    for line in r.text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return r.status_code, rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    mode = sys.argv[1]
    if mode == "colls":
        cs = collections()
        print(len(cs), "collections")
        for c in cs[:20]:
            print("  ", c)
    elif mode == "query":
        coll = sys.argv[2]
        patt = sys.argv[3]
        code, rows = query(coll, patt)
        print("status", code)
        if isinstance(rows, str):
            print(rows)
        else:
            print("rows", len(rows))
            seen = set()
            for row in rows:
                u = row.get("url", "")
                if u in seen:
                    continue
                seen.add(u)
                print(f"   {row.get('status')} {row.get('mime')} {u}")
