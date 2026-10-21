# -*- coding: utf-8 -*-
"""README: replace machine-specific install section with portable public instructions."""
from pathlib import Path

p = Path("README.md")
text = p.read_text(encoding="utf-8")

START = "## 2. 安装与运行"
END = "## 3. 工具清单（26 个工具 / 3 个资源 / 1 个提示词）"
i = text.index(START)
j = text.index(END)

new = """## 2. 安装与运行

**Python 3.10+**。以下三种方式任选其一，都不需要 Docker。

### 2.1 直接使用（推荐）

```powershell
# 方式 A：uvx 直接从 GitHub 运行（装一次 uv 即可，无需 clone）
uvx --from git+https://github.com/nastenzin/groundwater-monthly-mcp.git groundwater-mcp

# 方式 B：pip 从 Git 安装
pip install "git+https://github.com/nastenzin/groundwater-monthly-mcp.git"
groundwater-mcp

# 方式 C：从 GitHub Release 下载 wheel（离线/内网）
pip install "https://github.com/nastenzin/groundwater-monthly-mcp/releases/download/v0.4.0/groundwater_monthly_mcp-0.4.0-py3-none-any.whl"
groundwater-mcp
```

`groundwater-mcp` 默认 stdio；需要 HTTP 时用
`groundwater-mcp --transport streamable-http --host 127.0.0.1 --port 8765`。

### 2.2 从源码运行（开发者）

```powershell
git clone https://github.com/nastenzin/groundwater-monthly-mcp.git
cd groundwater-monthly-mcp
python -m pip install -e .
python -m groundwater_mcp
```

### 2.3 在 MCP 客户端中注册

DeepSeek Harness（`mcp_register`，推荐 uvx 方式，无需本机安装）：

```jsonc
{
  "name": "groundwater-monthly",
  "transport": "stdio",
  "command": "uvx",
  "args": ["--from", "git+https://github.com/nastenzin/groundwater-monthly-mcp.git", "groundwater-mcp"]
}
```

Claude Desktop / Cursor / Cline 等（`mcpServers`）：

```json
{
  "mcpServers": {
    "groundwater-monthly": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/nastenzin/groundwater-monthly-mcp.git", "groundwater-mcp"]
    }
  }
}
```

若已 `pip install`，也可用 `"command": "python", "args": ["-m", "groundwater_mcp"]`（不需要 `cwd`）。

### 2.4 发布与分发（维护者）

1. 推送 `main` 与 `v*` tag → `.github/workflows/release.yml` 自动构建 wheel/sdist、创建 GitHub Release
   并生成 `SHA256SUMS`；Docker / PyPI 任务默认跳过（仓库变量 `PUBLISH_DOCKER=true` / `PUBLISH_PYPI=true`
   时才执行）；
2. 使用者用 2.1 的 `uvx --from git+...` 或 Release 里的 wheel 安装；
3. 可选 PyPI：配置 Trusted Publisher 后设仓库变量 `PUBLISH_PYPI=true`，之后可直接 `uvx groundwater-monthly-mcp`。

其他落地形态（Docker / 远程 HTTP / 内网镜像）见 **[docs/deploy.md](docs/deploy.md)**。Release 附带的 wheel
由 GitHub Actions 构建，其 sha256 见 Release 附件或文档中的 Release 资产值；本地重新构建的 wheel 哈希可能不同。

"""
text = text[:i] + new + text[j:]

OLD = ("- 每期数据均可回溯：原生 PDF 期次随仓库分发（`data/pdfs/`、`data/legacy/pdfs/`），HTML5 文本层期次逐页"
       "存档（`data/legacy/html/<YYYY-MM>/pageN.html`），数据库中每个数值都能对应到期号、页码/表号与")
NEW = ("- 每期数据均可回溯：原始 PDF/HTML 归档因体积较大不随 Git 仓库分发（可用 `scripts/download_pdfs.py`、"
       "`scripts/legacy_crawl.py` 等重新下载），数据库中每个数值都能对应到期号、页码/表号与")
if OLD in text:
    text = text.replace(OLD, NEW)
else:
    print("WARN: 回溯段落未匹配，跳过")
p.write_text(text, encoding="utf-8")
print("README updated")
