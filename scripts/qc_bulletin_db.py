# -*- coding: utf-8 -*-
"""QC the bulletin tables inside the bundled database."""
import sqlite3
from pathlib import Path

db = Path("src/groundwater_mcp/data/groundwater.db")
c = sqlite3.connect(db)
c.row_factory = sqlite3.Row
out = []


def q(sql):
    return [dict(r) for r in c.execute(sql)]


for t in ("bulletin_reports", "bulletin_national", "bulletin_regions", "bulletin_provinces", "bulletin_plains"):
    out.append(f"{t}: {c.execute(f'select count(*) from {t}').fetchone()[0]}")
out.append("national years: " + ",".join(str(r["year"]) for r in q("select year from bulletin_national order by year")))
out.append("region years: " + ",".join(str(r["year"]) for r in q("select distinct year from bulletin_regions order by year")))
out.append("province years: " + ",".join(str(r["year"]) for r in q("select distinct year from bulletin_provinces order by year")))
out.append("plain years: " + ",".join(str(r["year"]) for r in q("select distinct year from bulletin_plains order by year")))
out.append("\n-- national sample")
for r in q("select * from bulletin_national order by year desc limit 5"):
    out.append(str(r))
out.append("\n-- region 2020 sample")
for r in q("select year,region,region_group,ground_resource_1e8m3,ground_supply_1e8m3,total_supply_1e8m3,ground_share_pct from bulletin_regions where year=2020"):
    out.append(str(r))
out.append("\n-- province 2020 sample")
for r in q("select year,province,ground_resource_1e8m3,ground_supply_1e8m3,total_supply_1e8m3 from bulletin_provinces where year=2020 limit 6"):
    out.append(str(r))
out.append("\n-- plains 2021 sample")
for r in q("select year,plain,region,monitor_area_1e4km2,shallow_start_m,shallow_end_m,shallow_change_m from bulletin_plains where year=2021 limit 6"):
    out.append(str(r))
out.append("\n-- sanity: region aggregate sums")
for r in q("""select year, sum(ground_supply_1e8m3) as gw
             from bulletin_regions where region not in ('全国','北方6区','南方4区') and region not like '%太湖%'
             group by year order by year"""):
    out.append(str(r))
Path("data/bulletin/probe/db_qc.txt").write_text("\n".join(out), encoding="utf-8")
print("ok")
