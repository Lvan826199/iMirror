"""FormatDescriptor(fdsc) 解析的 fixture 测试。

fixture 已随仓库提供(tests/fixtures/coremedia, 拷贝自 Go 原版仓库, MIT 协议)。
对照 Go 测试: screencapture/coremedia/cmformatdescription_test.go
"""
import pathlib

from imirror.protocol import constants as c
from imirror.coremedia.formatdescriptor import FormatDescriptor

_ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = next(
    p for p in (
        _ROOT / "tests/fixtures/coremedia",
        _ROOT / "reference/quicktime_video_hack/screencapture/coremedia/fixtures",
    ) if p.is_dir()
)


def load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_parse_video_formatdescriptor():
    fd = FormatDescriptor.from_bytes(load("formatdescriptor.bin"))
    assert fd.media_type == c.MEDIA_TYPE_VIDEO
    assert fd.width > 0 and fd.height > 0
    assert fd.sps and fd.pps, "视频 fdsc 应能提取出 SPS/PPS"


def test_parse_audio_formatdescriptor():
    fd = FormatDescriptor.from_bytes(load("formatdescriptor-audio.bin"))
    assert fd.media_type == c.MEDIA_TYPE_SOUND
    assert fd.audio_description is not None
    assert fd.audio_description.sample_rate > 0
