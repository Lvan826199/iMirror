"""消息处理状态机: 驱动整个 QuickTime 采集会话。

对照源码: screencapture/messageprocessor.go

会话流程(设备主动发起, 我们只需正确应答):
  1. 设备发 PING          -> 回 PING
  2. SYNC OG              -> 回空 RPLY
  3. SYNC CWPA(音频时钟)   -> 发 2 次 ASYN HPD1, 回 CWPA-RPLY(deviceClockRef+1000), 发 ASYN HPA1
  4. ASYN SPRP/TBAS/SRAT/TJMP 等 -> 仅记录
  5. SYNC CVRP(视频时钟)   -> 发 ASYN NEED, 回 CVRP-RPLY(deviceClockRef+0x1000AF)
  6. SYNC CLOK/TIME/AFMT/SKEW    -> 按各自格式回复
  7. ASYN FEED(视频帧)     -> 交给 consumer, 并回 NEED 请求下一帧
     ASYN EAT!(音频帧)     -> 交给 consumer
  8. 关闭: 发 HPA0/HPD0, 等设备发 ASYN RELS
"""
from __future__ import annotations

import logging
import struct
import threading
from typing import Callable, Protocol

from .protocol import constants as c
from .protocol import sync as sync_pkt
from .protocol import asyn as asyn_pkt
from .protocol.ping import new_ping_packet
from .coremedia.cmclock import CMClock, calculate_skew
from .coremedia.cmtime import CMTime
from .coremedia.cmsamplebuffer import CMSampleBuffer

log = logging.getLogger(__name__)


class Consumer(Protocol):
    """音视频消费者接口。"""

    def consume(self, buf: CMSampleBuffer) -> None: ...
    def stop(self) -> None: ...


