"""Windows AirPlay backend wrapper.

This backend intentionally avoids the raw USB QuickTime path.  The first
implementation delegates AirPlay receiver duties to UxPlay (or a compatible
binary) so Windows users can keep Apple's official drivers and mirror from the
iOS Control Center.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass


UXPLAY_NAMES = ("uxplay.exe", "uxplay")
UXPLAY_HINT = "https://github.com/leapbtw/uxplay-windows/releases"
UXPLAY_UPSTREAM = "https://github.com/FDH2/UxPlay"


@dataclass(frozen=True)
class AirPlayStatus:
    platform_ok: bool
    executable: str | None
    bonjour_present: bool
    computer_name: str


def _candidate_dirs() -> list[Path]:
    root = Path(__file__).resolve().parents[1]
    dirs = [
        root / "tools" / "uxplay",
        root / "bin",
        Path.cwd(),
    ]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        dirs.extend([
            Path(local) / "Programs" / "UxPlay",
            Path(local) / "imirror" / "uxplay",
        ])
    program_files = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]
    for value in program_files:
        if value:
            dirs.append(Path(value) / "UxPlay")
    return dirs


def find_uxplay() -> str | None:
    env = os.environ.get("IMIRROR_UXPLAY")
    if env:
        path = Path(env)
        if path.exists():
            return str(path)
    for name in UXPLAY_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for directory in _candidate_dirs():
        for name in UXPLAY_NAMES:
            candidate = directory / name
            if candidate.exists():
                return str(candidate)
    return None


def _has_bonjour() -> bool:
    # UxPlay advertises the receiver through mDNS/Bonjour. On Windows this is
    # usually provided by Apple Mobile Device Support/iTunes/Apple Devices.
    return shutil.which("dns-sd.exe") is not None or any(
        Path(value).exists()
        for value in (
            r"C:\Program Files\Bonjour\mDNSResponder.exe",
            r"C:\Program Files (x86)\Bonjour\mDNSResponder.exe",
        )
    )


def status() -> AirPlayStatus:
    return AirPlayStatus(
        platform_ok=sys.platform == "win32",
        executable=find_uxplay(),
        bonjour_present=_has_bonjour(),
        computer_name=socket.gethostname(),
    )


def doctor() -> int:
    info = status()
    if not info.platform_ok:
        print("Windows AirPlay 后端只支持 Windows。")
        return 1
    print("Windows AirPlay 后端检查")
    print(f"电脑名  : {info.computer_name}")
    if info.bonjour_present:
        print("[OK] Bonjour/mDNS 可用")
    else:
        print("[WARN] 未检测到 Bonjour/mDNS")
        print("  建议: 安装 Apple Devices 或 iTunes, 它们会安装 Apple Mobile Device/Bonjour 组件。")
    if info.executable:
        print(f"[OK] 找到 UxPlay: {info.executable}")
        print("下一步: python -m imirror windows-airplay")
        return 0
    print("[FAIL] 未找到 UxPlay")
    print("  下载 Windows 版 UxPlay 后, 把 uxplay.exe 放到以下任一位置:")
    print("  - 项目目录 tools\\uxplay\\uxplay.exe")
    print("  - 项目目录 bin\\uxplay.exe")
    print("  - 或设置环境变量 IMIRROR_UXPLAY=完整路径\\uxplay.exe")
    print(f"  Windows 打包参考: {UXPLAY_HINT}")
    print(f"  上游项目参考: {UXPLAY_UPSTREAM}")
    return 1


def run_receiver(name: str = "iMirror", extra_args: list[str] | None = None) -> int:
    info = status()
    if not info.platform_ok:
        print("Windows AirPlay 后端只支持 Windows。")
        return 1
    if info.executable is None:
        doctor()
        return 1
    args = [info.executable, "-n", name]
    if extra_args:
        args.extend(extra_args)
    print("正在启动 Windows AirPlay 接收端...")
    print(f"接收端名称: {name}")
    print("手机操作: 控制中心 → 屏幕镜像 → 选择 iMirror")
    print("退出: 关闭 UxPlay 窗口或在本终端按 Ctrl+C")
    try:
        return subprocess.run(args, check=False).returncode
    except FileNotFoundError:
        print(f"无法启动 UxPlay: {info.executable}")
        return 1
    except KeyboardInterrupt:
        return 130
