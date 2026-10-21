# -*- coding: utf-8 -*-
"""数据完整性与工具功能测试（pytest）。

运行：python -m pytest -q
"""
from __future__ import annotations

import pytest

from groundwater_mcp import repository as repo
from groundwater_mcp import server


@pytest.fixture(scope="module")
def conn():
    c = repo.connect()
    yield c
    c.close()


def test_dataset_coverage(conn):
    periods = repo.available_periods(conn)
    assert len(periods) >= 25
    assert periods[0] == "2025-12"
    assert "2024-10" in periods
    assert "2023-12" in periods  # 历史期（旧版式 PDF，来自信息中心残留附件）
    assert "2024-07" in periods  # HTML5 文本层解析期
    # 期号唯一且按时间倒序
    years_months = [(int(p[:4]), int(p[5:])) for p in periods]
    assert years_months == sorted(years_months, reverse=True)
    assert len(set(periods)) == len(periods)


def test_every_report_has_17_tables(conn):
    for period in repo.available_periods(conn):
        n = conn.execute(
            "SELECT COUNT(*) AS n FROM report_tables WHERE period=?", (period,)
        ).fetchone()["n"]
        assert n == 17, (period, n)
        precip = conn.execute(
            "SELECT COUNT(*) AS n FROM precipitation WHERE period=?", (period,)
        ).fetchone()["n"]
        assert precip in (34, 35), (period, precip)
        shallow = conn.execute(
            "SELECT COUNT(*) AS n FROM shallow_regions WHERE period=?", (period,)
        ).fetchone()["n"]
        assert shallow == 24, (period, shallow)


def test_known_values_2025_12(conn):
    sanjiang = repo.region_snapshot(conn, "2025-12", "三江平原")
    assert sanjiang["mean_depth_m"] == pytest.approx(8.6)
    assert sanjiang["change_prev_month_m"] == pytest.approx(0.0)
    assert sanjiang["change_last_year_m"] == pytest.approx(0.3)
    assert sanjiang["area_share_pct"] == 86

    qiongbei = repo.region_snapshot(conn, "2025-12", "琼北台地平原")
    assert qiongbei["mean_depth_m"] == pytest.approx(8.8)

    precip = repo.precip_for(conn, "2025-12", "松嫩平原")
    assert precip["precip_mm"] == pytest.approx(6.8)
    assert precip["anomaly_pct"] == pytest.approx(31)

    deep = repo.deep_for_province(conn, "2025-12", "河北")
    assert deep["total_stations"] == 476
    assert deep["down_gt2_pct"] == pytest.approx(27.5)

    # 表15 重点站：河北保定南屯村水位 779.6
    row = conn.execute(
        "SELECT * FROM water_stations WHERE period='2025-12' AND station='南屯村'"
    ).fetchone()
    assert row["water_level_m"] == pytest.approx(779.6)
    # 表17 泉流量：涞源泉 0.330
    spring = conn.execute(
        "SELECT * FROM springs WHERE period='2025-12' AND station='涞源泉'"
    ).fetchone()
    assert spring["mean_flow_m3s"] == pytest.approx(0.330)
    # 表16 水温：全国 64 站
    n_temp = conn.execute(
        "SELECT COUNT(*) AS n FROM temperature_stations WHERE period='2025-12'"
    ).fetchone()["n"]
    assert n_temp == 64


def test_known_values_2023_12(conn):
    """旧版式 PDF（2023-12）：校验别名归一化和表格解析。"""
    sanjiang = repo.region_snapshot(conn, "2023-12", "三江平原")
    assert sanjiang["mean_depth_m"] == pytest.approx(8.2)
    # 旧版命名“浙东沿海一般平原”应归一为“浙东沿海平原”
    zhedong = repo.region_snapshot(conn, "2023-12", "浙东沿海平原")
    assert zhedong is not None and zhedong["mean_depth_m"] == pytest.approx(4.8)
    precip = repo.precip_for(conn, "2023-12", "河西走廊平原")
    assert precip["precip_mm"] == pytest.approx(3.2)
    deep = repo.deep_for_province(conn, "2023-12", "河北")
    assert deep["total_stations"] == 476


