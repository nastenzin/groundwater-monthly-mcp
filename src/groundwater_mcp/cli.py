# -*- coding: utf-8 -*-
"""groundwater-monthly MCP 服务器的统一命令行入口。

用法::

    groundwater-mcp                          # 默认 stdio（客户端拉起）
    python -m groundwater_mcp                # 同上
    groundwater-mcp --version                # 打印版本
    groundwater-mcp --transport streamable-http --host 0.0.0.0 --port 8765 --path /mcp
    groundwater-mcp --transport sse --host 0.0.0.0 --port 8765 --path /sse

环境变量（优先级低于显式命令行参数）::

    GROUNDWATER_MCP_TRANSPORT   stdio | streamable-http | sse
    GROUNDWATER_MCP_HOST        监听地址，默认 127.0.0.1
    GROUNDWATER_MCP_PORT        监听端口，默认 8765
    GROUNDWATER_MCP_PATH        HTTP 路径，默认 /mcp（sse 传输时默认 /sse）
    GROUNDWATER_MCP_LOG_LEVEL   DEBUG/INFO/WARNING/ERROR，默认 INFO

本模块只负责传输层与参数解析，17 个工具、3 个资源、1 个 prompt 全部来自
:mod:`groundwater_mcp.server`，不做任何改动。
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from .server import mcp

try:  # 安装后以包元数据为准（pyproject.toml 的 version）
    from importlib.metadata import PackageNotFoundError, version as _dist_version

    try:
        __version__ = _dist_version("groundwater-monthly-mcp")
    except PackageNotFoundError:  # pragma: no cover - 源码目录未安装时
        from . import __version__ as __version__
except Exception:  # pragma: no cover - 极端环境兜底
    from . import __version__ as __version__

TRANSPORTS = ("stdio", "streamable-http", "sse")
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_PATH = "/mcp"
DEFAULT_LOG_LEVEL = "INFO"

LOG = logging.getLogger("groundwater_mcp")


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _port(value: str) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"端口必须是整数，收到 {value!r}") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError(f"端口必须在 1-65535 之间，收到 {port}")
    return port


def _log_level(value: str) -> str:
    level = str(value).upper()
    if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        raise argparse.ArgumentTypeError(
            f"日志级别必须是 DEBUG/INFO/WARNING/ERROR/CRITICAL 之一，收到 {value!r}"
        )
    return level


def build_parser() -> argparse.ArgumentParser:
    """构造命令行解析器（可单独用于测试）。"""
    parser = argparse.ArgumentParser(
        prog="groundwater-mcp",
        description="《地下水动态月报》数据 MCP 服务器（stdio / streamable-http / sse）",
        epilog=(
            "示例：groundwater-mcp --transport streamable-http "
            "--host 0.0.0.0 --port 8765 --path /mcp"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"groundwater-mcp {__version__}",
    )
    parser.add_argument(
        "--transport",
        choices=TRANSPORTS,
        default=_env("GROUNDWATER_MCP_TRANSPORT", "stdio"),
        help="传输方式：stdio（客户端拉起）或 streamable-http / sse（独立 HTTP 服务）",
    )
    parser.add_argument(
        "--host",
        default=_env("GROUNDWATER_MCP_HOST", DEFAULT_HOST),
        help="HTTP 传输监听地址；容器/公网部署用 0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=_port,
        default=_port(_env("GROUNDWATER_MCP_PORT", str(DEFAULT_PORT))),
        help="HTTP 传输监听端口",
    )
    parser.add_argument(
        "--path",
        default=_env("GROUNDWATER_MCP_PATH", DEFAULT_PATH),
        help="streamable-http 的端点路径；sse 传输时请设为 /sse 之类的 SSE 路径",
    )
    parser.add_argument(
        "--log-level",
        type=_log_level,
        default=_log_level(_env("GROUNDWATER_MCP_LOG_LEVEL", DEFAULT_LOG_LEVEL)),
        help="日志级别（写入 stderr，stdio 传输时不会污染 stdout）",
    )
    return parser


def configure_logging(level: str) -> None:
    """配置日志到 stderr（stdio 传输时 stdout 只留给 JSON-RPC）。

    ``force=True``：mcp 导入时可能已给 root logger 装好 handler，不加 force 时
    basicConfig 会静默跳过，``--log-level`` 就不生效了。
    """
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def main(argv: list[str] | None = None) -> None:
    """CLI 主入口；``python -m groundwater_mcp`` 与 ``groundwater-mcp`` 都走这里。"""
    args = build_parser().parse_args(argv)
    configure_logging(args.log_level)
    LOG.info(
        "groundwater-monthly-mcp %s transport=%s host=%s port=%s path=%s",
        __version__,
        args.transport,
        args.host,
        args.port,
        args.path,
    )

    if args.transport == "stdio":
        mcp.run(transport="stdio")
        return

    if args.transport == "streamable-http":
        if args.host not in ("127.0.0.1", "localhost", "::1"):
            LOG.warning(
                "HTTP 传输监听在 %s，任何能访问该端口的客户端都可调用工具；"
                "公网部署请放在 HTTPS 反向代理与鉴权之后。",
                args.host,
            )
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path=args.path,
        )
        return

    mcp.run(transport="sse", host=args.host, port=args.port, sse_path=args.path)


if __name__ == "__main__":  # pragma: no cover
    main()
