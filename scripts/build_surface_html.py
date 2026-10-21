# -*- coding: utf-8 -*-
"""数字化 2024-01~09 HTML5 期次的埋深等值面图（来源：官网 flipbook 页面缩略图 335×480）。

HTML 期次的页面大图已从官网移除，仅存 335×480 缩略图，因此：
* 图例通过“色块聚类”定位后单独放大解码；
* 城市注记太小无法 OCR，定标退化为“叙述监测面积反推尺度 + 区域多边形质心”，
  quality 固定为 low，并在记录中标注 source=html-thumbnail；
* 一页两图时按彩色图斑的垂直间隙自动切分。
"""
from __future__ import annotations

import base64
import json
import re
import sys
import zlib
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import build_surface_data as B  # noqa: E402
from groundwater_mcp.ingest import surface as surf  # noqa: E402

THUMB_DIR = ROOT / "data" / "surface" / "html"
OUT_DIR = ROOT / "data" / "surface" / "parsed"
PERIODS = ["2024-01", "2024-02", "2024-03", "2024-04", "2024-05",
           "2024-06", "2024-07", "2024-08", "2024-09"]

PALETTE = [[51, 116, 252], [112, 200, 252], [195, 252, 179], [255, 254, 175],
           [252, 196, 253], [190, 153, 253], [254, 208, 93], [253, 175, 102],
           [249, 118, 95], [242, 12, 17]]
PALETTE_LEGEND = [{"range": surf.RANGES[i], "lo": surf.BOUNDS[i], "hi": surf.BOUNDS[i + 1],
                   "rgb": PALETTE[i]} for i in range(10)]


def page_text(period: str, page: int) -> str:
    path = ROOT / "data" / "legacy" / "html" / period / f"page{page}.html"
    if not path.exists():
        return ""
    raw = path.read_text(encoding="utf-8", errors="ignore")
    body = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", body)


def page_captions(period: str, page: int) -> list[tuple[int, str, str]]:
    """返回 [(图号, 区域文字, 完整图题)]。"""
    text = page_text(period, page)
    out = []
    pat = re.compile(r"图\s*(\d+)\s*([\u4e00-\u9fa5A-Za-z（）()及和、与]{2,40}?)\s*(\d+)\s*月份"
                     r"\s*地下水埋深等值面图")
    for m in pat.finditer(text):
        out.append((int(m.group(1)), m.group(2).strip(), m.group(0).strip()))
    return out


def detect_legend_box(up: np.ndarray) -> tuple[int, int, int, int] | None:
    cls = surf.classify_map(up, PALETTE_LEGEND)
    mask = (cls >= 0).astype(np.uint8)
    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    small = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        w, h = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if not (25 <= area <= 4000 and 3 <= w <= 120 and 3 <= h <= 90):
            continue
        small.append((float(cents[i][0]), float(cents[i][1]), w, h))
    if len(small) < 6:
        return None
    best: list = []
    for cx, cy, _, _ in small:
        group = [s for s in small if abs(s[0] - cx) < 110 and abs(s[1] - cy) < 110]
        if len(group) > len(best):
            best = group
    if len(best) < 6:
        return None
    xs0 = min(s[0] - s[2] / 2 for s in best)
    xs1 = max(s[0] + s[2] / 2 for s in best)
    ys0 = min(s[1] - s[3] / 2 for s in best)
    ys1 = max(s[1] + s[3] / 2 for s in best)
    pad = 8
    return (max(0, int(xs0 - pad)), max(0, int(ys0 - pad)),
            int(xs1 - xs0 + 2 * pad), int(ys1 - ys0 + 2 * pad))


def decode_thumb_legend(up: np.ndarray, box) -> list[dict]:
    if box is not None:
        x, y, w, h = box
        crop = up[y:y + h, x:x + w]
        if crop.size:
            for scale in (2.5, 3.5, 2.0):
                big = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                legend = surf.decode_legend_array(big)
                if len(legend) == 10:
                    return legend
    return PALETTE_LEGEND


