# 地下水动态月报 MCP 服务器（groundwater-monthly-mcp）

当前版本 **0.4.0**（26 个工具；月报 + 水文年报 + 历年水资源公报 + 等值面连续埋深场四套数据）。

<!-- mcp-name: io.github.nastenzin/groundwater-monthly -->
<!-- 发布到 MCP Registry 时，这一行用于校验 PyPI 包归属（本仓库 owner: nastenzin）。 -->

把水利部公开发布的《地下水动态月报》PDF 变成**可被大模型/MCP 客户端直接调用的结构化数据服务**：
报告目录、综述、降水量（表 1–5）、浅层地下水埋深及变化（表 6–13）、深层地下水水位变幅（表 14）、
裂隙水/岩溶水重点站（表 15）、水温（表 16）、泉流量（表 17），以及原文全文检索与任意原始表格读取。

当前覆盖 **25 期月报（2023-12 至 2025-12 连续）** + **年际基准（2020-12、2021-12、2022-12）**
+ **历年公报地下水资源量/供水量/占比（1997、1998、2001-2024）**
+ **437 幅埋深等值面图连续场（覆盖全部 25 期月报，2023-12 ~ 2025-12）**：
2024-10~2025-12 来自官方 PDF，2024-01~2024-09 来自官方 HTML5 翻页书文本层（表格文本流解析），
2023-12 来自信息中心残留 PDF；年际基准来自《中国水文年报》地下水章节——2022 年卷（文本层，表 5-2/5-3）
提供 2021/2022 年末数据，2021 年卷（扫描件，OCR + 逐行校验）提供 2020/2021 年末数据。
历年公报来自《中国水资源公报》地下水章节与附表：全国口径 1997、1998、2001-2024；水资源一级区
1997、2010-2024；省级行政区 2011、2016-2022、2024；主要平原/盆地年末埋深 2021/2022。新增 5 张
`bulletin_*` 表、约 605 行。
每期月报 17 张表、24 个地貌单元叙述数据均已结构化入库；2024 年 HTML 文本层的重点站/水温表因表格换行
存在少量站点未解析（水温约 42–50/64 站），其余核心表完整。

等值面层把全部 25 期月报的彩色“地下水埋深等值面图”数字化为**连续埋深场**，共 **437 幅可用**
（每期 18 幅、25 期共 450 次尝试，13 幅因缩略图分页/裁切失败被剔除），入库表 `surface_maps`
（437 行、25 个期号）：图例 10 级色块解码（<2、2~4、4~8、8~12、12~16、16~20、20~30、30~40、40~50、>50 m）
→ Lab 颜色分级 → 抗锯齿空隙补齐 → 按等级边界提取等值线（2/4/8/12/16/20/30/40/50 m）
→ 像元到上下等值线的距离加权线性插值得到连续场。来源分两类：`source='pdf'` **288 幅**
（2023-12 旧版 PDF 18 幅 + 2024-10~2025-12 共 15 期 270 幅）、`source='html-thumbnail'` **149 幅**
（2024-01~09 共 9 期，官网原大图已 404，只能用 335×480 页面缩略图）。城市注记只作为像元↔经纬度的
定标控制点，**不参与取值**；HTML 缩略图期次因注记太小无法 OCR，改为“叙述监测面积反推尺度 +
区域多边形质心”定标。查询时对连续场双线性取样，可返回 5.7 m 这类非分级边界值；
`get_depth_at_point` 还会返回 `source_kind`（pdf/html-thumbnail）与 `off_surface`（点落在图斑外时
按最近像元取值）。精度与限制见 [docs/surface.md](docs/surface.md)。

位置查询支持三种输入方式（本服务器内置地理定位，无需外部服务）：

| 方式 | 工具 | 输入 |
| --- | --- | --- |
| 经纬度 | `locate_by_coordinates` | `lat`、`lon` |
| 选择行政区 | `locate_by_administrative_region` | `province`、可选 `city` |
| 地图选点 | `locate_by_map_point` | 先用 `get_map_picker` 在浏览器地图上点击取坐标，再传 `lat`、`lon` |

