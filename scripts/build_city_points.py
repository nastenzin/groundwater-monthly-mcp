# -*- coding: utf-8 -*-
"""生成随包分发的城市点位数据（WGS84）：src/groundwater_mcp/data/geo/city_points.json。

输入：data/recon/city_geo.json（百度 BD09，来源 88250/city-geo 的 data.json，预城市级）。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))
from groundwater_mcp.ingest.surface import bd09_to_wgs84

src = json.loads(Path("data/recon/city_geo.json").read_text(encoding="utf-8"))
out = {}
for name, (lon, lat) in src.items():
    wlon, wlat = bd09_to_wgs84(lon, lat)
    out[name] = [round(wlon, 4), round(wlat, 4)]
dest = Path("src/groundwater_mcp/data/geo/city_points.json")
dest.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")
print("cities", len(out), "->", dest, dest.stat().st_size, "B")
