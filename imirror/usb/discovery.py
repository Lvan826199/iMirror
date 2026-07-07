"""用 pyusb 枚举 iOS 设备, 检测 QuickTime 隐藏配置是否已激活。

对照源码: screencapture/discovery.go

判定规则:
  - Apple 设备 VID = 0x05AC(足够筛选 iPhone/iPad, 精确匹配用序列号)
  - usbmux 配置:    某 interface 的 class=0xFF(Vendor Specific), subclass=0xFE
  - QuickTime 配置: 某 interface 的 class=0xFF, subclass=0x2A
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import usb.core
import usb.util

log = logging.getLogger(__name__)

APPLE_VID = 0x05AC
CLASS_VENDOR_SPECIFIC = 0xFF
SUBCLASS_USBMUX = 0xFE   # gousb.ClassApplication 在此上下文即 0xFE? 以真机验证为准
SUBCLASS_QUICKTIME = 0x2A


@dataclass
class IosDevice:
    serial: str
    product_name: str
    vid: int
    pid: int
    usbmux_config_index: int   # bConfigurationValue
    qt_config_index: int       # -1 表示 QT 配置未激活(需要先发激活控制请求)

    @property
    def qt_enabled(self) -> bool:
        return self.qt_config_index != -1


def find_ios_devices() -> list[IosDevice]:
    devices = []
    for dev in usb.core.find(find_all=True, idVendor=APPLE_VID):
        try:
            info = _inspect(dev)
        except (usb.core.USBError, ValueError) as e:
            log.warning("检查设备 %04x:%04x 失败: %s", dev.idVendor, dev.idProduct, e)
            continue
        finally:
            usb.util.dispose_resources(dev)
        if info is not None:
            devices.append(info)
    return devices


def open_by_serial(serial: str) -> usb.core.Device:
    for dev in usb.core.find(find_all=True, idVendor=APPLE_VID):
        try:
            if usb.util.get_string(dev, dev.iSerialNumber) == serial:
                return dev
        except usb.core.USBError:
            pass
        usb.util.dispose_resources(dev)
    raise RuntimeError(f"未找到序列号为 {serial} 的设备")


def _inspect(dev: usb.core.Device) -> IosDevice | None:
    muxconfig, qtconfig = -1, -1
    for cfg in dev:
        for intf in cfg:
            if intf.bInterfaceClass != CLASS_VENDOR_SPECIFIC:
                continue
            if intf.bInterfaceSubClass == SUBCLASS_USBMUX:
                muxconfig = cfg.bConfigurationValue
            elif intf.bInterfaceSubClass == SUBCLASS_QUICKTIME:
                qtconfig = cfg.bConfigurationValue
    if muxconfig == -1 and qtconfig == -1:
        return None  # 不是 iOS 设备(如 Apple 键盘)
    serial = usb.util.get_string(dev, dev.iSerialNumber) or ""
    product = usb.util.get_string(dev, dev.iProduct) or ""
    return IosDevice(
        serial=serial, product_name=product,
        vid=dev.idVendor, pid=dev.idProduct,
        usbmux_config_index=muxconfig, qt_config_index=qtconfig,
    )
