# 地图选点功能黑盒测试报告

- 测试对象：MCP 工具 `get_map_picker` / `locate_by_map_point` / `query_by_location(mode="map_point")`，以及 MCP 资源 `groundwater://map/picker` 和随包页面 `src/groundwater_mcp/data/map/map_picker.html`
- 测试类型：端到端黑盒（Python 直接调用 + MCP stdio 协议 + Chrome 真实浏览器交互 + 回归）
- 测试时间：2026-10-21
- 总体结论：**功能可用，全部用例 PASS**（A 静态/契约 29/29，B 浏览器交互 12/12，C 回归 2/2，D 边界 8/8；修复 1 处描述不一致小问题，新增 2 个地图选点回归测试）

---

## 1. 测试环境

| 项目 | 值 |
| --- | --- |
| 操作系统 | Windows（工作目录 `D:\MCP服务器`） |
| Python | 3.13.9（Anaconda） |
| MCP SDK | `mcp` 2.3.0（`mcp.server.mcpserver.MCPServer`） |
| 服务器版本 | `groundwater-monthly` 0.4.0，26 个工具、2 个资源、1 个资源模板、1 个 prompt |
| 安装方式 | `pip install -e .`（源码目录 `src/` 生效；测试同时用 `PYTHONPATH=src`） |
| 数据库 | 随包 `src/groundwater_mcp/data/groundwater.db`，查询期号 `2025-12` |
| 浏览器 | Chrome 153.0.0.0（Chrome DevTools MCP 自动化），视口 1280×656 CSS px，DPR 1.5 |
| 页面 URL | `file:///D:/MCP%E6%9C%8D%E5%8A%A1%E5%99%A8/src/groundwater_mcp/data/map/map_picker.html`（中文路径已 URL 编码） |
| 编码设置 | PowerShell 中 `$env:PYTHONIOENCODING='utf-8'`，Python 侧 `$env:PYTHONPATH='src'` |

页面加载后的运行时信息（`evaluate_script` 实测）：

```json
{"title":"地下水动态月报 · 地图选点取坐标","readyState":"complete","leafletVersion":"1.9.4",
 "mapSize":{"x":960,"y":656},"zoom":4,"center":{"lat":35,"lng":105},
 "basemapOptions":["osm","gaode","esri","none"],"leafletLoaded":true}
```

---

## 2. 测试方法与证据来源

- **A. 静态/契约**：`from groundwater_mcp import server` 直接调用；同时用 `mcp.client.stdio` 启动 `python -m groundwater_mcp`，走真实 MCP 协议 `initialize / list_tools / list_resources / read_resource`。HTML 本地资源引用用正则解析后逐个校验存在性。
- **B. 浏览器真实交互**：Chrome DevTools MCP 打开本地 `file://` 页面；通过 `initScript` 在 Leaflet 初始化时捕获 `window.__mapPickerMap`（仅测试注入，不改页面源码），用 `map.latLngToContainerPoint()` 计算目标像素后向 `#map` 派发真实 `mousedown/mouseup/click` DOM 事件（等价于用户点击），读取页面显示值。离线用 CDP `Network.emulateNetworkConditions=Offline` 模拟。
- **C. 回归**：`python -m pytest -q tests`；`python scripts\test_mcp.py`。
- **D. 边界**：直接调用工具函数并捕获 `repo.DataError` 类型与消息。

---

## 3. 用例矩阵与结果

### A. 静态 / 契约（29/29 PASS）

