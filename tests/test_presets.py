"""presets.merge 单元测试：优先级与空值丢弃。"""
from __future__ import annotations

from sqlmapx.core.presets import Preset, merge


def _preset(opts: dict[str, object]) -> Preset:
    return Preset(key="k", title="t", desc="d", options=dict(opts))


def test_preset_options_form_base():
    p = _preset({"-u": "http://x", "--batch": "1"})
    out = merge(p, {}, {})
    assert out["-u"] == "http://x"
    assert out["--batch"] == "1"


def test_extra_overrides_preset():
    p = _preset({"-u": "http://old"})
    out = merge(p, {"-u": "http://new"}, {})
    assert out["-u"] == "http://new"


def test_fills_override_extra():
    p = _preset({"-u": "http://base"})
    out = merge(p, {"-u": "http://extra"}, {"-u": "http://fill"})
    assert out["-u"] == "http://fill"


def test_empty_values_dropped():
    p = _preset({"-u": "http://x", "--empty": ""})
    out = merge(p, {"--also-empty": None}, {"--fill-empty": ""})
    assert "--empty" not in out
    assert "--also-empty" not in out
    assert "--fill-empty" not in out
    assert out["-u"] == "http://x"


def test_keeps_only_nonempty():
    p = _preset({"-a": "1", "-b": ""})
    out = merge(p, {}, {})
    assert "-a" in out
    assert "-b" not in out
