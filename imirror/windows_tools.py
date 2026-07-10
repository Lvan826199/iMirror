"""Helpers for the Windows reference tools from quicktime_video_hack_windows.

The chotgpt project ships practical Windows tools: a modified usbmuxd,
ideviceinfo/idevice_id, iproxy and a driver installer.  We do not vendor those
binary files in this repository; instead users can download them locally and
point iMirror at the extracted tool directory.
"""
from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys


REF_REPO = "https://github.com/chotgpt/quicktime_video_hack_windows"
DEFAULT_TOOL_DIR = Path("tools")

TOOL_FILES = {
    "usbmuxd": "usbmuxd.exe",
    "ideviceinfo": "ideviceinfo.exe",
    "idevice_id": "idevice_id.exe",
    "iproxy": "iproxy.exe",
    "driver_installer": str(Path("驱动安装器") / "UsbDeviceEnumMFC.exe"),
}


def candidate_tool_dirs() -> list[Path]:
    dirs: list[Path] = []
    env = os.environ.get("IMIRROR_QVH_TOOLS")
    if env:
        dirs.append(Path(env))
    root = Path(__file__).resolve().parents[1]
    dirs.extend([
        root / DEFAULT_TOOL_DIR,
        root / "tool",
        Path.cwd() / DEFAULT_TOOL_DIR,
        Path.cwd() / "tool",
    ])
    return dirs


def find_tool_dir() -> Path | None:
    for directory in candidate_tool_dirs():
        if all((directory / rel).exists() for rel in TOOL_FILES.values()):
            return directory
    return None


def tool_path(name: str) -> Path | None:
    rel = TOOL_FILES[name]
    directory = find_tool_dir()
    if directory is not None:
        candidate = directory / rel
        if candidate.exists():
            return candidate
    found = shutil.which(Path(rel).name)
    if found:
        return Path(found)
    return None


def doctor() -> int:
    if sys.platform != "win32":
        print("Windows reference tools only run on Windows.")
        return 1
    print("quicktime_video_hack_windows tools check")
    print(f"reference: {REF_REPO}")
    directory = find_tool_dir()
    if directory is None:
        print("[FAIL] tool directory not found")
        print("  Run: powershell -ExecutionPolicy Bypass -File scripts\\fetch-qvh-windows-tools.ps1")
        print("  Or set IMIRROR_QVH_TOOLS to the extracted tool directory.")
        return 1
    print(f"[OK] tool directory: {directory}")
    ok = True
    for name, rel in TOOL_FILES.items():
        exists = (directory / rel).exists()
        print(f"{'[OK]' if exists else '[FAIL]'} {name}: {rel}")
        ok = ok and exists
    print("Next: python -m imirror windows-usbmuxd")
    return 0 if ok else 1


def run_tool(name: str, args: list[str] | None = None) -> int:
    if sys.platform != "win32":
        print("Windows reference tools only run on Windows.")
        return 1
    exe = tool_path(name)
    if exe is None:
        doctor()
        return 1
    cmd = [str(exe), *(args or [])]
    try:
        return subprocess.run(cmd, cwd=str(exe.parent), check=False).returncode
    except KeyboardInterrupt:
        return 130


def start_usbmuxd(args: list[str] | None = None) -> int:
    print("Starting reference usbmuxd. It should listen on TCP 37015 and arm QuickTime mode.")
    print("Keep this process running while testing raw USB capture.")
    return run_tool("usbmuxd", args)


def ideviceinfo(args: list[str] | None = None) -> int:
    return run_tool("ideviceinfo", args)


def open_driver_installer() -> int:
    return run_tool("driver_installer")
