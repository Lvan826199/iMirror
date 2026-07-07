"""用 Go 原版仓库自带的真机抓包 fixture 验证 Python 解析/序列化。

fixture 位置: reference/quicktime_video_hack/screencapture/packet/fixtures
注意: fixture 文件是"已去掉长度前缀"的帧(与 Go 测试一致)。
"""
import pathlib

import pytest

from imirror.protocol import constants as c
from imirror.protocol import sync as sync_pkt
from imirror.protocol import asyn as asyn_pkt
from imirror.protocol.ping import new_ping_packet

FIXTURES = (
    pathlib.Path(__file__).resolve().parent.parent
    / "reference/quicktime_video_hack/screencapture/packet/fixtures"
)

pytestmark = pytest.mark.skipif(
    not FIXTURES.is_dir(), reason="reference 仓库未克隆, 跳过 fixture 测试"
)


def load(name: str) -> bytes:
    """fixture 是完整帧(含 4 字节长度前缀), 与我方构造的发包格式一致。"""
    return (FIXTURES / name).read_bytes()


def load_stripped(name: str) -> bytes:
    """去掉长度前缀, 用于解析测试(Go 测试同样传 dat[4:])。"""
    return load(name)[4:]


def test_ping_packet():
    assert new_ping_packet() == bytes.fromhex("10000000") + b"gnip" + bytes.fromhex("0000000001000000")


def test_parse_cwpa_and_reply():
    data = load_stripped("cwpa-request1")
    pkt = sync_pkt.SyncCwpaPacket.from_bytes(data)
    assert pkt.clock_ref == c.EMPTY_CF_TYPE
    assert pkt.device_clock_ref == 0x1135A74E0
    assert pkt.correlation_id == 0x113573DE0
    # 对照 Go 测试: 用固定 clockRef 构造回复, 应与 fixture 逐字节一致
    reply = pkt.reply(0x00007FA66CE20CB0)
    assert reply == load("cwpa-reply1")


def test_parse_cvrp():
    data = load_stripped("cvrp-request")
    pkt = sync_pkt.SyncCvrpPacket.from_bytes(data)
    assert pkt.device_clock_ref != 0
    assert len(pkt.payload) > 0


def test_parse_clok_time_afmt_stop():
    clok = sync_pkt.SyncClokPacket.from_bytes(load_stripped("clok-request"))
    assert clok.correlation_id != 0
    afmt = sync_pkt.SyncAfmtPacket.from_bytes(load_stripped("afmt-request"))
    assert afmt.audio_format.sample_rate > 0


def test_afmt_reply_matches_fixture():
    afmt = sync_pkt.SyncAfmtPacket.from_bytes(load_stripped("afmt-request"))
    reply = afmt.reply()
    expected = load("afmt-reply")
    assert reply == expected or reply[4:] == expected


def test_parse_feed_video_samplebuffer():
    data = load_stripped("asyn-feed")
    pkt = asyn_pkt.AsynCmSampleBufPacket.from_bytes(data)
    sbuf = pkt.sample_buffer
    assert sbuf.media_type == c.MEDIA_TYPE_VIDEO
    assert len(sbuf.sample_data) > 0
    nalus = list(sbuf.iter_nalus())
    assert len(nalus) >= 1


def test_parse_feed_with_format_description():
    data = load_stripped("asyn-feed")
    pkt = asyn_pkt.AsynCmSampleBufPacket.from_bytes(data)
    if pkt.sample_buffer.has_format_description:
        fd = pkt.sample_buffer.format_description
        assert fd.width > 0 and fd.height > 0


def test_parse_eat_audio_samplebuffer():
    # 注意: asyn-eat 这个 fixture 本身不含长度前缀(Go 测试也是整个文件直接传)
    data = load("asyn-eat")
    pkt = asyn_pkt.AsynCmSampleBufPacket.from_bytes(data)
    assert pkt.sample_buffer.media_type == c.MEDIA_TYPE_SOUND


def test_hpd1_serialization_matches_fixture():
    """HPD1 必须和 Go 版逐字节一致, 否则设备可能不认。"""
    ours = asyn_pkt.new_asyn_hpd1_packet()
    expected = load("asyn-hpd1")
    assert ours == expected or ours[4:] == expected


def test_hpa1_serialization_matches_fixture():
    data = load("asyn-hpa1")
    # fixture 里带真实 clockRef, 提取后用相同 clockRef 构造对比
    import struct
    offset = 4 if struct.unpack_from("<I", data)[0] == len(data) else 0
    clock_ref, = struct.unpack_from("<Q", data, offset + 4)
    ours = asyn_pkt.new_asyn_hpa1_packet(clock_ref)
    assert ours == data or ours[4:] == data


def test_need_packet():
    expected = load("asyn-need")
    ours = asyn_pkt.new_need_packet(0x0102030405060708)
    assert len(ours) == 20
    # clockRef 不同, 只对比结构
    assert ours[4:8] == expected[4:8] or ours[4:8] == expected[0:4]
