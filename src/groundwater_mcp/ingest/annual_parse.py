# -*- coding: utf-8 -*-
"""解析《中国水文年报》地下水章节（年末 12 月平原/盆地埋深与同比水位变幅）。

目前利用可提取文本层的 2022 年报：表 5-2（全国主要平原及盆地 2021/2022 年 12 月）
与表 5-3（重点区域），把月末/年末数据补进数据库，作为月报之外的前期年际基准。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pymupdf

# 表5-2 中出现的平原/盆地名称 → 月报中的规范地貌单元名
PLAIN_ALIASES: dict[str, str] = {
    "三江平原": "三江平原",
    "松嫩平原": "松嫩平原",
    "穆棱兴凯平原": "穆棱兴凯平原",
    "辽河平原": "辽河平原",
    "海河平原": "海河平原",
    "大同盆地": "大同盆地",
    "忻定盆地": "忻定盆地",
    "长治盆地": "长治盆地",
    "黄淮平原": "黄淮平原",
    "运城盆地": "运城盆地",
    "临汾盆地": "临汾盆地",
    "太原盆地": "太原盆地",
    "内蒙古呼包平原": "呼包平原",
    "内蒙古河套平原": "河套平原",
    "陕西关中平原": "关中平原",
    "宁夏银川卫宁平原": "银川卫宁平原",
    "江汉平原": "江汉平原",
    "鄱阳湖平原": "鄱阳湖平原",
    "长江三角洲平原": "长江三角洲平原",
    "河南南襄山间平原区": "河南省南襄山间平原",
    "成都平原": "成都平原",
    "浙东沿海平原": "浙东沿海平原",
    "广东珠江三角洲平原": "广东珠江三角洲平原",
    "雷州半岛平原": "雷州半岛平原",
    "琼北台地平原": "琼北台地平原",
    "甘肃河西走廊平原": "河西走廊平原",
    "青海柴达木盆地": "柴达木盆地",
    "新疆塔里木盆地": "塔里木盆地",
    "新疆准噶尔盆地": "准噶尔盆地",
}

GROUP_NAMES = {
    "松花江区", "辽河区", "海河区", "黄河区、淮河区", "黄河区", "淮河区、黄河区",
    "长江区", "东南诸河区", "珠江区", "西北诸河区", "淮河区",
}

KEY_REGION_NAMES = [
    "华北地区", "三江平原", "松嫩平原", "辽河平原", "西辽河流域", "黄淮地区",
    "鄂尔多斯台地", "河西走廊", "汾渭谷地", "天山南北麓与吐哈盆地", "北部湾地区",
]

NUMBER_RE = re.compile(r"^-?\d+(?:\.\d+)?$")


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _is_number(token: str) -> bool:
    return bool(NUMBER_RE.match(token))


def _read_numbers(lines: list[str], start: int) -> tuple[list[str], int]:
    nums = []
    i = start
    while i < len(lines) and (_is_number(lines[i]) or lines[i] in {"—", "-", "/"}):
        nums.append(lines[i])
        i += 1
    return nums, i


def _num(token: str) -> float | None:
    if token in {"—", "-", "/"}:
        return None
    return float(token)


def _parse_table52(page_text: str) -> list[dict[str, Any]]:
    lines = _lines(page_text)
    rows = []
    group = ""
    i = 0
    while i < len(lines):
        line = lines[i]
        if line in GROUP_NAMES:
            group = line
            i += 1
            continue
        canonical = PLAIN_ALIASES.get(line)
        if canonical:
            nums, i = _read_numbers(lines, i + 1)
            if len(nums) >= 3:
                shallow_first, shallow_second, shallow_chg = _num(nums[0]), _num(nums[1]), _num(nums[2])
                deep_first = deep_second = deep_chg = None
                if len(nums) >= 6:
                    deep_first, deep_second, deep_chg = _num(nums[3]), _num(nums[4]), _num(nums[5])
                rows.append(
                    {
                        "region": canonical,
                        "region_label": line,
                        "region_group": group,
                        "shallow_first": shallow_first,
                        "shallow_second": shallow_second,
                        "shallow_change": shallow_chg,
                        "deep_first": deep_first,
                        "deep_second": deep_second,
                        "deep_change": deep_chg,
                    }
                )
            continue
        i += 1
    return rows


KEY_REGION_PARTS = [
    ("鄂尔多斯", "台地", "鄂尔多斯台地"),
    ("天山南北麓", "与吐哈盆地", "天山南北麓与吐哈盆地"),
]


def _parse_table53(page_text: str) -> list[dict[str, Any]]:
    lines = _lines(page_text)
    rows = []
    i = 0
    while i < len(lines):
        line = lines[i]
        base = None
        skip_extra = 0
        for prefix, suffix, full in KEY_REGION_PARTS:
            if line == prefix and i + 1 < len(lines) and lines[i + 1] == suffix:
                base = full
                skip_extra = 2
                break
        if base is None:
            for name in KEY_REGION_NAMES:
                if line == name or line.startswith(name + "(") or line.startswith(name + "（"):
                    base = name
                    break
        if base:
            # 跳过“（重点）”、城市列表行（可能被折行且末尾无顿号）
            j = i + (skip_extra if skip_extra else 1)
            while j < len(lines):
                line_j = lines[j]
                if line_j in {"(重点)", "（重点）"}:
                    j += 1
                    continue
                if _is_number(line_j) or line_j in {"—", "-", "/"}:
                    break
                if any(ch in line_j for ch in "市州盟旗") and not any(
                    line_j.startswith(name) for name in KEY_REGION_NAMES
                ):
                    j += 1
                    continue
                break
            nums, j = _read_numbers(lines, j)
            if len(nums) >= 3:
                shallow_first, shallow_second, shallow_chg = _num(nums[0]), _num(nums[1]), _num(nums[2])
                deep_first = deep_second = deep_chg = None
                if len(nums) >= 6:
                    deep_first, deep_second, deep_chg = _num(nums[3]), _num(nums[4]), _num(nums[5])
                has_key = any("重点" in x for x in lines[i:j])
                rows.append(
                    {
                        "region": base + ("（重点）" if has_key else ""),
                        "region_label": base,
                        "shallow_first": shallow_first,
                        "shallow_second": shallow_second,
                        "shallow_change": shallow_chg,
                        "deep_first": deep_first,
                        "deep_second": deep_second,
                        "deep_change": deep_chg,
                    }
                )
            i = j
            continue
        i += 1
    return rows


def parse_annual_report(pdf_path: str | Path, report_year: int, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """解析年报地下水章节，返回表 5-2/表 5-3 的结构化数据。"""
    pdf_path = Path(pdf_path)
    meta = dict(meta or {})
    doc = pymupdf.open(str(pdf_path))
    pages = [doc[i].get_text("text") for i in range(doc.page_count)]
    doc.close()

    table52_page = None
    table53_page = None
    for idx, text in enumerate(pages):
        compact = re.sub(r"\s+", "", text)
        if table52_page is None and "表52" in compact and "全国主要平原及盆地" in compact:
            table52_page = idx + 1
        if table53_page is None and "表53" in compact and "重点区域" in compact:
            table53_page = idx + 1

    if table52_page is None:
        raise ValueError("未找到表5-2（全国主要平原及盆地）")

    plains = _parse_table52(pages[table52_page - 1])
    # 跨页：若下一页仍以数字/区域名开始，继续解析
    for idx in range(table52_page, min(table52_page + 2, len(pages))):
        extra = _parse_table52(pages[idx])
        if extra:
            plains.extend(extra)
    key_regions = []
    if table53_page:
        key_regions = _parse_table53(pages[table53_page - 1])
        for idx in range(table53_page, min(table53_page + 2, len(pages))):
            extra = _parse_table53(pages[idx])
            if extra:
                key_regions.extend(extra)

    # 数据年份从标题推断
    title_text = pages[table52_page - 1]
    years = [int(y) for y in re.findall(r"(20\d{2})年", title_text)]
    data_years = sorted(set(years))[:2] or [report_year - 2, report_year - 1]

    return {
        "report_year": report_year,
        "title": meta.get("title") or f"{report_year}中国水文年报",
        "detail_url": meta.get("detail_url"),
        "pdf_url": meta.get("pdf_url"),
        "pages": len(pages),
        "data_years": data_years,
        "table52_page": table52_page,
        "table53_page": table53_page,
        "plains": plains,
        "key_regions": key_regions,
        "warnings": [],
    }


if __name__ == "__main__":
    import json
    import sys

    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2022
    index = json.loads(Path("data/annual/annual_index.json").read_text(encoding="utf-8"))
    meta = next((r for r in index if r["year"] == year), {})
    result = parse_annual_report(f"data/annual/pdfs/{year}.pdf", year, meta)
    out = Path(f"data/annual/parsed/{year}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        year,
        "data_years", result["data_years"],
        "plains", len(result["plains"]),
        "key_regions", len(result["key_regions"]),
        "pages", result["table52_page"], result["table53_page"],
    )
    for row in result["plains"]:
        print(row["region"], row["shallow_first"], row["shallow_second"], row["shallow_change"],
              row["deep_first"], row["deep_second"], row["deep_change"])
