"""SYNC 报文解析与 RPLY 回复构造。

对照源码: screencapture/packet/sync*.go

收到的帧(已去长度前缀)布局:
  [0:4]   "sync"
  [4:12]  clockRef (CFTypeID, u64)
  [12:16] 子类型 (cwpa/cvrp/clok/time/afmt/skew/stop/og)
  [16:24] correlationID (u64)
  [24:]   子类型相关载荷

RPLY 布局(发出, 含长度前缀):
  [len(4)]["rply"][correlationID(8)][0(4)][payload...]
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from . import constants as c
from ..coremedia.cmtime import CMTime
from ..coremedia.qtdict import parse_string_key_dict
from ..coremedia.asbd import AudioStreamBasicDescription


def parse_header(data: bytes, expected_subtype: int) -> tuple[int, int, bytes]:
    """返回 (clock_ref, correlation_id, 剩余载荷)。data 不含长度前缀。"""
    magic, = struct.unpack_from("<I", data)
    if magic != c.SYNC_MAGIC:
        raise ValueError(f"不是 SYNC 包: {data[:4]!r}")
    clock_ref, = struct.unpack_from("<Q", data, 4)
    subtype, = struct.unpack_from("<I", data, 12)
    if subtype != expected_subtype:
        raise ValueError(f"子类型不匹配: 期望 {c.magic_to_ascii(expected_subtype)}, "
                         f"实际 {data[12:16]!r}")
    correlation_id, = struct.unpack_from("<Q", data, 16)
    return clock_ref, correlation_id, data[24:]


def clock_ref_reply(clock_ref: int, correlation_id: int) -> bytes:
    """通用回复: 告诉设备我们创建的时钟 ID。总长 28 字节(含长度前缀)。"""
    return struct.pack("<IIQIQ", 28, c.RPLY_MAGIC, correlation_id, 0, clock_ref)


def empty_reply(correlation_id: int) -> bytes:
    """OG/STOP 使用的简单回复: [len]["rply"][correlationID][0(8字节)], 总长 24。"""
    return struct.pack("<IIQQ", 24, c.RPLY_MAGIC, correlation_id, 0)


@dataclass
class SyncCwpaPacket:
    """音频时钟握手。回复 clockRef 后设备开始 EAT 音频流。"""
    clock_ref: int
    correlation_id: int
    device_clock_ref: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncCwpaPacket":
        clock_ref, correlation_id, rest = parse_header(data, c.CWPA)
        if clock_ref != c.EMPTY_CF_TYPE:
            raise ValueError(f"CWPA 的 clockRef 应为空 CFType, 实际 {clock_ref:x}")
        device_clock_ref, = struct.unpack_from("<Q", rest)
        return cls(clock_ref, correlation_id, device_clock_ref)

    def reply(self, clock_ref: int) -> bytes:
        return clock_ref_reply(clock_ref, self.correlation_id)


@dataclass
class SyncCvrpPacket:
    """视频时钟握手。载荷是一个参数字典(含 FormatDescription)。"""
    clock_ref: int
    correlation_id: int
    device_clock_ref: int
    payload: list = field(default_factory=list)

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncCvrpPacket":
        clock_ref, correlation_id, rest = parse_header(data, c.CVRP)
        device_clock_ref, = struct.unpack_from("<Q", rest)
        payload = parse_string_key_dict(rest[8:])
        return cls(clock_ref, correlation_id, device_clock_ref, payload)

    def reply(self, clock_ref: int) -> bytes:
        return clock_ref_reply(clock_ref, self.correlation_id)


@dataclass
class SyncClokPacket:
    clock_ref: int
    correlation_id: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncClokPacket":
        clock_ref, correlation_id, _ = parse_header(data, c.CLOK)
        return cls(clock_ref, correlation_id)

    def reply(self, clock_ref: int) -> bytes:
        return clock_ref_reply(clock_ref, self.correlation_id)


@dataclass
class SyncTimePacket:
    clock_ref: int
    correlation_id: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncTimePacket":
        clock_ref, correlation_id, _ = parse_header(data, c.TIME)
        return cls(clock_ref, correlation_id)

    def reply(self, time: CMTime) -> bytes:
        payload = time.serialize()
        return (
            struct.pack("<IIQI", 20 + len(payload), c.RPLY_MAGIC, self.correlation_id, 0)
            + payload
        )


@dataclass
class SyncAfmtPacket:
    """设备通告音频格式(ASBD)。回复一个 Error:0 字典表示接受。"""
    clock_ref: int
    correlation_id: int
    audio_format: AudioStreamBasicDescription

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncAfmtPacket":
        clock_ref, correlation_id, rest = parse_header(data, c.AFMT)
        return cls(clock_ref, correlation_id, AudioStreamBasicDescription.from_bytes(rest))

    def reply(self) -> bytes:
        from ..coremedia.nsnumber import NSNumber
        from ..coremedia.qtdict import serialize_string_key_dict
        dict_bytes = serialize_string_key_dict([("Error", NSNumber.from_uint32(0))])
        return (
            struct.pack("<IIQI", 20 + len(dict_bytes), c.RPLY_MAGIC, self.correlation_id, 0)
            + dict_bytes
        )


@dataclass
class SyncSkewPacket:
    clock_ref: int
    correlation_id: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncSkewPacket":
        clock_ref, correlation_id, _ = parse_header(data, c.SKEW)
        return cls(clock_ref, correlation_id)

    def reply(self, skew: float) -> bytes:
        return struct.pack("<IIQId", 28, c.RPLY_MAGIC, self.correlation_id, 0, skew)


@dataclass
class SyncStopPacket:
    clock_ref: int
    correlation_id: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncStopPacket":
        clock_ref, correlation_id, _ = parse_header(data, c.STOP)
        return cls(clock_ref, correlation_id)

    def reply(self) -> bytes:
        return empty_reply(self.correlation_id)


@dataclass
class SyncOgPacket:
    clock_ref: int
    correlation_id: int

    @classmethod
    def from_bytes(cls, data: bytes) -> "SyncOgPacket":
        clock_ref, correlation_id, _ = parse_header(data, c.OG)
        return cls(clock_ref, correlation_id)

    def reply(self) -> bytes:
        return empty_reply(self.correlation_id)
