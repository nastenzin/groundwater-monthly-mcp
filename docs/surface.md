# 等值面图数字化：从颜色到连续埋深场

本项目新增一层数据：把《地下水动态月报》中的彩色“地下水埋深等值面图”（如“图1 三江平原和穆棱兴凯平原
12 月份地下水埋深等值面图”）数字化为**连续埋深场**，从而可以查询任意经纬度点的埋深，而不是只按行政区/
城市归类取值。

数据规模：已数字化 **全部 25 期月报（2023-12 ~ 2025-12）**，每期 18 幅、共 **450 次尝试**，其中
**13 幅因缩略图分页/裁切失败被剔除**，最终 **437 幅可用**入库（`surface_maps` 表 437 行、25 个期号）。
按来源分：`source='pdf'` **288 幅**（2023-12 旧版 PDF 18 幅 + 2024-10~2025-12 共 15 期 270 幅）、
`source='html-thumbnail'` **149 幅**（2024-01~09 共 9 期）。数字化中间件为 `data/surface/parsed/*.json`
（25 期）；HTML 缩略图缓存为 `data/surface/html/<period>/pN.jpg`（构建用，不随包分发）。
城市点位 `src/groundwater_mcp/data/geo/city_points.json` 共 339 个（WGS84），仅用于城市名取坐标/定标。

## 1. 处理流程

### 1.1 PDF 期次（288 幅）

PDF 来源包括 2023-12 旧版 PDF（页面约 900×926 等，完整 18 幅）与 2024-10~2025-12 共 15 期 270 幅，
均走同一套 PDF 数字化流程：

1. **图例解码**：从同页图例图中自动检测 10 个色块，得到等级色与埋深区间
   （<2、2~4、4~8、8~12、12~16、16~20、20~30、30~40、40~50、>50 m）。
2. **颜色分级**：Lab 空间最近色分类，排除白底、文字、河流线；抗锯齿/描边造成的空隙用最近有效像元补齐，
   得到“等级栅格”。
3. **等值线提取**：等级 i 与 i+1 的分界即上界等值线（2/4/8/12/16/20/30/40/50 m 共 9 条）。
4. **连续场重建**：对每个像元，按到上/下两条等值线的距离线性插值

   ```
   v = L_low + (L_high - L_low) × d_low / (d_low + d_high)
   ```

   最浅/最深一级向边界外推；结果钳制在所属等级区间内。
5. **经纬度定标**：城市注记（如“·哈尔滨市”）仅作为像元↔经纬度的控制点。
   尺度优先由“监测面积 = 像元面积 × k²”反推（叙述面积是独立来源），平移用各注记偏移的中位数抗差；
   无注记时用区域多边形质心兜底。**城市数据不参与数值分配**。
6. **入库**：每张图存图例、粗分辨率等级栅格（256px 长边，zlib 压缩）、连续场（BLOB）、定标模型、
   经纬度 bbox、`source`、质量指标（控制点数/残差/面积一致性）与连续场统计（均值、等级占比、等级一致性）。

### 1.2 HTML 缩略图期次（149 幅）

2024-01~09 的官网原大图（`files/page`、`files/large`）已 404，仅存 **335×480 的页面缩略图**，因此单独走一条流水线：

1. **抓取**：`fetch_html_thumbs.py` 从官方 flipbook 逐页抓缩略图到 `data/surface/html/<period>/pN.jpg`。
2. **切图**：`build_surface_html.py` 自动定位图例，按彩色图斑的垂直间隙把一页切成两幅图。
3. **定标**：城市注记太小无法 OCR，只能用“叙述监测面积反推尺度 + 区域多边形质心”；因此这 149 幅
   `quality` 固定为 `low`，并带有约 **+1 m** 的缩略图色偏/裁切偏差。
4. **入库**：与 PDF 同一套等值线/连续场算法，`source='html-thumbnail'`。

## 2. 查询接口

| 工具 | 说明 |
| --- | --- |
| `list_surface_maps(period?)` | 已数字化图件清单：期号、图号、覆盖区域、质量、`source`（pdf/html-thumbnail）；省略 `period` 返回全部 25 期 |
| `get_depth_at_point(lat, lon, period?)` | 任意经纬度点：返回连续埋深 `depth_m`、所在等级 `class_range`、`quality`、控制点数 `n_anchors`、控制点残差 `anchor_rmse_km`、`source_kind`（pdf/html-thumbnail）与 `off_surface`（点落在图斑外时按最近像元取值）；跨期查询返回各期结果 |
| `get_depth_surface(period, figure?, region?, include_grid?)` | 查看某幅图的图例、定标模型、连续场统计、等级占比与 `source_kind`；`figure` 为图号，`region` 用于按地貌单元筛选，`include_grid=true` 返回粗分辨率等级栅格 |
| `get_city_depth(city, period?)` | 城市点位（仅坐标）→ 该点由等值面反演的埋深 |

位置查询 `locate_by_coordinates` / `locate_by_map_point` 的结果中新增 `data.surface_depth`（全部 25 期，
含 `source_kind` 与 `off_surface`）。

## 3. 校验与精度

