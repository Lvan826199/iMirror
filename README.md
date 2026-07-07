# iMirror — iOS 有线投屏采集（Python 版 quicktime_video_hack）

通过 USB 数据线直接采集 iPhone/iPad 的屏幕(H.264)和音频(LPCM)流，
是 [danielpaulus/quicktime_video_hack](https://github.com/danielpaulus/quicktime_video_hack)(Go)
与 [chotgpt/quicktime_video_hack_windows](https://github.com/chotgpt/quicktime_video_hack_windows)(C++)
的 Python 移植。

## 可行性评估结论

**可以转成 Python，且大部分核心工作已在本骨架中完成。**

| 层 | 难度 | 本项目状态 |
|---|---|---|
| USB 通信 (pyusb/libusb) | 中低 | ✅ 已实现：设备发现、QT 配置激活(控制请求 `0x40/0x52`)、bulk 读写循环 |
| 协议分帧 (4字节长度前缀) | 低 | ✅ 已实现 + 单测 |
| QuickTime 协议 (ping/sync/asyn) | 中高 | ✅ 已按 Go 源码逐字节移植：CWPA/CVRP/CLOK/TIME/AFMT/SKEW/STOP 握手、HPD1/HPA1 参数字典、NEED 流控 |
| CoreMedia 结构 (CMSampleBuffer/CMTime/dict) | 中高 | ✅ 已实现，可用 reference 里的真机抓包 fixture 做字节级验证 |
| H.264/音频落盘 | 中 | ✅ Annex-B .h264 + .wav 写入器 |
| 实时预览 GUI | 中 | ⚠️ 骨架已有(PyAV 解码 + OpenCV 显示)，需真机联调 |
| **真机联调** | — | ❌ 需要 iPhone + libusb 驱动环境，这是剩下的主要工作 |

关键点：**协议逻辑不需要重新逆向**——Go 版已经全部写清楚，本项目是对照
`reference/quicktime_video_hack/screencapture/` 逐文件移植的，每个模块的 docstring
都标了对应的 Go 源文件，遇到问题直接对照。

## 目录结构

```
imirror/
├── imirror/                  # Python 包
│   ├── cli.py              # 命令行入口 (devices/activate/record/gui)
│   ├── session.py          # 消息状态机 (对照 messageprocessor.go)
│   ├── protocol/           # 协议层
│   │   ├── constants.py    #   所有 magic 常量
│   │   ├── framing.py      #   USB 流分帧
│   │   ├── ping.py         #   PING
│   │   ├── sync.py         #   SYNC 解析 + RPLY 构造
│   │   └── asyn.py         #   ASYN 解析 + HPD1/HPA1/NEED 构造
│   ├── coremedia/          # CoreMedia 二进制结构
│   │   ├── cmtime.py       #   CMTime / CMSampleTimingInfo
│   │   ├── cmclock.py      #   本地时钟 + skew 计算
│   │   ├── cmsamplebuffer.py #  sbuf 解析(音视频帧载体)
│   │   ├── formatdescriptor.py # fdsc(分辨率/SPS/PPS/音频格式)
│   │   ├── qtdict.py       #   序列化字典 dict/keyv/...
│   │   ├── nsnumber.py     #   NSNumber
│   │   └── asbd.py         #   AudioStreamBasicDescription
│   ├── usb/                # USB 层 (pyusb)
│   │   ├── discovery.py    #   枚举 Apple 设备, 检测 QT 配置
│   │   ├── activation.py   #   激活隐藏 QuickTime 配置
│   │   └── adapter.py      #   claim 接口 + bulk 读写循环
│   ├── consumers/          # 数据消费者
│   │   ├── h264_writer.py  #   Annex-B .h264 落盘
│   │   └── wav_writer.py   #   .wav 落盘 + 组合器
│   └── gui/viewer.py       # PyAV 解码 + OpenCV 实时预览
├── tests/                  # pytest, 用真机抓包 fixture 做字节级验证
├── reference/              # 两个原版仓库的浅克隆(对照用, 不要改)
└── docs/protocol.md        # 协议速查
```

## 快速开始

```bash
cd imirror
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 先跑测试确认协议层正确(不需要 iPhone)
pytest

# 接上 iPhone 后
python -m imirror devices        # 列设备
python -m imirror record out.h264 out.wav   # 录制(自动激活 QT 配置)
ffplay -f h264 out.h264        # 播放验证

# 实时预览(需要 pip install av opencv-python)
python -m imirror gui
```

## Windows 驱动准备（和 C++ 版相同，绕不开）

1. 卸载/停用 **Apple Mobile Device Support**（与 libusb 冲突）
2. 用 [Zadig](https://zadig.akeo.ie/) 把 iPhone 的驱动替换为 **libusbK** 或 **WinUSB**
3. pyusb 需要 libusb 运行库：`pip install libusb-package` 或把 `libusb-1.0.dll` 放到 PATH
4. 首次连接在手机上点"信任此电脑"

Linux 下通常只需 udev 权限（或 sudo 运行）。

## 会话流程（详见 docs/protocol.md）

```
激活: 控制请求 0x40/0x52/wIndex=2 → 设备重新枚举, 暴露 QT 配置(class 0xFF, subclass 0x2A)
握手: PING↔PING → SYNC OG → SYNC CWPA(发2次HPD1 + 回RPLY + 发HPA1)
      → SYNC CVRP(发NEED + 回RPLY) → CLOK/TIME/AFMT 按需应答
数据: ASYN FEED(视频, 每帧回一个 NEED) / ASYN EAT!(音频) / SYNC SKEW(定期)
关闭: 发 HPA0/HPD0 → 等 ASYN RELS → 设备恢复普通模式
```

## 剩余工作(按优先级)

1. **真机联调**：跑通 `record`，重点验证 USB 激活后的重枚举时序、`clear_halt`、
   以及 `formatdescriptor.py` 里 SPS/PPS 的提取位置（标了 TODO，以真机数据为准）
2. GUI 延迟优化：解码放独立进程、丢帧策略
3. 音画同步（目前音视频分开落盘）
4. 推流扩展：RTMP/WebRTC/虚拟摄像头(OBS)
5. 多设备并行采集

## 致谢与协议

- 协议逆向: Daniel Paulus (MIT)
- Windows C++ 适配: chotgpt (MIT)
- 本项目: MIT
