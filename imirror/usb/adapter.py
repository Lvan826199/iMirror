"""USB bulk 端点读写循环: 找到 QuickTime 接口, 持续读流并分帧回调。

对照源码: screencapture/usbadapter.go

流程:
  1. set_configuration 到 QT 配置
  2. 找到 class=0xFF subclass=0x2A 的接口并 claim
  3. 对两个 bulk 端点发 CLEAR_FEATURE(halt) 复位
  4. 循环读 in 端点 -> LengthFieldExtractor 分帧 -> 回调
"""
from __future__ import annotations

import logging
import sys
import threading
from typing import Callable

import usb.core
import usb.util

from .discovery import IosDevice, open_by_serial, CLASS_VENDOR_SPECIFIC, SUBCLASS_QUICKTIME
from ..protocol.framing import LengthFieldExtractor

log = logging.getLogger(__name__)

READ_SIZE = 65536
READ_TIMEOUT_MS = 2000


class UsbAdapter:
    def __init__(self, device: IosDevice) -> None:
        if not device.qt_enabled:
            raise RuntimeError("QT 配置未激活, 先调用 enable_qt_config")
        self._info = device
        self._dev: usb.core.Device | None = None
        self._ep_in = None
        self._ep_out = None
        self._interface_number = -1
        self._stop = threading.Event()
        self._write_lock = threading.Lock()

    # -------------------------------------------------- 生命周期

    def open(self) -> None:
        dev = open_by_serial(self._info.serial)
        self._dev = dev

        # 切到 QT 配置。Windows 上 libusb 的 set_configuration 可能报
        # NotImplementedError(LIBUSB_ERROR_NOT_SUPPORTED), 逐级降级:
        # 已是目标配置则跳过 -> set_configuration -> 裸 SET_CONFIGURATION 控制请求
        target = self._info.qt_config_index
        active = None
        try:
            active = dev.get_active_configuration().bConfigurationValue
        except (usb.core.USBError, NotImplementedError) as e:
            log.debug("读活动配置失败(继续尝试设置): %s", e)
        if active == target:
            log.debug("活动配置已是 QT 配置 #%d, 跳过切换", target)
        else:
            log.debug("活动配置 #%s -> 目标 QT 配置 #%d", active, target)
            try:
                dev.set_configuration(target)
            except (usb.core.USBError, NotImplementedError) as e:
                log.warning("set_configuration(%d) 失败: %s — 改用标准控制请求重试", target, e)
                try:
                    # bmRequestType=0x00(标准/设备), bRequest=0x09(SET_CONFIGURATION)
                    dev.ctrl_transfer(0x00, 0x09, target, 0, None)
                except (usb.core.USBError, NotImplementedError) as e2:
                    log.warning("SET_CONFIGURATION 控制请求也失败: %s", e2)

        try:
            cfg = dev.get_active_configuration()
        except (usb.core.USBError, NotImplementedError) as e:
            raise RuntimeError(
                f"无法读取活动 USB 配置: {e}。Windows 上多为驱动未就绪, "
                f"请对当前形态的 iPhone 用 Zadig 换 libusbK(详见 docs/真机联调手册.md)"
            ) from e
        if cfg.bConfigurationValue != target:
            log.warning("活动配置仍是 #%d(目标 #%d), 尝试直接在当前配置里找 QT 接口",
                        cfg.bConfigurationValue, target)
        intf = usb.util.find_descriptor(
            cfg,
            custom_match=lambda i: (
                i.bInterfaceClass == CLASS_VENDOR_SPECIFIC
                and i.bInterfaceSubClass == SUBCLASS_QUICKTIME
            ),
        )
        if intf is None:
            msg = (f"活动配置 #{cfg.bConfigurationValue} 里没有 QuickTime 接口"
                   f"(它在配置 #{target})。")
            if sys.platform == "win32":
                msg += ("\nWindows 根因: 投屏接口在非默认 USB 配置上, 而 libusbK/WinUSB "
                        "驱动不支持切换配置。\n解决: 用 Zadig 把该设备的驱动从 libusbK "
                        "改成 libusb-win32(libusb0), 它支持切配置。\n详见 docs/真机联调手册.md 的驱动选择表。")
            raise RuntimeError(msg)
        self._interface_number = intf.bInterfaceNumber
        usb.util.claim_interface(dev, self._interface_number)

        self._ep_in = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
                and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
            ),
        )
        self._ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: (
                usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
                and usb.util.endpoint_type(e.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK
            ),
        )
        if self._ep_in is None or self._ep_out is None:
            raise RuntimeError("找不到 bulk 端点")

        # 复位两个端点(Go 版: usbDevice.Control(0x02, 0x01, 0, endpointAddress, nil))
        for ep in (self._ep_in, self._ep_out):
            try:
                dev.clear_halt(ep.bEndpointAddress)
            # Windows/libusbK 下 clear_halt 可能返回 NOT_SUPPORTED(NotImplementedError)
            except (usb.core.USBError, NotImplementedError) as e:
                log.warning("clear_halt(0x%02x) 失败(可忽略): %s", ep.bEndpointAddress, e)
        log.info("已 claim QuickTime 接口 #%d (in:0x%02x out:0x%02x)",
                 self._interface_number,
                 self._ep_in.bEndpointAddress, self._ep_out.bEndpointAddress)

    def close(self) -> None:
        self._stop.set()
        if self._dev is not None:
            try:
                usb.util.release_interface(self._dev, self._interface_number)
            except usb.core.USBError:
                pass
            usb.util.dispose_resources(self._dev)
            self._dev = None

    # -------------------------------------------------- 读写

    def write(self, frame: bytes) -> None:
        """写一个完整帧(帧本身已含长度前缀)。多线程安全。"""
        with self._write_lock:
            self._ep_out.write(frame)

    def read_loop(self, on_frame: Callable[[bytes], None]) -> None:
        """阻塞读循环, 每解出一个完整帧就调用 on_frame(frame)。

        在独立线程里跑; 调用 close() 或读超时且 _stop 置位时退出。
        """
        extractor = LengthFieldExtractor()
        while not self._stop.is_set():
            try:
                data = self._ep_in.read(READ_SIZE, timeout=READ_TIMEOUT_MS)
            except usb.core.USBTimeoutError:
                continue
            except usb.core.USBError as e:
                if self._stop.is_set():
                    break
                log.error("USB 读错误: %s", e)
                break
            for frame in extractor.feed(bytes(data)):
                on_frame(frame)
        log.info("读循环退出")

    def stop_reading(self) -> None:
        self._stop.set()
