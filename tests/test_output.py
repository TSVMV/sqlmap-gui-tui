"""output.parse_log 单元测试：从模拟 sqlmap 输出解析结果。"""
from __future__ import annotations

from sqlmapx.core.output import parse_log


def test_parse_injectable_parameter():
    text = (
        "Parameter 'id' is vulnerable and injectable\n"
        "technique (boolean-based blind)\n"
    )
    s = parse_log(text)
    assert "id" in s.injections
    assert s.technique == "boolean-based blind"


def test_parse_dbms():
    s = parse_log("[DBMS]: MySQL")
    assert s.dbms == "MySQL"


def test_parse_databases_block():
    text = (
        "available databases [2]:\n"
        "   'users'\n"
        "   'shop'\n"
    )
    s = parse_log(text)
    assert s.databases == ["users", "shop"]


def test_parse_empty_text():
    s = parse_log("nothing relevant here")
    assert s.injections == []
    assert s.dbms is None
    assert s.technique is None
