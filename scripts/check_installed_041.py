# -*- coding: utf-8 -*-
"""Verify installed package version and map picker defaults."""
import groundwater_mcp
from groundwater_mcp import server

print("version", groundwater_mcp.__version__)
info = server.get_map_picker()
html = server.map_picker_resource()
print("gaode_default", '<option value="gaode" selected>' in html)
print("gcj_to_wgs84", "gcj02ToWgs84" in html and "GCJ-02" in html)
print("tools", len(server.mcp._tool_manager.list_tools()))
print("exists", info["exists"])
