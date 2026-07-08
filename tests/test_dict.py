"""字典解析/序列化的 fixture 测试。

fixture 已随仓库提供(tests/fixtures/coremedia, 拷贝自 Go 原版仓库, MIT 协议)。
"""
import pathlib

from imirror.coremedia.qtdict import (
    parse_string_key_dict,
    parse_index_key_dict,
    serialize_string_key_dict,
)

_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = next(
    p for p in (
        _ROOT / "tests/fixtures/coremedia",
        _ROOT / "reference/quicktime_video_hack/screencapture/coremedia/fixtures",
    ) if p.is_dir()
)


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parse_simple_dict():
    entries = parse_string_key_dict(load("dict.bin"))
    assert len(entries) > 0
    keys = [k for k, _ in entries]
    assert all(isinstance(k, str) for k in keys)


def test_parse_complex_dict():
    entries = parse_string_key_dict(load("complex_dict.bin"))
    assert len(entries) > 0


def test_parse_int_dict():
    entries = parse_index_key_dict(load("intdict.bin"))
    assert all(isinstance(k, int) for k, _ in entries)


def test_roundtrip_serialize():
    """serialize_dict.bin 是 Go 序列化器的期望输出, 解析->再序列化应逐字节一致。"""
    raw = load("serialize_dict.bin")
    entries = parse_string_key_dict(raw)
    assert serialize_string_key_dict(entries) == raw
