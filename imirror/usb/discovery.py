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


def usb_find(**kwargs):
    """优先用 libusb-package 自带的 libusb 后端(Windows 免装 dll), 否则走 pyusb 默认查找。"""
    try:
        import libusb_package
        return libusb_package.find(**kwargs)
    except ImportError:
        return usb.core.find(**kwargs)


@dataclass
class IosDevice:
    serial: str
    product_name: str
    vid: int
    pid: int
    usbmux_config_index: int   # bConfigurationValue
    qt_config_index: int       # -1 表示没有暴露 QT 配置描述符
    active_config_index: int   # 当前活动 bConfigurationValue, -1 表示无法读取

    @property
    def qt_available(self) -> bool:
        """是否能在配置描述符里看到 QuickTime/Valeria 接口。"""
        return self.qt_config_index != -1

    @property
    def qt_enabled(self) -> bool:
        """QuickTime/Valeria 配置是否就是当前活动 USB 配置。"""
        return self.qt_available and self.active_config_index == self.qt_config_index


def find_ios_devices() -> list[IosDevice]:
    devices = []
    for dev in usb_find(find_all=True, idVendor=APPLE_VID):
        try:
            info = _inspect(dev)
        except (usb.core.USBError, NotImplementedError, ValueError) as e:
            # 复合设备子接口/未换驱动的设备读不了描述符是常态, 只在 DEBUG 级记录
            log.debug("检查设备 %04x:%04x 失败: %s", dev.idVendor, dev.idProduct, e)
            continue
        finally:
            usb.util.dispose_resources(dev)
        if info is not None:
            devices.append(info)
    return devices


def clean_str(s: str | None) -> str:
    """iPhone 的 USB 字符串描述符常带 NUL 填充(打印不可见但比较不相等), 统一清洗。"""
    return (s or "").replace("\x00", "").strip()


def open_by_serial(serial: str) -> usb.core.Device:
    for dev in usb_find(find_all=True, idVendor=APPLE_VID):
        try:
            if clean_str(usb.util.get_string(dev, dev.iSerialNumber)) == serial:
                return dev
        except (usb.core.USBError, NotImplementedError, ValueError):
            # ValueError(no langid): Windows 未换驱动/Linux 无权限时读不了字符串描述符
            pass
        usb.util.dispose_resources(dev)
    raise RuntimeError(f"未找到序列号为 {serial} 的设备")


def _inspect(dev: usb.core.Device) -> IosDevice | None:
    muxconfig, qtconfig = -1, -1
    active_config = -1
    try:
        active_config = dev.get_active_configuration().bConfigurationValue
    except (usb.core.USBError, NotImplementedError, ValueError) as e:
        log.debug("读取活动配置失败: %s", e)
    for cfg in dev:
        has_mux = False
        has_qt = False
        for intf in cfg:
            if intf.bInterfaceClass != CLASS_VENDOR_SPECIFIC:
                continue
            if intf.bInterfaceSubClass == SUBCLASS_USBMUX:
                has_mux = True
            elif intf.bInterfaceSubClass == SUBCLASS_QUICKTIME:
                has_qt = True
        if has_mux and not has_qt:
            muxconfig = cfg.bConfigurationValue
        if has_qt:
            qtconfig = cfg.bConfigurationValue
    if muxconfig == -1 and qtconfig == -1:
        return None  # 不是 iOS 设备(如 Apple 键盘)
    serial = clean_str(usb.util.get_string(dev, dev.iSerialNumber))
    product = clean_str(usb.util.get_string(dev, dev.iProduct))
    return IosDevice(
        serial=serial, product_name=product,
        vid=dev.idVendor, pid=dev.idProduct,
        usbmux_config_index=muxconfig, qt_config_index=qtconfig,
        active_config_index=active_config,
    )
