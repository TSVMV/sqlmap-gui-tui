"""路径与运行环境配置。

sqlmap 本体作为黑盒依赖，定位顺序为：

1. 环境变量 ``SQLMAP_HOME``（指向含 sqlmap.py 的目录）；
2. pip 安装的 ``sqlmap`` 包（``pip install sqlmapx`` 会自动拉取）；
3. 项目内 ``vendor/sqlmap``（源码开发时由 install 脚本 clone 而来）。

所有可写数据落在数据目录（开发期为项目内 ``profiles/``，pip 安装后为
用户数据目录），便于迁移与清理。

本模块只负责路径/环境常量与校验，不含文件 IO。
JSON 读写由调用方（profiles.py / catalog.py）按各自路径策略实现：
- profiles.py 用 _safe() 白名单净化文件名 + 固定 PROFILES_DIR 拼接，
- catalog.py 用固定常量 CATALOG_CACHE，
均无用户可控路径，故不存在路径穿越。
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

# 项目根：本文件位于 <root>/sqlmapx/core/config.py
BASE_DIR = Path(__file__).resolve().parents[2]


def _writable(path: Path) -> bool:
    """目录是否可写（用于区分开发检出与 site-packages 安装）。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        return os.access(path, os.W_OK)
    except OSError:
        return False


def _sqlmap_dir() -> Path:
    """按 SQLMAP_HOME > pip 包 > vendor/sqlmap 顺序定位 sqlmap 根目录。"""
    home = os.environ.get("SQLMAP_HOME")
    if home:
        return Path(home)
    # pip 安装的 sqlmap 包：sqlmap/sqlmap.py 即其入口脚本
    spec = importlib.util.find_spec("sqlmap")
    if spec is not None and spec.origin:
        pkg_dir = Path(spec.origin).resolve().parent
        if (pkg_dir / "sqlmap.py").is_file():
            return pkg_dir
    return BASE_DIR / "vendor" / "sqlmap"


SQLMAP_DIR = _sqlmap_dir()
SQLMAP_PY = SQLMAP_DIR / "sqlmap.py"

# 数据目录：开发检出可写时落在项目内，否则用用户数据目录（site-packages 只读）
if _writable(BASE_DIR):
    _DATA_DIR = BASE_DIR / "profiles"
else:
    _base = os.environ.get("SQLMAPX_DATA")
    if _base:
        _DATA_DIR = Path(_base)
    elif os.name == "nt":
        _DATA_DIR = Path(os.environ.get("LOCALAPPDATA", "~/AppData/Local")) / "sqlmapx"
    elif sys.platform == "darwin":
        _DATA_DIR = Path.home() / "Library" / "Application Support" / "sqlmapx"
    else:
        _DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")) / "sqlmapx"
    _DATA_DIR = _DATA_DIR.expanduser()

PROFILES_DIR = _DATA_DIR
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
            "可用以下任一方式提供 sqlmap：\n"
            "  pip install sqlmap          （推荐，自动随 sqlmapx 安装）\n"
            f"  git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git "
            f"\"{BASE_DIR / 'vendor' / 'sqlmap'}\"\n"
            "或设置环境变量 SQLMAP_HOME 指向已有的 sqlmap 目录。"
        )
