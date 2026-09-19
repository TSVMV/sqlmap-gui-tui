"""任务预设（一键任务）与常用参数快捷。

目标：把"繁琐"的多选项组合收敛成"点一下 = 一条典型 sqlmap 路径"，
同时保留全选项表单供专家展开使用。所有预设都只是 sqlmap 原生选项的
不同组合，**不引入任何新能力**，功能与官方 CLI 完全一致。

选项名均以 ``sqlmap -hh`` 为准（短形如 -D/-T/-v 在 sqlmap 中无长形）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Preset:
    key: str
    title: str
    desc: str
    options: Dict[str, object] = field(default_factory=dict)
    needs: List[str] = field(default_factory=list)  # 需用户补全的选项名
    category: str = "core"


def _p(key, title, desc, opts, needs=(), cat="core") -> Preset:
    return Preset(key, title, desc, dict(opts), list(needs), cat)


# 常用参数快捷（单选项，主屏可直接点/填）
QUICK_PARAMS: List[dict] = [
    {"opt": "--batch", "label": "Batch（跳过交互提问）", "hint": "自动化运行，遇提示取默认"},
    {"opt": "-v", "label": "Verbosity（0-6）", "hint": "默认 1；高则日志更多", "value": "3"},
    {"opt": "--level", "label": "Level（检测深度 1-5）", "hint": "默认 1；越高 payload 越多、越慢", "value": "3"},
    {"opt": "--risk", "label": "Risk（风险 1-3）", "hint": "默认 1", "value": "1"},
    {"opt": "--technique", "label": "Technique（B/E/U/Q/T/S…）", "hint": "如 BEUSTQ"},
    {"opt": "--tamper", "label": "Tamper（混淆脚本，逗号分隔）", "hint": "绕 WAF，如 space2comment,basedex2num"},
    {"opt": "--proxy", "label": "Proxy（代理）", "hint": "http://127.0.0.1:8080"},
    {"opt": "--threads", "label": "Threads（并发线程）", "hint": "默认 1", "value": "4"},
    {"opt": "--delay", "label": "Delay（请求间隔秒）", "hint": "规避限速", "value": "1"},
    {"opt": "--timeout", "label": "Timeout（超时秒）", "hint": "默认 30", "value": "30"},
    {"opt": "--dbms", "label": "DBMS（强制后端）", "hint": "MySQL / PostgreSQL / …"},
    {"opt": "--cookie", "label": "Cookie（登录态）", "hint": "PHPSESSID=…"},
    {"opt": "--data", "label": "POST 数据", "hint": "id=1&x=2"},
]

# 一键任务（按类别）
PRESETS: List[Preset] = [
    # 核心注入链
    _p("detect", "探测注入", "检测是否可注入（不进一步枚举）。sqlmap 默认即检测。",
       {"--batch": "1"}, needs=[]),
    _p("dbs", "列出数据库", "检测并枚举可用数据库名。",
       {"--dbs": "1", "--batch": "1"}, needs=[]),
    _p("tables", "列出表", "在指定库下列出表。需选库(-D)。",
       {"--tables": "1", "--batch": "1"}, needs=["-D"]),
    _p("columns", "列出列", "列出指定表的列。需选库表(-D/-T)。",
       {"--columns": "1", "--batch": "1"}, needs=["-D", "-T"]),
    _p("dump", "读取数据", "导出指定表的数据。需选库表(-D/-T)。",
       {"--dump": "1", "--batch": "1"}, needs=["-D", "-T"]),
    _p("os-shell", "拿 OS 壳", "注入点转 OS 命令行交互。",
       {"--os-shell": "1", "--batch": "1"}, needs=[]),
    _p("sql-shell", "拿 SQL 壳", "注入点转数据库命令行交互。",
       {"--sql-shell": "1", "--batch": "1"}, needs=[]),
    # 凭证 / 哈希枚举
    _p("current-user", "当前用户", "获取数据库当前用户。",
       {"--current-user": "1", "--batch": "1"}, needs=[]),
    _p("users", "枚举用户", "枚举全部数据库用户。",
       {"--users": "1", "--batch": "1"}, needs=[]),
    _p("passwords", "读密码哈希", "枚举用户密码哈希。需选库(-D)。",
       {"--passwords": "1", "--batch": "1"}, needs=["-D"]),
    _p("privileges", "读用户权限", "枚举用户权限。需选库(-D)。",
       {"--privileges": "1", "--batch": "1"}, needs=["-D"]),
    # 高级 / 特殊任务
    _p("file-read", "读文件", "读取指定文件(绝对路径)。",
       {"--file-read": ""}, needs=["--file-read"], cat="adv"),
    _p("os-cmd", "执行 OS 命令", "在目标上执行命令(-os-cmd)。",
       {"--os-cmd": ""}, needs=["--os-cmd"], cat="adv"),
    _p("xxe-oob", "OOB 外带 XXE", "对 XXE 注入做 OOB。",
       {"--xxe": "1", "--oob-server": "", "--batch": "1"}, needs=["--oob-server"], cat="adv"),
    _p("fingerprint", "指纹/WAF 识别", "识别后端 DBMS 与 WAF。",
       {"--fingerprint": "1", "--batch": "1"}, cat="adv"),
]

PRESETS_BY_KEY = {p.key: p for p in PRESETS}


def merge(preset: Preset, extra: Dict[str, object], fills: Dict[str, object]) -> Dict[str, object]:
    """合并预设 + 用户常用参数 + 占位补全，得到最终选项字典。

    - extra：QUICK_PARAMS 里勾选/填写的常用参数。
    - fills：界面针对 preset.needs 补全的值（如 -D/-T/--file-read/…）。
    后者优先级更高（覆盖同键）。空值占位键会被丢弃，避免传空参数。
    """
    out: Dict[str, object] = {}
    out.update(preset.options)
    out.update({k: v for k, v in extra.items() if v not in (None, "")})
    out.update({k: v for k, v in fills.items() if v not in (None, "")})
    return {k: v for k, v in out.items() if v not in (None, "")}
