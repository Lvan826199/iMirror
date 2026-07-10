import logging
import threading

import usb.core

from imirror.protocol.ping import new_ping_packet
from imirror.usb.adapter import UsbAdapter, WRITE_TIMEOUT_MS


class _FakeOutEndpoint:
    def __init__(self):
        self.calls = []

    def write(self, frame, timeout=None):
        self.calls.append((bytes(frame), timeout))
        return len(frame)


class _TimeoutOutEndpoint:
    def __init__(self):
        self.calls = []

    def write(self, frame, timeout=None):
        self.calls.append((bytes(frame), timeout))
        raise usb.core.USBTimeoutError("timed out")


class _FakeDevice:
    def __init__(self):
        self.ctrl_calls = []

    def ctrl_transfer(self, bm_request_type, b_request, w_value, w_index, data_or_w_length):
        self.ctrl_calls.append((bm_request_type, b_request, w_value, w_index, data_or_w_length))
        return 0


def _adapter_with(ep_out, dev=None):
    adapter = object.__new__(UsbAdapter)
    adapter._write_lock = threading.Lock()
    adapter._ep_out = ep_out
    adapter._dev = dev
    return adapter


def test_usb_write_uses_explicit_timeout():
    ep_out = _FakeOutEndpoint()
    adapter = _adapter_with(ep_out)
    frame = b"\x08\x00\x00\x00test"

    adapter.write(frame)

    assert ep_out.calls == [(frame, WRITE_TIMEOUT_MS)]


def test_windows_kick_ping_write_timeout_is_debug_probe(caplog):
    dev = _FakeDevice()
    ep_out = _TimeoutOutEndpoint()
    adapter = _adapter_with(ep_out, dev)

    caplog.set_level(logging.ERROR)
    adapter._kick_device(timeouts=1)

    assert dev.ctrl_calls == [(0x40, 0x40, 0x6400, 0x6400, None)]
    assert ep_out.calls == [(new_ping_packet(), WRITE_TIMEOUT_MS)]
    assert not caplog.records
