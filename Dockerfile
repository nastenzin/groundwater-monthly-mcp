# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# groundwater-monthly MCP 服务器容器镜像
#
#   docker build -t groundwater-monthly-mcp:0.4.1 .
#   docker run --rm -p 8765:8765 groundwater-monthly-mcp:0.4.1            # streamable-http
#   docker run -i --rm groundwater-monthly-mcp:0.4.1 --transport stdio     # stdio（客户端拉起）
#
# 设计要点：
#   * 多阶段构建：builder 阶段把本包 + 全部依赖打成 wheel，runtime 阶段用
#     --no-index 离线安装，避免 pip 缓存残留，镜像更小。
#   * 随包数据只有 data/groundwater.db（约 2.7MB）、data/geo/*.geojson（约 2.9MB）、
#     data/map/*（约 170KB）；原始 PDF（data/pdfs，约 60MB）由 .dockerignore 排除。
#   * 默认以非 root 用户运行；数据库只读即可（sqlite 只读查询不写 journal）。
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /build

# 只拷打包所需文件：pyproject.toml 的 readme 指向 README.md
COPY pyproject.toml README.md ./
COPY src ./src

# 把本包和它的全部运行时依赖都做成 wheel（mcp 2.x / pydantic / uvicorn / starlette ...）
RUN python -m pip install --upgrade pip \
    && python -m pip wheel . -w /wheels

# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

# CLI 默认值：容器内无参数启动即 streamable-http 0.0.0.0:8765/mcp
ENV GROUNDWATER_MCP_TRANSPORT=streamable-http
ENV GROUNDWATER_MCP_HOST=0.0.0.0
ENV GROUNDWATER_MCP_PORT=8765
ENV GROUNDWATER_MCP_PATH=/mcp
ENV GROUNDWATER_MCP_LOG_LEVEL=INFO

WORKDIR /app

# 仅当把镜像作为 oci 包发布到 MCP Registry 时需要；
# 该注解值必须与 server.json 里的 name 完全一致（占位符记得替换成你的 GitHub owner）
LABEL io.modelcontextprotocol.server.name="io.github.nastenzin/groundwater-monthly"

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels groundwater-monthly-mcp \
    && rm -rf /wheels

# 非 root 运行；容器内数据只读，无需写权限
RUN useradd --create-home --uid 10001 appuser
USER 10001:10001

EXPOSE 8765

# 健康检查：TCP 连接探测（不依赖 curl/wget），端口跟随 GROUNDWATER_MCP_PORT
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import os, socket; socket.create_connection(('127.0.0.1', int(os.environ.get('GROUNDWATER_MCP_PORT', '8765'))), 3).close()"

ENTRYPOINT ["groundwater-mcp"]
# 不写 CMD：默认参数全部来自上面的 ENV；`docker run ... --transport stdio` 可整体覆盖
