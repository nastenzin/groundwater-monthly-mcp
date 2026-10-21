# groundwater-monthly MCP 部署与使用指南

本文件覆盖：本地安装、客户端配置（DSH / Claude Desktop / Cursor / Cline / Claude Code）、
Docker（stdio 与 HTTP）、公网 HTTPS 部署、PyPI 与 MCP Registry 发布，以及本机的实测记录。

服务器概况：

| 项目 | 值 |
| --- | --- |
| PyPI 包名 | `groundwater-monthly-mcp` |
| 控制台命令 | `groundwater-mcp` |
| 版本 | 0.4.1（`server.json` / `pyproject.toml` 同步） |
| 内容 | 26 个工具（17 个基线 + `list_annual_reports` / `get_annual_groundwater` 两个年度报告工具 + `list_bulletin_reports` / `get_bulletin_groundwater` / `get_bulletin_series` 三个历年公报工具 + `list_surface_maps` / `get_depth_at_point` / `get_depth_surface` / `get_city_depth` 四个等值面连续埋深工具）、2 个静态资源 + 1 个资源模板、1 个 prompt |
| 数据 | 随包分发 SQLite（25 期月报 2023-12 ~ 2025-12 + 年度报告表 + 公报 5 张表 + 437 幅埋深等值面图连续场，约 7,608 KB / 7,790,592 B）+ 行政区/地貌单元 GeoJSON + 339 个城市点位（仅取坐标）+ 离线地图选点页 |
| 需要 API Key？ | **不需要**。纯本地只读数据，无网络调用。 |
| Python | >= 3.10；依赖 `mcp>=2.0,<3`（mcp 1.x 不兼容） |
| 运行时依赖 | 只有 `mcp`；`pdfplumber` 仅在“重建数据集”时需要（`pip install "groundwater-monthly-mcp[ingest]"`） |

传输方式三种：

| transport | 用途 | 启动方式 |
| --- | --- | --- |
| `stdio`（默认） | 本地 MCP 客户端拉起子进程 | `groundwater-mcp` 或 `python -m groundwater_mcp` |
| `streamable-http` | 独立 HTTP 服务、远程/多客户端共享 | `groundwater-mcp --transport streamable-http --host 0.0.0.0 --port 8765 --path /mcp` |
| `sse` | 旧版 SSE 客户端 | `groundwater-mcp --transport sse --host 0.0.0.0 --port 8765 --path /sse` |

> `python -m groundwater_mcp` 与 `groundwater-mcp` 是**同一个入口**（`groundwater_mcp.cli:main`）：
> `__main__.py` 只是转调 `cli.main()`，所以两者参数、环境变量完全一致；不带参数时默认 stdio，
> 与旧版 `groundwater_mcp.server:main` 行为等价。

---

## 0. 30 秒快速开始

```powershell
# 方式 A：从本仓库的 wheel 安装（离线可用）
python -m pip wheel . -w dist --no-deps
python -m pip install dist\groundwater_monthly_mcp-0.4.1-py3-none-any.whl

# 方式 B：PyPI 发布之后
# pip install groundwater-monthly-mcp
# uvx --from groundwater-monthly-mcp groundwater-mcp

groundwater-mcp --version        # groundwater-mcp 0.4.1
groundwater-mcp                  # stdio，等客户端发 JSON-RPC
```

自检（不需要客户端）：

```powershell
python scripts/package_check.py wheel     # 检查 dist/*.whl 里的 DB/geo/map
python scripts/package_check.py stdio     # initialize + tools/list + 1 次工具调用
python scripts/package_check.py http --url http://127.0.0.1:8765/mcp
python scripts\build_bulletin_dataset.py  # 重新生成公报解析 JSON（ingest.build 会自动并入 5 张 bulletin_* 表）

# 等值面连续场重建（437 幅 / 25 期）：城市点位 -> PDF/旧版 PDF 数字化 -> 抓 HTML 缩略图 -> 缩略图期数字化 -> 后处理 -> build
python scripts\build_city_points.py
python scripts\build_surface_data.py
python scripts\fetch_html_thumbs.py
python scripts\build_surface_html.py
python scripts\postprocess_surface.py
```

---

## 1. CLI 参考

```text
groundwater-mcp [--transport {stdio,streamable-http,sse}] [--host HOST] [--port PORT]
                [--path PATH] [--log-level LEVEL] [--version]
```

| 参数 | 默认值 | 说明 |
| --- | --- | --- |
| `--transport` | `stdio` | `stdio` / `streamable-http` / `sse` |
| `--host` | `127.0.0.1` | HTTP 监听地址；容器/公网用 `0.0.0.0`，本机反代用 `127.0.0.1` |
| `--port` | `8765` | HTTP 监听端口 |
| `--path` | `/mcp` | streamable-http 端点路径；`sse` 传输时填 `/sse` |
| `--log-level` | `INFO` | 日志写 **stderr**（stdio 下 stdout 只留给 JSON-RPC） |
| `--version` | — | 打印版本后退出 |

环境变量（优先级低于显式命令行参数，高于内置默认值）：

