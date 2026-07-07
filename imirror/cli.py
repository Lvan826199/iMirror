"""命令行入口。

用法:
  python -m imirror devices             # 列出 iOS 设备及 QT 配置状态
  python -m imirror activate            # 激活 QuickTime 配置
  python -m imirror record out.h264 out.wav [--udid SERIAL]   # 录制
  python -m imirror gui                 # 实时预览(需要 PyAV + OpenCV)
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading

log = logging.getLogger("imirror")


def cmd_devices(_args) -> int:
    from .usb.discovery import find_ios_devices
    devices = find_ios_devices()
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
    print("录制中... Ctrl+C 停止")
    try:
        stop_event.wait()
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
    parser = argparse.ArgumentParser(prog="imirror", description="iMirror: iOS 有线投屏采集 (Python 版 quicktime_video_hack)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="列出 iOS 设备")

    p = sub.add_parser("activate", help="激活 QuickTime 配置")
    p.add_argument("--udid", help="设备序列号")

    p = sub.add_parser("record", help="录制 h264+wav")
    p.add_argument("h264", help="输出 .h264 文件")
    p.add_argument("wav", help="输出 .wav 文件")
    p.add_argument("--udid", help="设备序列号")

    p = sub.add_parser("gui", help="实时预览窗口")
    p.add_argument("--udid", help="设备序列号")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    handlers = {
        "devices": cmd_devices,
        "activate": cmd_activate,
        "record": cmd_record,
        "gui": cmd_gui,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
