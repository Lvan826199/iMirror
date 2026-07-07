"""CMFormatDescription ("fdsc") 解析: 视频含分辨率与 SPS/PPS, 音频含 ASBD。

对照源码: screencapture/coremedia/cmformatdescription.go
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

from ..protocol import constants as c
from ..protocol.framing import parse_length_and_magic
from .asbd import AudioStreamBasicDescription

# extn 字典里 PPS/SPS 所在的 index key (Go: parses extension dict, keys 见 nalutypetable)
KEY_EXTENSION_ATOMS = 47  # extn 里嵌套的 dict, 内含 SPS(105)/PPS(106) — 以实际抓包为准


@dataclass
class FormatDescriptor:
    media_type: int = 0
    width: int = 0
    height: int = 0
    codec: int = 0
    extensions: list = field(default_factory=list)   # IndexKeyDict
    audio_description: AudioStreamBasicDescription | None = None
    # 视频专用: 从 extensions 里提取出的参数集
    pps: bytes = b""
    sps: bytes = b""

    @classmethod
    def from_bytes(cls, data: bytes) -> "FormatDescriptor":
        _, remaining = parse_length_and_magic(data, c.FORMAT_DESCRIPTOR_MAGIC)

        media_type_length, _ = parse_length_and_magic(remaining, c.MEDIA_TYPE_MAGIC)
        (media_type,) = struct.unpack_from("<I", remaining, 8)
        remaining = remaining[media_type_length:]

        fd = cls(media_type=media_type)

        if media_type == c.MEDIA_TYPE_SOUND:
            # [len]["adsb"?] 后跟 56 字节 ASBD — Go 里直接跳 8 字节头
            fd.audio_description = AudioStreamBasicDescription.from_bytes(remaining[8:])
            return fd

        # 视频: vdim + codc + extn
        vdim_length, _ = parse_length_and_magic(remaining, c.VIDEO_DIMENSION_MAGIC)
        fd.width, fd.height = struct.unpack_from("<II", remaining, 8)
        remaining = remaining[vdim_length:]

        codec_length, _ = parse_length_and_magic(remaining, c.CODEC_MAGIC)
        (fd.codec,) = struct.unpack_from("<I", remaining, 8)
        remaining = remaining[codec_length:]

        from .qtdict import parse_index_key_dict
        fd.extensions = parse_index_key_dict(remaining, root_magic=c.EXTENSION_MAGIC)
        fd.sps, fd.pps = _extract_parameter_sets(fd.extensions)
        return fd

    def __str__(self) -> str:
        if self.media_type == c.MEDIA_TYPE_SOUND:
            return f"FormatDescriptor{{audio, {self.audio_description}}}"
        return (
            f"FormatDescriptor{{video {self.width}x{self.height}, "
            f"codec:{c.magic_to_ascii(self.codec)}, sps:{len(self.sps)}B, pps:{len(self.pps)}B}}"
        )


def _extract_parameter_sets(extensions: list) -> tuple[bytes, bytes]:
    """在 extn 的嵌套 index-key dict 里递归找 avcC 风格的 SPS/PPS 数据。

    Go 版逻辑: extensions[49](avcC atom 数据)里包含 SPS/PPS。
    这里做递归扫描: 找到形如 avcC 的 datv(以 0x01 开头的 AVCDecoderConfigurationRecord)
    或者直接是裸参数集的项。写文件/解码前需要在真机数据上验证一次。
    """
    sps, pps = b"", b""
    for _key, value in _walk(extensions):
        if isinstance(value, (bytes, bytearray)) and len(value) > 7 and value[0] == 0x01:
            # AVCDecoderConfigurationRecord
            try:
                sps, pps = _parse_avcc(bytes(value))
            except (IndexError, struct.error):
                continue
    return sps, pps


def _walk(entries):
    for key, value in entries:
        if isinstance(value, list):
            yield from _walk(value)
        else:
            yield key, value


def _parse_avcc(avcc: bytes) -> tuple[bytes, bytes]:
    """解析 AVCDecoderConfigurationRecord, 返回 (sps, pps)。注意内部长度是大端。"""
    pos = 5
    num_sps = avcc[pos] & 0x1F
    pos += 1
    sps = b""
    for _ in range(num_sps):
        (l,) = struct.unpack_from(">H", avcc, pos)
        pos += 2
        sps = avcc[pos:pos + l]
        pos += l
    num_pps = avcc[pos]
    pos += 1
    pps = b""
    for _ in range(num_pps):
        (l,) = struct.unpack_from(">H", avcc, pos)
        pos += 2
        pps = avcc[pos:pos + l]
        pos += l
    return sps, pps
