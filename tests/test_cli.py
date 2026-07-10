import pytest

from imirror import cli
from imirror.usb.discovery import IosDevice


def _device(serial: str, product: str = "iPhone") -> IosDevice:
    return IosDevice(
        serial=serial,
        product_name=product,
        vid=0x05AC,
        pid=0x12A8,
        usbmux_config_index=1,
        qt_config_index=5,
        active_config_index=5,
    )


def test_pick_device_requires_udid_when_multiple_devices(monkeypatch):
    monkeypatch.setattr(
        "imirror.usb.discovery.find_ios_devices",
        lambda: [_device("serial-a"), _device("serial-b", "iPad")],
    )

    with pytest.raises(SystemExit) as exc:
        cli._pick_device(None, need_qt=False)

    message = str(exc.value)
    assert "发现多台 iOS 设备" in message
    assert "serial-a" in message
    assert "serial-b" in message


def test_main_prints_runtime_error_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(cli, "cmd_devices", lambda args: (_ for _ in ()).throw(RuntimeError("boom")))

    rc = cli.main(["devices"])

    assert rc == 1
    assert capsys.readouterr().out == "错误: boom\n"
