# -*- coding: utf-8 -*-
"""Improved anchor extraction (text-box-left marker) + RANSAC affine calibration."""
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR

from proto_anchor import bd09_to_wgs84, load_city_table

PDF = Path("data/pdfs/2025-12.pdf")
OUT = Path("data/recon/maps_2025-12")
OUT.mkdir(parents=True, exist_ok=True)
tbl = load_city_table()
ocr = RapidOCR()


def anchor_point(box):
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    x0, x1 = min(xs), max(xs)
    yc = (min(ys) + max(ys)) / 2
    # 标记通常在文字左侧；OCR 常把「·」并入文本框
    return x0 + 2.0, yc


doc = pymupdf.open(PDF)
report = []
for pno in range(doc.page_count):
    page = doc[pno]
    text = page.get_text("text")
    caps = re.findall(r"图\s*(\d+)\s*([^\n]{0,50}埋深等值面图[^\n]{0,10})", text)
    if not caps:
        continue
    for fno, caption in caps:
        imgs = []
        for info in page.get_images(full=True):
            bb = page.get_image_bbox(info)
            imgs.append((info[2] * info[3], info[2], info[3], info[0], bb))
        imgs.sort(reverse=True)
        _, w, h, xref, bb = imgs[0]
        base = doc.extract_image(xref)
        img_path = OUT / f"p{pno+1}_fig{fno}_{w}x{h}.{base['ext']}"
        if not img_path.exists():
            img_path.write_bytes(base["image"])
        res, _ = ocr(str(img_path))
        anchors = []
        for box, text_, score in res or []:
            t = text_.strip(".·•⊙")
            t = re.sub(r"(市|地区|自治州|盟)$", "", t)
            if t in tbl:
                x, y = anchor_point(box)
                lon, lat = bd09_to_wgs84(*tbl[t])
                anchors.append((x, y, lon, lat, t))
        rec = {"page": pno + 1, "fig": int(fno), "caption": caption.strip(),
               "image": f"{w}x{h}", "n_anchors": len(anchors),
               "labels": [a[4] for a in anchors]}
        if len(anchors) >= 4:
            src = np.array([[a[0], a[1]] for a in anchors], np.float64)
            dst = np.array([[a[2], a[3]] for a in anchors], np.float64)
            A, inl = cv2.estimateAffine2D(src, dst, method=cv2.RANSAC,
                                          ransacReprojThreshold=0.012, maxIters=20000, confidence=0.999)
            if A is not None:
                pred = cv2.transform(src.reshape(-1, 1, 2), A).reshape(-1, 2)
                r = [math.hypot((p[0] - a[2]) * 111 * math.cos(math.radians(a[3])),
                                (p[1] - a[3]) * 111) for p, a in zip(pred, anchors)]
                good = [ri < 2.0 for ri in r]
                rec.update({"inliers": int(sum(good)),
                            "rmse_good_km": round(float(np.sqrt(np.mean(np.square([ri for ri in r if ri < 2.0]))) or 0), 2)
                            if any(good) else None,
                            "worst_km": round(float(max(r)), 1),
                            "A": A.tolist()})
        report.append(rec)
doc.close()
Path("data/recon/calib2_2025-12.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
ok = 0
for r in report:
    flag = "OK " if r.get("inliers", 0) >= 4 and (r.get("rmse_good_km") or 99) < 1.5 else "---"
    if flag == "OK ":
        ok += 1
    print(flag, r["page"], r["fig"], r["caption"][:30], "n", r["n_anchors"],
          "inl", r.get("inliers"), "rmse", r.get("rmse_good_km"), "worst", r.get("worst_km"))
print(f"\ncalibrated {ok}/{len(report)}")
