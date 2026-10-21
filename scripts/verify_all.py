# -*- coding: utf-8 -*-
"""全量核验：数据库内容、覆盖率、已知值、交叉校验、位置查询、产物文件。

输出：
  data/verification_report.json  机器可读报告
  docs/verification.md           人读报告（核验结果表）
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "src" / "groundwater_mcp" / "data" / "groundwater.db"
checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append({"name": name, "ok": bool(ok), "detail": detail})
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""))


conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row


def q(sql: str, params=()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params))


def one(sql: str, params=()):
    return conn.execute(sql, params).fetchone()


# ---------------------------------------------------------------- 数据库完整性
check("SQLite integrity_check", one("PRAGMA integrity_check")[0] == "ok")
check("数据库文件存在且 > 2.5MB", DB.exists() and DB.stat().st_size > 2_500_000,
      f"{DB.stat().st_size} B")

# ---------------------------------------------------------------- 月报
periods = [r["period"] for r in q("SELECT period FROM reports ORDER BY period DESC")]
check("月报期数 = 25", len(periods) == 25, str(len(periods)))
check("月报时间范围 2023-12 ~ 2025-12",
      periods[0] == "2025-12" and periods[-1] == "2023-12")
check("月报期号唯一", len(set(periods)) == len(periods))
bad_tables = [p for p in periods
              if one("SELECT COUNT(*) FROM report_tables WHERE period=?", (p,))[0] != 17]
check("每期 17 张表", not bad_tables, str(bad_tables[:3]))
bad_text = [p for p in periods if one("SELECT COUNT(*) FROM report_text WHERE period=?", (p,))[0] < 20]
check("每期原文页数 ≥20", not bad_text, str(bad_text[:3]))
precip_counts = {p: one("SELECT COUNT(*) FROM precipitation WHERE period=?", (p,))[0] for p in periods}
check("每期降水行 34/35", all(v in (34, 35) for v in precip_counts.values()),
      str(sorted(set(precip_counts.values()))))
check("每期浅层叙述 24 行",
      all(one("SELECT COUNT(*) FROM shallow_regions WHERE period=?", (p,))[0] == 24 for p in periods))
# 已知值
row = one("SELECT * FROM shallow_regions WHERE period='2025-12' AND region='三江平原'")
check("已知值：2025-12 三江平原埋深 8.6", row and abs(row["mean_depth_m"] - 8.6) < 1e-6)
row = one("SELECT * FROM precipitation WHERE period='2025-12' AND unit='松嫩平原'")
check("已知值：2025-12 松嫩平原降水 6.8mm", row and abs(row["precip_mm"] - 6.8) < 1e-6)
row = one("SELECT * FROM deep_provinces WHERE period='2025-12' AND province='河北'")
check("已知值：2025-12 河北深层站 476", row and row["total_stations"] == 476)
row = one("SELECT * FROM water_stations WHERE period='2025-12' AND station='南屯村'")
check("已知值：2025-12 南屯村水位 779.6", row and abs(row["water_level_m"] - 779.6) < 1e-6)
row = one("SELECT * FROM springs WHERE period='2025-12' AND station='涞源泉'")
check("已知值：2025-12 涞源泉 0.330", row and abs(row["mean_flow_m3s"] - 0.330) < 1e-6)
# 分布合计
bad_dist = q("""SELECT period, table_no, method, ROUND(SUM(share_pct),1) AS s
                FROM shallow_distribution GROUP BY period, table_no, method
                HAVING ABS(s-100) > 1.0""")
check("埋深变幅分布合计≈100%", not bad_dist, f"{len(bad_dist)} 组异常")
# 变幅缺失
null_chg = one("""SELECT COUNT(*) FROM shallow_regions
                  WHERE period>='2024-01' AND mean_depth_m IS NOT NULL
                    AND change_prev_month_m IS NULL AND change_last_year_m IS NULL""")[0]
check("2024 年后叙述行无全空变幅", null_chg == 0, f"{null_chg} 行")

# ---------------------------------------------------------------- 水文年报
check("年报 2 卷", one("SELECT COUNT(*) FROM annual_reports")[0] == 2)
check("年报表 109 行", one("SELECT COUNT(*) FROM annual_groundwater")[0] == 109)
check("年报表数据年份 2020/2021/2022",
      {r[0] for r in q("SELECT DISTINCT data_year FROM annual_groundwater")} == {2020, 2021, 2022})
row = one("""SELECT * FROM annual_groundwater WHERE data_year=2022 AND region='三江平原'
             AND row_type='plain_basin'""")
check("已知值：2022 年报三江平原埋深 8.3", row and abs(row["shallow_depth_m"] - 8.3) < 1e-6)
check("年报区域 ≥ 29", one("""SELECT COUNT(DISTINCT region) FROM annual_groundwater
                              WHERE row_type='plain_basin'""")[0] >= 29)

# ---------------------------------------------------------------- 公报
check("公报目录 27 年", one("SELECT COUNT(*) FROM bulletin_reports")[0] == 27)
check("公报全国 26 年", one("SELECT COUNT(*) FROM bulletin_national")[0] == 26)
check("公报一级区 206 行", one("SELECT COUNT(*) FROM bulletin_regions")[0] == 206)
check("公报省级 288 行", one("SELECT COUNT(*) FROM bulletin_provinces")[0] == 288)
check("公报平原 58 行", one("SELECT COUNT(*) FROM bulletin_plains")[0] == 58)
years_nat = {r[0] for r in q("SELECT year FROM bulletin_national")}
check("公报全国年份覆盖 1997-2024（缺 1999/2000）",
      years_nat == set(range(1997, 2025)) - {1999, 2000})
check("公报省级年份 = 2011、2016-2022、2024",
      {r[0] for r in q("SELECT DISTINCT year FROM bulletin_provinces")}
      == {2011, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2024})
check("公报一级区年份含 1997/2010-2024",
      {1997, 2010, 2024} <= {r[0] for r in q("SELECT DISTINCT year FROM bulletin_regions")})
nat = {r["year"]: r for r in q("SELECT * FROM bulletin_national")}
check("已知值：1997 地下水资源量 6942.38", abs(nat[1997]["ground_resource_1e8m3"] - 6942.38) < 1e-6)
check("已知值：1997 地下水供水量 1031.49", abs(nat[1997]["ground_supply_1e8m3"] - 1031.49) < 1e-6)
check("已知值：2022 地下水资源量 7924.4", abs(nat[2022]["ground_resource_1e8m3"] - 7924.4) < 1e-6)
check("已知值：2022 地下水供水量 828.2", abs(nat[2022]["ground_supply_1e8m3"] - 828.2) < 1e-6)
# 北方 + 南方 = 全国
agg_bad = []
for y in {r["year"] for r in q("SELECT DISTINCT year FROM bulletin_regions")}:
    rows = {r["region"]: r for r in q("SELECT * FROM bulletin_regions WHERE year=?", (y,))}
    if all(k in rows for k in ("全国", "北方6区", "南方4区")):
        for f in ("ground_resource_1e8m3", "ground_supply_1e8m3"):
            a, b, c = (rows["全国"][f], rows["北方6区"][f], rows["南方4区"][f])
            if None not in (a, b, c) and abs(a - b - c) > 1.0:
                agg_bad.append((y, f, a, b, c))
check("公报一级区 北方+南方=全国", not agg_bad, str(agg_bad[:3]))
# 省级和 = 全国
prov_bad = []
for y in {r["year"] for r in q("SELECT DISTINCT year FROM bulletin_provinces")}:
    natrow = one("SELECT ground_supply_1e8m3 FROM bulletin_national WHERE year=?", (y,))
    total = one("""SELECT SUM(ground_supply_1e8m3) FROM bulletin_provinces
                   WHERE year=? AND province<>'全国'""", (y,))[0]
    if natrow and natrow[0] and total and abs(total - natrow[0]) > 2.0:
        prov_bad.append((y, total, natrow[0]))
check("公报省级地下水供水量之和=全国", not prov_bad, str(prov_bad[:3]))
# 公报 vs 年报 年末埋深
rows = q("""SELECT b.plain, b.year AS y, b.shallow_end_m AS be, a.shallow_depth_m AS ad
            FROM bulletin_plains b JOIN annual_groundwater a
              ON a.region=b.plain AND a.row_type='plain_basin' AND a.data_year=b.year""")
diffs = [abs(r["be"] - r["ad"]) for r in rows]
check("公报平原埋深与水文年报一致（≤0.05m）", rows and max(diffs) <= 0.05,
      f"{len(rows)} 对，max={max(diffs) if diffs else None}")
check("公报 1998 年无数值（仅比例）",
      one("SELECT ground_resource_1e8m3 FROM bulletin_national WHERE year=1998")[0] is None)

# ---------------------------------------------------------------- 位置查询
import sys
sys.path.insert(0, str(ROOT / "src"))
from groundwater_mcp import repository as repo, server  # noqa: E402

r1 = server.locate_by_coordinates(45.75, 126.63, period="2025-12")
check("位置-经纬度 → 松嫩平原", "松嫩平原" in [u["name"] for u in r1["matched_units"]])
r2 = server.locate_by_administrative_region("河北省", city="衡水市", period="2025-12")
check("位置-行政区 → 海河平原", "海河平原" in [u["name"] for u in r2["matched_units"]])
check("位置-行政区附带省级公报历史", "province_groundwater_history" in r2["data"])
r3 = server.locate_by_map_point(39.90, 116.40, period="2025-12")
check("位置-地图选点 → 海河平原", "海河平原" in [u["name"] for u in r3["matched_units"]])
check("位置-单元附带公报埋深序列",
      any("bulletin_series" in u for u in r1["data"]["units"]))
try:
    server.locate_by_coordinates(999, 999)
    check("位置-非法坐标应报错", False)
except repo.DataError:
    check("位置-非法坐标报错", True)
stats = repo.db_stats(conn)
check("db_stats 覆盖四套数据",
      stats["reports"] == 25 and stats["annual_groundwater_rows"] == 109
      and stats["bulletin_national_rows"] == 26 and stats.get("surface_maps", 0) >= 400)

# ---------------------------------------------------------------- 等值面连续场
surf_n = one("SELECT COUNT(*) FROM surface_maps")[0]
surf_periods = {r[0] for r in q("SELECT DISTINCT period FROM surface_maps")}
check("等值面图已数字化 ≥400 幅", surf_n >= 400, f"{surf_n} 幅")
check("等值面覆盖全部 25 期月报", len(surf_periods) == 25,
      f"{len(surf_periods)} 期: {min(surf_periods)}~{max(surf_periods)}")
src = q("SELECT source, COUNT(*) n FROM surface_maps GROUP BY source")
check("等值面包含 PDF 与 HTML 缩略图两种来源",
      {"pdf", "html-thumbnail"} <= {r[0] for r in src},
      str({r[0]: r[1] for r in src}))
surf_q = q("SELECT quality, COUNT(*) n FROM surface_maps GROUP BY quality")
check("等值面质量分级存在 medium", "medium" in {r[0] for r in surf_q},
      str({r[0]: r[1] for r in surf_q}))
cons_min = one("SELECT MIN(class_consistency) FROM surface_maps")[0]
check("等值面等级一致性（每图 ≥90%）", cons_min >= 90, f"min={cons_min}")
err_rows = q("""SELECT ABS(mean_error_m) e FROM surface_maps
                WHERE mean_error_m IS NOT NULL ORDER BY e""")
if err_rows:
    med = err_rows[len(err_rows) // 2][0]
    check("连续场均值 vs 叙述均值（中位误差 <1m）", med < 1.0, f"median={round(med, 2)}m, n={len(err_rows)}")
pt = server.get_depth_at_point(45.75, 126.63, period="2025-12")
check("任意点反演可用（哈尔滨附近）", pt["count"] >= 1,
      f"depth={pt['hits'][0]['depth_m'] if pt['hits'] else None}")
pt_all = server.get_depth_at_point(45.75, 126.63)
check("跨期点查询覆盖多期", pt_all["count"] >= 5, f"{pt_all['count']} 期命中")
html_pt = server.get_depth_at_point(43.85, 125.30, period="2024-05")
check("HTML 缩略图期次可查询", html_pt["count"] >= 1,
      f"depth={html_pt['hits'][0]['depth_m'] if html_pt['hits'] else None}")
check("位置查询附带等值面反演值", r1["data"].get("surface_depth", {}).get("count", 0) >= 1)

# ---------------------------------------------------------------- 产物文件
wheel = ROOT / "dist" / "groundwater_monthly_mcp-0.4.0-py3-none-any.whl"
import hashlib
if wheel.exists():
    h = hashlib.sha256(wheel.read_bytes()).hexdigest()
    check("wheel 存在且 >5MB", wheel.stat().st_size > 5_000_000, f"{wheel.stat().st_size} B")
    check("wheel sha256 与文档一致",
          h == "24ae8fea9a8e270661c8d36f9f97a0335f9ce635610733bac3a3283c3f1ec9c4", h[:16] + "…")
else:
    check("wheel 存在", False)
if wheel.exists():
    import zipfile

    names = zipfile.ZipFile(wheel).namelist()
    check("wheel 含城市点位（get_city_depth 依赖）",
          "groundwater_mcp/data/geo/city_points.json" in names, f"{len(names)} files")
check("README 版本 0.4.0", "0.4.0" in (ROOT / "README.md").read_text(encoding="utf-8"))
check("docs/deploy.md 版本 0.4.0", "0.4.0" in (ROOT / "docs" / "deploy.md").read_text(encoding="utf-8")[:3000])

conn.close()

total = len(checks)
passed = sum(1 for c in checks if c["ok"])
report = {"total": total, "passed": passed, "failed": total - passed, "checks": checks,
          "db_size_bytes": DB.stat().st_size}
(ROOT / "data" / "verification_report.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

lines = ["# 数据与产物核验报告", "",
         f"- 核验时间：自动生成（脚本 `scripts/verify_all.py`）",
         f"- 数据库：`src/groundwater_mcp/data/groundwater.db`（{DB.stat().st_size} B）",
         f"- 结果：**{passed}/{total} 项通过**", "",
         "| 项目 | 结果 | 说明 |", "| --- | --- | --- |"]
for c in checks:
    lines.append(f"| {c['name']} | {'✅' if c['ok'] else '❌'} | {c['detail']} |")
(ROOT / "docs" / "verification.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"\n{passed}/{total} checks passed -> data/verification_report.json, docs/verification.md")
