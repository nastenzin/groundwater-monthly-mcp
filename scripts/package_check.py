# -*- coding: utf-8 -*-
"""打包自检脚本：wheel 内容检查 + stdio / streamable-http 冒烟。

只做只读检查与临时目录写入，不修改仓库数据文件。

用法::

    python scripts/package_check.py wheel                 # 检查 dist/*.whl 内容与体积
    python scripts/package_check.py stdio                 # 用当前解释器跑 stdio 冒烟
    python scripts/package_check.py stdio --command groundwater-mcp   # 跑已安装的命令
    python scripts/package_check.py http --url http://127.0.0.1:8765/mcp
    python scripts/package_check.py all                   # wheel + stdio

退出码：0 全部通过；1 有检查失败。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# wheel 里必须存在的随包数据（相对 wheel 根目录的包路径）
REQUIRED_WHEEL_GLOBS = {
    "db": "groundwater_mcp/data/groundwater.db",
    "geo": "groundwater_mcp/data/geo/",
    "map": "groundwater_mcp/data/map/",
}
REQUIRED_MAP_FILES = ("leaflet.js", "leaflet.css", "map_picker.html")
FORBIDDEN_WHEEL_SUBSTRINGS = ("data/pdfs", "data/annual", "data/parsed", "data/legacy")


def _fail(problems: list[str], message: str) -> None:
    problems.append(message)
    print(f"[FAIL] {message}")


def check_wheel(wheel: Path | None = None) -> dict:
    """检查 wheel 是否存在、体积、必需数据文件、是否混入原始 PDF 等大文件。"""
    problems: list[str] = []
    if wheel is None:
        candidates = sorted((ROOT / "dist").glob("*.whl"))
        if not candidates:
            _fail(problems, "dist/ 下没有 wheel，请先运行 python -m pip wheel . -w dist --no-deps")
            return {"ok": False, "problems": problems}
        wheel = candidates[-1]
    if not wheel.exists():
        _fail(problems, f"wheel 不存在：{wheel}")
        return {"ok": False, "problems": problems}

    size = wheel.stat().st_size
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()

    rel = names
    found: dict[str, int] = {}
    for key, needle in REQUIRED_WHEEL_GLOBS.items():
        hits = [n for n in rel if (n == needle or n.startswith(needle))]
        found[key] = len(hits)
        if not hits:
            _fail(problems, f"wheel 缺少 {key} 数据：{needle}")

    map_hits = [n for n in rel if n.startswith("groundwater_mcp/data/map/")]
    map_names = {n.rsplit("/", 1)[-1] for n in map_hits}
    for fn in REQUIRED_MAP_FILES:
        if fn not in map_names:
            _fail(problems, f"wheel 缺少地图文件 data/map/{fn}")

    for bad in FORBIDDEN_WHEEL_SUBSTRINGS:
        hits = [n for n in rel if bad in n]
        if hits:
            _fail(problems, f"wheel 混入了不该打包的原始数据：{bad}（{len(hits)} 个文件）")

    # 体积上限：DB(~2.7MB)+geo(~2.9MB)+map(~170KB)+代码，压缩后应远小于 20MB
    max_bytes = 20 * 1024 * 1024
    if size > max_bytes:
        _fail(problems, f"wheel 体积 {size/1048576:.2f} MB 超过上限 {max_bytes/1048576:.0f} MB")

    result = {
        "ok": not problems,
        "wheel": str(wheel),
        "size_bytes": size,
        "size_mb": round(size / 1048576, 2),
        "file_count": len(names),
        "data_hits": found,
        "has_console_script": any(n.endswith("entry_points.txt") for n in names),
        "problems": problems,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _summarize_tools(tools) -> list[str]:
    return [t.name for t in tools.tools]


def _payload(result) -> str:
    parts = []
    for c in result.content:
        text = getattr(c, "text", None)
        if text is not None:
            parts.append(text)
    raw = "\n".join(parts)
    return raw[:400]


async def smoke_stdio(command: list[str], call_tool: str) -> dict:
    """以子进程方式拉起 stdio 服务器，完成 initialize + tools/list + 1 次工具调用。"""
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    problems: list[str] = []
    params = StdioServerParameters(
        command=command[0],
        args=command[1:],
        env={"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1", "GROUNDWATER_MCP_LOG_LEVEL": "WARNING"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            names = _summarize_tools(tools)
            if len(names) < 17:
                _fail(problems, f"tools/list 只有 {len(names)} 个工具，期望 17 个：{names}")
            for required in ("describe_dataset", "query_by_location", "get_map_picker"):
                if required not in names:
                    _fail(problems, f"缺少工具 {required}")
            resources = await session.list_resources()
            resource_uris = [str(r.uri) for r in resources.resources]
            prompts = await session.list_prompts()
            prompt_names = [p.name for p in prompts.prompts]
            call_result = await session.call_tool(call_tool, {})
            summary = _payload(call_result)
            if call_result.is_error:
                _fail(problems, f"工具调用 {call_tool} 返回 is_error=True：{summary}")
            payload = {
                "ok": not problems,
                "command": " ".join(command),
                "server": f"{init.server_info.name} {init.server_info.version}",
                "protocol_version": init.protocol_version,
                "tool_count": len(names),
                "tools": names,
                "resource_count": len(resource_uris),
                "resources": resource_uris,
                "prompt_count": len(prompt_names),
                "prompts": prompt_names,
                "call_tool": call_tool,
                "call_ok": not call_result.is_error,
                "call_preview": summary,
                "problems": problems,
            }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


async def smoke_http(url: str, call_tool: str) -> dict:
    """连接 streamable-http 端点，完成 initialize + tools/list + 1 次工具调用。"""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    problems: list[str] = []
    async with streamable_http_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            tools = await session.list_tools()
            names = _summarize_tools(tools)
            if len(names) < 17:
                _fail(problems, f"tools/list 只有 {len(names)} 个工具，期望 17 个")
            call_result = await session.call_tool(call_tool, {})
            summary = _payload(call_result)
            if call_result.is_error:
                _fail(problems, f"工具调用 {call_tool} 返回 is_error=True：{summary}")
            payload = {
                "ok": not problems,
                "url": url,
                "server": f"{init.server_info.name} {init.server_info.version}",
                "protocol_version": init.protocol_version,
                "tool_count": len(names),
                "tools": names,
                "call_tool": call_tool,
                "call_ok": not call_result.is_error,
                "call_preview": summary,
                "problems": problems,
            }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def _default_stdio_command() -> list[str]:
    return [sys.executable, "-m", "groundwater_mcp"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="groundwater-monthly-mcp 打包自检")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_wheel = sub.add_parser("wheel", help="检查 dist/*.whl 内容与体积")
    p_wheel.add_argument("--wheel", default=None, help="指定 wheel 路径，默认取 dist/ 下最新的")

    p_stdio = sub.add_parser("stdio", help="stdio 冒烟：initialize + tools/list + 1 次调用")
    p_stdio.add_argument("--command", default=None, help="服务器命令，默认 `python -m groundwater_mcp`")
    p_stdio.add_argument("--tool", default="describe_dataset")

    p_http = sub.add_parser("http", help="streamable-http 冒烟")
    p_http.add_argument("--url", default="http://127.0.0.1:8765/mcp")
    p_http.add_argument("--tool", default="describe_dataset")

    p_all = sub.add_parser("all", help="wheel + stdio")
    p_all.add_argument("--command", default=None)

    args = parser.parse_args(argv)
    if args.cmd == "wheel":
        wheel = Path(args.wheel) if args.wheel else None
        return 0 if check_wheel(wheel)["ok"] else 1
    if args.cmd == "stdio":
        command = args.command.split() if args.command else _default_stdio_command()
        result = asyncio.run(smoke_stdio(command, args.tool))
        return 0 if result["ok"] else 1
    if args.cmd == "http":
        result = asyncio.run(smoke_http(args.url, args.tool))
        return 0 if result["ok"] else 1
    if args.cmd == "all":
        wheel_ok = check_wheel()["ok"]
        command = args.command.split() if args.command else _default_stdio_command()
        stdio_ok = asyncio.run(smoke_stdio(command, "describe_dataset"))["ok"]
        return 0 if (wheel_ok and stdio_ok) else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