| 环境变量 | 对应 |
| --- | --- |
| `GROUNDWATER_MCP_TRANSPORT` | `--transport` |
| `GROUNDWATER_MCP_HOST` | `--host` |
| `GROUNDWATER_MCP_PORT` | `--port` |
| `GROUNDWATER_MCP_PATH` | `--path` |
| `GROUNDWATER_MCP_LOG_LEVEL` | `--log-level` |
| `GROUNDWATER_DB` | 覆盖 SQLite 路径（默认用包内 `data/groundwater.db`） |
| `GROUNDWATER_DATA_DIR` | 覆盖数据根目录（默认仓库 `data/`） |

示例：

```powershell
# 只暴露给本机反代
groundwater-mcp --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp

# 用环境变量配置（容器里常用）
$env:GROUNDWATER_MCP_TRANSPORT="streamable-http"
$env:GROUNDWATER_MCP_HOST="0.0.0.0"
$env:GROUNDWATER_MCP_PORT="8765"
groundwater-mcp
```

手工验证 HTTP 端点（不装客户端）：

```bash
curl -sS -X POST http://127.0.0.1:8765/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' -D -
# → HTTP/1.1 200，响应头带 Mcp-Session-Id，响应体是 `event: message` + `data: {...}`（SSE 格式）
```

---

## 2. 本地运行：pip / pipx / uv / uvx

### 2.1 pip（任意虚拟环境）

```bash
python -m pip install groundwater-monthly-mcp      # PyPI 发布后
python -m pip install dist/groundwater_monthly_mcp-0.4.1-py3-none-any.whl  # 本地 wheel
groundwater-mcp --version
```

如果只从原始材料重建数据集（普通用户不需要）：

```bash
python -m pip install "groundwater-monthly-mcp[ingest]"
python -m groundwater_mcp.ingest.build --help

# 月报：抓目录 -> 下载 PDF -> 解析入库
python scripts/crawl_index.py
python scripts/download_pdfs.py
python -m groundwater_mcp.ingest.build

# 《中国水文年报》：下载 -> 解析地下水章节 -> build 自动并入
python scripts/download_annual.py
python -m groundwater_mcp.ingest.annual_parse 2022
python -m groundwater_mcp.ingest.build

# 《中国水资源公报》：抓栏目页 -> 下载 -> 解析表格 -> 生成数据集 -> build 自动并入 5 张 bulletin_* 表
python scripts/crawl_bulletin_index.py
python scripts/download_bulletin.py
python scripts/parse_bulletin_pdf.py
python scripts/build_bulletin_dataset.py
python -m groundwater_mcp.ingest.build

# 等值面图（全量 25 期，437 幅）：生成城市点位 -> PDF 数字化 -> 抓 HTML 缩略图 -> 缩略图期数字化 -> 后处理 -> build 自动并入 surface_maps 表
python scripts/build_city_points.py
python scripts/build_surface_data.py
python scripts/fetch_html_thumbs.py
python scripts/build_surface_html.py
python scripts/postprocess_surface.py
python -m groundwater_mcp.ingest.build
```

### 2.2 pipx（隔离安装 CLI）

```bash
pipx install groundwater-monthly-mcp
pipx run --spec groundwater-monthly-mcp groundwater-mcp --version
```

### 2.3 uv / uvx（推荐给只读客户端用）

注意：包名是 `groundwater-monthly-mcp`，命令名是 `groundwater-mcp`，两者不同，
所以 `uvx` 必须用 `--from` 指定包：

```bash
uvx --from groundwater-monthly-mcp groundwater-mcp            # stdio
uvx --from groundwater-monthly-mcp groundwater-mcp --transport streamable-http --host 0.0.0.0 --port 8765
```

`uv run` 也可以（不污染全局环境）：

```bash
uv run --with groundwater-monthly-mcp groundwater-mcp --version
```

---

## 3. 客户端配置

所有客户端都是同一套 MCP 握手：先 `initialize`，再 `tools/list` 拿到 26 个工具。

### 3.1 DSH（本机 MCP 能力库）

在 DSH 会话里直接对话即可，底层等价于调用下面的注册工具：

**stdio（uvx）**

```text
mcp_register(
  name="groundwater-monthly",
  transport="stdio",
  command="uvx",
  args=["--from", "groundwater-monthly-mcp", "groundwater-mcp"],
  tier="on-demand",
  notes="《地下水动态月报》26 个工具：降水/浅埋深/深埋深/重点站/年报/历年公报/等值面连续埋深/全文检索/位置查询"
)
```

**stdio（已安装的可执行文件 / 仓库源码）**

```text
mcp_register(name="groundwater-monthly", transport="stdio",
             command="C:\\Anaconda\\Scripts\\groundwater-mcp.exe", tier="on-demand")

# 或直接从仓库源码跑（开发用）
mcp_register(name="groundwater-monthly-dev", transport="stdio",
             command="python", args=["-m", "groundwater_mcp"],
             cwd="<repo>", tier="on-demand")
```

**streamable-http（远程/本机服务）**

```text
mcp_register(name="groundwater-monthly-http", transport="streamable-http",
             url="http://127.0.0.1:8765/mcp", tier="on-demand",
             notes="先启动 groundwater-mcp --transport streamable-http")
```

注册后：

```text
mcp_load groundwater-monthly          # 拉取工具定义
mcp_call {name:"groundwater-monthly", tool:"describe_dataset", args:{}}
```

### 3.2 Claude Desktop

配置文件位置：

| 系统 | 路径 |
| --- | --- |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

stdio（推荐，uvx 自动装依赖）：

