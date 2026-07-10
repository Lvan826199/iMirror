"""命令行入口。

用法:
  python -m imirror doctor              # 环境自检(跨平台, 不需要 iPhone)
  python -m imirror devices [--json]    # 列出 iOS 设备及 QT 配置状态
  python -m imirror activate            # 激活 QuickTime 配置
  python -m imirror reset               # USB reset, 恢复半激活状态
  python -m imirror record out.h264 out.wav [--udid SERIAL] [--duration 秒]   # 录制
  python -m imirror gui                 # 实时预览(Windows 默认 raw USB 有线)
  python -m imirror windows-poc-check   # Windows 有线 POC 预检
  python -m imirror windows-usbmuxd     # 启动 chotgpt 参考工具里的 usbmuxd
  python -m imirror macos-record out.mov --duration 10   # macOS 原生录制
"""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import threading

from . import __version__

log = logging.getLogger("imirror")


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024


def _qt_state_text(device) -> str:
    if device.qt_enabled:
        return f"已激活 (active #{device.active_config_index})"
    if device.qt_available:
        active = "未知" if device.active_config_index == -1 else f"#{device.active_config_index}"
        return f"可用但未激活 (active {active}, QT #{device.qt_config_index})"
    return "未激活 (record 时会自动激活)"


def cmd_doctor(_args) -> int:
    """环境自检: 逐项检查并给出当前平台的修复建议, 没接 iPhone 也能跑。"""
    import platform
    os_name = platform.system()   # Linux / Darwin / Windows
    friendly = {"Darwin": "macOS"}.get(os_name, os_name)
    print(f"平台    : {friendly} ({platform.platform()})")
    print(f"Python  : {sys.version.split()[0]}")

    try:
        import usb.core
        import usb.util
    except ImportError:
        print('✗ pyusb 未安装        修复: 在项目目录执行 pip install -e ".[dev]"')
        return 1
    print("✓ pyusb 已安装")

    from .usb import discovery
    try:
        apple_devs = list(discovery.usb_find(find_all=True, idVendor=discovery.APPLE_VID))
    except usb.core.NoBackendError:
        print("✗ 找不到 libusb 运行库")
        print({
            "Windows": "  修复: pip install libusb-package",
            "Darwin": "  修复: brew install libusb",
        }.get(os_name, "  修复: sudo apt install libusb-1.0-0 (或发行版对应包)"))
        return 1
    print("✓ libusb 后端可用")

    if not apple_devs:
        print("✗ 未发现 Apple USB 设备 (vid=05ac)")
        print("  检查: 数据线要支持数据传输 / 手机解锁并点了\"信任\" / 换个 USB 口")
        if os_name == "Windows":
            print("  Windows 还需: 先运行 windows-usbmuxd；如驱动未就绪, 用 windows-driver-installer")
        return 1
    print(f"✓ 发现 {len(apple_devs)} 个 Apple USB 设备")

    denied, accessible = 0, 0
    for dev in apple_devs:
        try:
            usb.util.get_string(dev, dev.iSerialNumber)
            accessible += 1
        # Windows 未换驱动/Linux 无权限时, pyusb 可能抛 ValueError(no langid) 而非 USBError
        except (usb.core.USBError, NotImplementedError, ValueError):
            denied += 1
        finally:
            usb.util.dispose_resources(dev)
    if accessible == 0:
        print(f"✗ {denied} 个 Apple 设备节点全部无法访问")
        print({
            "Linux": "  修复: 加 udev 规则(见 docs/真机联调手册.md)或在命令前加 sudo",
            "Windows": "  修复: 运行 python -m imirror windows-driver-installer, 使用内置 chotgpt 驱动安装器准备设备;\n"
                       "        并确认 Apple Mobile Device Support 服务未占用(详见 docs/真机联调手册.md)",
            "Darwin": "  修复: 退出可能占用设备的程序(QuickTime、爱思助手等)后重试",
        }.get(os_name, ""))
        return 1
    if denied:
        # 复合设备的子接口节点/未换驱动的另一台设备会读不了, 不影响采集
        print(f"⚠ {accessible} 个节点可访问, {denied} 个不可访问(多为复合设备子接口或未换驱动的其它设备, 可忽略)")
    else:
        print("✓ 设备可访问 (权限/驱动正常)")

    ios = [d for d in (discovery.find_ios_devices() or [])]
    if not ios:
        print("✗ 没有识别出 iOS 设备")
        if os_name == "Windows":
            print("  检查: 先跑 windows-poc-check / windows-usbmuxd;")
            print("        如驱动未就绪, 跑 windows-driver-installer 并选择当前 iPhone 条目")
        else:
            print("  发现的可能是键盘/耳机等 Apple 外设")
        return 1
    for d in ios:
        print(f"✓ {d.serial}  {d.product_name}  QT配置: {_qt_state_text(d)}")
    print("\n环境就绪, 下一步: python -m imirror record out.h264 out.wav --duration 10")
    return 0


