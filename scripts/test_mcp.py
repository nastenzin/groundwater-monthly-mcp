# -*- coding: utf-8 -*-
"""MCP stdio smoke test: list tools/resources and call every tool once."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[1]
CALLS = [
    ("describe_dataset", {}),
    ("list_reports", {"year": 2025, "limit": 5}),
    ("get_report", {"period": "2025-12"}),
    ("get_precipitation", {"period": "2025-12", "group": "东北平原"}),
    ("get_shallow_groundwater", {"period": "2025-12", "region": "三江平原"}),
    ("get_deep_groundwater", {"period": "2025-12", "province": "河北"}),
    ("get_key_stations", {"period": "2025-12", "kind": "spring"}),
    ("get_time_series", {"metric": "depth", "region": "松嫩平原"}),
    ("search_report_text", {"query": "松嫩平原", "limit": 3}),
    ("get_report_text", {"period": "2025-12", "section": "综述"}),
    ("list_tables", {"period": "2025-12"}),
    ("get_table", {"period": "2025-12", "table_no": 1}),
    ("get_map_picker", {}),
    ("locate_by_coordinates", {"lat": 45.75, "lon": 126.63, "period": "2025-12"}),
    ("locate_by_administrative_region", {"province": "河北省", "city": "衡水市", "period": "2025-12"}),
    ("locate_by_map_point", {"lat": 39.90, "lon": 116.40, "period": "2025-12"}),
    ("query_by_location", {"mode": "administrative", "province": "广东省", "period": "2025-12"}),
    ("list_annual_reports", {}),
    ("get_annual_groundwater", {"year": 2022, "region": "三江平原", "row_type": "plain_basin"}),
    ("list_bulletin_reports", {}),
    ("get_bulletin_groundwater", {"year": 2020, "level": "region", "name": "海河区"}),
    ("get_bulletin_series", {"metric": "ground_supply", "level": "province", "name": "河北"}),
    ("list_surface_maps", {"period": "2025-12"}),
    ("get_depth_at_point", {"lat": 45.75, "lon": 126.63, "period": "2025-12"}),
    ("get_depth_surface", {"period": "2025-12", "figure": 4}),
    ("get_city_depth", {"city": "石家庄", "period": "2025-12"}),
]


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "groundwater_mcp"],
        cwd=str(ROOT),
        env={"PYTHONIOENCODING": "utf-8"},
    )
    out = {}
    ok = 0
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            print("server:", init.server_info.name, init.server_info.version)
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("tools:", len(names), names)
            resources = await session.list_resources()
            print("resources:", [str(r.uri) for r in resources.resources])
            templates = await session.list_resource_templates()
            print("resource templates:", [str(r.uri_template) for r in templates.resource_templates])
            prompts = await session.list_prompts()
            print("prompts:", [p.name for p in prompts.prompts])
            # read resources
            try:
                content = await session.read_resource("groundwater://catalog")
                catalog = json.loads(content.contents[0].text)
                print("catalog resource periods:", len(catalog["reports"]))
            except Exception as exc:  # noqa: BLE001
                print("catalog resource failed:", exc)
            try:
                content = await session.read_resource("groundwater://report/2025-12")
                detail = json.loads(content.contents[0].text)
                print("report resource:", detail["period"], detail["title"])
            except Exception as exc:  # noqa: BLE001
                print("report resource failed:", exc)
            try:
                prompt = await session.get_prompt("region_groundwater_brief", {"region": "松嫩平原", "period": "2025-12"})
                print("prompt chars:", len(prompt.messages[0].content.text))
            except Exception as exc:  # noqa: BLE001
                print("prompt failed:", exc)
            for name, args in CALLS:
                try:
                    result = await session.call_tool(name, args)
                    payload = []
                    for c in result.content:
                        text = getattr(c, "text", None)
                        if text is not None:
                            payload.append(text)
                    raw = "\n".join(payload)
                    try:
                        data = json.loads(raw)
                    except Exception:  # noqa: BLE001
                        data = raw
                    out[name] = {"ok": True, "is_error": result.is_error, "data": data}
                    if not result.is_error:
                        ok += 1
                    summary = json.dumps(data, ensure_ascii=False)
                    print(f"\n### {name} OK: {summary[:240]}")
                except Exception as exc:  # noqa: BLE001
                    out[name] = {"ok": False, "error": repr(exc)}
                    print(f"\n### {name} FAILED: {exc!r}")
    Path("data/mcp_smoke_result.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n{ok}/{len(CALLS)} tool calls succeeded; wrote data/mcp_smoke_result.json")


if __name__ == "__main__":
    asyncio.run(main())
