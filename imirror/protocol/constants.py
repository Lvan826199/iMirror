"""QuickTime 屏幕采集协议的所有 magic 常量。

所有多字节整数一律小端（little-endian）。四字符 magic 以 uint32 小端存储，
所以在原始字节流里看到的是反序 ASCII（例如 "ping" 在线上是 b"gnip"）。

对照源码: reference/quicktime_video_hack/screencapture/packet/{ping,sync,asyn}.go
"""

# ---- 顶层包类型 ----
PING_MAGIC = 0x70696E67   # "ping"
SYNC_MAGIC = 0x73796E63   # "sync" 设备发起、需要回复（带 correlationID）
RPLY_MAGIC = 0x72706C79   # "rply" 我们对 SYNC 的回复
ASYN_MAGIC = 0x6173796E   # "asyn" 单向消息，无需回复

# ---- SYNC 子类型 ----
OG   = 0x676F2120  # "go! " 会话开始
CWPA = 0x63777061  # Clock Walltime Anchor(音频时钟握手, 收到后要发 HPD1/HPA1)
AFMT = 0x61666D74  # Audio Format
CVRP = 0x63767270  # 视频时钟握手, 回复后开始收 FEED
CLOK = 0x636C6F6B  # 设备要求我们创建一个时钟
TIME = 0x74696D65  # 设备查询我们时钟的当前时间
SKEW = 0x736B6577  # 音频时钟偏差查询
STOP = 0x73746F70  # 停止

# ---- ASYN 子类型 ----
FEED = 0x66656564  # "feed" 视频帧: 内含 CMSampleBuffer(H.264 NALU)
EAT  = 0x65617421  # "eat!" 音频帧: 内含 CMSampleBuffer(PCM)
SPRP = 0x73707270  # Set Property
TJMP = 0x746A6D70  # Time Jump
SRAT = 0x73726174  # SetRateAndAnchorTime
TBAS = 0x74626173  # TimeBase
RELS = 0x72656C73  # Release(关闭会话时设备发来)
HPD1 = 0x68706431  # 主机->设备: 视频参数字典
HPA1 = 0x68706131  # 主机->设备: 音频参数字典
HPD0 = 0x68706430  # 主机->设备: 关闭视频
HPA0 = 0x68706130  # 主机->设备: 关闭音频
NEED = 0x6E656564  # 主机->设备: 请求下一帧(流控, 每收到一个 FEED 就要回一个 NEED)

# ---- 序列化字典 (dict.go) ----
DICT_MAGIC           = 0x64696374  # "dict"
KEY_VALUE_PAIR_MAGIC = 0x6B657976  # "keyv"
STRING_KEY_MAGIC     = 0x7374726B  # "strk"
INT_KEY_MAGIC        = 0x6964786B  # "idxk"
BOOL_VALUE_MAGIC     = 0x62756C76  # "bulv"
DATA_VALUE_MAGIC     = 0x64617476  # "datv"
STRING_VALUE_MAGIC   = 0x73747276  # "strv"
NUMBER_VALUE_MAGIC   = 0x6E6D6276  # "nmbv"

# ---- CMFormatDescription (cmformatdescription.go) ----
FORMAT_DESCRIPTOR_MAGIC = 0x66647363  # "fdsc"
MEDIA_TYPE_MAGIC        = 0x6D646961  # "mdia"
MEDIA_TYPE_VIDEO        = 0x76696465  # "vide"
MEDIA_TYPE_SOUND        = 0x736F756E  # "soun"
VIDEO_DIMENSION_MAGIC   = 0x7664696D  # "vdim"
CODEC_MAGIC             = 0x636F6463  # "codc"
CODEC_AVC1              = 0x61766331  # "avc1" H.264
EXTENSION_MAGIC         = 0x6578746E  # "extn"

# ---- CMSampleBuffer 内部块 (cmsamplebuf.go) ----
SBUF = 0x73627566  # "sbuf" 外层容器
OPTS = 0x6F707473  # "opts" OutputPresentationTimestamp (CMTime)
STIA = 0x73746961  # "stia" SampleTimingInfoArray (每项 3 个 CMTime: duration/pts/dts)
SDAT = 0x73646174  # "sdat" 载荷: 视频为 AVCC 格式 NALU, 音频为 PCM
SATT = 0x73617474  # "satt" SampleAttachments (index-key dict)
SARY = 0x73617279  # "sary" 附加 dict
SSIZ = 0x7373697A  # "ssiz" sample size 数组(uint32 each)
NSMP = 0x6E736D70  # "nsmp" num samples (uint32)

# ---- 其他 ----
EMPTY_CF_TYPE = 1  # 空 CFTypeID
AUDIO_FORMAT_ID_LPCM = 0x6C70636D  # "lpcm"


def magic_to_ascii(magic: int) -> str:
    """把 uint32 magic 还原成可读的四字符串, 用于日志。"""
    try:
        return magic.to_bytes(4, "big").decode("ascii", errors="replace")
    except (OverflowError, ValueError):
        return f"0x{magic:08x}"
