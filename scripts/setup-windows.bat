@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title iMirror Windows 一键环境安装
cd /d "%~dp0.."

echo ============================================
echo  iMirror Windows 环境一键安装
echo ============================================
echo.

rem ---- 1/5 uv ----
where uv >nul 2>nul
if errorlevel 1 (
    echo [1/5] 正在安装 uv ...
    powershell -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;!PATH!"
    where uv >nul 2>nul
    if errorlevel 1 (
        echo [错误] uv 安装失败, 请手动安装: https://docs.astral.sh/uv/
        goto :fail
    )
) else (
    echo [1/5] uv 已安装
)

rem ---- 2/5 venv ----
if not exist ".venv" (
    echo [2/5] 创建虚拟环境 .venv ...
    uv venv .venv
    if errorlevel 1 goto :fail
) else (
    echo [2/5] .venv 已存在, 跳过
)

rem ---- 3/5 依赖 ----
echo [3/5] 安装全部依赖 dev+windows+gui, 含 libusb 与投屏预览所需的解码库 ...
uv pip install --python .venv\Scripts\python.exe -e ".[dev,windows,gui]"
if errorlevel 1 goto :fail

rem ---- 4/5 离线测试 ----
echo [4/5] 运行离线测试, 不需要 iPhone ...
.venv\Scripts\python.exe -m pytest tests -q
if errorlevel 1 goto :fail

rem ---- 5/5 ffmpeg 可选 ----
where ffplay >nul 2>nul
if errorlevel 1 (
    echo [5/5] 尝试用 winget 安装 ffmpeg - 播放验证用, 装不上不影响采集
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
) else (
    echo [5/5] ffmpeg 已安装
)

echo.
echo ============================================
echo  软件环境就绪! 运行 Windows AirPlay 检查:
echo ============================================
.venv\Scripts\python.exe -m imirror windows-doctor
if errorlevel 1 goto :airplay_help

echo.
echo --------------------------------------------
echo 全部就绪! 启动投屏接收端:
echo   .venv\Scripts\python.exe -m imirror windows-airplay
echo 手机操作: 控制中心, 屏幕镜像, 选择 iMirror
goto :end

:airplay_help
echo.
echo --------------------------------------------
echo AirPlay 检查未完全通过。Windows 默认路线不需要 Zadig 换驱动。
echo 如果提示缺 UxPlay:
echo   1. 打开 https://github.com/leapbtw/uxplay-windows/releases
echo   2. 下载并安装 uxplaywindows-installer.msi
echo   3. 或使用 portable zip, 把 uxplay-windows.exe 放到 tools\uxplay\uxplay-windows.exe
echo   4. 重新运行: .venv\Scripts\python.exe -m imirror windows-doctor
echo 如果手机看不到 iMirror, 检查 Windows 防火墙, Bonjour, 手机和电脑同一局域网
echo raw USB 是高级实验模式, 才需要按 docs\真机联调手册.md 使用 Zadig
goto :end

:fail
echo.
echo [失败] 安装中断, 请把上方输出完整复制反馈
:end
echo.
pause
