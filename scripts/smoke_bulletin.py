# -*- coding: utf-8 -*-
"""Smoke-test the bulletin repository functions and new MCP tools."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))
from groundwater_mcp import repository as repo  # noqa: E402

conn = repo.connect()
out = {}
out["reports"] = repo.list_bulletin_reports(conn)[:3]
out["national"] = repo.get_bulletin_national(conn, year=2010)
out["regions"] = repo.get_bulletin_regions(conn, year=2020)
r = out["regions"]["rows"][:3]
out["regions"] = {"count": out["regions"]["count"], "rows": r}
out["provinces"] = repo.get_bulletin_provinces(conn, year=2020, province="河北")
out["plains"] = repo.get_bulletin_plains(conn, year=2022, plain="三江")
out["series_nat"] = repo.get_bulletin_series(conn, metric="ground_supply", level="national")
out["series_region"] = repo.get_bulletin_series(conn, metric="ground_share", level="region", name="海河区")
out["series_plain"] = repo.get_bulletin_series(conn, metric="shallow_end", level="plain", name="三江")
out["province_hist"] = repo.bulletin_series_for_province(conn, "河北")
conn.close()
Path("data/bulletin/probe/tool_smoke.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("keys", list(out))
print("series_nat count", out["series_nat"]["count"])
