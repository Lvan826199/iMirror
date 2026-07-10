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
echo  软件环境就绪! 检查内置 Windows 有线投屏工具:
echo ============================================
.venv\Scripts\python.exe -m imirror windows-tools-doctor
if errorlevel 1 goto :tools_help

echo.
echo --------------------------------------------
echo 全部就绪! Windows 主线是有线 QuickTime POC:
echo   1. 连接并信任 iPhone
echo   2. 预检: .venv\Scripts\python.exe -m imirror windows-poc-check
echo   3. 开一个终端运行: .venv\Scripts\python.exe -m imirror windows-usbmuxd
echo   4. 录制验证: .venv\Scripts\python.exe -m imirror -v record out.h264 out.wav --duration 10 --udid 设备序列号
goto :end

:tools_help
echo.
echo --------------------------------------------
echo 内置 tools 检查未通过。内部仓库应包含 tools\usbmuxd.exe 等文件。
echo 若缺失, 运行: powershell -ExecutionPolicy Bypass -File scripts\fetch-qvh-windows-tools.ps1
echo 当前 Windows 路线只维护有线 QuickTime POC, 请先补齐内置 tools。
goto :end

:fail
echo.
echo [失败] 安装中断, 请把上方输出完整复制反馈
:end
echo.
pause
