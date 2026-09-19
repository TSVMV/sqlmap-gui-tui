"""统一入口。

用法::

    python -m sqlmapx --mode cli  -u http://x --dbs   # 把 -u ... 透传给 sqlmap
    python -m sqlmapx --mode tui                            # 启动 Textual TUI
    python -m sqlmapx --mode gui                            # 启动 tkinter GUI

等价的可执行入口：``sqlmap-cli`` / ``sqlmap-tui`` / ``sqlmap-gui``。

注意：``--mode`` 之后的所有参数都原样透传给 sqlmap（不解析 sqlmap 自身的
``--version``、``-h`` 等），避免与 sqlmap 参数冲突。
"""
from __future__ import annotations

import sys


def _split_args(argv):
    """从 argv 中剥离 sqlmapx 自身的 --mode/--batch，其余原样透传。

    返回 (mode, batch, passthrough)。仅在最前面解析 sqlmapx 自身参数，
    遇到第一个其它选项即停止，保证 ``sqlmap -u ...`` 等参数不丢失。
    """
    mode = "cli"
    batch = False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--mode" and i + 1 < len(argv):
            mode = argv[i + 1]
            i += 2
            continue
        if a == "--batch":
            batch = True
            i += 1
            continue
        break
    return mode, batch, argv[i:]


def _cli(passthrough) -> int:
    """CLI 透传：委托给 runner.quick_run（子进程参数列表，shell=False）。"""
    from .core import runner, config
    config.check_sqlmap()
    proc = runner.quick_run(passthrough)
    return proc.returncode


def main() -> int:
    mode, _batch, passthrough = _split_args(sys.argv[1:])
    if mode == "tui":
        from .tui import app as tui
        return tui.main()
    if mode == "gui":
        from .gui import app as gui
        return gui.main()
    # 默认 cli
    return _cli(passthrough)


if __name__ == "__main__":
    sys.exit(main())