| ID | 用例 | 结果 | 实际输出摘要 |
| --- | --- | --- | --- |
| A1 | `get_map_picker()` 字段齐全 | ✅ PASS | 返回键：`exists, how_to, note, picker_path, resource_uri` |
| A2 | `exists=True` | ✅ PASS | `True` |
| A3 | `picker_path` 指向真实文件 | ✅ PASS | `D:\MCP服务器\src\groundwater_mcp\data\map\map_picker.html`（is_file=True） |
| A4 | `picker_path` 位于包内 `data/map` | ✅ PASS | 与 `PACKAGE_DIR/data/map/map_picker.html` 一致 |
| A5 | `resource_uri` 正确 | ✅ PASS | `groundwater://map/picker` |
| A6 | `how_to` 为使用说明列表 | ✅ PASS | 3 条说明（含 `locate_by_map_point` 与 `query_by_location(mode='map_point')`） |
| A7 | `note` 说明离线能力 | ✅ PASS | 提及“Leaflet 已随包分发…离线也能加载页面并取坐标；底图瓦片需要联网，离线时可切换‘无底图’” |
| A8 | `map_picker_resource()` 内容 == 文件内容 | ✅ PASS | 均为 5585 字符，完全相等 |
| A9 | HTML 本地引用资源均存在 | ✅ PASS | 本地引用 `['leaflet.js', 'leaflet.css']`，缺失 `[]` |
| A10 | `data/map/leaflet.js` 存在 | ✅ PASS | 147552 B |
| A11 | `data/map/leaflet.css` 存在 | ✅ PASS | 14806 B |
| A12 | 页面含本地 `leaflet.js` 脚本 | ✅ PASS | `src="leaflet.js"` |
| A13 | 页面含点击处理逻辑 | ✅ PASS | `map.on('click', ...)` |
| A14 | 页面含坐标显示元素 | ✅ PASS | `id="coord"` |
| A15 | 页面含“无底图（离线可用）” | ✅ PASS | `value="none"` 且含“无底图”文案 |
| A16 | 页面含复制按钮 | ✅ PASS | `copyLatLon` / `copyJson` |
| A17 | 页面含本地 `leaflet.css` | ✅ PASS | `href="leaflet.css"` |
| A18 | MCP 工具列表含 `get_map_picker` | ✅ PASS | 共 26 个工具 |
| A19 | 工具列表含 `locate_by_map_point` | ✅ PASS | `True` |
| A20 | `get_map_picker` 工具描述正确 | ✅ PASS | “获取‘地图选点’用的本地交互地图…” |
| A21 | 资源列表含 `groundwater://map/picker` | ✅ PASS | `['groundwater://catalog', 'groundwater://map/picker']` |
| A22 | MCP 协议读取资源内容 == 文件 | ✅ PASS | 5585 字符，逐字符相等 |
| A23 | 资源 `mime_type=text/html` | ✅ PASS | 协议返回 `text/html` |
| A24 | 资源内容含 `leaflet.js` | ✅ PASS | `True` |
| A25 | 资源内容含点击逻辑 | ✅ PASS | `True` |
| A26 | 资源内容含坐标显示元素 | ✅ PASS | `True` |
| A27 | `locate_by_map_point` 返回 `mode=map_point` | ✅ PASS | `map_point` |
| A28 | 返回含 `map_picker` 附加说明 | ✅ PASS | `{"how_to": "...", "resource_uri": "groundwater://map/picker"}` |
| A29 | `input` 含 `lat/lon/picked_on` | ✅ PASS | `{"lat": 39.9, "lon": 116.4, "picked_on": "map"}` |

真实 MCP stdio 会话输出：

```text
server: groundwater-monthly 0.4.0
tools: 26 [... 'get_map_picker']
resources: ['groundwater://catalog', 'groundwater://map/picker']
resource templates: ['groundwater://report/{period}']
prompts: ['region_groundwater_brief']
```

### B. 浏览器真实交互（12/12 PASS）

| ID | 用例 | 结果 | 实际输出摘要 |
| --- | --- | --- | --- |
| B1 | `file://` 页面加载成功 | ✅ PASS | 标题“地下水动态月报 · 地图选点取坐标”，`readyState=complete`；控制台无 JS 错误 |
| B2 | Leaflet 本地加载可用 | ✅ PASS | `L.version = "1.9.4"`，`.leaflet-container` 存在；`leaflet.js/css` 请求均 200（file://） |
| B3 | 点击北京 (39.90, 116.40) 取坐标 | ✅ PASS | 页面显示 `lat = 39.90974` / `lon = 116.36719`；状态“已选点”；marker 数=1 |
| B4 | 误差 < 0.05° | ✅ PASS | 纬度误差 **0.00974°**，经度误差 **0.03281°** |
| B5 | 第二次点击广州 (23.13, 113.26) 更新坐标 | ✅ PASS | 页面显示 `lat = 23.16056` / `lon = 113.29102`；marker 数仍=1（位置更新为 `translate3d(574px,483px,0)`）；误差 **0.03056°/0.03102°** |
| B6 | 坐标显示格式正确 | ✅ PASS | `coord.textContent` 为两行 `lat = …\nlon = …`，`coord.dataset.lat/lon` 同步；顺序为 lat, lon，与工具参数一致 |
| B7 | `locate_by_map_point` vs `locate_by_coordinates`（北京） | ✅ PASS | 除 `mode/input/map_picker` 外 **payload 完全一致**；均命中 `海河平原`，`shallow_depth.mean_depth_m=10.6`，`resolution_confidence=high`，`surface_depth.count=1` |
| B8 | 同上（广州） | ✅ PASS | 除 `mode/input/map_picker` 外 **payload 完全一致**；均命中 `广东珠江三角洲平原`，`mean_depth_m=3.4`，`surface_depth.count=1` |
| B9 | `query_by_location(mode="map_point")` 与直接调用一致 | ✅ PASS | 两地均为 `ql == locate_by_map_point(...)`（mode=`map_point`，payload 完全相同） |
| B10 | 离线模式可加载并可取坐标 | ✅ PASS | CDP `networkConditions=Offline` 后刷新：Leaflet 仍为本地 1.9.4，页面可交互；15 个底图瓦片全部加载失败（预期）；切换“无底图”后瓦片节点数=0；点击北京仍得到 `39.90974, 116.36719`（误差 0.00974°/0.03281°），marker 正常；反向地理编码失败时页面提示“所属行政区：反向解析失败（可继续使用坐标）” |
| B11 | 复制按钮交互 | ✅ PASS | 点击“复制 JSON”后状态栏显示“已复制到剪贴板”（无 JS 异常）；页面生成的 JSON 可由 dataset 还原为 `{"lat":23.16056,"lon":113.29102}` |
| B12 | 联网恢复 | ✅ PASS | 关闭网络模拟后刷新：`leaflet.js/css` 200、OSM 瓦片请求恢复 200，页面正常，控制台无错误 |

