"""实时预览: PyAV 解码 H.264 -> OpenCV 窗口显示。

采集线程(USB 读) -> 帧队列 -> 解码/显示主线程。
依赖: pip install av opencv-python
"""
from __future__ import annotations

import logging
import queue
import threading

log = logging.getLogger(__name__)


class DecodingConsumer:
    """把视频 NALU 转成 Annex-B 塞进队列, 供解码线程消费。"""

    def __init__(self, nalu_queue: "queue.Queue[bytes]") -> None:
        self._queue = nalu_queue
        self._params = b""

    def consume(self, buf) -> None:
        from ..protocol import constants as c
        if buf.media_type != c.MEDIA_TYPE_VIDEO:
            return
        start = b"\x00\x00\x00\x01"
        chunk = b""
        if buf.has_format_description and buf.format_description:
            fd = buf.format_description
            if fd.sps and fd.pps:
                self._params = start + fd.sps + start + fd.pps
                chunk += self._params
        for nalu in buf.iter_nalus():
            chunk += start + nalu
        if chunk:
            try:
                self._queue.put_nowait(chunk)
            except queue.Full:
                pass  # 显示端跟不上就丢帧, 保持低延迟

    def stop(self) -> None:
        pass


def run_viewer(udid: str | None) -> int:
    import av
    import cv2

    from ..usb.adapter import UsbAdapter
    from ..session import MessageProcessor
    from .. import cli

    device = cli._pick_device(udid, need_qt=True)

    nalu_queue: "queue.Queue[bytes]" = queue.Queue(maxsize=60)
    consumer = DecodingConsumer(nalu_queue)

    adapter = UsbAdapter(device)
    adapter.open()
    processor = MessageProcessor(adapter.write, consumer,
                                 stop_callback=adapter.stop_reading)
    reader = threading.Thread(
        target=adapter.read_loop, args=(processor.receive_frame,), daemon=True
    )
    reader.start()

    codec = av.CodecContext.create("h264", "r")
    window = f"iMirror - {device.product_name or device.serial}"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    try:
        while True:
            try:
                chunk = nalu_queue.get(timeout=1.0)
            except queue.Empty:
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
                continue
            for packet in codec.parse(chunk):
                for frame in codec.decode(packet):
                    img = frame.to_ndarray(format="bgr24")
                    cv2.imshow(window, img)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    except KeyboardInterrupt:
        pass
    finally:
        processor.close_session()
        adapter.close()
        cv2.destroyAllWindows()
    return 0
