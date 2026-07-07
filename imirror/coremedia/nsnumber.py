"""NSNumber 的二进制编码: 1 字节类型 + 数值。

对照源码: screencapture/common/nsnumber.go
类型: 0x03=uint32(4B) 0x04=uint64(8B) 0x05=uint32(4B, 仅解析) 0x06=float64(8B)
"""
from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass
class NSNumber:
    type_specifier: int
    value: float | int

    @classmethod
    def from_uint32(cls, v: int) -> "NSNumber":
        return cls(3, v)

    @classmethod
    def from_uint64(cls, v: int) -> "NSNumber":
        return cls(4, v)

    @classmethod
    def from_float64(cls, v: float) -> "NSNumber":
        return cls(6, v)

    @classmethod
    def from_bytes(cls, data: bytes) -> "NSNumber":
        t = data[0]
        if t == 6:
            return cls(6, struct.unpack_from("<d", data, 1)[0])
        if t == 5:
            return cls(5, struct.unpack_from("<I", data, 1)[0])
        if t == 4:
            return cls(4, struct.unpack_from("<Q", data, 1)[0])
        if t == 3:
            return cls(3, struct.unpack_from("<I", data, 1)[0])
        raise ValueError(f"未知 NSNumber 类型 {t}: {data.hex()}")

    def to_bytes(self) -> bytes:
        if self.type_specifier == 6:
            return struct.pack("<Bd", 6, self.value)
        if self.type_specifier == 4:
            return struct.pack("<BQ", 4, self.value)
        if self.type_specifier in (3, 5):
            return struct.pack("<BI", self.type_specifier, self.value)
        raise ValueError(f"无法序列化 NSNumber 类型 {self.type_specifier}")
