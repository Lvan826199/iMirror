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
echo  软件环境就绪! 运行环境自检:
echo ============================================
.venv\Scripts\python.exe -m imirror doctor
if errorlevel 1 goto :driver_help

echo.
echo --------------------------------------------
echo 全部就绪! 直接开始录制, 多台设备时加 --udid 序列号 指定:
echo   .venv\Scripts\python.exe -m imirror -v record out.h264 out.wav --duration 10
goto :end

:driver_help
echo.
echo --------------------------------------------
echo 自检未通过。若上方提示与驱动/权限有关, 按下列步骤换驱动, 一次性:
echo   1. Win+R 输入 services.msc 回车, 找到 Apple Mobile Device Service,
echo      右键停止, 并把启动类型设为"禁用", 没有该服务则跳过
echo   2. 右键以管理员身份运行本目录自带的 scripts\zadig-2.9.exe
echo   3. Options 菜单: 勾选 List All Devices,
echo      并且取消勾选 Ignore Hubs or Composite Parents, 这步是关键
echo   4. 下拉框按 USB ID 列选 05AC 12A8 的条目, 名字可能只显示 Apple,
echo      有多个就选标 Composite Parent 的, 驱动选 libusb-win32, Replace Driver
echo      注意: 必须选 libusb-win32, 不是 libusbK; 投屏接口在非默认配置,
echo            只有 libusb-win32 支持切配置。名字带 win32 但 64 位系统照样用
echo   5. 校验: 换好后跑 doctor 能识别设备且 record 不报 set_configuration 错
echo 完成后重新运行本脚本或单独跑 doctor 复查
goto :end

:fail
echo.
echo [失败] 安装中断, 请把上方输出完整复制反馈
:end
echo.
pause
