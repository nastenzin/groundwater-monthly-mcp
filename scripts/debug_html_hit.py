# -*- coding: utf-8 -*-
"""Inspect 2024-05 hit source."""
from groundwater_mcp import server

res = server.get_depth_at_point(43.85, 125.30, period="2024-05")
for h in res["hits"]:
    print({k: h[k] for k in ("period", "figure", "source_kind", "depth_m", "off_surface", "regions")})
