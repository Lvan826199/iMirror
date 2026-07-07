"""QuickTime 协议的序列化字典(dict/keyv/strk/idxk/...)解析与序列化。

对照源码: screencapture/coremedia/dict.go 与 dict_serializer.go

结构(全部小端, length 均含 8 字节头):
  dict  := [len]["dict"] entry*
  entry := [len]["keyv"] key value
  key   := [len]["strk"] utf8  |  [len]["idxk"] uint16
  value := [len]["strv"] utf8
         | [len]["datv"] bytes
         | [len]["bulv"] u8
         | [len]["nmbv"] NSNumber
         | dict                       (嵌套)
         | [len]["fdsc"] ...          (FormatDescriptor, 见 formatdescriptor.py)
"""
from __future__ import annotations

import struct
from typing import Any

from ..protocol import constants as c
from ..protocol.framing import parse_length_and_magic
from .nsnumber import NSNumber

# 值为 (key, value) 列表而非 Python dict, 保持顺序且允许重复 key —— 序列化需逐字节一致
StringKeyDict = list  # list[tuple[str, Any]]
IndexKeyDict = list   # list[tuple[int, Any]]


# ---------------------------------------------------------------- 解析

def parse_string_key_dict(data: bytes, root_magic: int = c.DICT_MAGIC) -> StringKeyDict:
    length, _ = parse_length_and_magic(data, root_magic)
    return _parse_entries(data[8:length], string_keys=True)


def parse_index_key_dict(data: bytes, root_magic: int = c.DICT_MAGIC) -> IndexKeyDict:
    length, _ = parse_length_and_magic(data, root_magic)
    return _parse_entries(data[8:length], string_keys=False)


def _parse_entries(data: bytes, string_keys: bool) -> list:
    entries = []
    while len(data) > 0:
        pair_length, _ = parse_length_and_magic(data, c.KEY_VALUE_PAIR_MAGIC)
        pair = data[8:pair_length]
        key, rest = _parse_key(pair, string_keys)
        value = _parse_value(rest)
        entries.append((key, value))
        data = data[pair_length:]
    return entries


def _parse_key(data: bytes, string_key: bool):
    if string_key:
        key_length, _ = parse_length_and_magic(data, c.STRING_KEY_MAGIC)
        return data[8:key_length].decode("utf-8"), data[key_length:]
    key_length, _ = parse_length_and_magic(data, c.INT_KEY_MAGIC)
    (key,) = struct.unpack_from("<H", data, 8)
    return key, data[key_length:]


def _parse_value(data: bytes) -> Any:
    length, magic = struct.unpack_from("<II", data)
    body = data[8:length]
    if magic == c.STRING_VALUE_MAGIC:
        return body.decode("utf-8")
    if magic == c.DATA_VALUE_MAGIC:
        return bytes(body)
    if magic == c.BOOL_VALUE_MAGIC:
        return body[0] == 1
    if magic == c.NUMBER_VALUE_MAGIC:
        return NSNumber.from_bytes(body)
    if magic == c.DICT_MAGIC:
        # 嵌套 dict: 先按 string key 试, 失败再按 index key
        try:
            return parse_string_key_dict(data[:length])
        except ValueError:
            return parse_index_key_dict(data[:length])
    if magic == c.FORMAT_DESCRIPTOR_MAGIC:
        from .formatdescriptor import FormatDescriptor
        return FormatDescriptor.from_bytes(data[:length])
    raise ValueError(f"未知的 value magic: {data[4:8]!r} (0x{magic:08x})")


# ---------------------------------------------------------------- 序列化

def serialize_string_key_dict(entries: StringKeyDict) -> bytes:
    body = b"".join(_serialize_entry(k, v) for k, v in entries)
    return struct.pack("<II", len(body) + 8, c.DICT_MAGIC) + body


def _serialize_entry(key: str, value: Any) -> bytes:
    key_bytes = _serialize_string_key(key)
    value_bytes = _serialize_value(value)
    body = key_bytes + value_bytes
    return struct.pack("<II", len(body) + 8, c.KEY_VALUE_PAIR_MAGIC) + body


def _serialize_string_key(key: str) -> bytes:
    raw = key.encode("utf-8")
    return struct.pack("<II", len(raw) + 8, c.STRING_KEY_MAGIC) + raw


def _serialize_value(value: Any) -> bytes:
    if isinstance(value, bool):
        return struct.pack("<IIB", 9, c.BOOL_VALUE_MAGIC, 1 if value else 0)
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return struct.pack("<II", len(raw) + 8, c.STRING_VALUE_MAGIC) + raw
    if isinstance(value, (bytes, bytearray)):
        return struct.pack("<II", len(value) + 8, c.DATA_VALUE_MAGIC) + bytes(value)
    if isinstance(value, NSNumber):
        raw = value.to_bytes()
        return struct.pack("<II", len(raw) + 8, c.NUMBER_VALUE_MAGIC) + raw
    if isinstance(value, list):
        return serialize_string_key_dict(value)
    raise TypeError(f"无法序列化类型 {type(value)}: {value!r}")
