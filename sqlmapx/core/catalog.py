"""选项目录：解析 ``sqlmap -hh`` 为结构化数据。

目录按 sqlmap 自带分组组织，每项含规范名(--long)、短名、metavar、是否布尔开关、
帮助文本与默认值线索。缓存到 ``profiles/catalog.json``，并以 sqlmap 版本号作为
失效键——升级 vendored sqlmap 后自动重建。
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, asdict, field
from typing import List, Optional

from . import config

# 匹配分组头：2 个前导空格、大写开头的标题、以冒号结尾。
_SECTION_RE = re.compile(r"^  ([A-Z][A-Za-z /()\-]+):\s*$")
# 规范段由逗号分隔的选项 token 组成（每个 token 以 '-' 开头）。
# 描述段是去掉 token 后的剩余文本。这里不做"按空格切分"，而是按
# "-token" 序列切分，避免 sqlmap 帮助中分隔空格数不固定带来的误判。
def _split_spec_and_desc(body: str) -> tuple:
    """从选项行正文切分出 (规范段, 描述段)。

    规范段 = 行首由逗号分隔的选项 token 序列；每个 token 形如
      "-s"、"-s META"、"--long"、"--long=METAVAR"。
    描述段 = 行首连续选项 token 结束后剩余文本（首个不以 '-' 开头的
    token 起，且不是前一个短形值选项的 metavar）。

    状态机：遇到 '-' token → 并入规范段；该 token 是短形（-X）且其后
    紧跟纯大写 metavar（URL、DB、VERBOSE）→ 一并入规范段；遇 "," 并入
    并继续；遇首个非 '-' token（且不是刚并入的短形 metavar）→ 进入描述。
    """
    tokens: list = []
    # 先按空格切分，再把每个 token 末尾粘连的逗号剥离为独立 token
    # （sqlmap 帮助形如 "-u URL, --url=URL"，"URL," 需还原为 "URL" + ","）。
    for raw in body.split():
        if raw.endswith(",") and len(raw) > 1:
            tokens.append(raw[:-1])
            tokens.append(",")
        else:
            tokens.append(raw)
    spec_parts: list = []
    i = 0
    n = len(tokens)
    last_opt_short = False  # 上一个并入规范的 token 是否短形值选项
    while i < n:
        t = tokens[i]
        if t == ",":
            spec_parts.append(",")
            i += 1
            last_opt_short = False
            continue
        if t.startswith("-"):
            spec_parts.append(t)
            is_short = t.startswith("-") and not t.startswith("--")
            i += 1
            # 短形值选项 "-X META"：后跟纯大写 metavar 并入规范段
            if is_short and i < n and re.match(r"^[A-Z][A-Z0-9.]*$", tokens[i]) \
                    and tokens[i] not in (",",):
                spec_parts.append(tokens[i])
                i += 1
                last_opt_short = True
            else:
                last_opt_short = False
            continue
        # 非 '-' token
        if last_opt_short and re.match(r"^[A-Z][A-Z0-9.]*$", t):
            # 可能是短形值选项的第二个 metavar（罕见，跳过）
            spec_parts.append(t)
            i += 1
            continue
        break  # 描述段开始
    spec = " ".join(spec_parts)
    desc = " ".join(tokens[i:]).strip()
    return spec, desc
# 单个 token：--long、--long=meta、-s、-s meta 四种。
# dash 部分取到第一个分隔符（= 或 空白或行尾），meta 为可选。
_TOKEN_RE = re.compile(
    r"^(?P<dash>-{1,2}[A-Za-z][A-Za-z0-9.]*)(?:[ =](?P<meta>\S+))?$"
)


@dataclass
class Option:
    name: str            # 规范名，优先 --long；仅有短名时用短名
    long: Optional[str]  # --xxx
    short: Optional[str]  # -x
    metavar: Optional[str]
    is_flag: bool        # True=布尔开关（无值），False=需提供值
    group: str
    help: str
    # 排序与原始展示
    spec: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Catalog:
    version: str
    groups: List[str] = field(default_factory=list)
    options: List[Option] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "groups": self.groups,
            "options": [o.to_dict() for o in self.options],
        }

    def by_group(self) -> dict:
        out: dict = {}
        for o in self.options:
            out.setdefault(o.group, []).append(o)
        return out


def _run_hh() -> str:
    """运行 ``sqlmap -hh`` 拿到帮助文本。"""
    config.check_sqlmap()
    proc = subprocess.run(
        [config.SQLMAP_PYTHON, str(config.SQLMAP_PY), "-hh"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    return proc.stdout or ""


def _run_version() -> str:
    """运行 ``sqlmap --version`` 拿到版本字符串作为缓存失效键。"""
    config.check_sqlmap()
    try:
        proc = subprocess.run(
            [config.SQLMAP_PYTHON, str(config.SQLMAP_PY), "--version"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if line and not line.startswith("Press Enter") and "ERROR" not in line:
                return line
    except Exception:
        pass
    return "unknown"


def _parse_option_spec(spec: str) -> tuple:
    """解析规范段，返回 (long, short, metavar, is_flag)。

    逐 token 处理（逗号分隔）。每个 token 形如：
      -h            短形 flag
      -D DB         短形值选项（metavar 由 split 时并入 spec，形如 "-D DB"）
      --url=URL     长形值选项（metavar 在 '=' 后）
      --drop-set-cookie  长形 flag
    """
    long_name = None
    short_name = None
    metavar = None
    is_flag = True
    # spec 由 _split_spec_and_desc 产出：短形值选项的 metavar 已作为
    # 空格分隔 token 并入，故按空格切分还原 "短形 值"。
    tokens = [t for t in spec.split() if t]
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t == ",":
            i += 1
            continue
        if not t.startswith("-"):
            # 这是前一个短形值选项的 metavar（如 "-D" 后的 "DB"）
            metavar = metavar or t
            is_flag = False
            i += 1
            continue
        # 去掉逗号粘连（split 后不会发生，但保险）
        t = t.rstrip(",")
        if "=" in t:
            nm, mv = t.split("=", 1)
            metavar = mv or metavar
            is_flag = False
            if nm.startswith("--"):
                long_name = long_name or nm
            else:
                short_name = short_name or nm
        else:
            if t.startswith("--"):
                long_name = long_name or t
            else:
                short_name = short_name or t
        i += 1
    return long_name, short_name, metavar, is_flag


def parse_hh(text: str, version: str) -> Catalog:
    """把 ``sqlmap -hh`` 文本解析成 Catalog。

    选项行：行首有缩进且首个非空字符是 ``-``（兼容 2/4 空格缩进，覆盖
    ``-v``/``-D``/``-T`` 等短形独占选项与 ``--os-shell`` 等长形选项）。
    续行：首字符非 ``-`` 且比选项行更深的缩进（对齐到描述列）。
    """
    cat = Catalog(version=version)
    current_group = "General"
    current_opt: Optional[Option] = None

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        m = _SECTION_RE.match(line)
        if m:
            current_group = m.group(1).strip()
            if current_group not in cat.groups:
                cat.groups.append(current_group)
            current_opt = None
            continue
        if stripped.startswith("-") and indent > 0:
            body = stripped
            spec, desc = _split_spec_and_desc(body)
            long, short, metavar, is_flag = _parse_option_spec(spec)
            name = long or short
            if not name:
                continue
            opt = Option(
                name=name, long=long, short=short, metavar=metavar,
                is_flag=is_flag, group=current_group, help=desc, spec=spec,
            )
            cat.options.append(opt)
            current_opt = opt
        elif current_opt is not None and not stripped.startswith("-"):
            # 续行：归入上一个选项的描述。
            current_opt.help = (current_opt.help + " " + stripped).strip()
    return cat


def build(version: Optional[str] = None) -> Catalog:
    """实时构建目录（不读缓存）。"""
    if version is None:
        version = _run_version()
    text = _run_hh()
    return parse_hh(text, version)


def load(force: bool = False) -> Catalog:
    """加载目录；缓存缺失或版本不匹配时重建。

    ``sqlmap`` 也内置 ``--gui``/``--tui``/``--wizard``，本目录仍把它们当作普通
    选项收录，启动器自身不依赖这几个开关。
    """
    config.ensure_dirs()
    cached = None
    if not force and config.CATALOG_CACHE.is_file():
        try:
            cached = json.loads(config.CATALOG_CACHE.read_text(encoding="utf-8"))
        except Exception:
            cached = None
    live_version = _run_version()
    if cached and cached.get("version") == live_version:
        return _from_dict(cached)
    cat = build(live_version)
    config.CATALOG_CACHE.parent.mkdir(parents=True, exist_ok=True)
    config.CATALOG_CACHE.write_text(
        json.dumps(cat.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return cat


def _from_dict(data: dict) -> Catalog:
    cat = Catalog(version=data.get("version", "unknown"), groups=list(data.get("groups", [])))
    for o in data.get("options", []):
        cat.options.append(Option(**o))
    return cat