也可以用统一入口 `query_by_location(mode=..., ...)` 自动分派。定位结果包含：
`resolved_admin`（省/市）、`matched_units`（地貌单元及 `relation=inside/nearby`、`distance_km`）、
`resolution_confidence`（high/medium/low）、以及各单元的当期数据与近 12 期序列。

位置查询还会附带历史序列：`locate_by_administrative_region` 的 `data.province_groundwater_history`
给出该省历年公报的地下水资源量/供水量/占比（库内覆盖 2011、2016-2022、2024）；`locate_by_coordinates` /
`locate_by_map_point` 的单元数据在 `annual_series` 之外，还会带 `bulletin_series`（2021/2022 年公报的
年末埋深与变幅，仅当该平原/盆地在公报表中时返回）。

新增等值面层后，`locate_by_coordinates` / `locate_by_map_point` 的结果还会在 `data.surface_depth`
中附带该点由等值面反演的连续埋深（全部 25 期；含 `source_kind` 与 `off_surface`）。


---

## 1. 数据来源

- 报告原文：水利部网站「数据 → 统计公报 → 地下水动态月报」
  - 统计页：<http://www.mwr.gov.cn/sj/tjgb/dxsdtyb/>
  - 信息中心镜像：<http://xxzx.mwr.gov.cn/xxgk/gbjb/dxsdtyb/>
- 年际基准：水利部「数据 → 统计公报 → 中国水文年报」（2021–2025 年卷，地下水章节）
  - 栏目页：<http://www.mwr.gov.cn/sj/tjgb/zgswnb/>
  - 2022 年卷（PDF 文本层）：表 5-2/5-3，含 2021 年 12 月与 2022 年 12 月两个时点；
  - 2021 年卷（扫描版 PDF）：表 5-3，含 2020 年 12 月与 2021 年 12 月两个时点。扫描页经 OCR 后按
    “区域锚点 + 列坐标”重建，并用“埋深差 = 水位变幅”逐行校验（29/29 一致），交叉比对 2022 年卷重叠年份。
  - 同一数据年份若多份年报给出修订值，库内优先采用“当年年报”的版本（`annual_groundwater.report_year`），
    年际变化请使用库内 `*_water_level_change_m`，不要用不同年报版本的埋深直接相减。
  - 逐项记录来源页码与表号（`annual_groundwater.source_table/source_page`）。
- 历年公报：水利部「数据 → 统计公报 → 中国水资源公报」
  - 栏目页：<http://www.mwr.gov.cn/sj/tjgb/szygb/>（**必须用 `http://` 访问**，`https://` 会跳转/拒绝）
  - 年份：1997、1998、2001-2024（1999/2000 未在官网公开；2023 年卷为扫描版 PDF，未做 OCR，未解析入库）
  - 已机读的表：全国口径（地下水资源量、地下水供水量、地下水占总供水比例、总供水量、平原区地下水资源量、
    北方平原区浅层地下水储存量较年初变化）；水资源一级区（10 个一级区 + 北方 6 区/南方 4 区/全国/太湖，
    含地下水资源量、供水量、总供水量与占比）；省级行政区（2011、2016-2022、2024）；主要平原及盆地
    “浅层/深层地下水动态”表的年末埋深与变幅（2021/2022）
  - 口径差异：公报是**年度**资源量/供水量/储存量变化，月报是**逐月**埋深，水文年报是**年末**埋深；
    三者互补，**不要把不同口径的数值直接拼接成一条“埋深序列”**
  - 1997 年为九大流域片口径（松辽片/海河片/…），2006 年起改为 10 个水资源一级区口径；本库一级区机读数据
    自 2010 年起（2006-2009 年公报的一级区表格在网页中只是扁平化文本且内容重复，未做机读解析，仅保留全国数值）
- 每期数据均可回溯：原生 PDF 期次随仓库分发（`data/pdfs/`、`data/legacy/pdfs/`），HTML5 文本层期次逐页
  存档（`data/legacy/html/<YYYY-MM>/pageN.html`），数据库中每个数值都能对应到期号、页码/表号与
  `reports.detail_url` / `reports.pdf_url`（HTML 期次无 PDF 直链时 `pdf_url` 为空）。