```json
{
  "mcpServers": {
    "groundwater-monthly": {
      "command": "uvx",
      "args": ["--from", "groundwater-monthly-mcp", "groundwater-mcp"]
    }
  }
}
```

stdio（已安装到固定路径，Windows 示例；JSON 里反斜杠要转义）：

```json
{
  "mcpServers": {
    "groundwater-monthly": {
      "command": "C:\\Anaconda\\Scripts\\groundwater-mcp.exe",
      "args": []
    }
  }
}
```

改完配置后完全退出并重启 Claude Desktop，在输入框的 “Tools” 里应能看到 26 个工具。

远程 HTTP：新版 Claude Desktop 支持在 “Settings → Connectors → Add custom connector”
里填 URL（`https://gw.example.com/mcp`）；如需自定义请求头，参考 3.4 Cursor 的 `headers` 写法
（不同版本 UI 略有差异，Claude Desktop 的配置文件形态以官方文档为准）。

### 3.3 Cursor

配置文件：全局 `~/.cursor/mcp.json`，或项目内 `.cursor/mcp.json`。

```json
{
  "mcpServers": {
    "groundwater-monthly": {
      "command": "uvx",
      "args": ["--from", "groundwater-monthly-mcp", "groundwater-mcp"]
    }
  }
}
```

远程 streamable-http（带鉴权头）：

```json
{
  "mcpServers": {
    "groundwater-monthly-http": {
      "url": "https://gw.example.com/mcp",
      "headers": { "Authorization": "Bearer REPLACE_WITH_TOKEN" }
    }
  }
}
```

### 3.4 Cline（VS Code 扩展）

配置文件：

| 系统 | 路径 |
| --- | --- |
| Windows | `%APPDATA%\Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json` |
| macOS | `~/Library/Application Support/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json` |

stdio：

