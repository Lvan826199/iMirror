"""CMTime / CMSampleTimingInfo 二进制结构。

对照源码: screencapture/coremedia/cmtime.go
布局(小端): value(u64) + timescale(u32) + flags(u32) + epoch(u64) = 24 字节
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

CMTIME_LENGTH = 24

KCMTIME_FLAGS_VALID = 0x0
KCMTIME_FLAGS_HAS_BEEN_ROUNDED = 0x1
KCMTIME_FLAGS_POSITIVE_INFINITY = 0x2
KCMTIME_FLAGS_NEGATIVE_INFINITY = 0x4
KCMTIME_FLAGS_INDEFINITE = 0x8

NANO_SECOND_SCALE = 1_000_000_000


@dataclass
class CMTime:
    value: int = 0
    timescale: int = 0
    flags: int = 0
    epoch: int = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "CMTime":
        value, timescale, flags, epoch = struct.unpack_from("<QIIQ", data)
        return cls(value, timescale, flags, epoch)

    def serialize(self) -> bytes:
        return struct.pack("<QIIQ", self.value, self.timescale, self.flags, self.epoch)

    def seconds(self) -> float:
        if self.value == 0 or self.timescale == 0:
            return 0.0
        return self.value / self.timescale

    def get_time_for_scale(self, new_scale: "CMTime") -> float:
        factor = new_scale.timescale / self.timescale
        return self.value * factor

    def __str__(self) -> str:
        return f"CMTime{{{self.value}/{self.timescale}, flags:{self.flags:x}, epoch:{self.epoch}}}"


@dataclass
class CMSampleTimingInfo:
    """stia 数组的元素: 3 个连续 CMTime, 共 72 字节。"""

    duration: CMTime
    presentation_timestamp: CMTime
    decode_timestamp: CMTime

    LENGTH = 3 * CMTIME_LENGTH

    @classmethod
    def from_bytes(cls, data: bytes) -> "CMSampleTimingInfo":
        return cls(
            duration=CMTime.from_bytes(data),
            presentation_timestamp=CMTime.from_bytes(data[CMTIME_LENGTH:]),
            decode_timestamp=CMTime.from_bytes(data[2 * CMTIME_LENGTH:]),
        )
