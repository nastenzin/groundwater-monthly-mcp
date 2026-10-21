# -*- coding: utf-8 -*-
"""Test digitization of a thumbnail map page (HTML period) at 4x upscale."""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, "src")
from groundwater_mcp.ingest import surface as surf

img = surf.imread_unicode(Path("data/surface/html/2024-09/p7.jpg"))
print("page", img.shape)
up = cv2.resize(img, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
legend = surf.decode_legend_array(up)
print("legend:", len(legend), [c["rgb"] for c in legend])
if legend:
    cls = surf.fill_gaps(surf.classify_map(up, legend))
    field, _ = surf.build_field(cls)
    stats = surf.field_stats(field, cls)
    print("share:", stats["class_share"])
    print("mean:", stats["mean_depth_m"], "cons:", stats["class_consistency"])
    ys, xs = np.where(cls >= 0)
    print("bbox colored:", xs.min(), xs.max(), ys.min(), ys.max(), "colored px:", len(xs))
# OCR anchors (upscaled)
cities = surf.load_city_points(Path("src/groundwater_mcp/data/geo/city_points.json"))
labels = surf.ocr_city_labels(up, cities)
print("ocr labels:", [(b["name"], round(b["x"]), round(b["y"])) for b in labels])
