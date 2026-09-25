"""TUI 模式：极简主屏 + 可展开全选项的 Textual 终端界面。

主屏布局（自上而下）：
  - 目标输入（-u）
  - 一键任务按钮组（探测/列库/列表/读数据/OS壳/SQL壳/枚举用户/哈希…）
  - 常用参数快捷（batch/level/technique/tamper/proxy/threads…）
  - 运行 / 停止 / 保存 / 加载
  - 流式日志
按 [m] 切换"全选项专家面板"（16 分组、222 项，布尔=Switch、值=Input），
满足"极简 + 全选项可见"。
sqlmap 经子进程驱动，本体零修改。
"""
from __future__ import annotations

import sys

from ..core import config, presets, profiles
from ..core.catalog import Catalog
from ..core.catalog import load as load_catalog
from ..core.output import parse_log
from ..core.presets import Preset
from ..core.runner import Runner, RunResult, build_argv


def _build_catalog() -> Catalog:
    try:
        return load_catalog()
    except Exception as e:
        raise SystemExit(f"无法构建选项目录：{e}") from e


def main() -> int:
    config.check_sqlmap()
    catalog = _build_catalog()
    by_group = catalog.by_group()
    flag_names = {o.name for o in catalog.options if o.is_flag}

    try:
        from textual.app import App, ComposeResult
        from textual.binding import Binding
        from textual.containers import Horizontal, Vertical
        from textual.widgets import (
            Button,
            Footer,
            Header,
            Input,
            RichLog,
            Select,
            Switch,
            TabbedContent,
            TabPane,
        )
    except ImportError:
        print("未安装 Textual。请 `pip install textual`，或改用 CLI 模式。", file=sys.stderr)
        return 127

    state = {"runner": None}

    def _task_buttons() -> list[tuple]:
        # (preset_key, label) 按类别分组
        labels = {
            "detect": "探测注入", "dbs": "列数据库", "tables": "列表",
            "columns": "列列", "dump": "读数据", "os-shell": "OS壳",
            "sql-shell": "SQL壳", "current-user": "当前用户", "users": "枚举用户",
            "passwords": "读哈希", "privileges": "读权限", "file-read": "读文件",
            "os-cmd": "执行命令", "xxe-oob": "OOB-XXE", "fingerprint": "指纹/WAF",
        }
        return [(p.key, labels.get(p.key, p.title), p.category) for p in presets.PRESETS]

    class SqlmapTUI(App):
        TITLE = "sqlmap-x · TUI（极简）"
        SUB_TITLE = f"sqlmap {catalog.version} · [m]专家面板 [r]运行 [s]停止"
        CSS = """
        #main { layout: vertical; height: 1fr; }
        .task-btn { width: 1fr; }
        #log { height: 12; }
        #panel { display: none; }
        #panel.show { display: block; }
        """
        BINDINGS = [
            Binding("m", "toggle_panel", "专家面板", show=True),
            Binding("r", "run", "运行", show=True),
            Binding("s", "stop", "停止", show=True),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.catalog = catalog
            self._expert_switches: dict[str, Switch] = {}
            self._expert_inputs: dict[str, Input] = {}
            self._selected_preset: Preset | None = None
            self._expert_visible = False

        # ---- 极简主屏 -----------------------------------------------------
        def compose(self) -> ComposeResult:
            yield Header()
            with Vertical(id="main"):
                yield Input(placeholder="目标 URL（-u）… 例如 http://t.example/vuln.php?id=1",
                           id="target")
                # 一键任务按钮
                with Horizontal(id="tasks"):
                    for key, label, cat in _task_buttons():
                        y = "*" if cat == "adv" else ""
                        yield Button(label + y, id=f"t_{key}", classes="task-btn",
                                     variant="primary" if cat == "core" else "default")
                # 常用参数快捷
                with Horizontal(id="quick"):
                    for q in presets.QUICK_PARAMS:
                        if q["opt"] in flag_names:
                            sw = Switch(label=q["label"], id=f"q_{q['opt']}")
                        else:
                            sw = Input(placeholder=q["label"] + ("  " + q.get("value","")),
                                       id=f"q_{q['opt']}")
                        yield sw
                # 运行控制
                with Horizontal(id="runbar"):
                    yield Button("▶ 运行", id="run", variant="success")
                    yield Button("■ 停止", id="stop", variant="error")
                    yield Button("保存", id="save")
                    sel = Select(options=profiles.list_profiles() or ["(无)"], value="", id="profile")
                    yield sel
                    yield Button("加载", id="load")
                # 流式日志
                yield RichLog(id="log", wrap=True, markup=True, highlight=False)
                # 全选项专家面板（默认隐藏，[m] 切换）
                with TabbedContent(id="panel"):
                    for group, opts in by_group.items():
                        with TabPane(group, id=f"e_{group}"):
                            for o in opts:
                                with Horizontal(classes="erow"):
                                    sw = Switch(label=o.name, id=f"sw_{o.name}")
                                    yield sw
                                    self._expert_switches[o.name] = sw
                                    if not o.is_flag:
                                        inp = Input(placeholder=o.metavar or "值", id=f"ei_{o.name}")
                                        yield inp
                                        self._expert_inputs[o.name] = inp
            yield Footer()

        # ---- 收集 ---------------------------------------------------------
        def _quick_extra(self) -> dict[str, object]:
            extra: dict[str, object] = {}
            for q in presets.QUICK_PARAMS:
                wid = f"q_{q['opt']}"
                w = self.query_one(f"#{wid}", (Switch, Input))
                if isinstance(w, Switch):
                    if w.value:
                        extra[q["opt"]] = "1"
                else:
                    v = w.value.strip()
                    if v:
                        extra[q["opt"]] = v
            return extra

        def _expert_opts(self) -> dict[str, object]:
            out: dict[str, object] = {}
            for name, sw in self._expert_switches.items():
                if not sw.value:
                    continue
                if name in flag_names:
                    out[name] = "1"
                else:
                    inp = self._expert_inputs[name]
                    out[name] = inp.value.strip() or name
            return out

        def _collect(self) -> dict[str, object]:
            opts: dict[str, object] = {}
            tg = self.query_one("#target", Input).value.strip()
            if tg:
                opts["-u"] = tg
            # 专家面板覆盖层
            opts.update(self._expert_opts())
            # 常用参数
            opts.update(self._quick_extra())
            # 选中任务预设 + 占位补全
            if self._selected_preset:
                opts = presets.merge(self._selected_preset, opts, {})
                # 占位需补全（-D/-T/--file-read/…）：取专家面板对应输入值
                for need in self._selected_preset.needs:
                    if need in opts and str(opts.get(need) or "") == "":
                        inp = self._expert_inputs.get(need)
                        opts[need] = inp.value.strip() if inp else ""
            return opts

        # ---- 运行 ---------------------------------------------------------
        def _log(self, widget, msg, tag=None):
            if tag:
                widget.print(f"[{tag}]{msg}[/]")
            else:
                widget.write(msg)

        def action_run(self):
            self._start()

        def _start(self):
            if state["runner"] and state["runner"].is_running():
                return
            opts = self._collect()
            if self._selected_preset and not all(v for k, v in opts.items()
                                                  if k in self._selected_preset.needs):
                self._log(self.query_one("#log", RichLog),
                          f"预设 [bold]{self._selected_preset.title}[/] 需补全：{self._selected_preset.needs}（专家面板填值或取消任务）",
                          "yellow")
                return
            preview = " ".join(build_argv(opts, self.catalog))
            self._log(self.query_one("#log", RichLog), f"[bold green]▶ {preview}[/]")
            state["runner"] = Runner(opts, self.catalog,
                                     on_line=lambda line: self.call_from_thread(
                                         self._on_line, line.rstrip("\n")),
                                     on_done=lambda r: self.call_from_thread(self._on_done, r))
            state["runner"].start()

        def _on_line(self, line: str):
            if line:
                self.query_one("#log", RichLog).write(line)

        def _on_done(self, res: RunResult):
            lg = self.query_one("#log", RichLog)
            s = parse_log(res.output)
            lg.print(f"[bold]结束（exit {res.exit_code}）[/] " +
                     ("[green]完成[/]" if res.exit_code == 0 else "[red]非零退出[/]"))
            lines = s.to_lines()
            if lines:
                lg.print("[bold]摘要：[/] " + "  ·  ".join(lines))

        # ---- 事件 ---------------------------------------------------------
        def on_button_pressed(self, e) -> None:
            if e.button.id == "run":
                self._start()
            elif e.button.id == "stop":
                if state["runner"]:
                    state["runner"].stop()
                    self._log(self.query_one("#log", RichLog), "[yellow]请求停止…[/]")
            elif e.button.id == "save":
                self._save()
            elif e.button.id == "load":
                self._load()
            elif e.button.id.startswith("t_"):
                self._pick_preset(e.button.id[2:])

        def _pick_preset(self, key: str):
            p = presets.PRESETS_BY_KEY.get(key)
            if not p:
                return
            self._selected_preset = p
            self._log(self.query_one("#log", RichLog),
                      f"已选任务：[bold]{p.title}[/] — {p.desc}" +
                      (f"（需填 {p.needs}）" if p.needs else ""), "info")

        def action_toggle_panel(self):
            self._expert_visible = not self._expert_visible
            self.query_one("#panel").classes.toggle("show", self._expert_visible)
            state_text = "展开" if self._expert_visible else "收起"
            self._log(self.query_one("#log", RichLog), f"[dim]专家面板 {state_text}[/]")

        def _save(self):
            tg = self.query_one("#target", Input).value.strip()
            p = profiles.Profile(name=f"profile{len(profiles.list_profiles()) + 1}",
                                 target=tg, options=self._collect())
            profiles.save(p)
            sel = self.query_one("#profile", Select)
            sel.add_options([p.name])
            sel.value = p.name
            self._log(self.query_one("#log", RichLog), f"[green]已保存配置档 {p.name}[/]")

        def _load(self):
            sel = self.query_one("#profile", Select)
            name = sel.value or ""
            if not name or name == "(无)":
                self._log(self.query_one("#log", RichLog), "[dim]无配置档。[/]")
                return
            p = profiles.load(name)
            self.query_one("#target", Input).value = p.target
            for n, v in p.options.items():
                if n == "-u":
                    continue
                sw = self._expert_switches.get(n)
                if sw is None:
                    continue
                sw.value = (str(v) not in ("", "0", "False") and bool(v))
                if n not in flag_names and n in self._expert_inputs:
                    self._expert_inputs[n].value = str(v) if str(v) != n else ""
            self._log(self.query_one("#log", RichLog), f"[green]已加载 {p.name}（{len(p.options)} 项）[/]")

    SqlmapTUI().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