```json
{
  "mcpServers": {
    "groundwater-monthly": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "groundwater-monthly-mcp", "groundwater-mcp"],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

streamable-http：

```json
{
  "mcpServers": {
    "groundwater-monthly-http": {
      "type": "streamableHttp",
      "url": "https://gw.example.com/mcp",
      "headers": { "Authorization": "Bearer REPLACE_WITH_TOKEN" },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### 3.5 Claude Code / 其他 CLI 客户端

```bash
claude mcp add groundwater-monthly -- uvx --from groundwater-monthly-mcp groundwater-mcp
claude mcp add --transport http groundwater-monthly-http https://gw.example.com/mcp
```

任何支持 MCP 的客户端，只要满足其中一种即可：

- 能执行命令：`uvx --from groundwater-monthly-mcp groundwater-mcp`（stdio）
- 能填 URL：`http://<host>:8765/mcp`（streamable-http，注意路径是 `/mcp`）

---

## 4. Docker

### 4.1 构建

```powershell
docker build -t groundwater-monthly-mcp:0.4.1 .
```

- 多阶段构建：builder 阶段 `pip wheel .` 把本包 + 全部依赖打成 wheel；runtime 阶段
  `pip install --no-index --find-links=/wheels groundwater-monthly-mcp`，不留 pip 缓存。
- 构建上下文很小：`.dockerignore` 排除了 `data/pdfs`（约 60MB 原始 PDF）、`data/surface` 中间件与缩略图缓存、
  `data/annual|parsed|legacy`、`docs/`、`tests/` 等；镜像里只有 `src/groundwater_mcp/data`
  下的 DB/GeoJSON/城市点位 JSON/地图页。
- 非 root 运行（uid 10001），默认 `streamable-http` + `0.0.0.0:8765/mcp`（见 Dockerfile 的 ENV）。
- 镜像实测约 **283MB**（`python:3.12-slim` 基础镜像 + mcp 2.x 运行依赖；不含 pdfplumber）。

### 4.2 默认：HTTP 服务

```powershell
docker run -d --name gw -p 127.0.0.1:8765:8765 groundwater-monthly-mcp:0.4.1
docker logs gw
docker inspect --format '{{.State.Health.Status}}' gw     # healthy
```

客户端填 `http://127.0.0.1:8765/mcp`。改了端口要同时改环境变量（HEALTHCHECK 跟随该变量）：

```powershell
docker run -d --name gw -p 9000:9000 -e GROUNDWATER_MCP_PORT=9000 groundwater-monthly-mcp:0.4.1
```

### 4.3 stdio：让 Docker 当“子进程启动器”

```powershell
docker run -i --rm groundwater-monthly-mcp:0.4.1 --transport stdio
```

客户端配置（Claude Desktop / Cursor / Cline 都可以这样写）：

```json
{
  "mcpServers": {
    "groundwater-monthly": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "groundwater-monthly-mcp:0.4.1", "--transport", "stdio"]
    }
  }
}
```

### 4.4 docker compose

```yaml
# docker-compose.yml
services:
  groundwater-mcp:
    build: .
    image: groundwater-monthly-mcp:0.4.1
    container_name: gw-mcp
    ports:
      - "127.0.0.1:8765:8765"
    environment:
      GROUNDWATER_MCP_TRANSPORT: streamable-http
      GROUNDWATER_MCP_HOST: 0.0.0.0
      GROUNDWATER_MCP_PORT: "8765"
      GROUNDWATER_MCP_PATH: /mcp
    read_only: true
    tmpfs:
      - /tmp
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import os, socket; socket.create_connection(('127.0.0.1', int(os.environ.get('GROUNDWATER_MCP_PORT','8765'))), 3).close()"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

```powershell
docker compose up -d --build
```

### 4.5 使用只读外部数据卷（可选）

镜像自带数据库，一般不需要挂载。若要换成自己的 `groundwater.db`（例如自己重新构建的数据集），
挂载成只读即可 —— 服务器只做 SELECT，SQLite 不会写 journal：

```powershell
docker run -d --name gw -p 127.0.0.1:8765:8765 `
  -v <repo>\src\groundwater_mcp\data\groundwater.db:/data/groundwater.db:ro `
  -e GROUNDWATER_DB=/data/groundwater.db `
  groundwater-monthly-mcp:0.4.1
```

---

## 5. 公网部署（HTTPS + 反代 + 鉴权 + 只读卷）

> ⚠️ **本服务器没有内置鉴权/限流**：任何能访问 `/mcp` 的客户端都能调用 26 个工具。
> 公网暴露时**必须**在反向代理层加鉴权，并且不要直接把 8765 端口开到公网。

推荐拓扑：

```text
MCP 客户端 ──HTTPS(443)──> nginx/Caddy（TLS + Bearer/Basic 鉴权 + 限流）
                              └──> 127.0.0.1:8765  groundwater-mcp（streamable-http，容器或裸机）
```

### 5.1 先让服务只监听本机

```bash
# 裸机
groundwater-mcp --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp

# Docker（只在宿主机回环上发布端口）
docker run -d --name gw -p 127.0.0.1:8765:8765 --restart unless-stopped \
  groundwater-monthly-mcp:0.4.1
```

### 5.2 nginx（HTTPS + Bearer 鉴权）

```nginx
# /etc/nginx/conf.d/gw-mcp.conf
server {
    listen 443 ssl;
    http2 on;
    server_name gw.example.com;

    ssl_certificate     /etc/letsencrypt/live/gw.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gw.example.com/privkey.pem;

    # 简单 Bearer 鉴权（token 换成你自己的长随机串）
    # 客户端配置里加 headers: {"Authorization": "Bearer <TOKEN>"}
    set $mcp_token "REPLACE_WITH_LONG_RANDOM_TOKEN";
    if ($http_authorization != "Bearer $mcp_token") {
        return 401;
    }

    # 也可以换成 Basic Auth：
    # auth_basic "MCP";
    # auth_basic_user_file /etc/nginx/.htpasswd;

    location /mcp {
        proxy_pass http://127.0.0.1:8765/mcp;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Connection "";

        # streamable-http 的流式响应：必须关掉缓冲/缓存
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        chunked_transfer_encoding on;

        client_max_body_size 8m;
    }
}
```

要点：

- **`proxy_buffering off`**：SSE 流式响应被缓冲会导致客户端收不到消息。
- **`Connection ""` + HTTP/1.1**：保持长连接。
- 只代理 `/mcp`，别把根路径整体反代。
- 日志里会记录 MCP 请求；如需隐藏 token 不要打在 access log 里。

### 5.3 Caddy（自动 HTTPS）

```caddyfile
gw.example.com {
    @mcp path /mcp*
    handle @mcp {
        reverse_proxy 127.0.0.1:8765 {
            flush_interval -1
            header_up Host {host}
        }
    }
}
```

鉴权可用 `basicauth` 或前置一层 `forward_auth` / `oauth2-proxy`。

### 5.4 鉴权方案对比（按需选一个）

| 方案 | 客户端支持 | 说明 |
| --- | --- | --- |
| Bearer token（nginx `if` / Caddy header 校验） | Cursor / Cline 支持 `headers`；Claude Desktop 需支持自定义 header 的版本 | 最简单，token 放环境变量管理 |
| Basic Auth | 部分客户端不支持自定义 Authorization | 适合临时内部使用 |
| Cloudflare Tunnel + Access | 浏览器 OAuth 登录；MCP 客户端需能走 CF Access Service Token | 免公网 IP、免证书 |
| oauth2-proxy / 自建 OAuth | 支持 OAuth 的 MCP 客户端 | 多用户场景 |

> 说明：MCP 规范里的 OAuth 授权流程需要服务端实现 `.well-known` 元数据与授权服务器；
> 本服务器是只读公开数据，推荐用上面的“反代 + 静态 token”方案，够用且零改造。

### 5.5 公网部署安全清单

- [ ] 8765 只绑 `127.0.0.1`（或容器 `-p 127.0.0.1:8765:8765`），公网只开 443
- [ ] TLS 证书自动续期（certbot / Caddy 自动）
- [ ] 反代层加鉴权（token / Basic / OAuth）
- [ ] 加基础限流：`limit_req_zone` / Caddy `rate_limit`，防止被当免费算力
- [ ] 容器 `read_only: true` + 只读数据卷（数据是只读的，不需要写权限）
- [ ] 非 root 用户运行（镜像已内置 uid 10001）
- [ ] 日志与监控：`docker logs` / `journalctl`，关注 4xx/5xx
- [ ] 定期 `docker pull` 新版本（数据更新随版本发布）
- [ ] 不要暴露 `--host 0.0.0.0` 且同时把端口映射到公网 —— CLI 会打 WARNING 提醒

### 5.6 健康检查与探测

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST https://gw.example.com/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"probe","version":"0"}}}'
# 200 表示反代 + 服务 + 鉴权都通
```

---

## 6. 发布：PyPI / GitHub Release / MCP Registry / 镜像仓库

### 6.0 一次性准备（用户自备）

| 需要什么 | 用途 | 在哪里配 |
| --- | --- | --- |
| GitHub 仓库 | `server.json` 的 `name`/`repository`、PyPI trusted publishing、ghcr 镜像 | github.com 新建仓库并 `git push` |
| PyPI 账号 + API token（或 trusted publisher） | 发布 `groundwater-monthly-mcp` | pypi.org |
| GitHub Actions 写权限 | 打 tag 自动发版、推 ghcr | 仓库 Settings → Actions → General |
| Docker Hub 账号（可选） | 额外推 Docker Hub 镜像 | hub.docker.com |
| 域名 + DNS（可选） | 公网 HTTP 部署 | 域名注册商 |
| `mcp-publisher` GitHub 登录 | 发布到 MCP Registry | 本机执行 `mcp-publisher login github` |

### 6.1 把占位符全部替换掉

发布前必须替换（本仓库里共 3 处文件）：

| 文件 | 占位符 | 替换成 |
| --- | --- | --- |
| `server.json` | `io.github.nastenzin/groundwater-monthly` | `io.github.nastenzin/groundwater-monthly`（**全小写**） |
| `server.json` | `nastenzin`（2 处 url） | 你的 GitHub 用户名/组织 |
| `pyproject.toml` | `nastenzin`（3 处 `[project.urls]`） | 同上 |
| `Dockerfile` | `io.github.nastenzin/groundwater-monthly`（LABEL） | 与 `server.json` 的 `name` 一致 |
| `README.md` | 需新增一行 `mcp-name:`（由 README 维护者加，见 6.4） | `io.github.nastenzin/groundwater-monthly` |

> MCP Registry 的命名空间必须与登录方式匹配：用 `mcp-publisher login github` 时，
> 名字必须以 `io.github.<你的账号>/` 开头，否则发布会被拒绝。

### 6.2 发布到 PyPI

**首次（手动 / token）**

```bash
python -m pip install --upgrade build twine
python -m build                       # 生成 dist/*.whl + dist/*.tar.gz
python -m twine check dist/*
python -m twine upload dist/*         # 交互输入 __token__ / pypi-xxxx（或设 TWINE_USERNAME/TWINE_PASSWORD）
```

**Trusted Publishing（推荐，无需 token）**

1. PyPI → 项目 `groundwater-monthly-mcp` → *Publishing* → *Add a new trusted publisher*：
   - Owner：你的 GitHub 用户名/组织
   - Repository：`groundwater-monthly-mcp`
   - Workflow name：`release.yml`
   - Environment name：`pypi`
2. 之后只需打 tag：

```bash
git tag v0.4.1
git push origin v0.4.1        # 触发 .github/workflows/release.yml：
                              # build → publish-pypi（OIDC）→ docker(ghcr) → github-release
```

**校验**

```bash
curl -s https://pypi.org/pypi/groundwater-monthly-mcp/json | head -c 300
pip download groundwater-monthly-mcp --no-deps -d /tmp/check   # 能下到就说明索引了
```

### 6.3 GitHub Release

工作流的 `github-release` job 会自动创建 Release 并附上 `dist/*`；也可以手动：

```bash
gh release create v0.4.1 dist/* --title "v0.4.1" --notes "groundwater-monthly MCP v0.4.1"
```

### 6.4 发布到 MCP Registry（官方 Registry）

Registry 只存元数据，**必须先把 PyPI 包发出去**，并且要能验证包归属：

1. **给 PyPI 包的 README 加校验标记**（注册表会检查 PyPI 项目描述里是否含
   `mcp-name: <server.json 的 name>`，可以放在 HTML 注释里隐藏）：

   ```markdown
   <!-- mcp-name: io.github.<你的账号>/groundwater-monthly -->
   ```

   > 本仓库的 `README.md` 由文档维护者负责，发布前请确认已加这一行；否则 Registry 校验
   > 会报 `Registry validation failed for package`。

2. **装 mcp-publisher**：

   ```powershell
   # Windows
   $arch = if ([System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture -eq "Arm64") { "arm64" } else { "amd64" }
   Invoke-WebRequest -Uri "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_windows_$arch.tar.gz" -OutFile "mcp-publisher.tar.gz"
   tar xf mcp-publisher.tar.gz mcp-publisher.exe
   # 把 mcp-publisher.exe 放到 PATH 里
   ```

   ```bash
   # macOS / Linux
   curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" | tar xz mcp-publisher && sudo mv mcp-publisher /usr/local/bin/
   # 或 brew install mcp-publisher
   ```

3. **版本号两处对齐**：`server.json` 的 `version` 与 `packages[0].version` 必须等于
   实际已发布的 PyPI 版本（PyPI 版本不可覆盖，改版本号再发）。

4. **发布**：

   ```bash
   mcp-publisher login github     # 浏览器 device code 授权
   mcp-publisher publish          # 读取当前目录的 server.json
   ```

5. **验证**：

   ```bash
   curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.<你的账号>/groundwater-monthly"
   ```

注意事项：

- `server.json` 里的 `$schema` 目前按任务要求用 `2025-09-29` 版；Registry 线上已出现
  `2025-12-11`。若 `mcp-publisher publish` 报 schema 版本过旧，把 `$schema` 换成
  `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json` 再发即可
  （字段结构兼容）。也可以直接 `mcp-publisher init` 生成新模板后照抄字段。
- 想同时把 Docker 镜像登记为 `oci` 包，在 `server.json` 的 `packages` 里追加：

  ```json
  {
    "registryType": "oci",
    "identifier": "ghcr.io/nastenzin/groundwater-monthly-mcp:0.4.1",
    "transport": { "type": "stdio" }
  }
  ```

  Registry 会检查镜像的 `io.modelcontextprotocol.server.name` 注解（Dockerfile 已预留 LABEL）。
- 每次发布 `server.json` 的 `version` 必须递增（同一版本不可重复发布）。

### 6.5 镜像仓库（ghcr / Docker Hub）

- **ghcr.io**：`release.yml` 的 `docker` job 已实现，用 `GITHUB_TOKEN`（需仓库
  Actions 权限为 “Read and write”），推送到 `ghcr.io/nastenzin/groundwater-monthly-mcp`。
- **Docker Hub**（可选）：

```bash
docker tag groundwater-monthly-mcp:0.4.1 <dockerhub-user>/groundwater-monthly-mcp:0.4.1
docker tag groundwater-monthly-mcp:0.4.1 <dockerhub-user>/groundwater-monthly-mcp:latest
docker login -u <dockerhub-user>
docker push <dockerhub-user>/groundwater-monthly-mcp:0.4.1
docker push <dockerhub-user>/groundwater-monthly-mcp:latest
```

若要在 CI 里自动推 Docker Hub，在仓库 Secrets 里加 `DOCKERHUB_USERNAME` /
`DOCKERHUB_TOKEN`（Docker Hub → Account settings → Security → New access token），
然后在 `release.yml` 里加一个 `docker/login-action` 步骤。

### 6.6 Smithery（可选）

仓库根目录已提供 `smithery.yaml`（`uvx --from groundwater-monthly-mcp groundwater-mcp`）。
在 <https://smithery.ai> 用 GitHub 登录并连接本仓库即可自动发现；本服务器无需任何
配置项/API Key，`configSchema` 留空。

---

## 7. 本机实测记录（2026-10-21，Windows）

环境：`python` 3.13.9、`mcp 2.3.0`、Docker CLI/Desktop 29.5.3（linux/amd64）。

> 0.4.1 验证结论：`python -m pytest -q tests` → **29 passed**；`python scripts\test_mcp.py` → **26/26 工具调用成功**；
> wheel `groundwater_monthly_mcp-0.4.1-py3-none-any.whl`（5,648,602 B，sha256 `60e98571…`）；
> Docker 镜像 `groundwater-monthly-mcp:0.4.1`（`842e4a1e5afd`，约 283MB，HEALTHCHECK `healthy`，HTTP 端 26 个工具）；
> 随包 DB 7,790,592 B（约 7,608 KB），含 `surface_maps` 437 行/25 期与 339 个城市点位。

### 7.1 stdio（默认 transport）

```powershell
PS> python -m groundwater_mcp --version
groundwater-mcp 0.4.1

PS> python scripts/package_check.py stdio
{
  "ok": true,
  "command": "python -m groundwater_mcp",
  "server": "groundwater-monthly 0.4.1",
  "protocol_version": "2025-11-25",
  "tool_count": 26,
  "tools": ["describe_dataset", "list_reports", "get_report", "get_precipitation",
            "get_shallow_groundwater", "get_deep_groundwater", "get_key_stations",
            "get_time_series", "search_report_text", "get_report_text", "list_tables",
            "get_table", "locate_by_coordinates", "locate_by_administrative_region",
            "locate_by_map_point", "query_by_location", "list_annual_reports",
            "get_annual_groundwater", "list_bulletin_reports", "get_bulletin_groundwater",
            "get_bulletin_series", "list_surface_maps", "get_depth_at_point",
            "get_depth_surface", "get_city_depth", "get_map_picker"],
  "resource_count": 2,
  "resources": ["groundwater://catalog", "groundwater://map/picker"],
  "prompt_count": 1,
  "prompts": ["region_groundwater_brief"],
  "call_tool": "describe_dataset",
  "call_ok": true,
  "call_preview": "{\"reports\": 25, \"periods\": [\"2025-12\", \"2025-11\", ...], ... \"surface_maps\": 437, \"surface_periods\": [\"2025-12\", ...]}",
  "problems": []
}
```

### 7.2 streamable-http

```powershell
PS> python -m groundwater_mcp --transport streamable-http --host 127.0.0.1 --port 8765 --path /mcp
INFO: Uvicorn running on http://127.0.0.1:8765 (Press CTRL+C to quit)

# 另一个终端：
PS> python scripts/package_check.py http --url http://127.0.0.1:8765/mcp
{ "ok": true, "server": "groundwater-monthly 0.4.1", "protocol_version": "2025-11-25",
  "tool_count": 26, "call_tool": "describe_dataset", "call_ok": true, "problems": [] }

# 裸 curl JSON-RPC（不需要客户端）：
PS> curl.exe -sS -X POST http://127.0.0.1:8765/mcp -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' -D -
HTTP/1.1 200 OK
mcp-session-id: 98a2598b80f84049adafab76eaa2ea88
content-type: text/event-stream

event: message
data: {"jsonrpc":"2.0","id":1,"result":{"capabilities":{...},"serverInfo":{"name":"groundwater-monthly","version":"0.4.1"},...}}
```

补充验证：

- `--host 0.0.0.0` 起服务后，用自定义 `Host: mcp.example.com:443` 与
  `Origin: https://gw.example.com` 请求同样返回 200（不会因 DNS rebinding 防护拒绝），
  因此可以直接放在反向代理后面。
- 错误路径（`/wrongpath`）返回 404，说明路径隔离正常。
- `sse` 传输也实测可用：`GET http://127.0.0.1:8767/sse` 返回
  `event: endpoint` + `data: /messages/?session_id=...`。

### 7.3 wheel 构建与内容检查

> 2026-10-21 在把等值面扩展到全量 25 期月报（437 幅；含 2023-12 旧版 PDF 与 2024-01~09 HTML 缩略图）后重新构建；以下为最新一次实测。

```powershell
PS> python -m pip wheel . -w dist --no-deps
Successfully built groundwater-monthly-mcp
Created wheel: groundwater_monthly_mcp-0.4.1-py3-none-any.whl (5646895 bytes)
sha256=63a3aa325bd3e5b63613c231274cdf7a975a715ddbb86e120115d5789c89c045

PS> python scripts/package_check.py wheel
{ "ok": true, "size_mb": 5.39, "file_count": 27,
  "data_hits": { "db": 1, "geo": 4, "map": 3 }, "problems": [] }
```

wheel 内清单（压缩后 5.39 MB，解压后约 11 MB）：

```text
groundwater_mcp/server.py                         36303
groundwater_mcp/repository.py                     30163
groundwater_mcp/geo.py                            24412
groundwater_mcp/surface_query.py                   9567   ← 零第三方依赖查询层
groundwater_mcp/paths.py                            619
groundwater_mcp/cli.py                             6003   ← 多 transport 入口
groundwater_mcp/__init__.py / __main__.py
groundwater_mcp/ingest/{__init__,build,annual_parse,html_parse,pdf_parse,surface}.py
groundwater_mcp/data/groundwater.db             7790592   ← 必需（含 annual_* / bulletin_* / surface_maps 437 行）
groundwater_mcp/data/geo/china_cities.geojson   2420879   ← 必需
groundwater_mcp/data/geo/china_provinces.geojson 413397
groundwater_mcp/data/geo/units.geojson             7562
groundwater_mcp/data/geo/city_points.json         12597   ← 必需（339 个城市点位，仅取坐标）
groundwater_mcp/data/map/leaflet.js              147552   ← 必需
groundwater_mcp/data/map/leaflet.css              14806
groundwater_mcp/data/map/map_picker.html           6149
groundwater_monthly_mcp-0.4.1.dist-info/*
```

确认**不含** `data/pdfs/**` 等原始 PDF/中间产物（`package_check.py` 会对此报错）。

### 7.4 临时 venv 安装 wheel（真实安装验证）

```powershell
PS> python -m venv $env:TEMP\gw_mcp_venv
PS> & $env:TEMP\gw_mcp_venv\Scripts\python.exe -m pip install dist\groundwater_monthly_mcp-0.4.1-py3-none-any.whl
Successfully installed groundwater-monthly-mcp-0.4.1 mcp-2.3.0 ...

PS> & $env:TEMP\gw_mcp_venv\Scripts\groundwater-mcp.exe --version
groundwater-mcp 0.4.1

PS> python scripts/package_check.py stdio --command "$env:TEMP\gw_mcp_venv\Scripts\groundwater-mcp.exe"
{ "ok": true, "server": "groundwater-monthly 0.4.1", "tool_count": 26, "call_ok": true }
# 包内 DB 定位正确：site-packages\groundwater_mcp\data\groundwater.db (7790592 bytes)
# 城市点位随包：site-packages\groundwater_mcp\data\geo\city_points.json (12597 bytes)
# 等值面工具实测：get_city_depth('哈尔滨', period='2025-12') → depth=20.31 m（松嫩平原）
```

### 7.5 Docker

```powershell
PS> docker build -t groundwater-monthly-mcp:0.4.1 .
# 构建上下文已按 .dockerignore 排除 data/pdfs 的 60MB 原始 PDF、data/surface 中间件与缩略图缓存
PS> docker images groundwater-monthly-mcp
REPOSITORY               TAG    IMAGE ID       SIZE
groundwater-monthly-mcp  0.4.1  842e4a1e5afd   283MB

PS> docker run -d --name gw -p 127.0.0.1:8765:8765 groundwater-monthly-mcp:0.4.1
PS> docker inspect --format '{{.State.Health.Status}}' gw
healthy
PS> python scripts/package_check.py http --url http://127.0.0.1:8765/mcp
{ "ok": true, "server": "groundwater-monthly 0.4.1", "protocol_version": "2025-11-25",
  "tool_count": 26, "call_ok": true }

PS> python scripts/package_check.py stdio --command "docker run -i --rm groundwater-monthly-mcp:0.4.1 --transport stdio"
{ "ok": true, "server": "groundwater-monthly 0.4.1", "tool_count": 26, "call_ok": true }

# 容器内等值面查询实测（HTML 缩略图期次；证明镜像内含 city_points.json 且运行期不需要 numpy/opencv/scipy）
# get_depth_at_point(43.85, 125.30, period='2024-05') → 命中 1 条，depth=8.0 m、source_kind=html-thumbnail、off_surface=true
```

镜像实测属性：

```text
User         = 10001:10001（非 root）
Entrypoint   = ["groundwater-mcp"]，Cmd = null（默认参数来自 ENV）
ExposedPorts = 8765/tcp
Labels       = {"io.modelcontextprotocol.server.name": "io.github.nastenzin/groundwater-monthly"}
镜像内 DB     = /usr/local/lib/python3.12/site-packages/groundwater_mcp/data/groundwater.db (7790592 bytes)
镜像内城市点位 = /usr/local/lib/python3.12/site-packages/groundwater_mcp/data/geo/city_points.json (12597 bytes)
镜像大小      = 283 MB（python:3.12-slim 基础 ~130MB + mcp 2.x 运行依赖 + 7.8MB 数据库）
```

---

## 8. 上线前的一次性配置清单（用户自备）

> 本仓库的代码/配置已就绪，但**下面这些账号与凭据只能由你本人提供**。按顺序做一遍即可上线。

### 8.1 必做

- [ ] **GitHub 仓库**：新建 `groundwater-monthly-mcp` 仓库并推送代码，最终地址形如
      `https://github.com/<你的账号>/groundwater-monthly-mcp`（这个地址要填进 `server.json` 的
      `repository.url` 与 `pyproject.toml` 的 `[project.urls]`）。
      - 需要的权限/scope：推送 tag 与 Release 需仓库 `contents: write`；
        推 ghcr 镜像需 `packages: write`（用默认 `GITHUB_TOKEN` 即可，无需自备 PAT）。
      - `Settings → Actions → General → Workflow permissions` 选 **Read and write**。
      - 需要能推送 tag：`git tag v0.4.1 && git push origin v0.4.1`。
- [ ] **PyPI 账号**（<https://pypi.org>）：注册 + 开启 2FA。
      - Token 路径：*Account settings → API tokens → Add API token*（**scope 建议选
        “Project: groundwater-monthly-mcp”** 而不是整个账号），形如 `pypi-AgE...`；
        也可不建 token，改用 6.2 的 trusted publishing（推荐，无 token 泄漏风险）。
      - `groundwater-monthly-mcp` 这个名字 2026-10-17 查询**未被占用**，可直接注册使用。
- [ ] **MCP Registry 发布凭据**：README 里加
      `<!-- mcp-name: io.github.<你的GitHub账号>/groundwater-monthly -->`
      （**这行由 README 维护者加**，否则 Registry 归属校验失败），然后
      `mcp-publisher login github`（OAuth device code，需浏览器；命名空间必须与登录账号一致）。

### 8.2 按需（要公网 / 要双镜像时）

- [ ] **域名 + DNS**：如 `gw.example.com` 的 A/AAAA 记录，指向部署机。
- [ ] **TLS 证书**：certbot（Let's Encrypt）或 Caddy 自动签发；证书路径填进 5.2 的 nginx 配置。
- [ ] **反向代理主机**：nginx / Caddy 任选，按 5.2 / 5.3 配置；只开 443。
- [ ] **访问 token**：`openssl rand -hex 32` 生成，填进反代与客户端 `headers`。
- [ ] **Docker Hub 账号（可选）**：<https://hub.docker.com> + *Account settings → Security →
      New access token*；如需 CI 推送，在仓库 Secrets 加 `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN`。
      （ghcr 用 `GITHUB_TOKEN`，**不需要**额外自备 token。）
- [ ] **Smithery 账号（可选）**：<https://smithery.ai> 用 GitHub 登录并连接仓库（已提供 `smithery.yaml`）。
- [ ] **自己的数据集（可选）**：若换用自己的 `groundwater.db`，设 `GROUNDWATER_DB` 指向它（只读卷即可）。

### 8.3 不需要自备

- ❌ 数据源 API Key：数据随包分发，无外部调用。
- ❌ 下游 MCP 客户端的 key：本服务器无鉴权，客户端只需命令或 URL。

---

## 9. 常见问题

| 现象 | 原因 / 处理 |
| --- | --- |
| `ModuleNotFoundError: No module named 'mcp.server.mcpserver'` | 装的是 mcp 1.x。升级：`pip install "mcp>=2.0,<3"` |
| 客户端连上但没工具 | 服务端 stdout 被日志污染。日志都在 stderr；不要把 `--log-level` 之外的输出打到 stdout |
| HTTP 客户端 406 | 请求头缺 `Accept: application/json, text/event-stream` |
| HTTP 客户端 404 | 路径不对，默认是 `/mcp`（不是 `/`） |
| `uvx groundwater-monthly-mcp` 报 command not found | 包名与命令名不同，用 `uvx --from groundwater-monthly-mcp groundwater-mcp` |
| Docker 里中文乱码 | 客户端侧问题；服务端 JSON 都是 UTF-8，`Ensure_ascii=False` |
| 数据库损坏/替换 | 用 `GROUNDWATER_DB=/path/to/groundwater.db` 指向新库，或重建数据集后重新打 wheel |
| 反代后 SSE 卡住 | nginx 没关 `proxy_buffering`，见 5.2 |
| 端口被占用 | `--port` 或 `GROUNDWATER_MCP_PORT` 换端口 |
