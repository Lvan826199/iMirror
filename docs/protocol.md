# QuickTime 屏幕采集协议速查

对照源码全部在 `reference/quicktime_video_hack/screencapture/`，以下为移植时整理的要点。
所有多字节整数**小端**；四字符 magic 按 uint32 小端存储（线上字节是反序 ASCII）。

## 1. USB 层

- Apple VID = `0x05AC`。iOS 设备有一个隐藏的 USB 配置，含 class `0xFF`/subclass `0x2A` 的接口和一对 bulk 端点。
- 激活: `ctrl_transfer(bmRequestType=0x40, bRequest=0x52, wValue=0, wIndex=2)` → 设备断开重枚举。
- 关闭: 同上但 `wIndex=0`。
- claim 接口后对两个 bulk 端点做 `CLEAR_FEATURE(HALT)`（Go: `Control(0x02, 0x01, 0, epAddr)`，pyusb 用 `dev.clear_halt`）。
- usbmux 配置的接口是 class `0xFF`/subclass `0xFE`（用于判断"这是台 iOS 设备"）。

## 2. 分帧

bulk in 流 = 连续的帧：`[u32 长度(含自身4字节)][载荷]`。载荷首 4 字节是包类型 magic。

## 3. 包类型

### PING `70696E67`
16 字节整帧: `[10 00 00 00]["gnip"][00 00 00 00 01 00 00 00]`。收到即原样回。

### SYNC `73796E63`（设备问，必须答）
```
[0:4] "sync"  [4:12] clockRef(u64)  [12:16] 子类型  [16:24] correlationID  [24:] 载荷
```
回复 RPLY: `[u32 len]["rply"][correlationID(u64)][u32 0][payload]`

| 子类型 | 含义 | 回复 payload |
|---|---|---|
| OG `676F2120` | 会话开始 | 8 字节 0（总长 24）|
| CWPA `63777061` | 音频时钟握手，载荷=deviceClockRef | 我方 clockRef = deviceClockRef **+1000**（总长 28）。回复前先发 2 次 ASYN HPD1，回复后发 ASYN HPA1 |
| AFMT `61666D74` | 音频格式(56B ASBD) | 序列化字典 `{"Error": NSNumber(u32 0)}` |
| CVRP `63767270` | 视频时钟握手，载荷=deviceClockRef+参数dict(含fdsc) | 我方 clockRef = deviceClockRef **+0x1000AF**。回复前先发首个 ASYN NEED |
| CLOK `636C6F6B` | 要求建时钟 | 我方 clockRef = 请求 clockRef **+0x10000**（此后 TIME 查询用它）|
| TIME `74696D65` | 查询时钟 | 24 字节 CMTime（总长 44）|
| SKEW `736B6577` | 音频时钟偏差 | f64（总长 28），公式见 cmclock.go CalculateSkew |
| STOP `73746F70` | 停止 | 8 字节 0（总长 24）|

### ASYN `6173796E`（单向）
```
[0:4] "asyn"  [4:12] clockRef(u64)  [12:16] 子类型  [16:] 载荷
```

| 子类型 | 方向 | 含义 |
|---|---|---|
| FEED `66656564` | 设备→主机 | 视频帧 CMSampleBuffer。**消费后必须回 NEED**，否则设备停发 |
| EAT! `65617421` | 设备→主机 | 音频帧 CMSampleBuffer (LPCM) |
| NEED `6E656564` | 主机→设备 | 20 字节: `[14 00 00 00]["nysa"][cvrp的deviceClockRef]["deen"]` |
| HPD1 `68706431` | 主机→设备 | 视频参数 dict（clockRef=EmptyCFType=1）: Valeria=true, HEVCDecoderSupports444=true, DisplaySize{Width:1920.0,Height:1200.0} |
| HPA1 `68706131` | 主机→设备 | 音频参数 dict（clockRef=CWPA 的 deviceClockRef）|
| HPD0/HPA0 | 主机→设备 | 停视频/停音频（20 字节，无载荷）|
| SPRP/TJMP/SRAT/TBAS | 设备→主机 | 属性/时间基调整，可只记日志 |
| RELS `72656C73` | 设备→主机 | 对 HPx0 的确认，收齐后会话结束 |

## 4. 序列化字典

```
dict  := [len]["dict"] entry*          (len 均含 8 字节头)
entry := [len]["keyv"] key value
key   := [len]["strk"] utf8 | [len]["idxk"] u16
value := [len]["strv"] utf8 | [len]["datv"] bytes | [len]["bulv"] u8
       | [len]["nmbv"] NSNumber | dict | [len]["fdsc"] ...
NSNumber := 类型u8 + 值 (0x03:u32, 0x04:u64, 0x05:u32, 0x06:f64)
```

## 5. CMSampleBuffer ("sbuf")

外层 `[len]["sbuf"]`，内部为连续 tagged 块（顺序不固定）：

| 块 | 内容 |
|---|---|
| opts | 24B CMTime（OutputPresentationTimestamp）|
| stia | CMSampleTimingInfo 数组（每项 3×CMTime=72B: duration/pts/dts）|
| sdat | 载荷。视频=AVCC NALU（4字节**大端**长度前缀）；音频=PCM |
| nsmp | u32 样本数（块总长恒 12）|
| ssiz | u32 数组，各样本字节数 |
| fdsc | FormatDescription：mdia(vide/soun) + vdim(w,h) + codc(avc1) + extn(嵌套dict，含SPS/PPS) |
| satt | attachments（index-key dict，root magic 就是 "satt"）|
| sary | `[len]["sary"]` + 完整 dict |

CMTime 布局: `value(u64) timescale(u32) flags(u32) epoch(u64)` = 24 字节。

## 6. 输出

- 视频: SPS/PPS 及每个 NALU 前加 Annex-B 起始码 `00 00 00 01` 写 .h264，ffplay 可直接播。
- 音频: 默认 48kHz/16bit/双声道 LPCM，直接进 .wav。

## 7. 已知移植注意点

- `formatdescriptor.py` 的 SPS/PPS 提取采用递归扫 avcC 记录的方式，与 Go 版
  （固定 extension key）实现不同，**需在真机数据上验证**（fixture `asyn-feed` 可先验）。
- fixture 文件是去掉长度前缀的帧；我方构造的发包含长度前缀，对比时注意。
- 设备对 HPD1/HPA1 的字典字节序敏感，序列化必须与 Go 版逐字节一致（有 fixture 测试兜底）。