def cmd_devices(args) -> int:
    from .usb.discovery import find_ios_devices
    devices = find_ios_devices()
    if args.json:
        print(json.dumps([{
            "serial": d.serial,
            "product": d.product_name,
            "vid": d.vid,
            "pid": d.pid,
            "active_config": d.active_config_index,
            "usbmux_config": d.usbmux_config_index,
            "qt_config": d.qt_config_index,
            "qt_available": d.qt_available,
            "qt_enabled": d.qt_enabled,
        } for d in devices], ensure_ascii=False, indent=2))
        return 0 if devices else 1
    if not devices:
        print("未发现 iOS 设备。检查: 1) 数据线 2) 手机已解锁并信任 3) Windows 先跑内置 windows-usbmuxd / windows-driver-installer")
        return 1
    for d in devices:
        print(f"{d.serial}  {d.product_name}  vid:pid={d.vid:04x}:{d.pid:04x}  QT配置: {_qt_state_text(d)}")
    return 0


def _pick_device(udid: str | None, need_qt: bool = False):
    from .usb.discovery import find_ios_devices
    from .usb.activation import enable_qt_config
    devices = find_ios_devices()
    if udid:
        # usbmuxd 风格的 udid 带短横线(00008110-xxxx), USB 序列号不带, 两种写法都接受
        want = udid.replace("-", "").lower()
        matched = [d for d in devices if d.serial.replace("-", "").lower() == want]
        if not matched:
            seen = ", ".join(d.serial for d in devices) or "无"
            raise SystemExit(f"未找到序列号 {udid} 的设备。当前可见: {seen}")
        devices = matched
    if not devices:
        raise SystemExit("未找到设备, 先跑: python -m imirror doctor")
    if not udid and len(devices) > 1:
        choices = "\n".join(
            f"  {d.serial}  {d.product_name}  QT配置: {_qt_state_text(d)}"
            for d in devices
        )
        raise SystemExit(
            "发现多台 iOS 设备, 为避免选错设备, 请用 --udid 明确指定其中一台:\n"
            f"{choices}"
        )
    device = devices[0]
    if need_qt and not device.qt_enabled:
        log.info("QT 配置未激活, 正在激活 %s ...", device.serial)
        device = enable_qt_config(device)
    elif need_qt and sys.platform == "win32":
        # Windows 失败会话可能把设备留在 active QT 配置, 但下一次直接复用不会重新出流。
        # 强制重发 QT enable, 让设备重新进入 PING/SYNC 会话起点。
        log.info("Windows: QT 配置已激活, 重新发送激活请求以启动新会话 %s ...", device.serial)
        device = enable_qt_config(device, force_rearm=True)
    return device


def cmd_activate(args) -> int:
    device = _pick_device(args.udid, need_qt=True)
    print(f"{device.serial} QuickTime 配置已激活 (config #{device.qt_config_index})")
    return 0


