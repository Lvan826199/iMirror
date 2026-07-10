from imirror.usb import activation
from imirror.usb.discovery import IosDevice


class _FakeDevice:
    def __init__(self):
        self.ctrl_calls = []

    def ctrl_transfer(self, bm_request_type, b_request, w_value, w_index, data_or_w_length):
        self.ctrl_calls.append((bm_request_type, b_request, w_value, w_index, data_or_w_length))
        return 0


def _qt_enabled_device() -> IosDevice:
    return IosDevice(
        serial="serial",
        product_name="iPhone",
        vid=0x05AC,
        pid=0x12A8,
        usbmux_config_index=1,
        qt_config_index=5,
        active_config_index=5,
    )


def test_enable_qt_config_skips_already_enabled_without_force(monkeypatch):
    device = _qt_enabled_device()
    fake = _FakeDevice()
    monkeypatch.setattr(activation, "open_by_serial", lambda serial: fake)
    monkeypatch.setattr(activation.usb.util, "dispose_resources", lambda dev: None)

    assert activation.enable_qt_config(device) is device
    assert fake.ctrl_calls == []


def test_enable_qt_config_force_rearms_already_enabled(monkeypatch):
    device = _qt_enabled_device()
    fake = _FakeDevice()
    monkeypatch.setattr(activation, "open_by_serial", lambda serial: fake)
    monkeypatch.setattr(activation, "_inspect", lambda dev: device)
    monkeypatch.setattr(activation.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(activation.usb.util, "dispose_resources", lambda dev: None)

    result = activation.enable_qt_config(device, force_rearm=True)

    assert result == device
    assert fake.ctrl_calls == [(
        activation.REQUEST_TYPE_VENDOR_OUT,
        activation.REQUEST_QT_CONFIG,
        0,
        activation.INDEX_ENABLE,
        b"",
    )]