class MessageProcessor:
    def __init__(self, write_to_usb: Callable[[bytes], None], consumer: Consumer,
                 stop_callback: Callable[[], None] | None = None) -> None:
        self._write = write_to_usb
        self._consumer = consumer
        self._stop_callback = stop_callback or (lambda: None)

        self._local_audio_clock: CMClock | None = None
        self._device_audio_clock_ref = 0
        self._clock: CMClock | None = None
        self._need_clock_ref = 0
        self._need_message = b""

        self._first_audio_time_taken = False
        self._start_local = CMTime()
        self._start_device = CMTime()
        self._last_local = CMTime()
        self._last_device = CMTime()

        self._video_count = 0
        self._audio_count = 0
        self._video_bytes = 0
        self._audio_bytes = 0
        # 计数信号量: 两个 RELS 可能到得很快, Event 会丢第二次(Go 用阻塞 channel 同样不丢)
        self._release_sem = threading.Semaphore(0)

    @property
    def stats(self) -> dict:
        """当前会话统计(供 CLI 周期性展示)。"""
        return {
            "video_frames": self._video_count,
            "audio_frames": self._audio_count,
            "video_bytes": self._video_bytes,
            "audio_bytes": self._audio_bytes,
        }

    # -------------------------------------------------- 入口

    def receive_frame(self, frame: bytes) -> None:
        """处理一个完整协议帧(不含长度前缀)。"""
        magic, = struct.unpack_from("<I", frame)
        if magic == c.PING_MAGIC:
            log.info("收到 PING, 回复 PING")
            self._write(new_ping_packet())
        elif magic == c.SYNC_MAGIC:
            self._handle_sync(frame)
        elif magic == c.ASYN_MAGIC:
            self._handle_asyn(frame)
        else:
            log.warning("未知包类型: %s", frame[:4])
            self._stop_callback()

    # -------------------------------------------------- SYNC

    def _handle_sync(self, frame: bytes) -> None:
        subtype, = struct.unpack_from("<I", frame, 12)
        if subtype == c.OG:
            pkt = sync_pkt.SyncOgPacket.from_bytes(frame)
            self._write(pkt.reply())
        elif subtype == c.CWPA:
            pkt = sync_pkt.SyncCwpaPacket.from_bytes(frame)
            clock_ref = pkt.device_clock_ref + 1000
            self._local_audio_clock = CMClock(clock_ref)
            self._device_audio_clock_ref = pkt.device_clock_ref
            device_info = asyn_pkt.new_asyn_hpd1_packet()
            log.debug("发送 ASYN HPD1 x2")
            self._write(device_info)
            self._write(device_info)
            log.debug("回复 CWPA clockRef=%x", clock_ref)
            self._write(pkt.reply(clock_ref))
            log.debug("发送 ASYN HPA1")
            self._write(asyn_pkt.new_asyn_hpa1_packet(pkt.device_clock_ref))
        elif subtype == c.CVRP:
            pkt = sync_pkt.SyncCvrpPacket.from_bytes(frame)
            self._need_clock_ref = pkt.device_clock_ref
            self._need_message = asyn_pkt.new_need_packet(self._need_clock_ref)
            log.debug("发送首个 NEED, clockRef=%x", self._need_clock_ref)
            self._write(self._need_message)
            self._write(pkt.reply(pkt.device_clock_ref + 0x1000AF))
        elif subtype == c.CLOK:
            pkt = sync_pkt.SyncClokPacket.from_bytes(frame)
            clock_ref = pkt.clock_ref + 0x10000
            self._clock = CMClock(clock_ref)
            self._write(pkt.reply(clock_ref))
        elif subtype == c.TIME:
            pkt = sync_pkt.SyncTimePacket.from_bytes(frame)
            assert self._clock is not None, "TIME 请求先于 CLOK 到达"
            self._write(pkt.reply(self._clock.get_time()))
        elif subtype == c.AFMT:
            pkt = sync_pkt.SyncAfmtPacket.from_bytes(frame)
            log.info("音频格式: %s", pkt.audio_format)
            self._write(pkt.reply())
        elif subtype == c.SKEW:
            pkt = sync_pkt.SyncSkewPacket.from_bytes(frame)
            skew = calculate_skew(self._start_local, self._last_local,
                                  self._start_device, self._last_device)
            self._write(pkt.reply(skew))
        elif subtype == c.STOP:
            pkt = sync_pkt.SyncStopPacket.from_bytes(frame)
            self._write(pkt.reply())
        else:
            log.warning("未知 SYNC 子类型: %s", frame[12:16])
            self._stop_callback()

    # -------------------------------------------------- ASYN

    def _handle_asyn(self, frame: bytes) -> None:
        subtype, = struct.unpack_from("<I", frame, 12)
        if subtype == c.FEED:
            try:
                pkt = asyn_pkt.AsynCmSampleBufPacket.from_bytes(frame)
            except ValueError as e:
                log.error("解析 FEED 失败: %s", e)
                self._write(self._need_message)
                return
            self._video_count += 1
            self._video_bytes += len(pkt.sample_buffer.sample_data)
            self._consumer.consume(pkt.sample_buffer)
            if self._video_count % 500 == 0:
                log.debug("已收视频帧 %d, 最后一帧: %s", self._video_count, pkt.sample_buffer)
            self._write(self._need_message)
        elif subtype == c.EAT:
            try:
                pkt = asyn_pkt.AsynCmSampleBufPacket.from_bytes(frame)
            except ValueError as e:
                log.warning("解析 EAT 失败: %s", e)
                return
            self._audio_count += 1
            self._audio_bytes += len(pkt.sample_buffer.sample_data)
            self._track_audio_clock(pkt.sample_buffer)
            self._consumer.consume(pkt.sample_buffer)
        elif subtype in (c.SPRP, c.TJMP, c.SRAT, c.TBAS):
            log.debug("收到 ASYN %s (忽略)", c.magic_to_ascii(subtype))
        elif subtype == c.RELS:
            log.debug("收到 ASYN RELS")
            self._release_sem.release()
        else:
            log.warning("未知 ASYN 子类型: %s", frame[12:16])
            self._stop_callback()

    def _track_audio_clock(self, buf: CMSampleBuffer) -> None:
        assert self._local_audio_clock is not None
        if not self._first_audio_time_taken:
            self._start_device = buf.output_presentation_timestamp
            self._start_local = self._local_audio_clock.get_time()
            self._first_audio_time_taken = True
        self._last_device = buf.output_presentation_timestamp
        self._last_local = self._local_audio_clock.get_time()

    # -------------------------------------------------- 关闭

    def close_session(self, timeout: float = 3.0) -> None:
        """通知设备停止推流。

        对照 Go CloseSession (messageprocessor.go): HPA0/HPD0 背靠背发出,
        等 2 次 RELS(每次最多 timeout 秒, 超时直接放弃), 收齐后结尾再补发一次 HPD0。
        """
        log.info("请求设备停止推流...")
        self._write(asyn_pkt.new_asyn_hpa0_packet(self._device_audio_clock_ref))
        self._write(asyn_pkt.new_asyn_hpd0_packet())
        for _ in range(2):
            if not self._release_sem.acquire(timeout=timeout):
                log.warning("等待设备 RELS 超时")
                break
        else:
            self._write(asyn_pkt.new_asyn_hpd0_packet())
        self._consumer.stop()
        log.info("会话已关闭 (视频帧:%d 音频帧:%d)", self._video_count, self._audio_count)
