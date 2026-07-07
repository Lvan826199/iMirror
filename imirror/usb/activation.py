"""激活/关闭 iOS 设备的隐藏 QuickTime USB 配置。

对照源码: screencapture/activator.go

激活 = 发送 vendor 控制请求 (bmRequestType=0x40, bRequest=0x52, wValue=0, wIndex=2)。
设备会断开并以新配置重新枚举(多出一对 bulk 端点), 所以发送后要轮询等它回来。
"""
from __future__ import annotations

import logging
import time

import usb.core
import usb.util

from .discovery import IosDevice, open_by_serial, _inspect

log = logging.getLogger(__name__)

REQUEST_TYPE_VENDOR_OUT = 0x40
REQUEST_QT_CONFIG = 0x52
INDEX_ENABLE = 2
INDEX_DISABLE = 0


def enable_qt_config(device: IosDevice, retries: int = 10) -> IosDevice:
    """激活 QuickTime 配置, 返回重新枚举后的设备信息。"""
    dev = open_by_serial(device.serial)
    try:
        if device.qt_enabled:
            log.debug("%s 的 QT 配置已激活, 跳过", device.serial)
            return device
        try:
            dev.ctrl_transfer(REQUEST_TYPE_VENDOR_OUT, REQUEST_QT_CONFIG, 0, INDEX_ENABLE, b"")
        except usb.core.USBError as e:
            # 设备收到请求后立即断开, 这里报 pipe error/no device 是正常现象
            log.debug("激活请求后设备断开(正常): %s", e)
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
            return info
    raise RuntimeError(f"无法为 {device.serial} 激活 QuickTime 配置")


def disable_qt_config(device: IosDevice) -> None:
    dev = open_by_serial(device.serial)
    try:
        dev.ctrl_transfer(REQUEST_TYPE_VENDOR_OUT, REQUEST_QT_CONFIG, 0, INDEX_DISABLE, b"")
        if device.usbmux_config_index != -1:
            dev.set_configuration(device.usbmux_config_index)
    except usb.core.USBError as e:
        log.debug("关闭 QT 配置时设备断开(正常): %s", e)
    finally:
        usb.util.dispose_resources(dev)