- 解析方式：`pdfplumber` 抽取文本与表格；先用「表 N 标题」把页面切成区域，再在区域内识别表格，
  解决同一页两张表（如表 10+表 11）被合并、跨页表（表 15/16）被截断的问题。2024-01~09 的 HTML5
  文本层按「表 N 标题」切段后，用各省/地貌单元名定位行，抽取同一套 17 张表。
- 数据表中的 `source_kind` 字段标明来源：`pdf`（原生 PDF）、`html5-text-layer`（HTML5 文本层）。
- 地貌单元（平原/盆地）边界为**近似多边形**，仅用于把位置映射到月报监测区，不作为精确地理边界使用。

> 数据以月报原文为准。月报注明：监测站埋深/水位/水温/流量为月均值；降水「常年」为 1981—2010 年；
> 因站网变动等原因，不同期成果可能有差异。

## 2. 安装与运行

```powershell
# Python 3.10+；本机使用 D:\Anaconda\python.exe
python -m pip install -e .
# 本地 MCP stdio 服务器（供 MCP 客户端拉起）
python -m groundwater_mcp
```

在 DeepSeek Harness 中注册（stdio）：

```jsonc
// mcp_register
{
  "name": "groundwater-monthly",
  "transport": "stdio",
  "command": "D:\\Anaconda\\python.exe",
  "args": ["-m", "groundwater_mcp"],
  "cwd": "D:\\MCP服务器"
}
```

其他 MCP 客户端（Claude Desktop 等）等价配置：

```json
{
  "mcpServers": {
    "groundwater-monthly": {
      "command": "python",
      "args": ["-m", "groundwater_mcp"],
      "cwd": "D:/MCP服务器"
    }
  }
}
```

## 2.1 发布与分发（不依赖 Docker）

推荐路径：**GitHub Release + 从 Git 直接安装**（不需要 Docker，也不需要 PyPI 账号）。
仓库：<https://github.com/nastenzin/groundwater-monthly-mcp>。

```powershell
# 方式 A：直接从 GitHub 安装（uv 自带工具，装一次即可）
uvx --from git+https://github.com/nastenzin/groundwater-monthly-mcp.git groundwater-mcp

# 方式 B：pip 从 Git 安装
pip install "git+https://github.com/nastenzin/groundwater-monthly-mcp.git"
groundwater-mcp

# 方式 C：从 GitHub Release 下载 wheel 后离线安装
pip install "https://github.com/nastenzin/groundwater-monthly-mcp/releases/download/v0.4.0/groundwater_monthly_mcp-0.4.0-py3-none-any.whl"
```

其他 MCP 客户端（Claude Desktop / Cursor / Cline / DSH）的 `uvx` 配置：

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

其他落地形态见 **[docs/deploy.md](docs/deploy.md)**：

| 形态 | 适用场景 | 启动/分发方式 |
| --- | --- | --- |
| GitHub Release / Git 安装（stdio） | 公开分发，零 Docker、零 PyPI | 上面的 `uvx`/`pip` 三种命令 |
| pip / uvx（本地目录） | 内网/离线 | `pip install .` 或 `uvx --from . groundwater-mcp` |
| Docker（stdio 或 HTTP） | 团队内共享、免环境配置 | `docker build -t groundwater-monthly-mcp .`（可选，非必需） |
| 远程 Streamable HTTP | 公网/内网服务化，多客户端复用 | `groundwater-mcp --transport streamable-http --host 0.0.0.0 --port 8765` + 反向代理/鉴权 |

发布流程（本仓库已配置好）：

1. 推送 `main` 分支与 `v0.4.0` tag → `.github/workflows/release.yml` 自动构建 wheel/sdist，
   并创建 GitHub Release 挂载产物（Docker 任务默认跳过，仓库变量 `PUBLISH_DOCKER=true` 时才执行）；
2. 使用者用上面的 `uvx --from git+...` 或 Release 里的 wheel 安装；
3. 如需发 PyPI（可选）：在 PyPI 配置 Trusted Publisher 后，把仓库变量 `PUBLISH_PYPI` 设为 `true`，
   之后 `uvx groundwater-monthly-mcp` 即可。


