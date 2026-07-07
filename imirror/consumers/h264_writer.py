"""把视频 CMSampleBuffer 写成 Annex-B .h264 裸流文件(可用 ffplay/VLC 直接播放)。

对照源码: screencapture/coremedia/avfilewriter.go

设备发来的 NALU 是 AVCC 格式(4 字节大端长度前缀), 写文件/喂解码器前要:
  1. 首帧前先写 SPS/PPS(来自 FormatDescription), 用 Annex-B 起始码 00 00 00 01
  2. 每个 NALU 的长度前缀替换为起始码
音频 buffer 直接跳过(交给 wav_writer)。
"""
from __future__ import annotations

import logging
from typing import BinaryIO

from ..protocol import constants as c
from ..coremedia.cmsamplebuffer import CMSampleBuffer

log = logging.getLogger(__name__)

START_CODE = b"\x00\x00\x00\x01"


class H264Writer:
    def __init__(self, fh: BinaryIO) -> None:
        self._fh = fh
        self._params_written = False

    def consume(self, buf: CMSampleBuffer) -> None:
        if buf.media_type != c.MEDIA_TYPE_VIDEO:
            return
        if buf.has_format_description and buf.format_description is not None:
            fd = buf.format_description
            if fd.sps and fd.pps:
                self._fh.write(START_CODE + fd.sps)
                self._fh.write(START_CODE + fd.pps)
                self._params_written = True
                log.info("写入参数集: %s", fd)
        if not buf.sample_data:
            return
        if not self._params_written:
            # 没有 SPS/PPS 之前写裸帧解码器无法启动, 丢弃
            return
        for nalu in buf.iter_nalus():
            self._fh.write(START_CODE + nalu)

    def stop(self) -> None:
        self._fh.flush()
