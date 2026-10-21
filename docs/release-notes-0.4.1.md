# v0.4.1 发布说明（2026-10-21）

本次为地图选点功能的可用性改进与小版本发布，数据本身与 0.4.0 相同（437 幅等值面图 / 25 期月报）。

## 变更

- **默认底图改为高德地图**（AutoNavi），并支持切换 OpenStreetMap / Esri 影像 / 无底图（离线可用）。
- 高德瓦片为 **GCJ-02** 坐标；选点后页面自动转换为 **WGS84**（与 MCP 数据、城市点位一致），
  状态栏提示“已选点（GCJ-02 → WGS84）”，避免约 300–800 m 的坐标偏移。
- 修正 `get_map_picker()` 的说明文案：原写“自动复制 JSON”，实际为“点按钮复制 lat, lon 或 JSON”。
- 新增地图选点黑盒测试报告 [docs/map_picker_test.md](map_picker_test.md)，并补充 2 个回归测试
  （`test_map_picker_contract`、`test_map_point_matches_coordinates`）与 map_point 越界断言。

## 验证

- 地图页面：默认选中高德、底图请求 `webrd0x.is.autonavi.com` 返回 200；点击 (39.90, 116.40) 显示
  WGS84 (39.89860, 116.39376)；切“无底图”后点击坐标不转换、仍可取值（离线可用）。
- MCP：`locate_by_map_point` 与 `locate_by_coordinates` 同坐标结果一致；`query_by_location(mode="map_point")`
  与直接调用一致。
- `pytest`：**29 passed**；MCP stdio 冒烟：**26/26**；`verify_all`：**59/59**。

## 安装（不依赖 Docker）

```powershell
# 从 Git 直接运行（总是最新 main）
uvx --from git+https://github.com/nastenzin/groundwater-monthly-mcp.git groundwater-mcp

# 本 Release 的 wheel（离线/内网）
pip install "https://github.com/nastenzin/groundwater-monthly-mcp/releases/download/v0.4.1/groundwater_monthly_mcp-0.4.1-py3-none-any.whl"
```

## 资产

- `groundwater_monthly_mcp-0.4.1-py3-none-any.whl`（5,648,307 B，
  sha256 `16f66d5d26c1996838a5570cacdfef6bfbad022a4d916aafd92fdc7004c77d0e`）
- `groundwater_monthly_mcp-0.4.1.tar.gz`（5,654,317 B，
  sha256 `bf247839a12d2d6af00af89f9b1ebfeb8534e925f010f831a1c19c4a188d35ec`）
- `SHA256SUMS`（由 GitHub Actions 在 Release 中生成；CI 构建的 wheel 哈希可能与本地构建略有差异，
  以 Release 附件中的 `SHA256SUMS` 为准）
