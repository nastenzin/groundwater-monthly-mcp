# -*- coding: utf-8 -*-
"""原型：从彩色等值面图提取等值线并反演连续埋深场（距离加权插值）。

步骤：
  1) 图例解码 -> 10 个等级色 + 等级边界（m）
  2) 颜色分类 -> 等级栅格（-1 为图外/文字/河流）
  3) 逐级提取等值线（等级 i 与 i+1 的分界 = 该级上界等值线）
  4) 距离加权插值：值 = L_i + (L_{i+1}-L_i) * d_i/(d_i+d_{i+1})
  5) 校验：每像素值必须落在其颜色等级区间内；输出可视化与统计
"""
import json
import math
from pathlib import Path

import cv2
import numpy as np

CLASS_RANGES = ["<2", "2~4", "4~8", "8~12", "12~16", "16~20", "20~30", "30~40", "40~50", ">50"]
BOUNDS = [0, 2, 4, 8, 12, 16, 20, 30, 40, 50, 1e9]   # 等级 i: [BOUNDS[i], BOUNDS[i+1])
LEVELS = [2, 4, 8, 12, 16, 20, 30, 40, 50]           # 等值线值

MAP = Path("data/recon/p7_img0_900x926.jpeg")
LEG = Path("data/recon/p7_img1_345x232.jpeg")


def decode_legend(path):
    img = cv2.imread(str(path))
    mx = np.max(img, axis=2).astype(np.int16)
    mn = np.min(img, axis=2).astype(np.int16)
    chroma = mx - mn
    mask = ((chroma > 12) & (mx > 100) & ~((mx > 245) & (mn > 235))).astype(np.uint8) * 255
    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    sw = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        x, y, w_, h_ = (int(v) for v in stats[i, :4])
        if not (200 <= area <= 3000 and 20 <= w_ <= 90 and 12 <= h_ <= 45):
            continue
        b, g, r = np.median(img[lab == i], axis=0)
        sw.append({"x": x, "y": y, "rgb": [int(r), int(g), int(b)], "area": area})
    sw.sort(key=lambda s: (0 if s["x"] < img.shape[1] / 2 else 1, s["y"]))
    return sw[:10]


def classify(img, legend_rgb):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.int16)
    refs = []
    for rgb in legend_rgb:
        bgr = np.uint8([[[rgb[2], rgb[1], rgb[0]]]])
        refs.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[0, 0].astype(np.int16))
    mx = img.max(axis=2).astype(np.int16)
    mn = img.min(axis=2).astype(np.int16)
    cand = ((mx > 100) & ((mx - mn) > 10) & ~((mx > 240) & (mn > 225))).reshape(-1)
    flat = lab.reshape(-1, 3)
    d = np.stack([np.linalg.norm(flat - r, axis=1) for r in refs], axis=1)
    cls = np.where((d.min(axis=1) < 22) & cand, d.argmin(axis=1), -1).reshape(img.shape[:2])
    return cls.astype(np.int8)


def main():
    sw = decode_legend(LEG)
    legends = [s["rgb"] for s in sw]
    img = cv2.imread(str(MAP))
    cls = classify(img, legends)
    # 等值面图内部有抗锯齿/描边造成的空隙：用最近有效像素补齐，保证等级区域连续
    col = (cls >= 0).astype(np.uint8)
    col = cv2.morphologyEx(col, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    col = cv2.morphologyEx(col, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    from scipy.ndimage import distance_transform_edt
    ind = distance_transform_edt(cls < 0, return_distances=False, return_indices=True)
    cls_filled = cls[ind[0], ind[1]]
    cls = np.where(col > 0, cls_filled, -1).astype(np.int8)
    valid = (cls >= 0).astype(np.uint8)
    print("legend colors:", legends)
    share = {CLASS_RANGES[i]: round(float((cls == i).sum() / valid.sum() * 100), 1)
             for i in range(10) if (cls == i).any()}
    print("class share:", share)

    # 等值线：等级 <= k 与 > k 的分界
    contours = {}
    for k, level in enumerate(LEVELS):
        inner = ((cls >= 0) & (cls <= k)).astype(np.uint8)
        outer = ((cls > k).astype(np.uint8))
        # 上采样 1px 膨胀差值找含 valid 内的分界线
        ker = np.ones((3, 3), np.uint8)
        dil = cv2.dilate(outer, ker)
        line = (dil > 0) & (inner > 0)
        line &= valid > 0
        ys, xs = np.where(line)
        if len(xs) < 10:
            continue
        contours[level] = (xs, ys)
        print(f"level {level:>3}: {len(xs)} px isoline")

    if not contours:
        raise SystemExit("no contours")

    # 距离场
    H, W = cls.shape
    # 每个等级的距离
    dists = {}
    for level, (xs, ys) in contours.items():
        m = np.ones((H, W), np.uint8)
        m[ys, xs] = 0
        dists[level] = cv2.distanceTransform(m, cv2.DIST_L2, 5)

    field = np.full((H, W), np.nan, np.float32)
    for c in range(10):
        m = cls == c
        if not m.any():
            continue
        lo, hi = BOUNDS[c], BOUNDS[c + 1]
        lower = lo if (c >= 1 and lo in dists) else None
        upper = hi if (hi < 1e8 and hi in dists) else None
        if lower is not None and upper is not None:
            dl, du = dists[lower], dists[upper]
            s = dl + du
            s[s == 0] = 1
            field[m] = (lower + (upper - lower) * (dl[m] / s[m])).astype(np.float32)
        elif lower is not None and upper is None:  # 最深一级：向中心外推
            field[m] = np.float32(min(lo + (hi - lo) * 0.5, lo + 8.0))
        elif upper is not None and lower is None:  # 最浅一级：向边缘外推
            field[m] = np.float32(max(upper - (upper - lo) * 0.5, 0.5))
        else:
            field[m] = np.float32((lo + min(hi, lo + 10)) / 2)
    # 校验：落在等级区间内的比例
    ok = 0
    tot = 0
    for c in range(10):
        m = (cls == c) & np.isfinite(field)
        if not m.any():
            continue
        lo, hi = BOUNDS[c], BOUNDS[c + 1]
        tot += int(m.sum())
        ok += int(((field[m] >= lo - 1e-3) & (field[m] <= hi + 1e-3)).sum())
    print(f"class-consistency: {ok}/{tot} ({ok / max(1, tot) * 100:.1f}%)")
    vals = field[np.isfinite(field)]
    print("field min/max/mean:", round(float(vals.min()), 2), round(float(vals.max()), 2),
          round(float(vals.mean()), 2))

    # 可视化
    vis = np.zeros((H, W, 3), np.uint8)
    fv = np.nan_to_num(field, nan=0.0)
    norm = np.clip(fv / 55.0 * 255, 0, 255).astype(np.uint8)
    vis = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)
    vis[~np.isfinite(field)] = (255, 255, 255)
    for level, (xs, ys) in contours.items():
        vis[ys, xs] = (0, 0, 0)
    out = Path("data/recon/field_sanjiang.png")
    cv2.imwrite(str(out), vis)
    print("saved", out)

    # 点采样示例：地图内随机点
    rng = np.random.default_rng(0)
    idx = rng.choice(np.where(np.isfinite(field))[0].shape[0], size=5, replace=False)
    ys, xs = np.where(np.isfinite(field))
    for i in idx:
        print(f"  sample pixel ({xs[i]},{ys[i]}) class={CLASS_RANGES[cls[ys[i], xs[i]]]} depth={field[ys[i], xs[i]]:.2f} m")


if __name__ == "__main__":
    main()