## 3. 工具清单（26 个工具 / 3 个资源 / 1 个提示词）

### 数据查询

| 工具 | 作用 |
| --- | --- |
| `describe_dataset` | 数据概况：期数、期号、各表行数、数据库位置 |
| `list_reports(year?, limit?)` | 报告期号目录 |
| `get_report(period?)` | 单期元数据、综述统计、章节结构 |
| `get_precipitation(period?, group?, unit?)` | 降水量与距平（表 1–5） |
| `get_shallow_groundwater(period?, region?, group?)` | 平均埋深、较上月/去年同期变化、面积占比、变幅分级（表 6–13） |
| `get_deep_groundwater(period?, province?)` | 深层地下水水位变幅站点占比（表 14） |
| `get_key_stations(period?, kind)` | 重点站：water / temperature / spring（表 15–17） |
| `get_time_series(metric, region?, start?, end?)` | 跨期时间序列（depth / change_prev / change_year / precip / anomaly） |
| `search_report_text(query, period?, limit?)` | 原文全文检索，返回命中页与片段 |
| `get_report_text(period?, section?, page_start?, page_end?)` | 读取原文（按章节或页码） |
| `list_tables(period?)` | 某期 17 张表的表号/标题/页码/行数 |
| `get_table(period?, table_no)` | 任意一张原始统计表（二维数组） |

### 年际基准（中国水文年报）

| 工具 | 作用 |
| --- | --- |
| `list_annual_reports()` | 已入库年报年份、地下水章节页范围与数据年份 |
| `get_annual_groundwater(year?, data_year?, region?, row_type?)` | 各平原/盆地与重点区域每年 12 月的平均埋深、同比水位/埋深变幅；`row_type=plain_basin/key_region` |

### 历年公报（中国水资源公报）

| 工具 | 作用 |
| --- | --- |
| `list_bulletin_reports()` | 已入库公报年份、来源形式（pdf/docx/html）、覆盖范围与缺失说明 |
| `get_bulletin_groundwater(year?, level="national", name?)` | 历年公报地下水数据；`level=national/region/province/plain`，`name` 按名称模糊过滤（如“海河区”“河北”“三江平原”） |
| `get_bulletin_series(metric, level="national", name?, start_year?, end_year?)` | 指标序列：`ground_resource`（地下水资源量）/`ground_supply`（地下水供水量）/`ground_share`（占比 %）/`total_supply`（总供水量）；national 另有 `plain_resource`、`plain_storage_change`；plain 级别为 `shallow_end`/`shallow_change`/`deep_end`/`deep_change` |


### 等值面连续埋深场（新增）

| 工具 | 作用 |
| --- | --- |
| `list_surface_maps(period?)` | 列出已数字化的埋深等值面图（期号、图号、覆盖区域、质量、`source`=pdf/html-thumbnail） |
| `get_depth_at_point(lat, lon, period?)` | 按经纬度从等值线反演任意点连续埋深（返回 `depth_m`、`class_range`、`quality`、`n_anchors`、`anchor_rmse_km`、`source_kind`、`off_surface` 等） |
| `get_depth_surface(period, figure?, region?, include_grid?)` | 查看某幅图的图例、定标模型、连续场统计与等级占比（含 `source_kind`）；`include_grid=true` 返回粗栅格 |
| `get_city_depth(city, period?)` | 城市点位（只作坐标）→ 该点反演埋深 |

### 位置输入（三种方式）

| 工具 | 作用 |
| --- | --- |
| `locate_by_coordinates(lat, lon, period?, include_series?)` | 经纬度 → 行政区 + 所在地貌单元 + 该单元当期数据/趋势（单元数据含 `annual_series`、`bulletin_series`） |
| `locate_by_administrative_region(province, city?, period?, include_series?)` | 行政区 → 覆盖该区的监测单元 + 数据 + 省级深层汇总 + `data.province_groundwater_history`（公报历史序列） |
| `locate_by_map_point(lat, lon, period?, include_series?)` | 地图选点坐标 → 同上（附带 map_picker 使用说明） |
| `query_by_location(...)` | 统一入口，按 `mode` 自动分派 |
| `get_map_picker()` | 返回本地交互地图 HTML 路径（浏览器打开后点击取经纬度） |

