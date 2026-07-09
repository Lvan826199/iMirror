#!/usr/bin/env bash
# iMirror macOS 一键环境安装
# 用法: bash scripts/setup-macos.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "============================================"
echo " iMirror macOS 环境一键安装"
echo "============================================"
echo

# ---- 1/5 Homebrew ----
if ! command -v brew >/dev/null 2>&1; then
    echo "[错误] 未安装 Homebrew。先执行下面这行装好后, 重新跑本脚本:"
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 1
fi
echo "[1/5] Homebrew 已安装"

# ---- 2/5 libusb / uv / ffmpeg ----
echo "[2/5] 安装 libusb + uv + ffmpeg (已装的会自动跳过)..."
brew install libusb uv ffmpeg

# ---- 3/5 venv ----
if [ ! -d .venv ]; then
    echo "[3/5] 创建虚拟环境 .venv ..."
    uv venv .venv
else
    echo "[3/5] .venv 已存在, 跳过"
fi

# ---- 4/5 依赖 ----
echo "[4/5] 安装项目依赖..."
uv pip install --python .venv/bin/python -e ".[dev]"

# ---- 5/5 离线测试 ----
echo "[5/5] 运行离线测试(不需要 iPhone)..."
.venv/bin/python -m pytest tests -q

echo
echo "============================================"
echo " 软件环境就绪! 运行环境自检:"
echo "============================================"
.venv/bin/python -m imirror doctor || true

echo
echo "--------------------------------------------"
echo "接下来:"
echo "  1. 退出 QuickTime、爱思助手等可能占用 iPhone 的程序"
echo "  2. 数据线连 iPhone -> 解锁 -> 点\"信任此电脑\""
echo "  3. 复查:   .venv/bin/python -m imirror doctor"
echo "  4. 录 10s: .venv/bin/python -m imirror record out.h264 out.wav --duration 10"
