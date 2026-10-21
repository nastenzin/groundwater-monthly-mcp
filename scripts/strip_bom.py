# -*- coding: utf-8 -*-
"""Strip UTF-8 BOM from the given files, preserving content."""
import sys
from pathlib import Path

for name in sys.argv[1:]:
    p = Path(name)
    data = p.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        p.write_bytes(data[3:])
        print("stripped", name)
    else:
        print("clean", name)
