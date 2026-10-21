# -*- coding: utf-8 -*-
"""Retry Common Crawl prefix queries with retries/backoff."""
import json
import sys
import time

import requests

HEAD = {"User-Agent": "legacy-corpus-research/1.0"}
S = requests.Session()
S.headers.update(HEAD)
BASE = "https://index.commoncrawl.org/"


def query(coll, patt, limit=200, tries=3):
    params = {"url": patt, "output": "json", "limit": limit}
    for i in range(tries):
        try:
            r = S.get(f"{BASE}{coll}-index", params=params, timeout=180)
        except Exception as e:  # noqa: BLE001
            print("   try err", repr(e)[:80])
            time.sleep(3)
            continue
        if r.status_code == 200:
            rows = []
            for line in r.text.splitlines():
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return rows
        print(f"   try {i}: HTTP {r.status_code}")
        time.sleep(4 * (i + 1))
    return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    coll = sys.argv[1]
    for patt in sys.argv[2:]:
        print(f"== {patt}")
        rows = query(coll, patt)
        if rows is None:
            print("   FAILED")
            continue
        print(f"   rows={len(rows)}")
        seen = set()
        for row in rows:
            u = row.get("url", "")
            if u in seen:
                continue
            seen.add(u)
            print(f"      {row.get('status')} {row.get('mime')} {u}")
