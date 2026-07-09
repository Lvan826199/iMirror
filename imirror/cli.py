"""命令行入口。

用法:
  python -m imirror doctor              # 环境自检(跨平台, 不需要 iPhone)
  python -m imirror devices [--json]    # 列出 iOS 设备及 QT 配置状态
  python -m imirror activate            # 激活 QuickTime 配置
  python -m imirror record out.h264 out.wav [--udid SERIAL] [--duration 秒]   # 录制
  python -m imirror gui                 # 实时预览(需要 PyAV + OpenCV)
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
            print("  Windows 还需: 用 Zadig 把 iPhone 驱动换成 libusbK 或 WinUSB")
        return 1
    print(f"✓ 发现 {len(apple_devs)} 个 Apple USB 设备")

    denied = 0
    for dev in apple_devs:
        try:
            usb.util.get_string(dev, dev.iSerialNumber)
        except (usb.core.USBError, NotImplementedError) as e:
            denied += 1
            print(f"✗ 设备 {dev.idVendor:04x}:{dev.idProduct:04x} 无法访问: {e}")
        finally:
            usb.util.dispose_resources(dev)
    if denied:
        print({
            "Linux": "  修复: 加 udev 规则(见 docs/真机联调手册.md)或在命令前加 sudo",
            "Windows": "  修复: 用 Zadig 换驱动为 libusbK/WinUSB, 并停用 Apple Mobile Device Support 服务",
            "Darwin": "  修复: 退出可能占用设备的程序(QuickTime、爱思助手等)后重试",
        }.get(os_name, ""))
        return 1
    print("✓ 设备可访问 (权限/驱动正常)")

    ios = [d for d in (discovery.find_ios_devices() or [])]
    if not ios:
        print("✗ 没有识别出 iOS 设备 (发现的可能是键盘/耳机等 Apple 外设)")
        return 1
    for d in ios:
        state = "已激活" if d.qt_enabled else "未激活 (record 时会自动激活)"
        print(f"✓ {d.serial}  {d.product_name}  QT配置: {state}")
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
            "qt_enabled": d.qt_enabled,
        } for d in devices], ensure_ascii=False, indent=2))
        return 0 if devices else 1
    if not devices:
        print("未发现 iOS 设备。检查: 1) 数据线 2) 手机已解锁并信任 3) libusb 驱动(Windows 需用 Zadig 替换)")
        return 1
    for d in devices:
        state = "已激活" if d.qt_enabled else "未激活"
        print(f"{d.serial}  {d.product_name}  vid:pid={d.vid:04x}:{d.pid:04x}  QT配置: {state}")
    return 0


def _pick_device(udid: str | None, need_qt: bool = False):
    from .usb.discovery import find_ios_devices
    from .usb.activation import enable_qt_config
    devices = find_ios_devices()
    if udid:
        devices = [d for d in devices if d.serial == udid]
    if not devices:
        raise SystemExit("未找到设备")
    device = devices[0]
    if need_qt and not device.qt_enabled:
        log.info("QT 配置未激活, 正在激活 %s ...", device.serial)
        device = enable_qt_config(device)
    return device


def cmd_activate(args) -> int:
    device = _pick_device(args.udid, need_qt=True)
    print(f"{device.serial} QuickTime 配置已激活 (config #{device.qt_config_index})")
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
    print(f"已保存: {args.h264} / {args.wav}")
    print(f"播放: ffplay -f h264 {args.h264}")
    return 0


def cmd_gui(args) -> int:
    try:
        from .gui.viewer import run_viewer
    except ImportError as e:
        print(f"GUI 依赖缺失({e})。安装: pip install av opencv-python")
        return 1
    return run_viewer(args.udid)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="imirror",
        description="iMirror: iOS 有线投屏采集 (Python 版 quicktime_video_hack)",
        epilog="示例: imirror record out.h264 out.wav --duration 30",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="输出 DEBUG 日志")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="环境自检(跨平台, 不需要 iPhone)")

    p = sub.add_parser("devices", help="列出 iOS 设备")
    p.add_argument("--json", action="store_true", help="以 JSON 输出(便于脚本调用)")

    p = sub.add_parser("activate", help="激活 QuickTime 配置")
    p.add_argument("--udid", help="设备序列号")

    p = sub.add_parser("record", help="录制 h264+wav")
    p.add_argument("h264", help="输出 .h264 文件")
    p.add_argument("wav", help="输出 .wav 文件")
    p.add_argument("--udid", help="设备序列号")
    p.add_argument("--duration", type=float, metavar="秒",
                   help="录制时长, 到时自动停止(默认无限, Ctrl+C 停止)")

    p = sub.add_parser("gui", help="实时预览窗口")
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
        "record": cmd_record,
        "gui": cmd_gui,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
