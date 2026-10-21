# 数据血缘与“颜色信息”审计

结论先行：**本项目没有从图片颜色中提取任何数值。** 数据库里的埋深、变幅、占比、供水量等全部来自
文字/表格（PDF 文本层、DOCX 表格、HTML 文本层，以及扫描件的文字 OCR）；报告中的彩色
“地下水埋深等值面图”没有被数字化，也没有参与计算。

## 1. 代码审计

| 检查 | 结果 |
| --- | --- |
| `src/groundwater_mcp/ingest/*.py` 是否有取色/像素/颜色分类逻辑 | 无（`grep color|rgb|pixel|pixmap|Image|颜色` 无命中） |
| 解析入口 | `pdf_parse.py`：`page.extract_tables()` + `page.extract_text_lines()`（文本层） |
| HTML 期次 | `html_parse.py`：FlipBuilder 文本层 `pageN.html` 的文本流，无图像处理 |
| 扫描件（2021 年水文年报） | `scripts/ocr_annual_table.py`：页面渲染为 PNG 后交给 RapidOCR，**只取识别文字与坐标**，不做颜色分割；`ocr_build_2021_table.py` 按“区域锚点 + 列坐标”重建表格 |
| 表格探测辅助脚本 | `scripts/detect_tables_scan.py`：仅把页面转灰度、统计横向表格线，用于找“表格页”，不产出数值 |
| 地图选点 | `get_map_picker` 是浏览器端交互 UI（Leaflet 取经纬度），与数据提取无关 |

## 2. 每条数据的来源（可直接在库内核对）

| 数据 | 库表/字段 | 来源证明 |
| --- | --- | --- |
| 月报各监测区平均埋深、较上月/去年同期变化 | `shallow_regions.mean_depth_m / change_*` | `raw_sentence` 保存原文句子，如“三江平原12月份地下水平均埋深 8.6m…” |
| 月报 17 张原始统计表 | `report_tables.rows_json` | 保存 PDF 表格单元格逐格文本（表号、标题、页码齐全） |
| 月报降水 | `precipitation` | 表 1–5 单元格（表号 + 地貌单元/省 + mm/%） |
| 月报变幅分级占比 | `shallow_distribution` | 表 8–13 的数值单元格（%），每组合计校验≈100% |
| 水文年报年末埋深 | `annual_groundwater` | `source_table`（表5-2/5-3）、`source_page`；`annual_reports.source_kind` = `pdf-text-layer` / `pdf-scan-ocr` |
| 水资源公报 | `bulletin_*` | `source` 字段标注 `html-table` / `docx` / `pdf`，并带页码 |

## 3. 源文件里确实有“靠颜色看”的图，但没有被使用

以 2025-12 期月报为例：第 7 页含 **图1“三江平原和穆棱兴凯平原12月份地下水埋深等值面图”**，
该页渲染后采样到数千种颜色（典型彩色等值面/色斑图）。本项目：**不读取该图，不按图例配色分级，
不描等值线，也不从色块反算埋深**。同页的“表6 三江平原和穆棱兴凯平原12月份与上月、去年同期相比
地下水埋深变化”才是入库数值来源；区域平均埋深则来自正文叙述。

因此，本项目的数据粒度是“表格/文字口径”：

- 有：区域平均埋深、与上月/去年同期变幅、变幅分级面积占比、重点站水位/水温/泉流量、年际与历年公报统计值；
- 没有：等值面图逐像元/逐网格的连续埋深面、图例颜色→埋深分级的栅格数据。

## 4. 两个需要如实说明的边界

1. **监测单元边界是手工近似多边形**（`src/groundwater_mcp/data/geo/units.geojson`），不是从报告色图上
   自动描边得到的，也不参与数值计算，只用于把输入位置映射到监测区；定位结果带 `relation/confidence`。
2. **扫描件 OCR 只识别文字**，可能有个别误识；2021 年报表已用“埋深差 = 水位变幅”逐行校验（29/29 通过），
   并与 2022 年卷重叠年份交叉比对。

## 5. 若确实需要“颜色里的信息”

需要另做一条独立管线：PDF 图件提取 → 图例（色标/分级）识别 → 颜色聚类/分割 → 与地理底图配准 →
精度评估（并与表格值交叉验证）。这属于“图件数字化”，当前项目没有做，也不应把现有库当作
“色斑图反演结果”。

## 6. 复核方式

```powershell
python scripts\verify_all.py        # 48 项数据与产物核验
python scripts\show_provenance.py   # 打印本文第 2 节的血缘样例
python scripts\check_images.py      # 查看月报中图件页分布与图题
python scripts\check_figure_colors.py  # 验证等值面图确为彩色图（仅审计，不取数）
```
