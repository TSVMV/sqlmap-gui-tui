"""config 路径与 sqlmap 发现逻辑单元测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from sqlmapx.core import config


def test_sqlmap_dir_honors_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SQLMAP_HOME", str(tmp_path))
    assert config._sqlmap_dir() == tmp_path


def test_sqlmap_dir_falls_back_to_vendor(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("SQLMAP_HOME", raising=False)
    monkeypatch.setattr(config.importlib.util, "find_spec", lambda _: None)
    out = config._sqlmap_dir()
    assert out == config.BASE_DIR / "vendor" / "sqlmap"


class _FakeSpec:
    def __init__(self, origin: str):
        self.origin = origin


def test_sqlmap_dir_uses_pip_package(monkeypatch, tmp_path: Path):
    pkg = tmp_path / "sqlmap"
    pkg.mkdir()
    (pkg / "sqlmap.py").write_text("# stub entry")
    monkeypatch.delenv("SQLMAP_HOME", raising=False)
    monkeypatch.setattr(
        config.importlib.util, "find_spec",
        lambda name: _FakeSpec(str(pkg / "__init__.py")) if name == "sqlmap" else None)
    out = config._sqlmap_dir()
    assert out == pkg


def test_check_sqlmap_raises_when_missing(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "SQLMAP_PY", tmp_path / "nope.py")
    with pytest.raises(FileNotFoundError) as exc:
        config.check_sqlmap()
    msg = str(exc.value)
    assert "sqlmap.py" in msg
    assert "SQLMAP_HOME" in msg
    assert "pip install sqlmap" in msg


def test_check_sqlmap_ok_when_present(monkeypatch, tmp_path: Path):
    entry = tmp_path / "sqlmap.py"
    entry.write_text("# stub")
    monkeypatch.setattr(config, "SQLMAP_PY", entry)
    config.check_sqlmap()  # 不抛异常


def test_ensure_dirs_creates_profiles(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(config, "PROFILES_DIR", tmp_path / "profiles")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "profiles" / "out")
    config.ensure_dirs()
    assert (tmp_path / "profiles" / "out").is_dir()
