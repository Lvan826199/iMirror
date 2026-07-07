"""PING 报文。对照源码: screencapture/packet/ping.go"""
import struct

from . import constants as c

PING_LENGTH = 16
PING_HEADER = 0x0000000100000000


def new_ping_packet() -> bytes:
    """构造发给设备的完整 PING 帧(含长度前缀), 收到设备 PING 时原样回复即可。"""
    return struct.pack("<IIQ", PING_LENGTH, c.PING_MAGIC, PING_HEADER)