def cmd_reset(args) -> int:
    from .usb.activation import reset_usb_device

    device = _pick_device(args.udid, need_qt=False)
    print(f"正在重置 {device.serial} 的 USB 连接...")
    info = reset_usb_device(device)
    print(f"{info.serial} USB reset 完成, QT配置: {_qt_state_text(info)}")
    return 0


def cmd_record(args) -> int:
    from .usb.adapter import UsbAdapter
    from .session import MessageProcessor
    from .consumers.h264_writer import H264Writer
    from .consumers.wav_writer import WavWriter, CompositeConsumer

    device = _pick_device(args.udid, need_qt=True)

    h264_file = open(args.h264, "wb")
    consumer = CompositeConsumer(H264Writer(h264_file), WavWriter(args.wav))

    adapter = UsbAdapter(device)
    adapter.open()
    processor = MessageProcessor(adapter.write, consumer,
                                 stop_callback=adapter.stop_reading)

    reader = threading.Thread(
        target=adapter.read_loop, args=(processor.receive_frame,), daemon=True
    )
    reader.start()

    stop_event = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, lambda *_: stop_event.set())

    if args.duration:
        print(f"录制中(限时 {args.duration}s)... Ctrl+C 提前停止")
    else:
        print("录制中... Ctrl+C 停止")
    try:
        # 周期性打印帧数/数据量, 顺带充当 --duration 的计时器
        elapsed = 0.0
        interval = 5.0
        while True:
            step = interval
            if args.duration:
                step = min(step, args.duration - elapsed)
            if stop_event.wait(step):
                break
            elapsed += step
            s = processor.stats
            fps = s["video_frames"] / elapsed if elapsed else 0
            print(f"  [{elapsed:5.0f}s] 视频 {s['video_frames']} 帧 (~{fps:.1f}fps, "
                  f"{_fmt_bytes(s['video_bytes'])})  音频 {s['audio_frames']} 帧 "
                  f"({_fmt_bytes(s['audio_bytes'])})")
            if args.duration and elapsed >= args.duration:
                break
    finally:
        processor.close_session()
        adapter.close()
        reader.join(timeout=3)
        h264_file.close()
    stats = processor.stats
    if stats["video_frames"] == 0:
        print("录制失败: 未收到视频帧。请用 -v 查看 USB/协议日志, 并按文档检查手机解锁信任、占用程序和 USB 连接。")
        return 1
    print(f"已保存: {args.h264} / {args.wav}")
    print(f"播放: ffplay -f h264 {args.h264}")
    return 0


def cmd_gui(args) -> int:
    backend = getattr(args, "backend", "auto")
    if backend == "auto":
        backend = "raw-usb"
    if backend != "raw-usb":
        print(f"不支持的 GUI backend: {backend}")
        return 1
    try:
        # av/cv2 在 viewer 函数体内才 import, 所以要把调用也包进来
        from .gui.viewer import run_viewer
        return run_viewer(args.udid)
    except ImportError as e:
        print(f"GUI 依赖缺失({e.name})。在项目目录安装:")
        if sys.platform == "win32":
            print('  uv pip install --python .venv\\Scripts\\python.exe -e ".[gui]"')
        else:
            print('  uv pip install --python .venv/bin/python -e ".[gui]"')
        return 1


def cmd_windows_tools_doctor(_args) -> int:
    from .windows_tools import doctor
    return doctor()


def cmd_windows_usbmuxd(args) -> int:
    from .windows_tools import start_usbmuxd
    return start_usbmuxd(args.tool_arg or None)


def cmd_windows_ideviceinfo(args) -> int:
    from .windows_tools import ideviceinfo
    return ideviceinfo(args.tool_arg or None)


def cmd_windows_poc_check(args) -> int:
    from .windows_tools import poc_check
    return poc_check(args.udid)


def cmd_windows_driver_installer(_args) -> int:
    from .windows_tools import open_driver_installer
    return open_driver_installer()


def cmd_macos_devices(args) -> int:
    from .macos_native import list_devices
    return list_devices(json_output=args.json)


