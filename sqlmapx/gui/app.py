"""GUI 模式：tkinter 极简主屏 + 可展开全选项。

主屏：目标输入 + 一键任务按钮 + 常用参数快捷 + 运行控制 + 流式日志。
"专家"按钮展开全选项表单（16 分组、222 项，布尔=复选框、值=复选框+输入）。
sqlmap 经子进程驱动，本体零修改；输出经 queue + after 轮询写回主线程。
"""
from __future__ import annotations

import queue
import sys
import tkinter as tk
from tkinter import ttk

from ..core import config, presets, profiles
from ..core.catalog import Catalog
from ..core.catalog import load as load_catalog
from ..core.output import parse_log
from ..core.presets import Preset
from ..core.runner import Runner, RunResult, build_argv


def _build_catalog() -> Catalog:
    return load_catalog()


def main() -> int:
    config.check_sqlmap()
    catalog = _build_catalog()
    by_group = catalog.by_group()
    flag_names = {o.name for o in catalog.options if o.is_flag}
    out_q: queue.Queue = queue.Queue()

    class App:
        def __init__(self, root: tk.Tk):
            self.root = root
            self.catalog = catalog
            self.runner: Runner | None = None
            self.target_var = tk.StringVar()
            self.selected_preset: Preset | None = None
            # 专家面板控件
            self.exp_checks: dict[str, tk.BooleanVar] = {}
            self.exp_entries: dict[str, tk.StringVar] = {}
            # 常用参数控件
            self.q_flags: dict[str, tk.BooleanVar] = {}
            self.q_entries: dict[str, tk.StringVar] = {}
            self._build()
            self.root.after(100, self._poll_log)

        # ---- UI ---------------------------------------------------------
        def _build(self):
            self.root.title(f"sqlmap-x · GUI 极简   (sqlmap {self.catalog.version})")
            self.root.geometry("860x640")

            # 顶部：目标
            top = ttk.Frame(self.root)
            top.pack(fill="x", padx=8, pady=6)
            ttk.Label(top, text="目标 URL：", width=10, anchor="w").pack(side="left")
            ttk.Entry(top, textvariable=self.target_var).pack(
                side="left", fill="x", expand=True)

            # 一键任务
            tb = ttk.LabelFrame(self.root, text="  一键任务  ")
            tb.pack(fill="x", padx=8, pady=4)
            for i, p in enumerate(presets.PRESETS):
                mark = "·(高级)" if p.category == "adv" else ""
                b = ttk.Button(tb, text=f"{p.title}{mark}",
                               command=lambda p=p: self._pick_preset(p))
                b.grid(row=i // 5, column=i % 5, padx=4, pady=4, sticky="ew")
                b.bind("<Enter>", lambda e, b=b, p=p: b.configure(state="!disabled"))
            for c in range(5):
                tb.columnconfigure(c, weight=1)

            # 常用参数快捷
            qb = ttk.LabelFrame(self.root, text="  常用参数  ")
            qb.pack(fill="x", padx=8, pady=4)
            for i, q in enumerate(presets.QUICK_PARAMS):
                row = i // 3
                col = i % 3
                cell = ttk.Frame(qb)
                cell.grid(row=row, column=col, padx=4, pady=2, sticky="ew")
                if q["opt"] in flag_names:
                    var = tk.BooleanVar()
                    self.q_flags[q["opt"]] = var
                    ttk.Checkbutton(cell, text=q["label"], variable=var).pack(side="left")
                else:
                    var = tk.StringVar()
                    if q.get("value"):
                        var.set(q["value"])
                    self.q_entries[q["opt"]] = var
                    ttk.Entry(cell, textvariable=var).pack(
                        side="left", fill="x", expand=True)
                    ttk.Label(cell, text=q["label"][:8]).pack(side="left", padx=(4, 0))
                for c in range(3):
                    qb.columnconfigure(c, weight=1)

            # 运行控制
            bar = ttk.Frame(self.root)
            bar.pack(fill="x", padx=8, pady=4)
            self.btn_run = ttk.Button(bar, text="▶ 运行", command=self.on_run)
            self.btn_stop = ttk.Button(bar, text="■ 停止", command=self.on_stop, state="disabled")
            self.btn_expert = ttk.Button(bar, text="专家选项 ▸", command=self.toggle_expert)
            self.btn_save = ttk.Button(bar, text="保存", command=self.on_save)
            self.btn_load = ttk.Button(bar, text="加载", command=self.on_load)
            self.btn_clear = ttk.Button(bar, text="清空日志", command=self.on_clear)
            for b in (self.btn_run, self.btn_stop, self.btn_expert,
                      self.btn_save, self.btn_load, self.btn_clear):
                b.pack(side="left", padx=3)
            self.profile_combo = ttk.Combobox(bar, width=16, state="readonly",
                                               values=profiles.list_profiles() or ["(无)"])
            self.profile_combo.pack(side="left", padx=6)
            self.profile_combo.bind("<<ComboboxSelected>>",
                                    lambda _e: self.on_load_from(self.profile_combo.get()))

            # 专家面板（默认隐藏）
            self.expert = ttk.Notebook(self.root)
            for group, opts in by_group.items():
                frame = ttk.Frame(self.expert)
                self.expert.add(frame, text=group)
                scroll = ttk.Scrollbar(frame)
                canvas = tk.Canvas(frame, height=300, yscrollcommand=scroll.set,
                                   highlightthickness=0, bd=0)
                inner = ttk.Frame(canvas)
                scroll.config(command=canvas.yview)
                cw = canvas.create_window((0, 0), window=inner, anchor="nw")

                def _resize(e, c=canvas, w=cw):
                    c.itemconfigure(w, width=e.width)

                inner.bind("<Configure>", _resize)
                canvas.configure(scrollregion=inner.bbox())
                scroll.pack(side="right", fill="y")
                canvas.pack(side="left", fill="both", expand=True)
                for r, o in enumerate(opts):
                    var = tk.BooleanVar()
                    self.exp_checks[o.name] = var
                    ttk.Checkbutton(inner, text=o.name, variable=var).grid(
                        row=r, column=0, sticky="w", padx=6, pady=2)
                    if not o.is_flag:
                        sv = tk.StringVar()
                        self.exp_entries[o.name] = sv
                        ttk.Entry(inner, textvariable=sv, width=32).grid(
                            row=r, column=1, sticky="w", padx=(4, 6))

            # 日志
            self.log = tk.Text(self.root, height=12, state="disabled", wrap="word")
            self.log.pack(fill="both", expand=True, padx=8, pady=4)
            for tag, fg in (("ok", "#0a7d33"), ("err", "#c00000"), ("info", "#0b5394")):
                self.log.tag_config(tag, foreground=fg)

        # ---- 收集 ---------------------------------------------------------
        def _collect(self) -> dict[str, object]:
            opts: dict[str, object] = {}
            tg = self.target_var.get().strip()
            if tg:
                opts["-u"] = tg
            # 专家面板
            for name, var in self.exp_checks.items():
                if not var.get():
                    continue
                if name in flag_names:
                    opts[name] = "1"
                else:
                    sv = self.exp_entries[name].get().strip()
                    opts[name] = sv if sv else name
            # 常用参数
            for opt, var in self.q_flags.items():
                if var.get():
                    opts[opt] = "1"
            for opt, var in self.q_entries.items():
                v = var.get().strip()
                if v:
                    opts[opt] = v
            # 预设 + 占位补全
            if self.selected_preset:
                opts = presets.merge(self.selected_preset, opts, {})
                for need in self.selected_preset.needs:
                    if str(opts.get(need) or "") == "":
                        sv = self.exp_entries.get(need)
                        opts[need] = sv.get().strip() if sv else ""
            return opts

        # ---- 日志 ---------------------------------------------------------
        def _append(self, text: str, tag: str = ""):
            self.log.configure(state="normal")
            self.log.insert("end", text + "\n", tag)
            self.log.see("end")
            self.log.configure(state="disabled")

        def _poll_log(self):
            try:
                while True:
                    kind, payload = out_q.get_nowait()
                    if kind == "line":
                        self._append(payload)
                    elif kind in ("ok", "err", "info"):
                        self._append(payload, kind)
                    elif kind == "done":
                        self._on_done(payload)
            except queue.Empty:
                pass
            self.root.after(100, self._poll_log)

        def _on_done(self, res: RunResult):
            self.btn_stop.configure(state="disabled")
            s = parse_log(res.output)
            self._append(f"完成（exit {res.exit_code}）" if res.exit_code == 0
                        else f"结束（exit {res.exit_code}）",
                        "ok" if res.exit_code == 0 else "err")
            lines = s.to_lines()
            if lines:
                self._append("摘要：" + "  ·  ".join(lines), "info")

        # ---- 运行 ---------------------------------------------------------
        def on_run(self):
            if self.runner and self.runner.is_running():
                return
            opts = self._collect()
            if self.selected_preset and not all(
                    str(opts.get(k) or "") for k in self.selected_preset.needs):
                self._append(f"预设 [{self.selected_preset.title}] 需补全 {self.selected_preset.needs}（专家面板填值）", "err")
                return
            if not opts:
                self._append("缺少目标：请填目标 URL。", "err")
                return
            self._append("▶ 运行：" + " ".join(build_argv(opts, self.catalog)), "info")
            self.btn_stop.configure(state="normal")

            def on_line(line: str):
                out_q.put(("line", line.rstrip("\n")))

            def on_done(res: RunResult):
                out_q.put(("done", res))

            self.runner = Runner(opts, self.catalog, on_line=on_line,
                                  on_done=on_done)
            self.runner.start()

        def on_stop(self):
            if self.runner:
                self.runner.stop()
                self._append("请求停止…", "info")

        def on_clear(self):
            self.log.configure(state="normal")
            self.log.delete("1.0", "end")
            self.log.configure(state="disabled")

        def toggle_expert(self):
            if self.expert.winfo_manager():
                self.expert.forget()
            else:
                self.expert.pack(fill="both", expand=True, padx=8, pady=4,
                                 before=self.log)

        def _pick_preset(self, p: Preset):
            self.selected_preset = p
            self._append(f"已选任务：[{p.title}] {p.desc}" +
                        (f"（需填 {p.needs}）" if p.needs else ""), "info")

        # ---- 配置档 -------------------------------------------------------
        def on_save(self):
            p = profiles.Profile(name=f"profile{len(profiles.list_profiles()) + 1}",
                                 target=self.target_var.get().strip(),
                                 options=self._collect())
            profiles.save(p)
            self.profile_combo.configure(values=profiles.list_profiles() or ["(无)"])
            self.profile_combo.set(p.name)
            self._append(f"已保存配置档：{p.name}", "ok")

        def on_load(self):
            self.on_load_from(self.profile_combo.get())

        def on_load_from(self, name: str):
            if not name or name == "(无)":
                self._append("无可加载配置档。", "info")
                return
            p = profiles.load(name)
            self.target_var.set(p.target)
            self.selected_preset = None
            for n, v in p.options.items():
                if n == "-u":
                    continue
                var = self.exp_checks.get(n)
                if var is None:
                    continue
                if n in flag_names:
                    var.set(bool(v) and str(v) not in ("", "0", "False"))
                else:
                    var.set(True)
                    self.exp_entries[n].set(str(v) if str(v) != n else "")
            self._append(f"已加载配置档：{p.name}（{len(p.options)} 项）", "info")

    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
