@echo off
setlocal
rem 一键安装：下载 sqlmap（如尚未）+ 安装本项目 + TUI 依赖
echo == sqlmap-x 安装 ==

if not exist vendor\sqlmap\sqlmap.py (
  echo [1/2] 下载 sqlmap ...
  git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git vendor\sqlmap
) else (
  echo [1/2] sqlmap 已存在，跳过下载。
)

echo [2/2] 安装依赖与可执行入口 ...
python -m pip install -e .
echo.
echo 完成。可用命令：
echo   sqlmap-cli  ^<sqlmap 参数^>   :: 透传给原生 sqlmap
echo   sqlmap-tui                    :: Textual 终端界面
echo   sqlmap-gui                    :: tkinter 桌面界面
echo   python -m sqlmapx --mode tui  :: 同上，模块方式
endlocal