def cmd_macos_record(args) -> int:
    from .macos_native import record
    return record(args.mov, args.udid, args.duration)


def cmd_macos_gui(args) -> int:
    from .macos_native import preview
    return preview(args.udid)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="imirror",
        description="iMirror: iOS 投屏采集 (Windows 主攻 QuickTime raw USB 有线)",
        epilog="示例: imirror gui 或 imirror windows-poc-check",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="输出 DEBUG 日志")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="环境自检(跨平台, 不需要 iPhone)")

    p = sub.add_parser("devices", help="列出 iOS 设备")
    p.add_argument("--json", action="store_true", help="以 JSON 输出(便于脚本调用)")

    p = sub.add_parser("activate", help="激活 QuickTime 配置")
    p.add_argument("--udid", help="设备序列号")

    p = sub.add_parser("reset", help="重置 iPhone USB 连接, 恢复半激活状态")
    p.add_argument("--udid", help="设备序列号")

    p = sub.add_parser("record", help="录制 h264+wav")
    p.add_argument("h264", help="输出 .h264 文件")
    p.add_argument("wav", help="输出 .wav 文件")
    p.add_argument("--udid", help="设备序列号")
    p.add_argument("--duration", type=float, metavar="秒",
                   help="录制时长, 到时自动停止(默认无限, Ctrl+C 停止)")

    p = sub.add_parser("gui", help="实时预览窗口")
    p.add_argument("--udid", help="设备序列号")
    p.add_argument("--backend", choices=("auto", "raw-usb"), default="auto",
                   help="预览后端: 默认 raw-usb 有线")

    sub.add_parser("windows-tools-doctor", help="检查 quicktime_video_hack_windows 的 tool 目录")

    p = sub.add_parser("windows-usbmuxd", help="启动 chotgpt 参考工具里的 usbmuxd")
    p.add_argument("--tool-arg", action="append", help="透传给 usbmuxd.exe 的参数, 可重复")

    p = sub.add_parser("windows-ideviceinfo", help="运行 chotgpt 参考工具里的 ideviceinfo")
    p.add_argument("--tool-arg", action="append", help="透传给 ideviceinfo.exe 的参数, 可重复")

    p = sub.add_parser("windows-poc-check", help="用内置 chotgpt tools 执行 Windows 有线 POC 预检")
    p.add_argument("--udid", help="设备序列号(可选, 会传给 ideviceinfo 并生成 record 命令)")

    sub.add_parser("windows-driver-installer", help="打开 chotgpt 参考工具里的驱动安装器")

    p = sub.add_parser("macos-devices", help="macOS 原生后端: 列出 iOS 屏幕源")
    p.add_argument("--json", action="store_true", help="以 JSON 输出")

    p = sub.add_parser("macos-record", help="macOS 原生后端: 录制 .mov")
    p.add_argument("mov", help="输出 .mov 文件")
    p.add_argument("--udid", help="设备序列号")
    p.add_argument("--duration", type=float, metavar="秒", default=10.0,
                   help="录制时长(默认 10 秒)")

    p = sub.add_parser("macos-gui", help="macOS 原生后端: 打开系统预览窗口")
    p.add_argument("--udid", help="设备序列号")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    handlers = {
        "doctor": cmd_doctor,
        "devices": cmd_devices,
        "activate": cmd_activate,
        "reset": cmd_reset,
        "record": cmd_record,
        "gui": cmd_gui,
        "windows-tools-doctor": cmd_windows_tools_doctor,
        "windows-usbmuxd": cmd_windows_usbmuxd,
        "windows-ideviceinfo": cmd_windows_ideviceinfo,
        "windows-poc-check": cmd_windows_poc_check,
        "windows-driver-installer": cmd_windows_driver_installer,
        "macos-devices": cmd_macos_devices,
        "macos-record": cmd_macos_record,
        "macos-gui": cmd_macos_gui,
    }
    try:
        return handlers[args.command](args)
    except RuntimeError as e:
        print(f"错误: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
