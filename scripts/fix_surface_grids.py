# -*- coding: utf-8 -*-
"""修复等级栅格编码（旧格式 -1 回绕为 255），去斑点并重新压缩。"""
import base64
import json
import zlib
from pathlib import Path

import cv2
import numpy as np

total = 0
for path in sorted(Path("data/surface/parsed").glob("*.json")):
    doc = json.loads(path.read_text(encoding="utf-8"))
    for m in doc.get("maps", []):
        if not m.get("grid"):
            continue
        raw = zlib.decompress(base64.b64decode(m["grid"]))
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(m["grid_h"], m["grid_w"]).astype(np.int16)
        # 旧格式：0..9 为等级，255 为图外
        grid = np.where(arr == 255, 0, arr + 1).astype(np.uint8)  # 新格式：cls+1
        for _ in range(2):
            blur = cv2.medianBlur(grid, 3)
            grid = np.where(grid == 0, 0, blur).astype(np.uint8)
        m["grid"] = base64.b64encode(zlib.compress(grid.tobytes(), 9)).decode()
        total += 1
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
print("fixed grids", total)