### 资源与提示词

- 资源：`groundwater://catalog`（目录 JSON）、`groundwater://report/{period}`（单期元数据）、
  `groundwater://map/picker`（地图选点页面 HTML）。
- 提示词：`region_groundwater_brief(region, period)` —— 生成某监测区某期的地下水动态简报。

## 4. 数据模型（SQLite）

`src/groundwater_mcp/data/groundwater.db` 主要表：

| 表 | 内容 | 来源 |
| --- | --- | --- |
| `reports` | 期号、发布时间、原文/ PDF 链接、站网数、深层变幅总占比、综述全文 | 综述 |
| `sections` | 章节标题与正文 | 全文 |
| `precipitation` | 大区/省/盆地 × 月降水量、距平 % | 表 1–5 |
| `shallow_regions` | 地貌单元平均埋深、较上月/去年同期变化、面积占比 | 第三章叙述 |
| `shallow_basins` | 山西六大盆地平均/最大/最小埋深及变化 | 表 11 |
| `shallow_distribution` | 埋深变幅分级（7 档）面积占比 | 表 6–13 |
| `deep_provinces` | 各省深层水位上升/稳定/下降站点占比 | 表 14 |
| `water_stations` | 裂隙水/岩溶水重点站水位及变化 | 表 15 |
| `temperature_stations` | 水温重点站水温、埋深 | 表 16 |
| `springs` | 泉流量重点站月均/最大/最小流量 | 表 17 |
| `report_tables` | 17 张表的原始行（JSON） | 全部表格 |
| `report_text` | 逐页原文（供全文检索） | 全文 |
| `annual_reports` | 年报年份、地下水章节页码、PDF/详情链接 | 中国水文年报 |
| `annual_groundwater` | 各平原/盆地、重点区域的年末（12 月）埋深与同比水位/埋深变幅 | 年报表 5-2/5-3 |
| `bulletin_reports` | 公报索引：年份、标题、详情链接、来源形式（pdf/docx/html）、页数、覆盖范围、备注（27 条，含 2025 年卷目录） | 中国水资源公报 |
| `bulletin_national` | 全国地下水资源量、地下水供水量、占比、总供水量、平原区地下水资源量、北方平原区浅层储存量较年初变化（26 条） | 公报全国表 |
| `bulletin_regions` | 10 个水资源一级区/北方 6 区/南方 4 区/全国/太湖的地下水资源量、供水量、总供水量、占比（1997 年为九大流域片口径，206 条） | 公报一级区表 |
| `bulletin_provinces` | 省级行政区的地下水资源量、地下水供水量、总供水量、占比（2011、2016-2022、2024，288 条） | 公报省级附表 |
| `bulletin_plains` | 主要平原及盆地浅层/深层年末埋深与变幅（2021/2022，29 个平原/盆地 ×2 年，58 条） | 公报平原动态表 |
| `surface_maps` | 437 幅埋深等值面图（25 个期号）的图例、粗栅格、连续场 BLOB、定标模型、bbox、`source`（pdf/html-thumbnail）、质量（medium/low、控制点数与残差）、面积一致性与均值校验字段 | 月报等值面图数字化 |

**字段约定**：`change_*_m` 表示「埋深变化」，**正值 = 埋深增大（地下水水位下降）**，
负值 = 埋深减小（水位上升）；深层数据中的上升/下降指水位。

## 5. 数据更新

```powershell
python scripts/crawl_index.py     # 抓取官方报告目录与 PDF 链接 -> data/report_index.json
python scripts/download_pdfs.py   # 下载 PDF -> data/pdfs/
python -m groundwater_mcp.ingest.build   # 重新解析并构建数据库
```

- 年报补齐：`python scripts/download_annual.py` 下载《中国水文年报》PDF，随后
  `python -m groundwater_mcp.ingest.annual_parse <年份>` 解析地下水章节，`build` 会自动并入年报数据。