> 说明：B10 中 CDP 离线模拟下 `navigator.onLine` 仍可能为 `true`（Chromium 行为），因此以“瓦片全部加载失败 + 反向地理编码失败 + 仍能取坐标”作为离线生效的证据。

### C. 回归（2/2 PASS）

| ID | 用例 | 结果 | 实际输出摘要 |
| --- | --- | --- | --- |
| C1 | `python -m pytest -q tests` | ✅ PASS | **29 passed**（原 27 项 + 本次新增 2 项地图选点测试） |
| C2 | `python scripts\test_mcp.py` | ✅ PASS | `26/26 tool calls succeeded`，退出码 0；`get_map_picker`、`locate_by_map_point` 均 ok 且 `is_error=false`；结果写入 `data/mcp_smoke_result.json`（脚本既有行为） |

### D. 边界（8/8 PASS）

| ID | 用例 | 结果 | 异常类型与消息 |
| --- | --- | --- | --- |
| D1 | `locate_by_map_point(999, 116.4)` | ✅ PASS | `DataError`：`经纬度超出合法范围：lat∈[-90,90]，lon∈[-180,180]` |
| D2 | `locate_by_map_point(39.9, 999)` | ✅ PASS | 同上 |
| D3 | `locate_by_map_point("abc", 116.4)` | ✅ PASS | `DataError`：`经纬度必须是数字` |
| D4 | `query_by_location(mode="map_point")` 缺 lat/lon | ✅ PASS | `DataError`：`地图选点模式需要同时提供 lat 和 lon` |
| D5 | 仅给 lat | ✅ PASS | 同 D4 清晰报错 |
| D6 | 仅给 lon | ✅ PASS | 同 D4 清晰报错 |
| D7 | `query_by_location(mode="map_point", lat=999)` | ✅ PASS | `DataError`：经纬度超范围 |
| D8 | 省略 mode + 同时给 lat/lon，自动走 `coordinates` | ✅ PASS | `mode="coordinates"`（符合文档“省略时按参数自动判断”） |

---

## 4. 发现的问题

| 编号 | 严重度 | 问题 | 处理 |
| --- | --- | --- | --- |
| P1 | 低（文档/字段不一致） | `get_map_picker()` 的 `how_to[1]` 原文为“在地图上点击目标位置，页面会显示经纬度并**自动复制 JSON**”，但页面实际不会自动复制，只显示坐标并提供“复制 lat, lon / 复制 JSON”两个按钮。 | **已修复**：改为“在地图上点击目标位置，页面会显示经纬度，可点按钮复制 lat, lon 或 JSON”。 |
| P2 | 观察项（外部环境） | 首次打开页面时，若使用默认 OpenStreetMap 底图，部分环境会返回 HTTP 403（OSM 志愿者瓦片服务器的使用政策拦截，页面显示 “Access blocked … tile usage policy of OpenStreetMap”）。此时地图区域无底图，但取坐标功能不受影响；切换“无底图”或其它底图即可。恢复网络后重载，瓦片请求实测恢复 200。 | 非代码 bug，未改代码；建议在页面/文档已有“底图瓦片需要联网”提示基础上，用户遇到 403 时改用高德/Esri/无底图。 |
| P3 | 观察项（无头环境限制） | 自动化环境点击“复制 JSON”后状态栏显示成功，但 `navigator.clipboard.readText()` 返回空串，无法在无头/无用户激活场景下验证系统剪贴板内容；页面在写入失败时已有“复制失败，请手动选择文本复制”的兜底提示。 | 非页面逻辑缺陷，未改代码；坐标本身可从 `#coord` 文本与 `dataset` 读取，不影响主流程。 |
| P4 | 说明（非缺陷） | 坐标以 `toFixed(5)`（约 1 m）显示；经像素取整，实测点击 (39.90,116.40) 显示为 (39.90974,116.36719)，偏差 ≤0.033°，满足 <0.05° 要求。若用户需要更高精度，可在页面上继续放大地图后点击。 | 无需修改。 |

