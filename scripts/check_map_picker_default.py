# -*- coding: utf-8 -*-
"""Check updated map picker HTML defaults and resource consistency."""
from groundwater_mcp import server

info = server.get_map_picker()
html = server.map_picker_resource()
print("exists:", info["exists"])
print("resource matches file:", html == info.get("picker_path") and True)
checks = {
    "default_gaode_selected": '<option value="gaode" selected>' in html,
    "gaode_is_default_layer": "let current = 'gaode'" in html,
    "gcj_to_wgs84": "gcj02ToWgs84" in html and "GCJ-02" in html,
    "offline_option": 'value="none"' in html,
    "note_mentions_gaode": "底图默认高德" in info["note"],
}
for k, v in checks.items():
    print(k, v)