- 公报补齐：按顺序执行
  `python scripts/crawl_bulletin_index.py`（抓栏目页索引）→ `python scripts/download_bulletin.py`（下载原文）
  → `python scripts/parse_bulletin_pdf.py`（解析表格/文本）→ `python scripts/build_bulletin_dataset.py`
  （生成 `data/bulletin/parsed/bulletin_dataset.json`），最后 `python -m groundwater_mcp.ingest.build`
  会自动并入 5 张 `bulletin_*` 表。
- 等值面连续场重建（查询层 `surface_query.py` 为零第三方依赖，纯标准库）：
  `python scripts\build_city_points.py`（从 88250/city-geo 的 `data.json` 生成 339 个城市点位）
  → `python scripts\build_surface_data.py`（同时扫描 `data/pdfs/` 与 `data/legacy/pdfs/`，数字化 PDF 来源 288 幅）
  → `python scripts\fetch_html_thumbs.py`（抓 2024-01~09 的 335×480 页面缩略图到 `data/surface/html/<period>/pN.jpg`）
  → `python scripts\build_surface_html.py`（缩略图期次数字化 149 幅）
  → `python scripts\postprocess_surface.py`
  → `python -m groundwater_mcp.ingest.build`（自动并入 `surface_maps` 表，437 行/25 期）。
- 解析结果缓存：`data/parsed/<YYYY-MM>.json`；全量结构化数据导出：`data/dataset.json`。
- 历史期：把可用的 PDF 写入 `data/legacy/pdfs/`，或把 HTML5 文本层逐页文件放在
  `data/legacy/html/<YYYY-MM>/pageN.html`，并在 `data/legacy_index.json` 登记（字段含 `period`、
  `pdf_file` 或 `local_path`、`pdf_url`、`source`），`build` 会自动合并；未达质量门的期号会被跳过并记录到
  `data/quality_skips.json`，避免污染数据集。
- 新增期号后重新运行以上三步即可，工具与数据库结构无需改动。

## 6. 目录结构

```
├─ src/groundwater_mcp/
│  ├─ server.py            # MCP 工具/资源/提示词
│  ├─ repository.py        # SQLite 查询层
│  ├─ paths.py             # 数据文件定位
│  ├─ geo.py               # 点面判断、行政区/监测区定位（纯标准库）
│  ├─ surface_query.py     # 等值面连续场查询层（纯标准库，无第三方依赖）
│  ├─ ingest/
│  │  ├─ pdf_parse.py      # 月报 PDF 解析（17 张表 + 叙述数据）
│  │  ├─ html_parse.py     # 2024 年官方 HTML5 文本层解析
│  │  ├─ annual_parse.py   # 《中国水文年报》地下水章节解析（表 5-2/5-3）
│  │  ├─ surface.py        # 等值面图数字化（图例→分级→等值线→连续场）
│  │  └─ build.py          # 解析 -> SQLite
│  ├─ cli.py               # 命令行入口（--transport/--host/--port）
│  └─ data/
│     ├─ groundwater.db    # 随包数据库（含 surface_maps 表）
│     ├─ geo/*.geojson     # 省/市边界 + 24 个监测区近似边界
│     ├─ geo/city_points.json  # 339 个城市点位（仅用于城市取坐标/定标）
│     └─ map/map_picker.html
├─ data/                   # 原始 PDF、索引、解析缓存
│  ├─ pdfs/                # 2024-10~2025-12 官方 PDF
│  ├─ legacy/              # 历史期 PDF（2023-12、2021-03）与 2024 年 HTML5 文本层
│  ├─ annual/              # 年报索引、地下水文本提取与解析 JSON
│  ├─ bulletin/            # 《中国水资源公报》：索引、原文/文本/表格缓存与解析 JSON
│  │  ├─ bulletin_index.json   # 公报年份、标题、详情链接、来源文件
│  │  ├─ files/            # 下载的公报 PDF/DOCX/HTML/JPG 原文
│  │  ├─ text/ htmltables/ # 网页/文档文本与表格文本
│  │  └─ parsed/bulletin_dataset.json  # 公报结构化数据（ingest.build 读取）
│  ├─ surface/             # 等值面数字化中间件（parsed/*.json，25 期；html/ 为缩略图缓存）
│  ├─ parsed/              # 单期解析缓存
│  ├─ legacy_index.json    # 历史期索引（扩展语料）
│  ├─ legacy_failures.json # 不可获取月份清单与原因
│  └─ quality_skips.json   # 未通过质量门的期号及原因
├─ docs/deploy.md          # 分发/容器/远程传输/各客户端配置指南
├─ docs/surface.md         # 等值面数字化算法、精度与限制
├─ Dockerfile / .dockerignore
├─ server.json / smithery.yaml   # MCP Registry / Smithery 清单
├─ .github/workflows/release.yml # tag 自动发布 PyPI + ghcr.io
├─ scripts/                # 抓取/下载/校验/冒烟测试/地理数据/等值面数字化脚本
└─ tests/                  # pytest 数据完整性测试
```