def figure_boxes(up: np.ndarray, legend: list[dict], box, n_figs: int) -> list[tuple[int, ...]]:
    """按彩色图斑返回每个图件的裁剪 bbox（x0,y0,x1,y1）。"""
    cls = surf.classify_map(up, legend)
    mask = (cls >= 0).astype(np.uint8)
    if box is not None:
        x, y, w, h = box
        mask[max(0, y - 2):y + h + 2, max(0, x - 2):x + w + 2] = 0
    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    comps = [(float(cents[i][0]), float(cents[i][1]), stats[i, cv2.CC_STAT_AREA])
             for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= 150]
    if not comps:
        raise RuntimeError("未找到有效图斑")
    comps.sort(key=lambda c: c[1])
    groups = [comps]
    if n_figs >= 2 and len(comps) >= 2:
        gaps = [(comps[i + 1][1] - comps[i][1], i) for i in range(len(comps) - 1)]
        gaps.sort(reverse=True)
        _, idx = gaps[0]
        groups = [comps[:idx + 1], comps[idx + 1:]]
    out = []
    for grp in groups:
        xs = [c[0] for c in grp]
        ys = [c[1] for c in grp]
        pad = 14
        # 用连通域真实 bbox 更稳：重新按组内质心范围 + 最大分量 bbox
        x0 = max(0, int(min(xs) - pad))
        x1 = min(up.shape[1] - 1, int(max(xs) + pad))
        y0 = max(0, int(min(ys) - pad))
        y1 = min(up.shape[0] - 1, int(max(ys) + pad))
        out.append((x0, y0, x1, y1))
    return out


def digitize_crop(crop: np.ndarray, legend: list[dict], expected: dict, *,
                  fig_no: int, caption: str, regions: list[str]) -> dict:
    cls = surf.fill_gaps(surf.classify_map(crop, legend))
    field, _ = surf.build_field(cls)
    stats_d = surf.field_stats(field, cls)
    exp = dict(expected)
    exp["cities"] = {}
    calib = surf.calibrate(crop, (cls >= 0).astype(np.uint8), exp)
    h, w = cls.shape
    scale = surf.COARSE_MAX / max(h, w)
    gw, gh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    grid_small = cv2.resize((cls + 1).astype(np.uint8), (gw, gh), interpolation=cv2.INTER_NEAREST)
    for _ in range(2):
        blur = cv2.medianBlur(grid_small, 3)
        grid_small = np.where(grid_small == 0, 0, blur).astype(np.uint8)
    rec = {"figure": fig_no, "caption": caption, "regions": regions,
           "image_size": [w, h], "legend": legend, "grid_w": gw, "grid_h": gh,
           "grid": base64.b64encode(zlib.compress(grid_small.tobytes(), 9)).decode(),
           "source": "html-thumbnail", **stats_d}
    if calib:
        rec.update(calib)
        rec["quality"] = "low"
        rec["area_km2"] = round(float(calib["k_km_per_px"] ** 2 * (cls >= 0).sum()), 1)
        exp_area = exp.get("area_km2")
        rec["expected_area_km2"] = round(float(exp_area), 1) if exp_area else None
        rec["area_ratio"] = round(rec["area_km2"] / exp_area, 2) if exp_area else None
    return rec


def process_period(period: str) -> dict:
    exp = B.load_expected(period)
    maps: list[dict] = []
    page_dir = THUMB_DIR / period
    pages = sorted((int(re.sub(r"\D", "", p.stem)) for p in page_dir.glob("p*.jpg")))
    for page in pages:
        img = surf.imread_unicode(page_dir / f"p{page}.jpg")
        caps = page_captions(period, page)
        if not caps:
            continue
        up = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        box = detect_legend_box(up)
        legend = decode_thumb_legend(up, box)
        try:
            boxes = figure_boxes(up, legend, box, len(caps))
        except Exception as exc:  # noqa: BLE001
            for fig_no, _, caption in caps:
                maps.append({"period": period, "page": page, "figure": fig_no,
                             "caption": caption, "error": repr(exc)})
            continue
        if len(boxes) != len(caps):
            # 分组数量与图题不一致时，退回均分
            h = up.shape[0]
            step = h // len(caps)
            boxes = [(0, i * step, up.shape[1] - 1, (i + 1) * step - 1)
                     for i in range(len(caps))]
        for (fig_no, region_text, caption), (x0, y0, x1, y1) in zip(caps, boxes):
            regions = B.caption_regions(f"图{fig_no} {region_text} 1 月份地下水埋深等值面图")
            e = B.expected_for(regions, exp)
            try:
                rec = digitize_crop(up[y0:y1 + 1, x0:x1 + 1], legend, e,
                                    fig_no=fig_no, caption=caption, regions=regions)
                rec.update({"period": period, "page": page})
                maps.append(rec)
            except Exception as exc:  # noqa: BLE001
                maps.append({"period": period, "page": page, "figure": fig_no,
                             "caption": caption, "regions": regions, "error": repr(exc)})
    return {"period": period, "count": len(maps), "maps": maps}


def main() -> None:
    periods = sys.argv[1:] or PERIODS
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for period in periods:
        res = process_period(period)
        (OUT_DIR / f"{period}.json").write_text(
            json.dumps(res, ensure_ascii=False), encoding="utf-8")
        ok = [m for m in res["maps"] if "error" not in m]
        print(f"{period}: figures={len(res['maps'])} ok={len(ok)}")


if __name__ == "__main__":
    main()
