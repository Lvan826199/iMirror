"""CMClock: 本地单调时钟, 用于回答设备的 TIME/SKEW 查询。

对照源码: screencapture/coremedia/cmclock.go
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .cmtime import CMTime, KCMTIME_FLAGS_HAS_BEEN_ROUNDED, NANO_SECOND_SCALE


@dataclass
class CMClock:
    clock_id: int
    timescale: int = NANO_SECOND_SCALE
    start_ns: int = field(default_factory=time.monotonic_ns)

    def get_time(self) -> CMTime:
        elapsed = time.monotonic_ns() - self.start_ns
        # timescale 为纳秒时直接用 elapsed; 其他 timescale 按比例折算
        if self.timescale != NANO_SECOND_SCALE:
            elapsed = elapsed * self.timescale // NANO_SECOND_SCALE
        return CMTime(
            value=elapsed,
            timescale=self.timescale,
            flags=KCMTIME_FLAGS_HAS_BEEN_ROUNDED,
            epoch=0,
        )


def calculate_skew(start_local: CMTime, end_local: CMTime,
                   start_device: CMTime, end_device: CMTime) -> float:
    """音频时钟偏差 = 设备时钟速率相对本地时钟的比值 * 采样率。

    对照 cmclock.go 的 CalculateSkew。
    """
    diff_local = end_local.value - start_local.value
    diff_device = end_device.value - start_device.value
    if diff_device == 0:
        return float(start_device.timescale)
    scaled = diff_local * start_device.timescale / start_local.timescale
    return start_device.timescale * (scaled / diff_device)