## 7. 验证与测试

| 测试 | 命令 | 结果 |
| --- | --- | --- |
| 数据完整性 pytest（期数、17 表、已知数值、位置三方式、年报/公报基准、等值面查询） | `python -m pytest -q tests` | 27 passed |
| MCP stdio 冒烟（tools/resources/prompts + 每个工具各调一次） | `python scripts\test_mcp.py` | 26/26 工具调用成功 |
| wheel 打包检查（DB/geo/map 是否齐全、是否混入原始 PDF） | `python scripts\package_check.py wheel` | 通过；`dist/groundwater_monthly_mcp-0.4.0-py3-none-any.whl`，5,647,599 B，sha256 `c9a87f5fe6f14153f6bac30ae73721ebb20f6a9c3fe0db5356a4d8002752dc7c` |
| 等值面数字化校验（25 期 × 18 幅尝试；等级一致性、独立均值校验） | `python scripts\verify_all.py`（59/59 项，覆盖数据与产物） | 437/437 幅等级一致性 100%；均值误差中位：PDF 0.25 m、HTML 缩略图 1.24 m、全体 0.67 m；68 幅 \|误差\|>5 m 标记 suspect |
| 解析质量检查（全部期号的表数量、占比合计、站数等） | `python scripts\qc_parse.py`、`python scripts\qc_db.py` | PROBLEMS 0；占比合计/深层总数校验通过 |
| 年报解析检查（2022 文本层表 5-2/5-3；2021 扫描件 OCR 表 5-3） | `python -m groundwater_mcp.ingest.annual_parse 2022`、`scripts/ocr_build_2021_table.py` | 29 个平原/盆地（2020/2021/2022）+ 11 个重点区域（2021/2022），逐行一致性校验通过 |
| 地理定位自检（32 个已知坐标点 + API 契约） | `python scripts\geo_check.py` | PASS 130/130 |
| 浏览器地图选点 | 打开 `data/map/map_picker.html`，点击地图 | 返回经纬度并成功查询（见 `locate_by_map_point`） |

已在该环境中通过 `mcp_register` 注册为 `groundwater-monthly` 并实际调用验证（26 个工具可见、可执行），
并用全新无上下文智能体按“2024年7月、浙江省杭州市余杭区”实测完成数据调取（发现 MCP 服务 → 调用行政区
/经纬度工具 → 返回 2024-07 浙东沿海平原与长江三角洲平原数据）。

## 8. 数据覆盖与限制

- **可用期号**：2023-12 ~ 2025-12，共 25 期连续。期号列表以 `list_reports` / `describe_dataset` 为准。
- **等值面连续埋深场**：覆盖全部 25 期月报（2023-12 ~ 2025-12），每期 18 幅、共 450 次尝试，
  13 幅因缩略图分页/裁切失败被剔除，最终 **437 幅**入库。来源：`pdf` 288 幅（2023-12 旧版 PDF 18 幅 +
  2024-10~2025-12 的 270 幅）、`html-thumbnail` 149 幅（2024-01~09，官网原大图 404，仅 335×480 缩略图）。
  等级一致性 437/437 = 100%；均值误差中位：PDF 0.25 m（p90 6.23、最大 8.43）、HTML 缩略图 1.24 m
  （p90 9.5、最大 15.33）、全体 0.67 m；68 幅 \|误差\|>5 m 标记 suspect；质量 medium 78 幅、low 359 幅
  （无 high；2023-12 旧版 PDF 有 5 幅缺质量字段，按 low 计）。
