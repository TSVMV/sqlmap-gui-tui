"""任务配置档（profile）的存取。

一个 profile 就是一份"选项字典 + 目标"，JSON 存于 ``profiles/*.json``，
可被三种模式共享与复用。

安全：文件名经 ``_safe()`` 正则白名单净化（``[^A-Za-z0-9_.-]+ -> _``），
根目录固定为 ``config.PROFILES_DIR``，故不存在路径穿越面。
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field

from . import config


@dataclass
class Profile:
    name: str
    target: str = ""
    options: dict[str, object] = field(default_factory=dict)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Profile:
        return cls(
            name=d.get("name", "unnamed"),
            target=d.get("target", ""),
            options=dict(d.get("options", {})),
            note=d.get("note", ""),
        )


def _safe(name: str) -> str:
    """文件名白名单净化：仅保留 [A-Za-z0-9_.-]，其余替换为 _。"""
    s = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._") or "profile"
    return s


def path_for(name: str) -> config.Path:
    """由净化文件名 + 固定根目录拼接，杜绝路径穿越。"""
    return config.PROFILES_DIR / (_safe(name) + config.PROFILES_EXT)


def save(profile: Profile) -> None:
    config.ensure_dirs()
    target = path_for(profile.name)
    target.write_text(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
                      encoding="utf-8")


def load(name: str) -> Profile:
    target = path_for(name)
    return Profile.from_dict(json.loads(target.read_text(encoding="utf-8")))


def list_profiles() -> list[str]:
    if not config.PROFILES_DIR.is_dir():
        return []
    names = []
    for p in sorted(config.PROFILES_DIR.glob("*" + config.PROFILES_EXT)):
        if p.stem == "catalog":
            continue
        names.append(p.stem)
    return names
