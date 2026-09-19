"""路径与运行环境配置。

sqlmap 本体作为黑盒依赖置于 ``vendor/sqlmap``，不修改其任何文件。
所有可写数据落在项目内 ``profiles/`` 目录，便于迁移与清理。

本模块只负责路径/环境常量与校验，不含文件 IO。
JSON 读写由调用方（profiles.py / catalog.py）按各自路径策略实现：
- profiles.py 用 _safe() 白名单净化文件名 + 固定 PROFILES_DIR 拼接，
- catalog.py 用固定常量 CATALOG_CACHE，
均无用户可控路径，故不存在路径穿越。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 项目根：本文件位于 <root>/sqlmapx/core/config.py
BASE_DIR = Path(__file__).resolve().parents[2]

# sqlmap 本体目录。可用 SQLMAP_HOME 环境变量覆盖（指向含 sqlmap.py 的目录）。
SQLMAP_DIR = Path(os.environ.get("SQLMAP_HOME") or (BASE_DIR / "vendor" / "sqlmap"))
SQLMAP_PY = SQLMAP_DIR / "sqlmap.py"

# 数据目录：任务配置档、扫描输出目录、选项目录缓存
PROFILES_DIR = BASE_DIR / "profiles"
OUTPUT_DIR = PROFILES_DIR / "out"
CATALOG_CACHE = PROFILES_DIR / "catalog.json"
PROFILES_EXT = ".json"

# 运行 sqlmap 用的解释器：默认复用当前 Python；若与 sqlmap 不兼容可设 SQLMAP_PYTHON。
SQLMAP_PYTHON = os.environ.get("SQLMAP_PYTHON") or sys.executable


def ensure_dirs() -> None:
    """确保数据目录存在。"""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def check_sqlmap() -> None:
    """启动期校验 sqlmap.py 是否就位，给出可操作的提示。"""
    if not SQLMAP_PY.is_file():
        raise FileNotFoundError(
            f"未找到 sqlmap.py：{SQLMAP_PY}\n"
            "请先下载 sqlmap：\n"
            f"  git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git "
            f"\"{BASE_DIR / 'vendor' / 'sqlmap'}\"\n"
            "或设置环境变量 SQLMAP_HOME 指向已有的 sqlmap 目录。"
        )