- **前期年际基准**：2020-12、2021-12、2022-12 三个时点、29 个平原/盆地 + 11 个重点区域（共 109 条记录），
  来自 2021 年卷（扫描 OCR，2020/2021）与 2022 年卷（文本层，2021/2022）。2023 年卷为扫描件且未做 OCR、
  2024/2025 年卷 PDF 存在字体编码问题，暂未入库（原始链接见 `data/annual/annual_index.json`）。
- **历年公报**：全国口径 1997-2024（1998 年仅比例、1999/2000 未公开、2023 年卷扫描未 OCR，该年 national 行保留为空）；
  水资源一级区 1997（九大流域片）+ 2010-2024（2023 缺）；省级 2011、2016-2022、2024（2011 年卷附表为
  供水量表口径，含地下水供水量）；主要平原年末埋深 2021/2022（与水文年报 2020-2022 重叠，可交叉校验）。
  2006-2009 年公报的一级区表格在网页中只是扁平化文本且内容重复，未做机读解析（仅保留全国数值）；
  2025 年卷已进入公报索引，地下水数据尚未解析。
- 公报与月报/年报口径不同：公报是年度资源量/供水量/储存量变化，月报是逐月埋深，年报是年末埋深；
  不要把不同口径的数值直接拼接成一条“埋深序列”。
- 年报深层地下水数值可能因站网/层位口径调整在后续年报中修订；跨年比较请使用库内给出的当年水位变幅字段。
- 2024-01 ~ 2024-09：官方 PDF 已 404，改用官方 HTML5 翻页书文本层重建，已入库；受文本表格换行影响，
  表 15/16/17（重点站/水温/泉流量）部分站点可能缺失，核心的降水、埋深、变幅、深层占比表完整。
- 2019-01 ~ 2023-11：官方 `zzsc` 翻页书目录与旧 PDF 均已 404，xxzx 附件文件名随机不可枚举；失败清单见
  `data/legacy_failures.json`。若后续官方恢复旧资源，按第 5 节流程可直接扩充。
- 2021-03：拿到了残留 PDF，但版式较旧（表号/指标口径不同），未通过质量门（`data/quality_skips.json`），
  为保证数据一致性未入库。
- 等值面层的“整幅图面积加权均值”与报告“区域站点平均埋深”不是同一口径，个别区域（河西走廊、关中、
  准噶尔、成都）会系统性偏差数米，属口径差异而非分类错误。
- HTML 缩略图期次（2024-01~09）官网原大图（files/page、files/large）已 404，仅存 335×480 页面缩略图；
  城市注记太小无法 OCR，定标只能用“叙述监测面积反推尺度 + 区域多边形质心”，因此 quality 固定 low，
  另有约 +1 m 的缩略图色偏/裁切偏差；`get_depth_at_point` 可能返回 `off_surface=true`（点落在图斑外，
  按最近像元取值）。`source_kind` 区分 `pdf` / `html-thumbnail`。
- “变幅图”（与上月/去年同期相比）不是埋深等值面，未纳入。
- 等值面为 10 级离散色阶，级内为插值估计，单点绝对精度受等级宽度限制（如 4~8 m 级最大约 ±2 m）；
  PDF 期次城市注记存在摆放偏移，单点查询水平定位误差约 10~20 km。`quality` 与 `anchor_rmse_km`
  逐图返回，低质量图请谨慎使用。

## 9. 精度与免责声明

- 监测区边界为近似范围（`accuracy: approximate`），定位结果中的 `relation`（`inside`/`nearby`）与
  `distance_km` 用于判断可靠程度；行政区查询可能命中多个监测区。
- 数值均来自月报/年报/公报原文；引用时请注明期号（或年报/公报年份）与来源链接。本服务器不构成任何官方发布，仅供数据检索与科研辅助。
- 等值面连续场是对 10 级色阶图件的插值反演，不是站点实测；引用时请注明“等值面反演值”、期号/图号与
  `source_kind`；HTML 缩略图期次（quality=low）精度更低，单点结果仅供趋势参考（详见
  [docs/surface.md](docs/surface.md)）。
