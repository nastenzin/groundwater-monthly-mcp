# -*- coding: utf-8 -*-
"""包内工具：定位数据文件。"""
from __future__ import annotations

import os
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent


def data_dir() -> Path:
    env = os.environ.get("GROUNDWATER_DATA_DIR")
    if env:
        return Path(env)
    return PROJECT_ROOT / "data"


def db_path() -> Path:
    env = os.environ.get("GROUNDWATER_DB")
    if env:
        return Path(env)
    bundled = PACKAGE_DIR / "data" / "groundwater.db"
    if bundled.exists():
        return bundled
    return data_dir() / "groundwater.db"