def test_known_values_2024_07(conn):
    """HTML5 文本层解析期（2024-07）：校验叙述数据与降水表。"""
    sanjiang = repo.region_snapshot(conn, "2024-07", "三江平原")
    assert sanjiang["mean_depth_m"] == pytest.approx(8.2)
    assert sanjiang["change_prev_month_m"] == pytest.approx(-0.1)
    assert sanjiang["change_last_year_m"] == pytest.approx(-0.5)

    zhedong = repo.region_snapshot(conn, "2024-07", "浙东沿海平原")
    assert zhedong["mean_depth_m"] == pytest.approx(4.9)
    precip = repo.precip_for(conn, "2024-07", "浙东沿海平原")
    assert precip["precip_mm"] == pytest.approx(75.7)
    assert precip["anomaly_pct"] == pytest.approx(-39.0)
    deep = repo.deep_for_province(conn, "2024-07", "浙江")
    assert deep["total_stations"] == 175
    # 2024-07 表15 重点站 38 个、表17 泉流量 9 个
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM water_stations WHERE period='2024-07'"
    ).fetchone()["n"] == 38
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM springs WHERE period='2024-07'"
    ).fetchone()["n"] == 9


def test_annual_groundwater(conn):
    """中国水文年报地下水数据：补齐 2020-12/2021-12/2022-12 年际基准。"""
    reports = repo.list_annual_reports(conn)
    assert len(reports) == 2
    by_year = {r["year"]: r for r in reports}
    assert by_year[2021]["data_years"] == [2020, 2021]
    assert by_year[2022]["data_years"] == [2021, 2022]

    rows = repo.get_annual_groundwater(conn, region="三江平原", row_type="plain_basin")["rows"]
    series = {r["data_year"]: r for r in rows}
    assert len(series) == 3
    assert series[2020]["shallow_depth_m"] == pytest.approx(7.8)
    assert series[2021]["shallow_depth_m"] == pytest.approx(8.3)
    assert series[2021]["shallow_water_level_change_m"] == pytest.approx(-0.5)
    assert series[2022]["shallow_water_level_change_m"] == pytest.approx(0.0)

    songnen = {
        r["data_year"]: r
        for r in repo.get_annual_groundwater(conn, region="松嫩平原", row_type="plain_basin")["rows"]
    }
    assert songnen[2020]["shallow_depth_m"] == pytest.approx(7.6)
    assert songnen[2021]["shallow_depth_m"] == pytest.approx(7.2)
    assert songnen[2021]["deep_depth_m"] == pytest.approx(12.2)
    assert songnen[2021]["shallow_water_level_change_m"] == pytest.approx(0.4)
    assert songnen[2022]["shallow_depth_m"] == pytest.approx(7.5)
    assert songnen[2022]["shallow_depth_change_m"] == pytest.approx(0.3)

    key = repo.get_annual_groundwater(conn, row_type="key_region")["rows"]
    assert len(key) == 22  # 11 个重点区域 × 2 个年份（来自 2022 年报）


def test_report_summary(conn):
    report = repo.get_report(conn, "2025-12")
    assert report["station_total"] == 20469
    assert report["shallow_stations"] == 10849
    assert report["deep_stations"] == 4183
    assert report["deep_up_pct"] == pytest.approx(36.1)
    assert "深层地下水水位变化" in report["summary_text"]
    assert any(s["heading"].startswith("三、") for s in report["sections"])


def test_table_raw_rows(conn):
    table = repo.get_table(conn, "2025-12", 1)
    assert table["caption"].startswith("东北平原")
    assert table["rows"][0][0] == "平原名称"
    assert len(table["rows"]) == 5

    table14 = repo.get_table(conn, "2025-12", 14)
    assert any(row[0] == "总计" for row in table14["rows"])


def test_time_series(conn):
    series = repo.get_time_series(conn, "depth", region="松嫩平原")
    points = series["series"]["松嫩平原"]
    assert len(points) >= 12
    assert points[0]["value"] is not None
    assert points[-1]["period"] == "2025-12"


def test_text_search(conn):
    result = repo.search_text(conn, "松嫩平原", limit=5)
    assert result["count"] >= 3
    assert all("snippet" in h for h in result["hits"])


def test_bad_inputs(conn):
    with pytest.raises(repo.DataError):
        repo.resolve_period(conn, "1999-01")
    with pytest.raises(repo.DataError):
        repo.get_table(conn, "2025-12", 99)
    with pytest.raises(repo.DataError):
        repo.get_time_series(conn, "unknown")


# ---------------------------------------------------------------------------
# 三种位置输入
# ---------------------------------------------------------------------------
def test_location_coordinates():
    result = server.locate_by_coordinates(45.75, 126.63, period="2025-12")
    assert result["resolved_admin"]["province"] == "黑龙江省"
    units = [u["name"] for u in result["matched_units"]]
    assert "松嫩平原" in units
    unit = result["data"]["units"][0]
    assert unit["shallow_depth"]["mean_depth_m"] == pytest.approx(7.2)


def test_location_admin():
    result = server.locate_by_administrative_region("河北省", city="衡水市", period="2025-12")
    units = [u["name"] for u in result["matched_units"]]
    assert "海河平原" in units
    assert result["data"]["province_deep"]["province"] == "河北"