---

## 5. 修复内容与改动文件

| 文件 | 改动 | 说明 |
| --- | --- | --- |
| `src/groundwater_mcp/server.py` | `get_map_picker()` 的 `how_to` 第 2 条文案（1 行） | 删除“自动复制 JSON”这一与实际行为不符的描述，改为“可点按钮复制 lat, lon 或 JSON”；仅涉及地图选点相关代码 |
| `tests/test_integrity.py` | 新增 `test_map_picker_contract`、`test_map_point_matches_coordinates`，并在 `test_location_out_of_range` 中补 1 个 `locate_by_map_point` 越界断言 | 覆盖：字段/路径/资源一致性、本地 Leaflet 资源存在性、点击逻辑与无底图元素、地图点选与经纬度查询 payload 一致、越界与缺参报错。pytest 由 27 项增至 **29 项** |
| `docs/map_picker_test.md` | 新增本报告 | 测试环境、用例矩阵、证据、问题与修复记录 |

未改动：`data/`（数据库与数据文件）、`pyproject.toml`、Docker/发布产物；未重建 wheel/镜像；未执行 `git push`。

---

## 6. 可复核命令与数据

```powershell
# A + D：静态契约、坐标一致性与边界（可直接内联运行等价脚本；此处为测试用一次性脚本路径）
$env:PYTHONIOENCODING='utf-8'; $env:PYTHONPATH='src'
python -c "from groundwater_mcp import server; import json; print(json.dumps(server.get_map_picker(), ensure_ascii=False, indent=1))"
python -c "from groundwater_mcp import server; print(server.map_picker_resource()[:120])"
python -c "from groundwater_mcp import server; mp=server.locate_by_map_point(39.90,116.40,period='2025-12'); co=server.locate_by_coordinates(39.90,116.40,period='2025-12'); print(mp['mode'], [u['name'] for u in mp['matched_units']], mp['data']['units'][0]['shallow_depth']['mean_depth_m']); print(co['mode'], [u['name'] for u in co['matched_units']], co['data']['units'][0]['shallow_depth']['mean_depth_m'])"

# C：回归
$env:PYTHONIOENCODING='utf-8'
python -m pytest -q tests          # 期望 29 passed
python scripts\test_mcp.py         # 期望 26/26 tool calls succeeded
```

浏览器复核：

1. 用 Chrome 打开 `file:///D:/MCP%E6%9C%8D%E5%8A%A1%E5%99%A8/src/groundwater_mcp/data/map/map_picker.html`；
2. 点击地图任意位置，右侧 `#coord` 显示两行 `lat = …` / `lon = …`，并有红色 marker；
3. 底图下拉选择“无底图（离线可用）”，断网后仍可点击取坐标；
4. 把坐标传给 `locate_by_map_point(lat, lon, period="2025-12")`，与 `locate_by_coordinates` 对比应一致。

本次关键实测值（可直接复核）：

| 点击目标 | 页面显示 | 纬度误差 | 经度误差 | 命中单元 | payload 对比 |
| --- | --- | --- | --- | --- | --- |
| 北京 (39.90, 116.40) | (39.90974, 116.36719) | 0.00974° | 0.03281° | 海河平原 | 与经纬度查询完全一致 |
| 广州 (23.13, 113.26) | (23.16056, 113.29102) | 0.03056° | 0.03102° | 广东珠江三角洲平原 | 与经纬度查询完全一致 |
| 离线·北京（无底图） | (39.90974, 116.36719) | 0.00974° | 0.03281° | 海河平原 | 离线仍可取坐标 |

---

## 7. 仍需注意

1. **底图联网依赖**：Leaflet 本体随包分发、离线可用；底图瓦片仍需联网。默认 OSM 底图在部分网络/自动化环境会被 OSM 使用政策拦截（403），可用“无底图”继续取坐标，或切换高德/Esri。建议在面向用户的说明中保留该提示。
2. **打包**：`pyproject.toml` 的 `[tool.setuptools.package-data]` 已包含 `data/map/*`，wheel 会带上 `leaflet.js|css` 与 `map_picker.html`；本次按授权未重建 wheel/镜像，发布时需按既有流程重新打包以包含 `server.py` 文案修复。
3. **测试项数变化**：新增 2 个地图选点测试后，`pytest tests` 期望值为 **29 passed**（原基线 27）。
4. **反向地理编码**：页面点击后会请求 Nominatim 显示“所属行政区”，离线/被限流时失败属预期；失败提示“可继续使用坐标”，不影响主流程。
