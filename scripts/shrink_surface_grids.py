# -*- coding: utf-8 -*-
"""把等值面等级栅格降采样到长边 160px，减小随包数据库体积（定标误差大于像元尺寸）。"""
import base64
import json
import zlib
from pathlib import Path

import cv2
import numpy as np

MAX = 160
total_before = 0
total_after = 0
for path in sorted(Path("data/surface/parsed").glob("*.json")):
    doc = json.loads(path.read_text(encoding="utf-8"))
    for m in doc.get("maps", []):
        if not m.get("grid"):
            continue
        raw = zlib.decompress(base64.b64decode(m["grid"]))
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(m["grid_h"], m["grid_w"])
        total_before += len(raw)
        h, w = arr.shape
        scale = MAX / max(h, w)
        gw, gh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        if gw == w and gh == h:
            total_after += len(raw)
            continue
        small = cv2.resize(arr, (gw, gh), interpolation=cv2.INTER_NEAREST)
        m["grid_w"], m["grid_h"] = gw, gh
        m["grid"] = base64.b64encode(zlib.compress(small.tobytes(), 9)).decode()
        total_after += len(small)
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
print("raw before", total_before, "after", total_after)
