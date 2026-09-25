"""扫描输出解析：从运行日志与 sqlmap 输出目录提取结构化摘要。

这是尽力而为（best-effort）的正则提取，用于在界面里给出"命中了什么"的
概览；权威结果仍以 sqlmap 自身输出与 ``profiles/out/`` 目录为准。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import config

_DBMS_RE = re.compile(r"(?i)\[DBMS\]:\s+(?P<dbms>[^\s]+)")
_TECH_RE = re.compile(r"(?i)using (?P<tech>technique\s+[(][A-Z\s,][)\]]|(?P<t>[AEUMNOPQRSTCZ]{1,}))")
_INJ_RE = re.compile(r"(?i)parameter[^\n]*?(?P<p>[^\n:]+):\s*(?P<tech>[A-Z ]+)")
_PAYLOAD_RE = re.compile(r"(?i)\[?payload[?]:\s*(?P<payload>.*)")
_DUMP_RE = re.compile(r"(?i)fetching data?\s+from\s+(?P<what>[\w./]+)")
_DB_RE = re.compile(r"(?i)available databases?[:\s]*(?P<list>.*)")


@dataclass
class Summary:
    dbms: str | None = None
    technique: str | None = None
    injections: list[str] = field(default_factory=list)
    payloads: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    dumps: list[str] = field(default_factory=list)

    @property
    def has_injection(self) -> bool:
        return bool(self.injections)

    def to_lines(self) -> list[str]:
        lines: list[str] = []
        if self.dbms:
            lines.append(f"DBMS: {self.dbms}")
        if self.technique:
            lines.append(f"Technique: {self.technique}")
        for i in self.injections:
            lines.append(f"Injection: {i}")
        for d in self.databases:
            lines.append(f"Database: {d}")
        for p in self.payloads:
            lines.append(f"Payload: {p}")
        for d in self.dumps:
            lines.append(f"Dump: {d}")
        return lines


def parse_log(text: str) -> Summary:
    s = Summary()
    for m in _DBMS_RE.finditer(text):
        s.dbms = m.group("dbms")
        break
    # 注入点：sqlmap 形如 "... parameter 'id' is dynamic ... is injectable"
    for m in re.finditer(
        r"(?i)parameter[^\n]*'(?P<p>[^']+)'[^\n]*injectable", text
    ):
        s.injections.append(m.group("p"))
    # technique：匹配 "technique (boolean-based blind)" / "technique (E, O, Q, T)" 等
    m = re.search(r"(?i)technique\s+\((?P<tech>[^)]*)\)", text)
    if m:
        s.technique = m.group("tech").strip()
    # 可用数据库：匹配 "available databases [X]: ..." 之后的若干 'name' 行
    dm = re.search(r"(?i)available databases? \[\d+\]:", text)
    if dm:
        tail = text[dm.end():]
        s.databases = re.findall(r"(?im)^\s+'(?P<db>[^']+)'\s*$", tail)[:20]
    # payload
    s.payloads = [m.group("payload").strip() for m in _PAYLOAD_RE.finditer(text)][:5]
    # dump
    s.dumps = [m.group("what") for m in _DUMP_RE.finditer(text)][:10]
    return s


def dump_path_for(target: str) -> config.Path | None:
    """推测 sqlmap 输出日志目录（若目标可稳定映射则返回，否则 None）。"""
    if not target:
        return None
    base = config.OUTPUT_DIR
    if not base.is_dir():
        return None
    # sqlmap 以目标 host/path 建子目录，这里仅返回候选根，交由调用方 glob。
    return base


def find_latest_log(target: str) -> config.Path | None:
    root = dump_path_for(target)
    if root is None:
        return None
    logs = list(root.glob("**/log"))
    return max(logs, key=lambda p: p.stat().st_mtime) if logs else None
