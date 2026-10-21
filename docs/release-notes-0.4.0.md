# v0.4.0 发布说明（2026-10-21）

《地下水动态月报》MCP 服务器 0.4.0：在月报结构化数据之上，新增**彩色地下水埋深等值面图的连续场数字化**，
支持按经纬度/城市查询任意点的连续埋深。

## 亮点

- **全量月报覆盖**：25 期月报（2023-12 ~ 2025-12）的 437 幅埋深等值面图已数字化（每期 18 幅）。
  - `pdf` 来源 288 幅：2023-12 旧版 PDF 18 幅 + 2024-10~2025-12 共 15 期 270 幅；
  - `html-thumbnail` 来源 149 幅：2024-01~09 共 9 期（官网原大图已下线，仅存 335×480 缩略图）。
- **算法**：图例颜色 → 等级色块 → 等值线（2/4/8/12/16/20/30/40/50 m）→ 到上下等值线的距离加权插值 →
  连续埋深场；城市注记只用于图件定标，不参与数值分配（城市数据仅用于取坐标）。
- **新增 4 个 MCP 工具**：`get_depth_at_point`、`get_city_depth`、`get_depth_surface`、`list_surface_maps`；
  位置查询结果新增 `data.surface_depth`。工具总数 22 → **26**。
- **数据**：`surface_maps` 表 437 行；整库 7,790,592 B；随包 339 个城市点位（WGS84）。

## 精度与限制（如实披露）

- 等级一致性 437/437 = 100%；整幅图面积加权均值 vs 报告区域平均埋深：PDF 来源中位误差 **0.25 m**
  （p90 6.23），HTML 缩略图来源中位 **1.24 m**（p90 9.5）；|误差|>5 m 的 68 幅已标记 `suspect`。
- 面积加权图均值与“站点平均埋深”不是同一口径，河西走廊、关中、准噶尔、成都等区域会系统性偏差数米。
- HTML 缩略图期次无城市注记 OCR 条件，定标退化为“叙述监测面积反推尺度 + 区域多边形质心”，
  `quality` 固定为 `low`，点查询可能返回 `off_surface=true`（点落在图斑外，按最近像元取值）。

## 安装（不依赖 Docker）

```powershell
# 从 Git 直接运行（uvx 会自动装到隔离环境）
uvx --from git+https://github.com/nastenzin/groundwater-monthly-mcp.git groundwater-mcp

# 或 pip 安装
pip install "git+https://github.com/nastenzin/groundwater-monthly-mcp.git"

# 或从本 Release 的 wheel 离线安装
pip install groundwater_monthly_mcp-0.4.0-py3-none-any.whl
```

MCP 客户端配置（Claude Desktop / Cursor / Cline / DSH 等）：

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

## 校验

- 产出物：`groundwater_monthly_mcp-0.4.0-py3-none-any.whl`（5,647,599 B，
  sha256 `c9a87f5fe6f14153f6bac30ae73721ebb20f6a9c3fe0db5356a4d8002752dc7c`）、
  `groundwater_monthly_mcp-0.4.0.tar.gz`（5,653,126 B，
  sha256 `c0beaaf13852c30d2a42a76dd979242d86cd48bc4d0f9987be5c6d816b1a0de1`）。
- 测试：`pytest` 27 passed；MCP stdio 冒烟 26/26 工具调用成功；`verify_all` 59/59。
- 详细算法、精度与限制见 [docs/surface.md](https://github.com/nastenzin/groundwater-monthly-mcp/blob/main/docs/surface.md)；
  安装/客户端配置见 [README](https://github.com/nastenzin/groundwater-monthly-mcp/blob/main/README.md)。
