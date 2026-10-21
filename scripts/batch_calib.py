# -*- coding: utf-8 -*-
"""Batch test: calibrate all 埋深等值面图 of one report with city-dot anchors."""
import json
import math
import re
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from rapidocr_onnxruntime import RapidOCR

from proto_anchor import bd09_to_wgs84, find_dots, load_city_table

PDF = Path("data/pdfs/2025-12.pdf")
OUT = Path("data/recon/maps_2025-12")
OUT.mkdir(parents=True, exist_ok=True)

tbl = load_city_table()
ocr = RapidOCR()
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
            w, h = info[2], info[3]
            imgs.append((w * h, w, h, info[0], bb))
        if not imgs:
            continue
        imgs.sort(reverse=True)
        _, w, h, xref, bb = imgs[0]
        base = doc.extract_image(xref)
        img_path = OUT / f"p{pno+1}_fig{fno}_{w}x{h}.{base['ext']}"
        img_path.write_bytes(base["image"])
        img = cv2.imread(str(img_path))
        res, _ = ocr(str(img_path))
        labels = []
        for box, text_, score in res or []:
            t = text_.strip(".·• ")
            t = re.sub(r"(市|地区|自治州|盟)$", "", t)
            if t in tbl:
                dot = find_dots(img, box)
                if dot:
                    labels.append((t, dot))
        anchors = []
        for t, dot in labels:
            lon, lat = bd09_to_wgs84(*tbl[t])
            anchors.append((dot[0], dot[1], lon, lat, t))
        rec = {"page": pno + 1, "fig": int(fno), "caption": caption.strip(),
               "image": f"{w}x{h}", "labels": [a[4] for a in anchors]}
        if len(anchors) >= 3:
            src = np.array([[a[0], a[1]] for a in anchors], np.float64)
            dst = np.array([[a[2], a[3]] for a in anchors], np.float64)
            A, inl = cv2.estimateAffine2D(src, dst, method=cv2.RANSAC,
                                          ransacReprojThreshold=0.0025, maxIters=5000, confidence=0.995)
            if A is not None:
                pred = cv2.transform(src.reshape(-1, 1, 2), A).reshape(-1, 2)
                res_km = [math.hypot((p[0] - a[2]) * 111 * math.cos(math.radians(a[3])),
                                     (p[1] - a[3]) * 111) for p, a in zip(pred, anchors)]
                inliers = int(inl.sum()) if inl is not None else 0
                rec.update({"n": len(anchors), "inliers": inliers,
                            "rmse_km": round(float(np.sqrt(np.mean(np.square(res_km)))), 2),
                            "max_km": round(float(max(res_km)), 2), "A": A.tolist()})
        report.append(rec)
doc.close()
Path("data/recon/calib_2025-12.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                                 encoding="utf-8")
for r in report:
    print(r["page"], r["fig"], r["caption"][:34], "|", r["image"], "| labels", len(r["labels"]),
          "| inliers", r.get("inliers"), "| rmse", r.get("rmse_km"))
