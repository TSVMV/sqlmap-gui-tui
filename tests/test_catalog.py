"""catalog 选项解析纯函数单元测试。"""
from __future__ import annotations

from sqlmapx.core.catalog import _parse_option_spec, _split_spec_and_desc


def test_parse_short_flag():
    long_, short, metavar, is_flag = _parse_option_spec("-h")
    assert short == "-h"
    assert is_flag is True
    assert long_ is None
    assert metavar is None


def test_parse_long_flag():
    long_, short, metavar, is_flag = _parse_option_spec("--drop-set-cookie")
    assert long_ == "--drop-set-cookie"
    assert is_flag is True


def test_parse_long_with_metavar():
    long_, short, metavar, is_flag = _parse_option_spec("--url=URL")
    assert long_ == "--url"
    assert metavar == "URL"
    assert is_flag is False


def test_parse_short_with_metavar():
    long_, short, metavar, is_flag = _parse_option_spec("-D DB")
    assert short == "-D"
    assert metavar == "DB"
    assert is_flag is False


def test_split_spec_and_desc_separates():
    spec, desc = _split_spec_and_desc("-h, --help    Show help")
    assert "-h" in spec
    assert "--help" in spec
    assert "Show" in desc


def test_split_spec_and_desc_no_desc():
    spec, desc = _split_spec_and_desc("--batch")
    assert "--batch" in spec
    assert desc.strip() == ""
