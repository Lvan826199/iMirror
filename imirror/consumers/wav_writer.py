"""把音频 CMSampleBuffer(LPCM 16bit 双声道 48kHz)写成 .wav 文件。

对照源码: screencapture/coremedia/wav_format.go
"""
from __future__ import annotations

import wave

from ..protocol import constants as c
from ..coremedia.cmsamplebuffer import CMSampleBuffer


class WavWriter:
    def __init__(self, path: str, sample_rate: int = 48000,
                 channels: int = 2, sample_width: int = 2) -> None:
        self._wav = wave.open(path, "wb")
        self._wav.setnchannels(channels)
        self._wav.setsampwidth(sample_width)
        self._wav.setframerate(sample_rate)

    def consume(self, buf: CMSampleBuffer) -> None:
        if buf.media_type != c.MEDIA_TYPE_SOUND or not buf.sample_data:
            return
        self._wav.writeframes(buf.sample_data)

    def stop(self) -> None:
        self._wav.close()


class CompositeConsumer:
    """把同一路回调分发给多个 consumer(如同时写 h264 + wav)。"""

    def __init__(self, *consumers) -> None:
        self._consumers = consumers

    def consume(self, buf: CMSampleBuffer) -> None:
        for consumer in self._consumers:
            consumer.consume(buf)

    def stop(self) -> None:
        for consumer in self._consumers:
            consumer.stop()
