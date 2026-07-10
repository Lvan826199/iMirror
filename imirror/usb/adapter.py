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
import time
from typing import Callable

import usb.core
import usb.util

from .discovery import IosDevice, open_by_serial, CLASS_VENDOR_SPECIFIC, SUBCLASS_QUICKTIME
from ..protocol.framing import LengthFieldExtractor

log = logging.getLogger(__name__)

READ_SIZE = 65536
READ_TIMEOUT_MS = 2000
WRITE_TIMEOUT_MS = 2000


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
        self._saw_device_data = False
        # Windows 专属"唤醒敲门": C++ 参考(QuickTime.cpp:893-905)在读超时(-116)时
        # 发 vendor 控制请求 0x40/0x40/0x6400/0x6400 + 主动 PING, 作者注释明言
        # "不调用可能导致无限读取超时"。Linux/macOS(Go 版路线)不需要。
        self._kick_enabled = sys.platform == "win32"

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
        except (usb.core.USBError, NotImplementedError, ValueError) as e:
            log.debug("读活动配置失败(继续尝试设置): %s", e)
        if active == target:
            log.debug("活动配置已是 QT 配置 #%d, 跳过切换", target)
        else:
            log.debug("活动配置 #%s -> 目标 QT 配置 #%d", active, target)
            try:
                dev.set_configuration(target)
            except (usb.core.USBError, NotImplementedError, ValueError) as e:
                log.warning("set_configuration(%d) 失败: %s — 改用标准控制请求重试", target, e)
                try:
                    # bmRequestType=0x00(标准/设备), bRequest=0x09(SET_CONFIGURATION)
                    dev.ctrl_transfer(0x00, 0x09, target, 0, None)
                except (usb.core.USBError, NotImplementedError, ValueError) as e2:
                    log.warning("SET_CONFIGURATION 控制请求也失败: %s", e2)

        try:
            cfg = dev.get_active_configuration()
        except (usb.core.USBError, NotImplementedError, ValueError) as e:
            raise RuntimeError(
                f"无法读取活动 USB 配置: {e}。Windows 上多为驱动未就绪, "
                f"请运行 python -m imirror windows-driver-installer 使用内置 chotgpt 驱动安装器处理当前形态的 iPhone"
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
                        "驱动不支持切换配置。\n解决: 运行 python -m imirror windows-driver-installer, "
                        "优先使用内置 chotgpt 驱动安装器重新准备该设备。\n详见 docs/真机联调手册.md。")
            raise RuntimeError(msg)
        self._interface_number = intf.bInterfaceNumber
        for attempt in range(1, 6):
            try:
                usb.util.claim_interface(dev, self._interface_number)
                break
            except (usb.core.USBError, NotImplementedError, ValueError) as e:
                if attempt == 5:
                    raise RuntimeError(f"claim QuickTime 接口 #{self._interface_number} 失败: {e}") from e
                log.debug("claim QuickTime 接口 #%d 失败(第 %d 次, 等待重试): %s",
                          self._interface_number, attempt, e)
                time.sleep(0.3)

        # Windows/libusb-win32 上, 端点常需显式设 altsetting 才真正激活,
        # 否则 bulk 读写会一直超时。失败(如驱动不支持)可忽略。
        try:
            dev.set_interface_altsetting(
                interface=self._interface_number,
                alternate_setting=intf.bAlternateSetting,
            )
            log.debug("set_interface_altsetting(intf=%d, alt=%d) 成功",
                      self._interface_number, intf.bAlternateSetting)
        except (usb.core.USBError, NotImplementedError, ValueError) as e:
            log.debug("set_interface_altsetting 失败(可忽略): %s", e)

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
            # Windows WinUSB/libusbK 下 clear_halt 可能返回 NOT_SUPPORTED(NotImplementedError)
            except (usb.core.USBError, NotImplementedError, ValueError) as e:
                log.warning("clear_halt(0x%02x) 失败(可忽略): %s", ep.bEndpointAddress, e)
        log.info("已 claim QuickTime 接口 #%d (in:0x%02x out:0x%02x)",
                 self._interface_number,
                 self._ep_in.bEndpointAddress, self._ep_out.bEndpointAddress)

    def close(self) -> None:
        self._stop.set()
        if self._dev is not None:
            try:
                usb.util.release_interface(self._dev, self._interface_number)
            except (usb.core.USBError, NotImplementedError, ValueError):
                pass
            usb.util.dispose_resources(self._dev)
            self._dev = None

    # -------------------------------------------------- 读写

    def write(self, frame: bytes) -> None:
        """写一个完整帧(帧本身已含长度前缀)。多线程安全。"""
        self._write_frame(frame, log_errors=True)

    def _write_frame(self, frame: bytes, *, log_errors: bool) -> None:
        with self._write_lock:
            try:
                n = self._ep_out.write(frame, timeout=WRITE_TIMEOUT_MS)
                log.debug("写出 %d/%d 字节 (magic=%s)", n, len(frame), frame[4:8])
            except (usb.core.USBError, NotImplementedError, ValueError) as e:
                # 写失败会导致设备收不到回复而卡死握手, 必须显式暴露
                if log_errors:
                    log.error("写 USB 失败(%d 字节 magic=%s): %s", len(frame), frame[4:8], e)
                else:
                    log.debug("探测写 USB 失败(%d 字节 magic=%s): %s", len(frame), frame[4:8], e)
                raise

    def read_loop(self, on_frame: Callable[[bytes], None]) -> None:
        """阻塞读循环, 每解出一个完整帧就调用 on_frame(frame)。

        在独立线程里跑; 调用 close() 或读超时且 _stop 置位时退出。
        """
        extractor = LengthFieldExtractor()
        timeouts = 0
        while not self._stop.is_set():
            try:
                data = self._ep_in.read(READ_SIZE, timeout=READ_TIMEOUT_MS)
            except usb.core.USBTimeoutError:
                timeouts += 1
                if self._kick_enabled and not self._saw_device_data:
                    self._kick_device(timeouts)
                elif self._kick_enabled and timeouts == 1:
                    log.debug("已收到过设备数据, 后续读超时不再发送唤醒敲门, 避免打断会话")
                # 每 3 次超时(约 6s)提示一次, 便于判断是"读不到数据"还是"读错"
                if timeouts % 3 == 0:
                    log.debug("读超时 %d 次(约 %ds 无数据), 仍在等待设备...",
                              timeouts, timeouts * READ_TIMEOUT_MS // 1000)
                continue
            except (usb.core.USBError, NotImplementedError, ValueError) as e:
                if self._stop.is_set():
                    break
                log.error("USB 读错误: %s", e)
                break
            timeouts = 0
            self._saw_device_data = True
            log.debug("读到 %d 字节", len(data))
            for frame in extractor.feed(bytes(data)):
                on_frame(frame)
        log.info("读循环退出")

    def _kick_device(self, timeouts: int) -> None:
        """读超时时唤醒设备(仅 Windows)。

        对照 C++ 参考 QuickTime.cpp:893-905: 读到 -116(超时)就发 vendor 控制
        请求(0x40,0x40,0x6400,0x6400) + 主机主动发 PING; 作者注释: 不调用会
        无限读取超时。Go 版(Linux/macOS)是被动等设备先 PING, Windows 上需主动。
        """
        try:
            self._dev.ctrl_transfer(0x40, 0x40, 0x6400, 0x6400, None)
            log.debug("唤醒敲门: 已发 vendor 复位请求 0x40/0x6400 (第 %d 次超时)", timeouts)
        except (usb.core.USBError, NotImplementedError, ValueError) as e:
            log.debug("唤醒敲门控制请求失败: %s", e)
            return
        try:
            from ..protocol.ping import new_ping_packet
            self._write_frame(new_ping_packet(), log_errors=False)
            log.debug("唤醒敲门: 已主动发送 PING")
        except (usb.core.USBError, NotImplementedError, ValueError) as e:
            log.debug("主动 PING 发送失败: %s", e)

    def stop_reading(self) -> None:
        self._stop.set()