def test_location_map_point():
    result = server.locate_by_map_point(39.90, 116.40, period="2025-12")
    units = [u["name"] for u in result["matched_units"]]
    assert "海河平原" in units
    assert result["mode"] == "map_point"
    assert "map_picker" in result


def test_query_by_location_dispatch():
    a = server.query_by_location(mode="coordinates", lat=30.57, lon=104.07, period="2025-12")
    assert a["matched_units"][0]["name"] == "成都平原"
    b = server.query_by_location(mode="administrative", province="广东省", period="2025-12")
    names = [u["name"] for u in b["matched_units"]]
    assert "广东珠江三角洲平原" in names or "雷州半岛平原" in names
    with pytest.raises(repo.DataError):
        server.query_by_location(mode="map_point")  # 缺经纬度
    with pytest.raises(repo.DataError):
        server.query_by_location(mode="不讲武德", lat=1, lon=1)


def test_location_out_of_range():
    assert server.get_map_picker()["exists"]
    with pytest.raises(repo.DataError):
        server.locate_by_coordinates(999, 999)
    with pytest.raises(repo.DataError):
        server.locate_by_map_point(999, 116.40, period="2025-12")


def test_map_picker_contract():
    """地图选点页面契约：字段齐全、资源内容一致、本地 Leaflet 齐备、关键交互存在。"""
    import re
    from pathlib import Path

    info = server.get_map_picker()
    assert {"picker_path", "exists", "how_to", "resource_uri", "note"} <= set(info)
    assert info["exists"] is True
    assert info["resource_uri"] == "groundwater://map/picker"
    picker = Path(info["picker_path"])
    assert picker.is_file()
    html = picker.read_text(encoding="utf-8")
    assert server.map_picker_resource() == html
    # HTML 中引用的本地资源（Leaflet）必须随包存在，离线可用
    refs = re.findall(r'(?:src|href)="([^"]+)"', html)
    local = [u for u in refs if not u.startswith(("http://", "https://", "data:", "//"))]
    assert "leaflet.js" in local and "leaflet.css" in local
    for ref in local:
        assert (picker.parent / ref).is_file(), ref
    # 关键交互与离线切换要素
    assert "map.on('click'" in html
    assert 'id="coord"' in html
    assert 'value="none"' in html and "无底图" in html


def test_map_point_matches_coordinates():
    """地图点选坐标与经纬度查询结果一致（除 mode/input/map_picker 字段）。"""
    for lat, lon in ((39.90, 116.40), (23.13, 113.26)):
        by_map = server.locate_by_map_point(lat, lon, period="2025-12")
        by_coord = server.locate_by_coordinates(lat, lon, period="2025-12")
        assert by_map["mode"] == "map_point"
        assert by_coord["mode"] == "coordinates"
        for key in ("mode", "input", "map_picker"):
            by_map.pop(key, None)
            by_coord.pop(key, None)
        assert by_map == by_coord
    with pytest.raises(repo.DataError):
        server.query_by_location(mode="map_point", period="2025-12")


# ---------------------------------------------------------------------------
# 《中国水资源公报》历史地下水数据（1997-2024）
# ---------------------------------------------------------------------------
def test_bulletin_coverage(conn):
    years = [r["year"] for r in repo.list_bulletin_reports(conn)]
    assert len(years) >= 20
    assert 1997 in years and 2024 in years
    assert 1999 not in years and 2000 not in years  # 未公开
    nat_years = [r["year"] for r in conn.execute("SELECT year FROM bulletin_national ORDER BY year")]
    assert 1997 in nat_years and 2010 in nat_years and 2024 in nat_years
    # 每个年份至少有一类数据
    assert len(nat_years) >= 25


def test_bulletin_national_known_values(conn):
    rows = {r["year"]: r for r in repo.get_bulletin_national(conn)["rows"]}
    assert rows[1997]["ground_resource_1e8m3"] == pytest.approx(6942.38)
    assert rows[1997]["ground_supply_1e8m3"] == pytest.approx(1031.49)
    assert rows[2010]["ground_resource_1e8m3"] == pytest.approx(8417.0)
    assert rows[2010]["ground_supply_1e8m3"] == pytest.approx(1107.3)
    assert rows[2022]["ground_resource_1e8m3"] == pytest.approx(7924.4)
    assert rows[2022]["ground_supply_1e8m3"] == pytest.approx(828.2)
    assert rows[2010]["plain_storage_change_1e8m3"] == pytest.approx(-29.2)


