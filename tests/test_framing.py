"""分帧器单元测试(不依赖 fixture)。"""
import struct

from imirror.protocol.framing import LengthFieldExtractor, add_length_prefix


def make_frame(payload: bytes) -> bytes:
    return struct.pack("<I", len(payload) + 4) + payload


def test_single_frame():
    ex = LengthFieldExtractor()
    frames = list(ex.feed(make_frame(b"hello")))
    assert frames == [b"hello"]


def test_split_across_reads():
    ex = LengthFieldExtractor()
    frame = make_frame(b"0123456789")
    assert list(ex.feed(frame[:3])) == []
    assert list(ex.feed(frame[3:7])) == []
    assert list(ex.feed(frame[7:])) == [b"0123456789"]


def test_multiple_frames_one_read():
    ex = LengthFieldExtractor()
    data = make_frame(b"aa") + make_frame(b"bbb") + make_frame(b"")
    assert list(ex.feed(data)) == [b"aa", b"bbb", b""]


def test_add_length_prefix_roundtrip():
    ex = LengthFieldExtractor()
    assert list(ex.feed(add_length_prefix(b"xyz"))) == [b"xyz"]
