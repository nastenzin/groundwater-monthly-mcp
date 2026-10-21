# -*- coding: utf-8 -*-
"""Classify a thumbnail map page using the PDF-edition palette; validate against narrative."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

PALETTE = [[51, 116, 252], [112, 200, 252], [195, 252, 179], [255, 254, 175],
           [252, 196, 253], [190, 153, 253], [254, 208, 93], [253, 175, 102],
           [249, 118, 95], [242, 12, 17]]
legend = [{"range": surf.RANGES[i], "lo": surf.BOUNDS[i], "hi": surf.BOUNDS[i + 1],
           "rgb": PALETTE[i]} for i in range(10)]

for pno, expected in ((7, 7.23), (9, 6.9), (11, 4.4), (13, 10.4)):
    img = surf.imread_unicode(Path(f"data/surface/html/2024-09/p{pno}.jpg"))
    up = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    cls = surf.fill_gaps(surf.classify_map(up, legend))
    field, _ = surf.build_field(cls)
    stats = surf.field_stats(field, cls)
    print(f"p{pno}: mean={stats['mean_depth_m']} expected~{expected} "
          f"cons={stats['class_consistency']} share={stats['class_share']}")