def test_bulletin_region_consistency(conn):
    for year in (2010, 2015, 2020, 2022, 2024):
        rows = repo.get_bulletin_regions(conn, year=year)["rows"]
        by = {r["region"]: r for r in rows}
        nat = by["全国"]["ground_resource_1e8m3"]
        ns = by["北方6区"]["ground_resource_1e8m3"] + by["南方4区"]["ground_resource_1e8m3"]
        assert nat == pytest.approx(ns, abs=1.0)
        assert by["全国"]["ground_supply_1e8m3"] == pytest.approx(
            by["北方6区"]["ground_supply_1e8m3"] + by["南方4区"]["ground_supply_1e8m3"], abs=1.0
        )


def test_bulletin_province_series(conn):
    rows = repo.bulletin_series_for_province(conn, "河北")
    assert len(rows) >= 8
    years = [r["year"] for r in rows]
    assert 2016 in years and 2020 in years
    val2020 = next(r for r in rows if r["year"] == 2020)
    assert val2020["ground_supply_1e8m3"] == pytest.approx(88.2)


def test_bulletin_plain_depths(conn):
    rows = repo.get_bulletin_plains(conn, year=2022)["rows"]
    by = {r["plain"]: r for r in rows}
    assert by["三江平原"]["shallow_end_m"] == pytest.approx(8.3)
    assert by["三江平原"]["shallow_change_m"] == pytest.approx(0.0)
    rows21 = repo.get_bulletin_plains(conn, year=2021)["rows"]
    by21 = {r["plain"]: r for r in rows21}
    assert by21["三江平原"]["shallow_start_m"] == pytest.approx(7.8)
    assert by21["三江平原"]["shallow_end_m"] == pytest.approx(8.3)


def test_bulletin_tools_and_series():
    rep = server.list_bulletin_reports()
    assert rep["count"] >= 20
    got = server.get_bulletin_groundwater(year=2020, level="province", name="河北")
    assert got["count"] == 1
    series = server.get_bulletin_series(metric="ground_share", level="region", name="海河区")
    assert "海河区" in series["series"]
    assert len(series["series"]["海河区"]) >= 10
    with pytest.raises(repo.DataError):
        server.get_bulletin_series(metric="nope")
    with pytest.raises(repo.DataError):
        server.get_bulletin_groundwater(level="nope")


# ---------------------------------------------------------------------------
# 等值面图数字化：连续埋深场
# ---------------------------------------------------------------------------
def test_surface_maps_available(conn):
    n = conn.execute("SELECT COUNT(*) FROM surface_maps").fetchone()[0]
    assert n >= 400
    periods = {r[0] for r in conn.execute("SELECT DISTINCT period FROM surface_maps")}
    assert len(periods) == 25
    assert {"2023-12", "2024-05", "2024-10", "2025-12"} <= periods
    sources = {r[0] for r in conn.execute("SELECT DISTINCT source FROM surface_maps")}
    assert {"pdf", "html-thumbnail"} <= sources
    row = conn.execute(
        "SELECT * FROM surface_maps WHERE period='2025-12' ORDER BY figure LIMIT 1").fetchone()
    assert row["quality"] in {"high", "medium", "low"}
    assert row["class_consistency"] >= 90
    med = [r[0] for r in conn.execute(
        "SELECT ABS(mean_error_m) FROM surface_maps WHERE mean_error_m IS NOT NULL "
        "ORDER BY 1")]
    assert med[len(med) // 2] < 1.0


def test_surface_point_query():
    res = server.get_depth_at_point(45.75, 126.63, period="2025-12")
    assert res["count"] >= 1
    hit = res["hits"][0]
    assert 0 < hit["depth_m"] < 60
    assert hit["class_range"] and hit["class_range"]["lo"] <= hit["depth_m"] <= hit["class_range"]["hi"]
    assert hit["source"].startswith("等值面图")


def test_surface_surface_and_city():
    detail = server.get_depth_surface("2025-12", figure=4)
    assert detail["legend"] and len(detail["legend"]) >= 8
    assert detail["stats"]["class_consistency"] >= 90
    looks = server.list_surface_maps(period="2025-12")
    assert looks["count"] >= 10
    city = server.get_city_depth("哈尔滨", period="2025-12")
    assert city["count"] >= 1


def test_location_payload_has_surface():
    res = server.locate_by_coordinates(45.75, 126.63, period="2025-12")
    assert "surface_depth" in res["data"]
    assert res["data"]["surface_depth"]["count"] >= 1


def test_surface_html_thumbnail_period():
    res = server.get_depth_at_point(43.85, 125.30, period="2024-05")
    assert res["count"] >= 1
    hit = res["hits"][0]
    assert hit["source_kind"] == "html-thumbnail"
    assert 0 < hit["depth_m"] < 60
    detail = server.get_depth_surface("2024-05", figure=4)
    assert detail["source_kind"] == "html-thumbnail"
    assert detail["stats"]["class_consistency"] >= 90
