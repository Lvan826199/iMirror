"""CMSampleBuffer ("sbuf") 解析 —— FEED(视频)/EAT(音频) 的载荷。

对照源码: screencapture/coremedia/cmsamplebuf.go
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..protocol import constants as c
from ..protocol.framing import parse_length_and_magic
from .cmtime import CMTime, CMSampleTimingInfo
from .formatdescriptor import FormatDescriptor


@dataclass
class CMSampleBuffer:
    media_type: int
    output_presentation_timestamp: CMTime = field(default_factory=CMTime)
    sample_timing_info: list = field(default_factory=list)   # list[CMSampleTimingInfo]
    sample_data: bytes = b""      # 视频: AVCC 格式 NALU([4字节大端长度][NALU])*; 音频: PCM
    num_samples: int = 0
    sample_sizes: list = field(default_factory=list)
    has_format_description: bool = False
    format_description: FormatDescriptor | None = None
    attachments: list = field(default_factory=list)
    sary: list = field(default_factory=list)

    @classmethod
    def from_bytes(cls, data: bytes, media_type: int) -> "CMSampleBuffer":
        sbuf = cls(media_type=media_type)
        length, remaining = parse_length_and_magic(data, c.SBUF)
        if length > len(data):
            raise ValueError(f"sbuf 声明 {length} 字节, 缓冲区只有 {len(data)}")

        from .qtdict import parse_index_key_dict

        while len(remaining) > 0:
            (chunk_len, magic) = struct.unpack_from("<II", remaining)
            if magic == c.OPTS:
                sbuf.output_presentation_timestamp = CMTime.from_bytes(remaining[8:])
                remaining = remaining[8 + 24:]
            elif magic == c.STIA:
                body_len = chunk_len - 8
                if body_len % CMSampleTimingInfo.LENGTH != 0:
                    raise ValueError(f"stia 长度非法: {body_len}")
                body = remaining[8:chunk_len]
                sbuf.sample_timing_info = [
                    CMSampleTimingInfo.from_bytes(body[i:])
                    for i in range(0, body_len, CMSampleTimingInfo.LENGTH)
                ]
                remaining = remaining[chunk_len:]
            elif magic == c.SDAT:
                sbuf.sample_data = bytes(remaining[8:chunk_len])
                remaining = remaining[chunk_len:]
            elif magic == c.NSMP:
                if chunk_len != 12:
                    raise ValueError(f"nsmp 长度应为 12, 实际 {chunk_len}")
                (sbuf.num_samples,) = struct.unpack_from("<I", remaining, 8)
                remaining = remaining[chunk_len:]
            elif magic == c.SSIZ:
                body_len = chunk_len - 8
                if body_len % 4 != 0:
                    raise ValueError(f"ssiz 长度非法: {body_len}")
                sbuf.sample_sizes = list(
                    struct.unpack_from(f"<{body_len // 4}I", remaining, 8)
                )
                remaining = remaining[chunk_len:]
            elif magic == c.FORMAT_DESCRIPTOR_MAGIC:
                sbuf.has_format_description = True
                sbuf.format_description = FormatDescriptor.from_bytes(remaining[:chunk_len])
                remaining = remaining[chunk_len:]
            elif magic == c.SATT:
                sbuf.attachments = parse_index_key_dict(remaining[:chunk_len], root_magic=c.SATT)
                remaining = remaining[chunk_len:]
            elif magic == c.SARY:
                # sary 是 [len]["sary"] 后跟一个完整 dict
                sbuf.sary = parse_index_key_dict(remaining[8:chunk_len])
                remaining = remaining[chunk_len:]
            else:
                raise ValueError(
                    f"sbuf 内未知块: {remaining[4:8]!r} (0x{magic:08x})"
                )
        return sbuf

    def iter_nalus(self):
        """迭代 sample_data 里的 NALU(AVCC: 4 字节大端长度前缀)。仅视频有效。"""
        data = self.sample_data
        pos = 0
        while pos + 4 <= len(data):
            (length,) = struct.unpack_from(">I", data, pos)
            pos += 4
            yield data[pos:pos + length]
            pos += length

    def __str__(self) -> str:
        kind = "video" if self.media_type == c.MEDIA_TYPE_VIDEO else "audio"
        return (
            f"CMSampleBuffer{{{kind}, pts:{self.output_presentation_timestamp}, "
            f"data:{len(self.sample_data)}B, fdsc:{self.has_format_description}}}"
        )