* **等级一致性**：反演值落在其颜色等级区间内的像元占比（逐图输出）。本批 **437/437 = 100%**。
* **面积一致性**：由定标尺度反推的图斑面积 vs 叙述监测面积（`area_ratio`，正常应接近 1.0）。
* **独立均值校验**：整幅图的面积加权平均埋深 vs 叙述的“区域平均埋深”加权值（`mean_error_m`），
  该指标与定标无关，可检验颜色分级/等值线是否正确。均值误差中位：`pdf` 来源 **0.25 m**
  （p90 6.23、最大 8.43）、`html-thumbnail` 来源 **1.24 m**（p90 9.5、最大 15.33）、全体 **0.67 m**；
  **68 幅** |误差| > 5 m 已标记为 suspect。
* **口径说明**：整幅图“面积加权均值”与报告“区域站点平均埋深”不是同一口径，个别区域
  （河西走廊、关中、准噶尔、成都）会系统性偏差数米，属口径差异而非分类错误。
* **定标质量**：本批无 high，medium 78 幅、low 359 幅（其中 2023-12 旧版 PDF 的 5 幅缺质量字段，按 low 计）。
  PDF 期次城市注记位置存在摆放偏移（常见 ±10~20 km），控制点残差通常 10~20 km，单点查询水平定位误差约
  **10~20 km**；HTML 缩略图期次另有约 +1 m 色偏/裁切偏差。`quality` 与 `anchor_rmse_km` 逐图返回。

## 4. 与旧数据的区别

* 旧数据（`shallow_regions.mean_depth_m`）是**报告给出的区域平均值**，一个监测区一个数；
* 新数据是**图上等值线反演的连续场**，同一监测区内不同点可有不同值（如 4.3 m、5.7 m、9.2 m），
  `get_depth_at_point` 返回的是后者。

## 5. 数据与重建

* **数据表**：`surface_maps` 437 行/25 期，字段含图例、粗栅格、连续场 BLOB、定标模型、bbox、
  `source`、质量（medium/low、控制点数、`anchor_rmse_km`）、面积一致性与均值校验字段；随包数据库约
  **7,608 KB（7,790,592 B）**。
* **查询层**：`src/groundwater_mcp/surface_query.py` 为零第三方依赖（纯标准库）；数值已在入库时预计算，
  查询只做解码 + 双线性取样，不重新执行图像数字化。
* **重建顺序**（`scripts/`；PDF/缩略图数字化需要 `[ingest]` 依赖 numpy/cv2/scipy）：
  `build_city_points.py`（生成 339 个城市点位）
  → `build_surface_data.py`（同时扫描 `data/pdfs/` 与 `data/legacy/pdfs/`，数字化 PDF 来源 288 幅）
  → `fetch_html_thumbs.py`（抓 2024-01~09 缩略图到 `data/surface/html/`）
  → `build_surface_html.py`（缩略图期次数字化 149 幅）
  → `postprocess_surface.py`（后处理/校验）
  → `python -m groundwater_mcp.ingest.build`（并入 `surface_maps` 表）。

## 6. 使用示例

```text
list_surface_maps(period="2024-05")
get_depth_surface(period="2024-05", figure=1)
get_depth_at_point(lat=43.85, lon=125.30, period="2024-05")   # HTML 缩略图期 → depth=8.0 m、source_kind=html-thumbnail、off_surface=true
get_depth_at_point(lat=45.75, lon=126.63, period="2025-12")   # PDF 期
get_city_depth(city="哈尔滨", period="2025-12")                # → depth=20.31 m（松嫩平原）
```

`depth_m` 是连续值（如 5.7 m），不是分级区间中点；`class_range` 给出它所属的 10 级区间。HTML 缩略图期次
若返回 `off_surface=true`，表示查询点落在该图彩色图斑之外，数值按最近像元外推，仅供趋势参考。

## 7. 已知限制

* 2024-01 ~ 2024-09 的官网原大图（`files/page`、`files/large`）已 404，仅存 335×480 页面缩略图；
  9 期 × 18 幅尝试中有 13 幅因缩略图分页/裁切失败被剔除（最终 149 幅）。这些期次城市注记太小无法 OCR，
  只能用“叙述监测面积反推尺度 + 区域多边形质心”定标，`quality` 固定 `low`，另有约 +1 m 色偏/裁切偏差，
  且 `get_depth_at_point` 可能返回 `off_surface=true`（点落在图斑外，按最近像元取值）。
* 图例为 10 级离散色阶，级内为插值估计，单点绝对精度受等级宽度限制（如 4~8 m 级最大约 ±2 m）。
* 变幅图（“与上月/去年同期相比变幅图”）不是埋深等值面，未纳入本层数据。
* 整幅图“面积加权均值”与报告“区域站点平均埋深”不是同一口径，河西走廊、关中、准噶尔、成都等区域
  会系统性偏差数米，属口径差异而非分类错误。
* PDF 期次城市注记存在摆放偏移，单点查询水平定位误差约 10~20 km；`quality`（medium/low）与
  `anchor_rmse_km` 逐图返回，低质量图请谨慎使用。
* 等值面为图面反演值，非站点实测；引用时请注明“等值面反演”、期号/图号与 `source_kind`。
