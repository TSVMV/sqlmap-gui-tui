# sqlmap-x —— 三模式（GUI / TUI / CLI）sqlmap 启动器

在**不改动 sqlmap 本体**的前提下，为 sqlmap 提供三种操作界面：

| 模式 | 命令 | 说明 |
|---|---|---|
| CLI | `sqlmap-cli` | 原样透传给原生 sqlmap，行为与 `sqlmap …` 完全一致 |
| TUI | `sqlmap-tui` | Textual 终端界面：分组选项 + 流式日志 + 运行/停止/存档 |
| GUI | `sqlmap-gui` | tkinter 桌面界面：选项 Notebook + 流式日志 + 运行/停止/存档 |

> sqlmap 是开源渗透测试工具，本启动器仅为其编写界面层，**未增删任何检测/利用
> 能力**，仅面向**已授权**的安全测试与研究场景。请仅用于你拥有权限或已获授权
> 的目标。

## 设计

```
CLI ─┐
TUI ─┼─▶ core/  ─▶ 子进程驱动 vendor/sqlmap/sqlmap.py（零修改）
GUI ─┘        ├─ catalog   解析 `sqlmap -hh` → 选项目录（随 sqlmap 版本自动失效重建）
               ├─ runner    选项→argv、Popen 流式输出、取消杀进程树、退出码
               ├─ profiles  任务配置档 JSON（三模式共享/复用）
               └─ output    运行日志 → 结构化摘要（DBMS / 注入点 / technique / payload）
```

- **集成方式**：子进程 CLI 包装。`vendor/sqlmap/` 里的 sqlmap 原封不动，启动器只做
  命令行组装与输出流转发，因此功能与官方 CLI 100% 一致。
- **CLI 透传**：`sqlmap-cli -u … --dbs` 等价于 `sqlmap -u … --dbs`，退出码原样返回。
- **选项目录**：自动解析当前 vendored sqlmap 的 `-hh`，分组/类型/默认值/帮助随之同步；
  升级 sqlmap 后目录按版本号自动重建，无需手工维护。

## 安装

```bash
# 从 PyPI 安装（推荐；会自动拉取 sqlmap 本体）
pip install sqlmapx
```

或从源码安装（Windows 可直接跑 `install.bat`）：

```bash
git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git vendor/sqlmap
python -m pip install -e .      # 安装 textual 依赖与三个可执行入口
```

sqlmap 自动发现顺序：`环境变量 SQLMAP_HOME` → pip 安装的 `sqlmap` 包 → 包内 `vendor/sqlmap`。无网络时把 sqlmap 放到 `vendor/sqlmap/` 即可。

## 使用

```bash
sqlmap-cli -u "http://target/?id=1" --dbs        # 原生透传
sqlmap-tui                                        # 终端界面（极简主屏）
sqlmap-gui                                        # 桌面窗口（极简主屏）
python -m sqlmapx --mode tui                      # 模块方式，等价
```

### 极简操控（TUI / GUI）

主屏只放三样：**目标输入 → 一键任务 → 常用参数**，点一下 = 跑通一条典型路径：

- **一键任务**：探测注入 / 列数据库 / 列表 / 读数据 / 拿 OS 壳 / 拿 SQL 壳 /
  枚举用户 / 读哈希 / 读权限 / 读文件 / 执行命令 / OOB-XXE / 指纹·WAF 识别。
- **常用参数**：batch / verbosity / level / risk / technique / tamper / proxy /
  threads / delay / dbms / cookie / POST 数据，直接勾选或填值。
- **全选项**：GUI 点"专家选项"展开、TUI 按 `[m]` 展开 16 分组 240+ 项专家表单，
  满足高级需求。

预设只是 sqlmap 原生选项的组合，**不新增任何能力**；目标与库表等占位（`-D`/`-T`
等）由界面提示补全后随命令带出。任务配置可 Save/Load 复用（存于 `profiles/`）。

## 目录

```
vendor/sqlmap/     原版 sqlmap（勿改）
sqlmapx/           启动器源码（core / cli / tui / gui）
profiles/          任务配置档、扫描输出、选项目录缓存
install.bat        一键安装
requirements.txt   textual（GUI 用标准库 tkinter，无额外依赖）
```

## 升级 sqlmap

重新 `git pull`/重新 clone `vendor/sqlmap` 即可；选项目录会在下次启动按新版本自动重建。

## 授权与免责声明

本项目仅用于已授权目标的安全测试、教学与研究。使用者须自行确认对目标拥有合法
权限，遵守当地法律法规。项目对因不当使用造成的任何损失不负责。
