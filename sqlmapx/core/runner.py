"""子进程运行引擎。

把选项字典组装成 sqlmap 命令行，用子进程流式驱动，支持实时输出回调、
取消（Windows 下回收进程树）与退出码。sqlmap 本体零修改。

安全说明：所有外部命令均以参数列表交给 subprocess（shell=False），
从不拼接 shell 字符串，用户输入不会进入 shell，无命令注入面。
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Callable

from . import config
from .catalog import Catalog

# 进程树终止命令。以参数列表形式传入 subprocess（shell=False），按 PID 递归终止。
_KILL_TREE_CMD = ["taskkill", "/T", "/F", "/PID"]


def _is_windows() -> bool:
    return os.name == "nt"


def _kill_process_tree(pid: int) -> None:
    """Windows 下按 PID 递归终止进程树（参数列表，无 shell 拼接）。"""
    subprocess.run(_KILL_TREE_CMD + [str(pid)], shell=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   stdin=subprocess.DEVNULL)


def build_argv(options: dict[str, object], catalog: Catalog | None = None) -> list[str]:
    """把选项字典转成 sqlmap 命令行参数。

    - 键已是选项名（如 ``-u``/``-D``/``-T``/``-v``/``--dbms``）：原样作为选项名透传。
    - 布尔开关（flag）：值为真则仅传选项名；值为假/空则跳过。
    - 值选项：传 选项名 值（None/空字符串跳过）。
    - 列表值（逗号分隔）原样透传，交由 sqlmap 解析。
    """
    cat = catalog or Catalog(version="")
    by_name = {o.name: o for o in cat.options}
    argv: list[str] = []
    for k, v in options.items():
        # 键原样作为选项名（短形如 -D/-T/-v 与长形如 --dbms 都直接透传，
        # 不因目录缺失而被强行加 "--" 前缀，从而保留 sqlmap 原始选项名）。
        name = str(k)
        opt = by_name.get(name)
        if isinstance(v, (list, tuple)):
            v = ",".join(str(x) for x in v)
        if opt is not None and opt.is_flag:
            if str(v) not in ("", "0", "False", "false"):
                argv.append(name)
        else:
            if v is None or str(v) == "":
                continue
            argv.extend([name, str(v)])
    return argv


@dataclass
class RunResult:
    exit_code: int | None
    argv: list[str]
    output: str = ""
    started: float = 0.0
    stopped: float = 0.0


class Runner:
    """封装一次 sqlmap 子进程执行。输出在独立线程内消费。"""

    def __init__(
        self,
        options: dict[str, object],
        catalog: Catalog | None = None,
        on_line: Callable[[str], None] | None = None,
        on_done: Callable[[RunResult], None] | None = None,
        extra_args: list[str] | None = None,
    ):
        config.ensure_dirs()
        config.check_sqlmap()
        self.options = options
        self.catalog = catalog
        self.on_line = on_line
        self.on_done = on_done
        self.extra_args = extra_args or []
        self.argv = build_argv(options, catalog) + self.extra_args
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._result = RunResult(exit_code=None, argv=self.argv)
        self._chunks: list[str] = []

    def start(self) -> None:
        self._result.started = time.time()
        kwargs = dict(
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if _is_windows():
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            kwargs["start_new_session"] = True
        self._proc = subprocess.Popen(
            [config.SQLMAP_PYTHON, str(config.SQLMAP_PY), *self.argv],
            stdin=subprocess.DEVNULL,
            cwd=str(config.SQLMAP_DIR),
            **kwargs,
        )
        self._thread = threading.Thread(target=self._consume, daemon=True)
        self._thread.start()

    def _consume(self) -> None:
        assert self._proc is not None and self._proc.stdout is not None
        for line in iter(self._proc.stdout.readline, ""):
            if line == "":
                break
            self._chunks.append(line)
            if self.on_line:
                with contextlib.suppress(Exception):
                    self.on_line(line)
        self._proc.wait()
        self._result.stopped = time.time()
        self._result.exit_code = self._proc.returncode
        self._result.output = "".join(self._chunks)
        if self.on_done:
            with contextlib.suppress(Exception):
                self.on_done(self._result)

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self) -> None:
        """取消：尽力杀掉整个进程树。"""
        if self._proc is None or self._proc.poll() is not None:
            return
        pid = self._proc.pid
        try:
            if _is_windows():
                _kill_process_tree(pid)
            else:
                os.killpg(os.getpgid(pid), 9)
        except Exception:
            with contextlib.suppress(Exception):
                self._proc.kill()

    def wait(self, timeout: float | None = None) -> RunResult:
        if self._thread:
            self._thread.join(timeout)
        if self._proc:
            with contextlib.suppress(subprocess.TimeoutExpired):
                self._proc.wait(timeout=0)
        return self._result


def quick_run(argv: list[str]) -> subprocess.CompletedProcess:
    """同步阻塞执行（CLI 透传模式），stdio 直通父进程。

    安全：argv 为参数列表，shell=False，用户输入不进入 shell。
    """
    config.check_sqlmap()
    cmd = [config.SQLMAP_PYTHON, str(config.SQLMAP_PY), *argv]
    return subprocess.run(cmd, shell=False, stdin=None,
                          stdout=None, stderr=None,
                          cwd=str(config.SQLMAP_DIR))
