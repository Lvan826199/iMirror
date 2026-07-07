"""AudioStreamBasicDescription (56 字节小端结构体)。

对照源码: screencapture/coremedia/audio_stream_basic_description.go
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

from ..protocol.constants import AUDIO_FORMAT_ID_LPCM

_FMT = "<dIIIIIIII"  # SampleRate(f64) FormatID FormatFlags BytesPerPacket FramesPerPacket BytesPerFrame ChannelsPerFrame BitsPerChannel Reserved
LENGTH = struct.calcsize(_FMT)  # 40? -> 实际 8 + 8*4 = 40; Go 里 buffer 是 56, 尾部有填充
SERIALIZED_LENGTH = 56


@dataclass
class AudioStreamBasicDescription:
    sample_rate: float = 48000.0
    format_id: int = AUDIO_FORMAT_ID_LPCM
    format_flags: int = 12
    bytes_per_packet: int = 4
    frames_per_packet: int = 1
    bytes_per_frame: int = 4
    channels_per_frame: int = 2
    bits_per_channel: int = 16
    reserved: int = 0

    @classmethod
    def from_bytes(cls, data: bytes) -> "AudioStreamBasicDescription":
        fields = struct.unpack_from(_FMT, data)
        return cls(*fields)

    def serialize(self) -> bytes:
        packed = struct.pack(
            _FMT,
            self.sample_rate, self.format_id, self.format_flags,
            self.bytes_per_packet, self.frames_per_packet, self.bytes_per_frame,
            self.channels_per_frame, self.bits_per_channel, self.reserved,
        )
        # Go 版序列化到 56 字节: 40 字节结构体后再写两遍 SampleRate(f64)
        return packed + struct.pack("<dd", self.sample_rate, self.sample_rate)
