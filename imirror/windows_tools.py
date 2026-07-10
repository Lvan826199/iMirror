"""Helpers for the Windows reference tools from quicktime_video_hack_windows.

The chotgpt project ships practical Windows tools: a modified usbmuxd,
ideviceinfo/idevice_id, iproxy and a driver installer.  This internal build
vendors those binaries under tools/ and uses them as the Windows QuickTime
toolchain.  IMIRROR_QVH_TOOLS is only a development override for an extracted
upstream tool directory.
"""
from __future__ import annotations

from pathlib import Path
import os
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


def project_python() -> str:
    return r".venv\Scripts\python.exe" if sys.platform == "win32" else ".venv/bin/python"


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
    return None


def doctor(*, next_command: str | None = None) -> int:
    if sys.platform != "win32":
        print("Windows reference tools only run on Windows.")
        return 1
    print("quicktime_video_hack_windows tools check")
    print(f"reference: {REF_REPO}")
    directory = find_tool_dir()
    if directory is None:
        print("[FAIL] tool directory not found")
        print("  Run: powershell -ExecutionPolicy Bypass -File scripts\\fetch-qvh-windows-tools.ps1")
        print("  Or set IMIRROR_QVH_TOOLS to the extracted quicktime_video_hack_windows tool directory.")
        return 1
    print(f"[OK] tool directory: {directory}")
    ok = True
    for name, rel in TOOL_FILES.items():
        exists = (directory / rel).exists()
        print(f"{'[OK]' if exists else '[FAIL]'} {name}: {rel}")
        ok = ok and exists
    if next_command is None:
        next_command = f"{project_python()} -m imirror windows-poc-check"
    if next_command:
        print(f"Next: {next_command}")
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


def _shell_execute_runas(exe: Path, args: list[str] | None = None) -> int:
    import ctypes

    params = subprocess.list2cmdline(args or [])
    return int(ctypes.windll.shell32.ShellExecuteW(
        None,
        "runas",
        str(exe),
        params,
        str(exe.parent),
        1,
    ))


def run_tool_elevated(name: str, args: list[str] | None = None) -> int:
    if sys.platform != "win32":
        print("Windows reference tools only run on Windows.")
        return 1
    exe = tool_path(name)
    if exe is None:
        doctor()
        return 1
    try:
        result = _shell_execute_runas(exe, args)
    except OSError as e:
        print(f"Failed to request administrator privileges for {exe.name}: {e}")
        return 1
    if result <= 32:
        print(f"Failed to start {exe.name} as administrator (ShellExecuteW={result}).")
        return 1
    print(f"Started {exe.name} as administrator. Complete the driver tool, then rerun windows-poc-check.")
    return 0


def start_usbmuxd(args: list[str] | None = None) -> int:
    print("Starting reference usbmuxd. It should listen on TCP 37015 and arm QuickTime mode.")
    print("Keep this process running while testing raw USB capture.")
    return run_tool("usbmuxd", args)


def ideviceinfo(args: list[str] | None = None) -> int:
    return run_tool("ideviceinfo", args)


def idevice_id(args: list[str] | None = None) -> int:
    return run_tool("idevice_id", args)


def open_driver_installer() -> int:
    return run_tool_elevated("driver_installer")


def poc_check(udid: str | None = None) -> int:
    """Run the wired Windows POC preflight using only bundled chotgpt tools."""
    rc = doctor(next_command=None)
    if rc != 0:
        return rc

    print("\n[1/2] Listing devices through bundled idevice_id...")
    id_args = ["-l"]
    rc_id = idevice_id(id_args)

    print("\n[2/2] Reading device info through bundled ideviceinfo...")
    info_args = ["-u", udid] if udid else None
    rc_info = ideviceinfo(info_args)

    if rc_id != 0 or rc_info != 0:
        print("\n[FAIL] chotgpt tools did not complete the device check.")
        print("This is before iMirror protocol code: bundled idevice tools cannot see the phone yet.")
        print("Check: cable, unlocked/trusted phone, Apple Mobile Device service state, and bundled driver installer.")
        print(f"Driver tool: {project_python()} -m imirror windows-driver-installer")
        return rc_info or rc_id

    py = project_python()
    record = f"{py} -m imirror -v record out.h264 out.wav --duration 10"
    if udid:
        record += f" --udid {udid}"
    print("\n[OK] Bundled chotgpt tools can see the device.")
    print(f"Next terminal A: {py} -m imirror windows-usbmuxd")
    print(f"Next terminal B: {record}")
    return 0
