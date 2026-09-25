"""CLI 模式：原样透传给 sqlmap.py。

``sqlmap-cli <任意 sqlmap 参数>`` 与直接运行 ``sqlmap <同参数>`` 行为完全一致，
实现"功能不改动"。stdio 直通父进程，退出码原样返回。
"""
from __future__ import annotations

import sys

from ..core import runner


def main() -> int:
    args = sys.argv[1:]
    # 允许把 mode 选项写在后面，剥掉 --mode cli 之类（若有）。
    if "--mode" in args:
        i = args.index("--mode")
        del args[i:i + 2]

    try:
        proc = runner.quick_run(args)
    except FileNotFoundError as e:
        print(f"[sqlmap-cli] 错误：{e}", file=sys.stderr)
        return 127
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
