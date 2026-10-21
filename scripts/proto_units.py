# -*- coding: utf-8 -*-
"""Find region polygons in units.geojson."""
import json
from pathlib import Path

g = json.loads(Path("src/groundwater_mcp/data/geo/units.geojson").read_text(encoding="utf-8"))
print("features:", len(g["features"]))
for f in g["features"]:
    p = f["properties"]
    name = p.get("name") or p.get("region") or str(p)
    if any(k in str(name) for k in ("三江", "穆棱", "兴凯", "松嫩", "辽河")):
        print(name, "| props:", p)
