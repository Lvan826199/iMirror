from imirror.usb import discovery
from imirror.usb.discovery import IosDevice


def _device(qt_config: int, active_config: int) -> IosDevice:
    return IosDevice(
        serial="serial",
        product_name="iPhone",
        vid=0x05AC,
        pid=0x12A8,
        usbmux_config_index=5,
        qt_config_index=qt_config,
        active_config_index=active_config,
    )


def test_qt_available_is_not_same_as_enabled():
    device = _device(qt_config=6, active_config=5)

    assert device.qt_available
    assert not device.qt_enabled


def test_qt_enabled_requires_active_qt_config():
    device = _device(qt_config=6, active_config=6)

    assert device.qt_available
    assert device.qt_enabled


class _RawDev:
    idVendor = 0x05AC
    idProduct = 0x12A8


def test_list_apple_usb_nodes_reports_ids(monkeypatch):
    monkeypatch.setattr(discovery, "usb_find", lambda **kwargs: [_RawDev()])
    monkeypatch.setattr(discovery.usb.util, "dispose_resources", lambda dev: None)

    nodes = discovery.list_apple_usb_nodes()

    assert len(nodes) == 1
    assert nodes[0].usb_id == "05ac:12a8"
