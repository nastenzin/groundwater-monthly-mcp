# -*- coding: utf-8 -*-
"""地下水 MCP 位置输入自检脚本。

覆盖：
A. 32 个已知城市/站点 -> 地貌单元映射（units_at 主单元）
B. 同一批点 -> 行政区定位（locate_admin）
C. 公共 API 契约：非法输入、海域、排序、数量、数据文件属性
D. units_for_admin 行政区检索

用法：D:\\Anaconda\\python.exe scripts\\geo_check.py
输出 PASS/FAIL 明细与统计；任一失败时退出码为 1。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from groundwater_mcp import geo  # noqa: E402

GEO_DIR = ROOT / "src" / "groundwater_mcp" / "data" / "geo"

# name, lat, lon, 期望主单元, 期望省, 期望市
POINTS = [
    ("北京", 39.90, 116.40, "海河平原", "北京市", "北京市"),
    ("石家庄", 38.04, 114.51, "海河平原", "河北省", "石家庄市"),
    ("天津", 39.13, 117.20, "海河平原", "天津市", "天津市"),
    ("哈尔滨", 45.75, 126.63, "松嫩平原", "黑龙江省", "哈尔滨市"),
    ("长春", 43.88, 125.32, "松嫩平原", "吉林省", "长春市"),
    ("沈阳", 41.80, 123.43, "辽河平原", "辽宁省", "沈阳市"),
    ("佳木斯", 46.80, 130.32, "三江平原", "黑龙江省", "佳木斯市"),
    ("密山", 45.53, 131.87, "穆棱兴凯平原", "黑龙江省", "鸡西市"),
    ("郑州", 34.75, 113.62, "黄淮平原", "河南省", "郑州市"),
    ("济南", 36.67, 117.00, "黄淮平原", "山东省", "济南市"),
    ("徐州", 34.26, 117.18, "黄淮平原", "江苏省", "徐州市"),
    ("太原", 37.87, 112.55, "山西主要盆地", "山西省", "太原市"),
    ("大同", 40.08, 113.30, "山西主要盆地", "山西省", "大同市"),
    ("运城", 35.03, 111.00, "山西主要盆地", "山西省", "运城市"),
    ("呼和浩特", 40.84, 111.75, "呼包平原", "内蒙古自治区", "呼和浩特市"),
    ("银川", 38.49, 106.23, "银川卫宁平原", "宁夏回族自治区", "银川市"),
    ("西安", 34.34, 108.94, "关中平原", "陕西省", "西安市"),
    ("兰州", 36.06, 103.83, "河西走廊平原", "甘肃省", "兰州市"),
    ("张掖", 38.93, 100.45, "河西走廊平原", "甘肃省", "张掖市"),
    ("格尔木", 36.40, 94.90, "柴达木盆地", "青海省", "海西蒙古族藏族自治州"),
    ("乌鲁木齐", 43.83, 87.62, "准噶尔盆地", "新疆维吾尔自治区", "乌鲁木齐市"),
    ("喀什", 39.47, 75.99, "塔里木盆地", "新疆维吾尔自治区", "喀什地区"),
    ("武汉", 30.59, 114.31, "江汉平原", "湖北省", "武汉市"),
    ("南昌", 28.68, 115.86, "鄱阳湖平原", "江西省", "南昌市"),
    ("上海", 31.23, 121.47, "长江三角洲平原", "上海市", "上海市"),
    ("杭州", 30.27, 120.16, "浙东沿海平原", "浙江省", "杭州市"),
    ("南阳", 32.99, 112.53, "河南省南襄山间平原", "河南省", "南阳市"),
    ("成都", 30.57, 104.07, "成都平原", "四川省", "成都市"),
    ("广州", 23.13, 113.26, "广东珠江三角洲平原", "广东省", "广州市"),
    ("湛江", 21.27, 110.36, "雷州半岛平原", "广东省", "湛江市"),
    ("海口", 20.04, 110.20, "琼北台地平原", "海南省", "海口市"),
]

# 允许“近邻”通过的点（任务说明：兰州 -> 河西走廊平原 或 nearby）
NEARBY_OK = {"兰州"}

_RESULTS: list[tuple[bool, str, str]] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    ok = bool(ok)
    _RESULTS.append((ok, label, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"  <-- {detail}"))
    return ok


def expect_raises(fn, exc_type, label: str) -> None:
    try:
        fn()
    except exc_type:
        check(True, label)
    except Exception as exc:  # noqa: BLE001
        check(False, label, f"期望 {exc_type.__name__}，实际 {type(exc).__name__}: {exc}")
    else:
        check(False, label, f"期望 {exc_type.__name__}，但没有抛异常")


def section_a_units() -> None:
    print("\n[A] units_at 地貌单元映射（32 点）")
    for name, lat, lon, expected_unit, _province, _city in POINTS:
        result = geo.units_at(lat, lon)
        top = result[0] if result else None
        if top is None:
            check(False, f"{name} -> {expected_unit}", "units_at 返回空")
            continue
        relation_ok = top["relation"] == "inside" or (
            name in NEARBY_OK and top["relation"] == "nearby"
        )
        detail = (
            f"unit={top['name']}({top['relation']}) "
            f"all={[u['name'] for u in result]}"
        )
        check(top["name"] == expected_unit and relation_ok, f"{name} -> {expected_unit}", detail)
        # 结构契约
        for item in result:
            keys_ok = {"id", "name", "group", "relation", "distance_km"} <= set(item)
            if not keys_ok:
                check(False, f"{name} 字段完整", f"缺字段: {item}")
                break
        else:
            check(True, f"{name} 返回字段完整")


def section_b_admin() -> None:
    print("\n[B] locate_admin 行政区定位（32 点）")
    for name, lat, lon, _unit, expected_province, expected_city in POINTS:
        admin = geo.locate_admin(lat, lon)
        got = (admin.get("province"), admin.get("city"))
        check(
            got == (expected_province, expected_city),
            f"{name} -> {expected_province}/{expected_city}",
            f"实际 {got}",
        )


def section_c_contract() -> None:
    print("\n[C] 数据与 API 契约")

    # UNITS 数量与字段
    check(len(geo.UNITS) == 24, "UNITS 数量为 24", f"实际 {len(geo.UNITS)}")
    ids = [u.get("id") for u in geo.UNITS]
    check(len(set(ids)) == 24 and all(ids), "单元 id 唯一且非空", f"ids={ids}")
    required = {"id", "name", "group", "provinces", "bbox", "accuracy"}
    missing = [u.get("id") for u in geo.UNITS if not required <= set(u)]
    check(not missing, "UNITS 字段齐全(id/name/group/provinces/bbox/accuracy)", f"缺字段: {missing}")
    check(
        all(u.get("accuracy") == "approximate" for u in geo.UNITS),
        "全部单元 accuracy=approximate",
    )
    check(
        all(isinstance(u.get("provinces"), list) and u["provinces"] for u in geo.UNITS),
        "全部单元 provinces 非空列表",
    )
    check(
        all(
            isinstance(u.get("bbox"), list)
            and len(u["bbox"]) == 4
            and u["bbox"][0] <= u["bbox"][2]
            and u["bbox"][1] <= u["bbox"][3]
            for u in geo.UNITS
        ),
        "全部单元 bbox 合法",
    )
    groups = {}
    for u in geo.UNITS:
        groups[u["group"]] = groups.get(u["group"], 0) + 1
    expected_groups = {
        "东北平原": 4,
        "黄淮海平原": 2,
        "山西及西北诸省区": 9,
        "长江中下游平原": 4,
        "其他监控区": 5,
    }
    check(groups == expected_groups, "五大分区单元数符合任务清单", f"实际 {groups}")

    # 数据文件属性
    for fname, req in (
        ("china_provinces.geojson", {"name", "adcode", "level"}),
        ("china_cities.geojson", {"name", "adcode", "province"}),
    ):
        path = GEO_DIR / fname
        data = json.loads(path.read_text(encoding="utf-8"))
        feats = data.get("features") or []
        props_ok = all(req <= set((f.get("properties") or {})) for f in feats)
        has_cjk = all(
            any("\u4e00" <= ch <= "\u9fff" for ch in str(f["properties"].get("name", "")))
            for f in feats
        )
        check(props_ok and has_cjk and bool(feats), f"{fname} 属性齐全且含中文 name")

    # 非法输入
    expect_raises(lambda: geo.locate_admin(91, 116), ValueError, "locate_admin 纬度越界抛 ValueError")
    expect_raises(lambda: geo.locate_admin(39.9, 181), ValueError, "locate_admin 经度越界抛 ValueError")
    expect_raises(lambda: geo.locate_admin("39.9", 116.4), ValueError, "locate_admin 非数字抛 ValueError")
    expect_raises(lambda: geo.units_at(-91, 0), ValueError, "units_at 纬度越界抛 ValueError")
    expect_raises(lambda: geo.nearest_units(39.9, 116.4, 0), ValueError, "nearest_units k=0 抛 ValueError")
    expect_raises(lambda: geo.nearest_units(39.9, 116.4, "3"), ValueError, "nearest_units k 非整数抛 ValueError")
    expect_raises(lambda: geo.units_for_admin(), ValueError, "units_for_admin 无参数抛 ValueError")

    # 纬度/经度顺序约定：把 (lat, lon) 颠倒后应越界或落到别处
    expect_raises(lambda: geo.units_at(116.4, 39.9), ValueError, "units_at 经纬度顺序颠倒被识别")

    # 海域点
    check(geo.locate_admin(0.0, 0.0) == {"province": None, "city": None}, "海洋点 locate_admin 返回 None")
    check(geo.units_at(0.0, 0.0) == [], "海洋点 units_at 返回空列表")

    # units_at 排序与上限
    result = geo.units_at(40.08, 113.30)  # 大同，同时落在山西盆地与海河平原
    relations = [u["relation"] for u in result]
    order_ok = relations == sorted(relations, key=lambda r: 0 if r == "inside" else 1)
    check(order_ok, "units_at 中 inside 排在 nearby 之前", f"relations={relations}")
    check(len(geo.units_at(39.9, 116.4)) <= geo.MAX_UNITS_AT, "units_at 最多返回 5 个")
    check(
        all(u["relation"] in ("inside", "nearby") for u in result),
        "units_at relation 取值合法",
    )
    check(
        all(u["distance_km"] is None or u["distance_km"] <= 120.0 for u in result if u["relation"] == "nearby"),
        "nearby 距离 <= 120km",
    )

    # nearest_units
    nearest = geo.nearest_units(39.90, 116.40, 3)
    check(len(nearest) == 3, "nearest_units 返回 k=3 个", f"实际 {len(nearest)}")
    check(
        nearest and nearest[0]["name"] == "海河平原" and nearest[0]["distance_km"] == 0.0,
        "nearest_units 最近为海河平原且距离 0",
        f"实际 {nearest[:1]}",
    )

    # 直辖市 city=province
    admin = geo.locate_admin(31.23, 121.47)
    check(
        admin["province"] == admin["city"] == "上海市",
        "直辖市 locate_admin 的 city 与 province 相同(上海市)",
        f"实际 {admin}",
    )


def section_d_units_for_admin() -> None:
    print("\n[D] units_for_admin 行政区检索")

    def names(result):
        return [u["name"] for u in result]

    r = geo.units_for_admin(province="河北省")
    check(
        names(r) == ["海河平原"],
        "province=河北省 -> 海河平原",
        f"实际 {names(r)}",
    )
    r = geo.units_for_admin(province="河北")  # 去后缀短名
    check(names(r) == ["海河平原"], "province=河北(短名) -> 海河平原", f"实际 {names(r)}")
    r = geo.units_for_admin(province="湖北省")
    check("江汉平原" in names(r), "province=湖北省 包含江汉平原", f"实际 {names(r)}")
    r = geo.units_for_admin(province="内蒙古自治区")
    check(
        {"呼包平原", "河套平原"} <= set(names(r)),
        "province=内蒙古自治区 含呼包/河套平原",
        f"实际 {names(r)}",
    )
    r = geo.units_for_admin(city="石家庄")
    check(names(r) == ["海河平原"], "city=石家庄 -> 海河平原", f"实际 {names(r)}")
    r = geo.units_for_admin(city="武汉市")
    check("江汉平原" in names(r), "city=武汉市 含江汉平原", f"实际 {names(r)}")
    r = geo.units_for_admin(province="山西省", city="太原市")
    check(names(r) == ["山西主要盆地"], "province=山西省+city=太原市 -> 山西主要盆地", f"实际 {names(r)}")
    r = geo.units_for_admin(province="浙江省", city="杭州市")
    check("浙东沿海平原" in names(r), "province=浙江省+city=杭州市 含浙东沿海平原", f"实际 {names(r)}")
    check(geo.units_for_admin(province="火星省") == [], "province=火星省 返回空列表")
    check(geo.units_for_admin(city="不存在市") == [], "city=不存在市 返回空列表")
    check(
        all({"id", "name", "group", "reason"} <= set(u) for u in geo.units_for_admin(province="湖北省")),
        "units_for_admin 返回字段齐全",
    )


def main() -> int:
    print("=" * 64)
    print("地下水 MCP 位置输入自检")
    print("=" * 64)
    section_a_units()
    section_b_admin()
    section_c_contract()
    section_d_units_for_admin()

    passed = sum(1 for ok, _, _ in _RESULTS if ok)
    total = len(_RESULTS)
    failed = [label for ok, label, _ in _RESULTS if not ok]
    print("\n" + "=" * 64)
    print(f"统计：PASS {passed}/{total}  ({passed / total * 100:.1f}%)")
    if failed:
        print("失败项：")
        for label in failed:
            print("  -", label)
        print("结果：FAIL")
        return 1
    print("结果：全部 PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
