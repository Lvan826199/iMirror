"""ASYN 报文解析与构造。

对照源码: screencapture/packet/asyn*.go

收到的帧(已去长度前缀)布局:
  [0:4]   "asyn"
  [4:12]  clockRef (u64)
  [12:16] 子类型 (feed/eat!/sprp/tjmp/srat/tbas/rels)
  [16:]   载荷
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from . import constants as c
from ..coremedia.cmsamplebuffer import CMSampleBuffer
from ..coremedia.nsnumber import NSNumber
from ..coremedia.qtdict import serialize_string_key_dict
from ..coremedia.asbd import AudioStreamBasicDescription


def parse_header(data: bytes, expected_subtype: int) -> tuple[int, bytes]:
    """返回 (clock_ref, 剩余载荷)。"""
    magic, = struct.unpack_from("<I", data)
    if magic != c.ASYN_MAGIC:
        raise ValueError(f"不是 ASYN 包: {data[:4]!r}")
    clock_ref, = struct.unpack_from("<Q", data, 4)
    subtype, = struct.unpack_from("<I", data, 12)
    if subtype != expected_subtype:
        raise ValueError(f"子类型不匹配: 期望 {c.magic_to_ascii(expected_subtype)}, "
                         f"实际 {data[12:16]!r}")
    return clock_ref, data[16:]


def get_subtype(data: bytes) -> int:
    return struct.unpack_from("<I", data, 12)[0]


# ---------------------------------------------------------------- 收包

@dataclass
class AsynCmSampleBufPacket:
    """FEED(视频)或 EAT(音频), 载荷是 CMSampleBuffer。"""
    clock_ref: int
    sample_buffer: CMSampleBuffer

    @classmethod
    def from_bytes(cls, data: bytes) -> "AsynCmSampleBufPacket":
        subtype = get_subtype(data)
        if subtype == c.FEED:
            clock_ref, rest = parse_header(data, c.FEED)
            media_type = c.MEDIA_TYPE_VIDEO
        elif subtype == c.EAT:
            clock_ref, rest = parse_header(data, c.EAT)
            media_type = c.MEDIA_TYPE_SOUND
        else:
            raise ValueError(f"不是 FEED/EAT: {data[12:16]!r}")
        return cls(clock_ref, CMSampleBuffer.from_bytes(rest, media_type))


# ---------------------------------------------------------------- 发包

def new_need_packet(device_clock_ref: int) -> bytes:
    """流控包: 每消费一个 FEED 必须回一个 NEED, 设备才继续发帧。总长 20 字节。"""
    return struct.pack("<IIQI", 20, c.ASYN_MAGIC, device_clock_ref, c.NEED)


def _new_dict_packet(entries: list, subtype: int, clock_ref: int) -> bytes:
    dict_bytes = serialize_string_key_dict(entries)
    header = struct.pack("<IIQI", 20 + len(dict_bytes), c.ASYN_MAGIC, clock_ref, subtype)
    return header + dict_bytes


def new_asyn_hpd1_packet() -> bytes:
    """通告设备端视频参数(在 CWPA 握手时发送, 需发两次)。"""
    return _new_dict_packet(create_hpd1_device_info_dict(), c.HPD1, c.EMPTY_CF_TYPE)


def new_asyn_hpa1_packet(device_clock_ref: int) -> bytes:
    """通告设备端音频参数。"""
    return _new_dict_packet(create_hpa1_device_info_dict(), c.HPA1, device_clock_ref)


def new_asyn_hpd0_packet() -> bytes:
    """请求设备停止视频流。"""
    return struct.pack("<IIQI", 20, c.ASYN_MAGIC, c.EMPTY_CF_TYPE, c.HPD0)


def new_asyn_hpa0_packet(clock_ref: int) -> bytes:
    """请求设备停止音频流。"""
    return struct.pack("<IIQI", 20, c.ASYN_MAGIC, clock_ref, c.HPA0)


def create_hpd1_device_info_dict() -> list:
    """对照 packet/asyn.go CreateHpd1DeviceInfoDict, 序列化结果必须逐字节一致
    (可用 reference 里的 fixture asyn-hpd1 验证)。"""
    return [
        ("Valeria", True),
        ("HEVCDecoderSupports444", True),
        ("DisplaySize", [
            ("Width", NSNumber.from_float64(1920.0)),
            ("Height", NSNumber.from_float64(1200.0)),
        ]),
    ]


def create_hpa1_device_info_dict() -> list:
    """对照 packet/asyn.go CreateHpa1DeviceInfoDict (fixture: asyn-hpa1)。"""
    asbd_bytes = AudioStreamBasicDescription().serialize()
    return [
        ("BufferAheadInterval", NSNumber.from_float64(0.07300000000000001)),
        ("deviceUID", "Valeria"),
        ("ScreenLatency", NSNumber.from_float64(0.04)),
        ("formats", asbd_bytes),
        ("EDIDAC3Support", NSNumber.from_uint32(0)),
        ("deviceName", "Valeria"),
    ]
