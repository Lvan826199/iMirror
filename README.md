# iMirror

[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)
[![Status](https://img.shields.io/badge/status-experimental-orange)](#project-status)

iMirror 是一个通过 USB 数据线采集 iPhone/iPad 屏幕视频和音频流的 Python 实现。它移植自
[danielpaulus/quicktime_video_hack](https://github.com/danielpaulus/quicktime_video_hack)
的 Go 版协议实现，并参考
[chotgpt/quicktime_video_hack_windows](https://github.com/chotgpt/quicktime_video_hack_windows)
的 Windows 适配经验。

当前目标是提供一个可测试、可维护的 QuickTime 有线投屏采集库和命令行工具，用于录制 H.264
视频流和 LPCM 音频流。

## Project Status

项目仍处于实验阶段。协议层、CoreMedia 解析和报文序列化已经完成，并通过真机抓包 fixture
进行字节级测试；剩余主要工作是真机 USB 联调和预览体验优化。

| 模块 | 状态 |
| --- | --- |
| USB 设备发现与 QuickTime 配置激活 | 已实现，待更多真机环境验证 |
| QuickTime PING/SYNC/ASYN 协议 | 已按 Go 版移植并覆盖 fixture 测试 |
| CoreMedia CMSampleBuffer/CMTime/dict 解析 | 已实现 |
| H.264 Annex-B 与 WAV 落盘 | 已实现 |
| 实时预览 GUI | 已有骨架，需真机联调 |
| 音画同步、推流、多设备 | 规划中 |

## Features

- 通过 `pyusb` 发现 iOS 设备并激活隐藏的 QuickTime USB 配置。
- 实现 PING、SYNC、ASYN、RPLY、HPD1、HPA1、NEED 等核心协议报文。
- 解析 CoreMedia 的 `CMSampleBuffer`、`CMTime`、format description 和 QuickTime 字典结构。
- 将视频帧写入 Annex-B `.h264` 文件，将音频写入 `.wav` 文件。
- 提供命令行工具：设备列表、激活、录制、实时预览。
- 使用真机抓包 fixture 进行协议解析和序列化的字节级回归测试。

## Requirements

- Python 3.10+
- libusb 运行环境
- iPhone 或 iPad，以及可信任的数据线连接
- Windows 用户需要用 Zadig 为设备安装 libusbK 或 WinUSB 驱动

可选依赖：

- `av` 和 `opencv-python`：用于实时预览 GUI
- `ffplay`：用于播放录制出的 `.h264` 文件

## Installation

推荐使用 `uv` 创建开发环境：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Windows PowerShell：

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

如果不使用 `uv`，也可以用标准虚拟环境：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

安装 GUI 可选依赖：

```bash
pip install -e ".[gui]"
```

## Quick Start

先运行测试，确认协议层和 fixture 解析正常：

```bash
pytest
```

列出已连接的 iOS 设备：

```bash
python -m imirror devices
```

激活 QuickTime USB 配置：

```bash
python -m imirror activate
```

录制屏幕和音频：

```bash
python -m imirror record out.h264 out.wav
```

播放录制出的视频流：

```bash
ffplay -f h264 out.h264
```

启动实时预览：

```bash
python -m imirror gui
```

安装为 editable 包后，也可以直接使用 console script：

```bash
imirror devices
imirror record out.h264 out.wav
```

## CLI

| 命令 | 用途 |
| --- | --- |
| `imirror devices` | 列出 iOS 设备以及 QuickTime 配置状态 |
| `imirror activate [--udid SERIAL]` | 激活指定设备的 QuickTime 配置 |
| `imirror record out.h264 out.wav [--udid SERIAL]` | 录制视频和音频 |
| `imirror gui [--udid SERIAL]` | 打开实时预览窗口 |

可以添加 `-v` 或 `--verbose` 输出更详细日志。

## Windows Driver Setup

Windows 下 Apple Mobile Device Support 会占用原生 iOS USB 接口，通常需要切换到 libusb 驱动：

1. 卸载或停用 Apple Mobile Device Support。
2. 使用 [Zadig](https://zadig.akeo.ie/) 将 iPhone/iPad 的驱动替换为 libusbK 或 WinUSB。
3. 安装 libusb 运行库，例如 `pip install libusb-package`，或将 `libusb-1.0.dll` 放入 `PATH`。
4. 首次连接设备时，在手机上选择信任此电脑。

Linux 通常只需要配置 udev 权限，或使用 sudo 运行命令。

## Protocol Notes

协议实现以 `reference/quicktime_video_hack/screencapture/` 中的 Go 源码为权威参考。Python
模块的 docstring 标注了对应的 Go 文件，修改协议逻辑前应先对照 Go 版。

关键约定：

- 发给设备的 HPD1、HPA1、RPLY、NEED 等报文必须与 Go 版逐字节一致。
- USB bulk 流使用 4 字节小端长度前缀分帧。
- `ASYN FEED` 视频帧消费后必须回 `NEED`，否则设备会停止继续推流。
- fixture 大多带 4 字节长度前缀，解析测试使用 `load_stripped`；`asyn-eat` 不带长度前缀。

更多细节见 [docs/protocol.md](docs/protocol.md)。

## Development

运行测试：

```bash
pytest tests/ -q
```

使用项目约定的虚拟环境路径：

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m imirror devices
.venv/bin/python -m imirror record out.h264 out.wav
```

Windows PowerShell 对应命令：

```powershell
.venv\Scripts\python.exe -m pytest tests/ -q
.venv\Scripts\python.exe -m imirror devices
.venv\Scripts\python.exe -m imirror record out.h264 out.wav
```

请不要修改 `reference/` 目录，它是只读参考副本。

## Project Layout

```text
imirror/
├── imirror/
│   ├── cli.py                  # 命令行入口
│   ├── session.py              # 消息状态机
│   ├── protocol/               # QuickTime 协议分帧和报文
│   ├── coremedia/              # CoreMedia 二进制结构解析
│   ├── usb/                    # pyusb 设备发现、激活和读写
│   ├── consumers/              # H.264/WAV 输出
│   └── gui/                    # 实时预览
├── tests/                      # pytest 测试和 fixture 验证
├── docs/protocol.md            # 协议速查
└── reference/                  # 上游 Go/C++ 参考实现，只读
```

## Roadmap

- 跑通更多真机环境下的 `record` 流程。
- 验证 USB 激活后的重枚举时序和 `clear_halt` 行为。
- 进一步确认 `formatdescriptor.py` 中 SPS/PPS 提取位置。
- 优化 GUI 延迟、解码进程和丢帧策略。
- 增加音画同步、RTMP/WebRTC 推流和虚拟摄像头输出。
- 支持多设备并行采集。

## Credits

- Protocol reverse engineering: Daniel Paulus
- Windows adaptation reference: chotgpt
- Python port: iMirror contributors

## License

MIT
