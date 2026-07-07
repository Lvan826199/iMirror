"""USB bulk 流的分帧: 每帧 = 4 字节小端长度(含自身) + 载荷。

对照源码: screencapture/usbadapter.go (frame extractor) 与 common/util.go
"""
from __future__ import annotations

import struct
from typing import Iterator


class LengthFieldExtractor:
    """把 USB bulk 端点读到的字节流切成完整的协议帧(去掉 4 字节长度前缀)。

    USB 读到的数据块边界和协议帧边界不一致, 需要缓冲拼接。
    """

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> Iterator[bytes]:
        """喂入一块 USB 读到的原始数据, 产出零个或多个完整帧(不含长度前缀)。"""
        self._buf.extend(data)
        while len(self._buf) >= 4:
            (length,) = struct.unpack_from("<I", self._buf)
            if length < 4:
                raise ValueError(f"非法帧长度 {length}")
            if len(self._buf) < length:
                return
            frame = bytes(self._buf[4:length])
            del self._buf[:length]
            yield frame


def parse_length_and_magic(data: bytes, expected_magic: int) -> tuple[int, bytes]:
    """解析 [length(4)][magic(4)] 头, 校验 magic, 返回 (length, 剩余字节)。

    对应 Go 的 common.ParseLengthAndMagic。注意 length 含头部 8 字节。
    """
    length, magic = struct.unpack_from("<II", data)
    if length > len(data):
        raise ValueError(f"数据不足: 声明 {length} 字节, 实际只有 {len(data)}")
    if magic != expected_magic:
        raise ValueError(
            f"magic 不匹配: 期望 0x{expected_magic:08x}, 实际 0x{magic:08x} "
            f"({data[4:8]!r})"
        )
    return length, data[8:]


def write_length_and_magic(length: int, magic: int) -> bytes:
    return struct.pack("<II", length, magic)


def add_length_prefix(payload: bytes) -> bytes:
    """给要写回设备的帧加 4 字节长度前缀(长度含前缀本身)。"""
    return struct.pack("<I", len(payload) + 4) + payload
