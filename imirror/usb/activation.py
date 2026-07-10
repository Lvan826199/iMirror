"""激活/关闭 iOS 设备的隐藏 QuickTime USB 配置。

对照源码: screencapture/activator.go

激活 = 发送 vendor 控制请求 (bmRequestType=0x40, bRequest=0x52, wValue=0, wIndex=2)。
设备会断开并以新配置重新枚举(多出一对 bulk 端点), 所以发送后要轮询等它回来。
"""
from __future__ import annotations

import logging
import sys
import time

import usb.core
import usb.util

from .discovery import IosDevice, find_ios_devices, open_by_serial, _inspect

log = logging.getLogger(__name__)

REQUEST_TYPE_VENDOR_OUT = 0x40
REQUEST_QT_CONFIG = 0x52
INDEX_ENABLE = 2
INDEX_DISABLE = 0


def enable_qt_config(device: IosDevice, retries: int = 30, force_rearm: bool = False) -> IosDevice:
    """激活 QuickTime 配置, 返回重新枚举后的设备信息。"""
    dev = open_by_serial(device.serial)
    try:
        if device.qt_enabled and not force_rearm:
            log.debug("%s 的 QT 配置已是活动配置 #%d, 跳过", device.serial, device.qt_config_index)
            return device
        if device.qt_enabled and force_rearm:
            log.debug("%s 已在 QT 配置 #%d, 强制重发激活请求以重新武装会话",
                      device.serial, device.qt_config_index)
            _request_qt_enable(dev, log_disconnect=True)
        elif device.qt_available and sys.platform == "win32":
            # Windows 上直接 set_configuration 能把 active config 切到 QT, 但不总能重新
            # 武装 QuickTime/Valeria 会话。优先走 Apple vendor enable, 让设备按原始
            # 激活路径重枚举并从会话起点重新发 PING。
            log.debug(
                "%s 已暴露 QT 配置 #%d, 当前活动配置是 #%d; Windows 优先重发 QT 激活请求",
                device.serial, device.qt_config_index, device.active_config_index,
            )
            if not _request_qt_enable(dev, log_disconnect=False):
                e = _request_qt_enable.last_error
                log.warning("QT 激活控制请求失败: %s — 回退到 set_configuration(%d)",
                            e, device.qt_config_index)
                try:
                    dev.set_configuration(device.qt_config_index)
                except (usb.core.USBError, NotImplementedError, ValueError) as e2:
                    log.debug("set_configuration 回退也失败: %s", e2)
        elif device.qt_available:
            log.debug(
                "%s 已暴露 QT 配置 #%d, 但当前活动配置是 #%d, 尝试直接切换配置",
                device.serial, device.qt_config_index, device.active_config_index,
            )
            try:
                dev.set_configuration(device.qt_config_index)
            except (usb.core.USBError, NotImplementedError, ValueError) as e:
                log.warning("set_configuration(%d) 失败: %s — 改发 QT 激活控制请求",
                            device.qt_config_index, e)
                _request_qt_enable(dev, log_disconnect=True)
        else:
            _request_qt_enable(dev, log_disconnect=True)
    finally:
        usb.util.dispose_resources(dev)

    for i in range(retries):
        time.sleep(0.5)
        try:
            dev = open_by_serial(device.serial)
        except RuntimeError:
            continue
        try:
            info = _inspect(dev)
        finally:
            usb.util.dispose_resources(dev)
        if info is not None and info.qt_enabled:
            log.info("%s QT 配置已激活 (config #%d)", info.serial, info.qt_config_index)
            time.sleep(1.0)
            return info
    hint = ""
    if sys.platform == "win32":
        hint = ("\nWindows 常见原因: 激活后设备以新形态重新枚举, Windows 给它派了默认驱动。"
                "\n自救: 保持手机连接, 重新打开 Zadig(勾 List All Devices、取消勾 Ignore Hubs"
                "\n      or Composite Parents), 给新出现的 iPhone 条目再换一次 libusb-win32,"
                "\n      然后跑 doctor 应显示 QT配置: 已激活。详见 docs/真机联调手册.md")
    raise RuntimeError(f"无法为 {device.serial} 激活 QuickTime 配置{hint}")


def _request_qt_enable(dev, *, log_disconnect: bool) -> bool:
    _request_qt_enable.last_error = None
    try:
        dev.ctrl_transfer(REQUEST_TYPE_VENDOR_OUT, REQUEST_QT_CONFIG, 0, INDEX_ENABLE, b"")
        return True
    except (usb.core.USBError, NotImplementedError, ValueError) as e:
        _request_qt_enable.last_error = e
        if log_disconnect:
            # 设备收到请求后可能立即断开, 这里报 pipe error/no device 是正常现象
            log.debug("激活请求后设备断开(正常): %s", e)
        return False


_request_qt_enable.last_error = None


def disable_qt_config(device: IosDevice) -> None:
    dev = open_by_serial(device.serial)
    try:
        dev.ctrl_transfer(REQUEST_TYPE_VENDOR_OUT, REQUEST_QT_CONFIG, 0, INDEX_DISABLE, b"")
        if device.usbmux_config_index != -1:
            dev.set_configuration(device.usbmux_config_index)
    except (usb.core.USBError, NotImplementedError, ValueError) as e:
        log.debug("关闭 QT 配置时设备断开(正常): %s", e)
    finally:
        usb.util.dispose_resources(dev)


def reset_usb_device(device: IosDevice, retries: int = 30) -> IosDevice:
    """对 USB 设备发 reset 并等待重新枚举。

    macOS 上 reset 常以 USBError(Entity not found) 返回, 但设备已经开始重新枚举；
    因此这里把该错误当成可恢复状态, 后续以重新发现设备为准。
    """
    dev = open_by_serial(device.serial)
    try:
        try:
            dev.reset()
            log.info("%s USB reset 已发出", device.serial)
        except (usb.core.USBError, NotImplementedError, ValueError) as e:
            log.debug("USB reset 后设备断开/重枚举(正常): %s", e)
    finally:
        usb.util.dispose_resources(dev)

    last_info: IosDevice | None = None
    for _ in range(retries):
        time.sleep(0.5)
        try:
            dev = open_by_serial(device.serial)
        except RuntimeError:
            continue
        try:
            info = _inspect(dev)
        finally:
            usb.util.dispose_resources(dev)
        if info is None:
            continue
        last_info = info
        if info.active_config_index != -1:
            log.info("%s USB reset 后已重新枚举 (active #%d)", info.serial, info.active_config_index)
            return info
    if last_info is not None:
        for _ in range(6):
            time.sleep(0.5)
            for info in find_ios_devices():
                if info.serial == device.serial:
                    if info.active_config_index != -1:
                        log.info("%s USB reset 后已稳定 (active #%d)",
                                 info.serial, info.active_config_index)
                        return info
                    last_info = info
        log.debug("%s 已重新枚举, 但 active config 暂不可读", last_info.serial)
        return last_info
    raise RuntimeError(f"USB reset 后未重新发现设备 {device.serial}")
