# iMirror

[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](#license)
[![Status](https://img.shields.io/badge/status-experimental-orange)](#project-status)

iMirror 是一个 iPhone/iPad 投屏采集实验项目。raw USB backend 移植自
[danielpaulus/quicktime_video_hack](https://github.com/danielpaulus/quicktime_video_hack)
的 Go 版协议实现，并参考
[chotgpt/quicktime_video_hack_windows](https://github.com/chotgpt/quicktime_video_hack_windows)
的 Windows 源码、工具链和产品化交付经验；Windows 主线聚焦 QuickTime raw USB 有线投屏。

当前目标是提供一个可测试、可维护的跨平台投屏采集库和命令行工具：Windows 优先复用
chotgpt 内置工具链跑通 QuickTime 有线 POC，macOS 优先原生 CoreMediaIO/AVFoundation。

## 文档导航

| 我想… | 看哪份 |
| --- | --- |
| 安装并使用（列设备/录制/预览） | 本 README 的 Installation + Quick Start |
| **接上真机开始联调**（一步步操作+预期输出+验收清单） | [docs/真机联调手册.md](docs/真机联调手册.md) |
| **Windows 有线路线评估** | [docs/Windows投屏路线评估.md](docs/Windows投屏路线评估.md) |
| **Windows 接下来怎么继续搞** | [docs/Windows投屏实施计划.md](docs/Windows投屏实施计划.md) |
| 查协议细节（报文格式/时序图/fixture 约定） | [docs/协议速查.md](docs/协议速查.md) |
| **联调踩坑/改代码前**（真机 bug 根因与防复发规约） | [docs/已知问题与归因.md](docs/已知问题与归因.md) |
| 了解已知问题和剩余工作 | 本 README 的 Roadmap + 协议速查.md 第 9 节 |

## Project Status

项目仍处于实验阶段。协议层、CoreMedia 解析和报文序列化已经完成，并通过真机抓包 fixture
进行字节级测试；Windows 当前主攻 chotgpt QuickTime 工具链验证，先跑通有线 POC，再决定
直接调用 exe/DLL、移植到 iMirror，或作为 MSCA 视频源集成。

| 模块 | 状态 |
| --- | --- |
| USB 设备发现与 QuickTime 配置激活 | 已实现，待更多真机环境验证 |
| QuickTime PING/SYNC/ASYN 协议 | 已按 Go 版移植并覆盖 fixture 测试 |
| CoreMedia CMSampleBuffer/CMTime/dict 解析 | 已实现 |
| H.264 Annex-B 与 WAV 落盘 | 已实现 |
| Windows chotgpt tools | 已内置 tools，待有线 POC 与 WDA 共存验证 |
| 实时预览 GUI | 默认 raw USB 有线 |
| 音画同步、推流、多设备 | 规划中 |

## Features

- Windows 内置 chotgpt `tools/`，优先做 QuickTime 有线投屏 POC。
- raw USB 模式通过 `pyusb` 发现 iOS 设备并激活隐藏的 QuickTime USB 配置。
- 实现 PING、SYNC、ASYN、RPLY、HPD1、HPA1、NEED 等核心协议报文。
- 解析 CoreMedia 的 `CMSampleBuffer`、`CMTime`、format description 和 QuickTime 字典结构。
- 将视频帧写入 Annex-B `.h264` 文件，将音频写入 `.wav` 文件。
- 提供命令行工具：环境自检（doctor）、设备列表（含 JSON 输出）、激活、USB reset 恢复、录制（支持限时与实时统计）、实时预览。
- macOS 提供实验性 CoreMediaIO/AVFoundation 原生后端，可列出系统 iOS 屏幕源、
  录制 `.mov` 或打开预览窗口；首次运行会把 Swift helper 编译并 ad-hoc 签名到
  `~/Library/Caches/imirror/`。
- Windows / macOS 一键安装脚本（`scripts/`），Linux 两条命令装好。
- 使用真机抓包 fixture 进行协议解析和序列化的字节级回归测试，fixture 已随仓库提供，
  克隆即可运行全部测试。

## Architecture

```
┌──────────┐  bulk USB   ┌────────────┐  完整帧   ┌──────────────────┐
│  iPhone   │ ──────────→ │ usb/adapter │ ───────→ │ session           │
│ (QT 配置) │ ←────────── │ (读循环+分帧)│ ←─────── │ MessageProcessor  │
└──────────┘  应答/NEED   └────────────┘  发包    │ (协议状态机)       │
                                                  └────────┬─────────┘
                                                   CMSampleBuffer
                                          ┌────────────────┼────────────────┐
                                          ↓                ↓                ↓
                                    H264Writer        WavWriter       gui/viewer
                                    (.h264 裸流)      (.wav)          (实时预览)
```

数据流：USB bulk 读循环把字节流按 4 字节长度前缀分帧 → `MessageProcessor`
按 PING/SYNC/ASYN 分派、维护时钟握手与 NEED 流控 → 解出的 `CMSampleBuffer`
交给消费者（文件写入器 / GUI），彼此通过 `Consumer` 协议解耦，可用
`CompositeConsumer` 组合多路输出。会话时序图见 [docs/协议速查.md](docs/协议速查.md)。

## Requirements

- Python 3.10+
- Windows / macOS / Linux 均可（各系统的准备步骤见 [docs/真机联调手册.md](docs/真机联调手册.md)）
- Windows 主攻 QuickTime raw USB 有线；内置 `tools/usbmuxd.exe`、`ideviceinfo.exe` 和驱动安装器
- libusb 运行环境（raw USB 模式需要；Windows 装 `.[windows]` 附加项即自带；macOS `brew install libusb`；Linux 发行版包）
- iPhone 或 iPad，以及可信任的数据线连接
- macOS 原生后端需要 Xcode Command Line Tools 提供的 `swiftc`/`swift`

可选依赖：

- `av` 和 `opencv-python`：用于实时预览 GUI
- `ffplay`：用于播放录制出的 `.h264` 文件

## Installation

**一键安装（推荐）**——自动完成装 uv → 建环境 → 装依赖 → 离线测试 → 环境自检：

```
Windows: 双击 scripts\setup-windows.bat
macOS:   bash scripts/setup-macos.sh
```

Windows 有线主线优先使用仓库内置 tools；驱动准备优先用 chotgpt 内置参考工具链，不要求用户自行下载驱动工具。

手动安装则使用 `uv` 创建开发环境：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev]"
```

Windows PowerShell：

```powershell
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -e ".[dev]"
```

没装 uv 的先装一下（单个二进制，不依赖系统 Python）：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh                              # macOS/Linux
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows
```

安装 GUI 可选依赖：

```bash
uv pip install --python .venv/bin/python -e ".[gui]"
```

## Quick Start

先运行测试，确认协议层和 fixture 解析正常（不需要 iPhone，fixture 已随仓库提供）：

```bash
pytest
```

环境自检（跨平台，逐项给出当前系统的修复建议）：

```bash
python -m imirror doctor
```

列出已连接的 iOS 设备：

```bash
python -m imirror devices
python -m imirror devices --json    # JSON 输出, 便于脚本调用
```

`devices --json` 会同时输出 `active_config`、`usbmux_config`、`qt_config`、
`qt_available` 和 `qt_enabled`。其中 `qt_available` 表示描述符里能看到
QuickTime/Valeria 配置，`qt_enabled` 才表示当前活动配置已经切到 QT。

激活 QuickTime USB 配置：

```bash
python -m imirror activate
```

USB reset 恢复设备普通枚举（macOS 半激活/残留 QT 描述符时很有用）：

```bash
python -m imirror reset
```

录制屏幕和音频（自动激活 QT 配置，Ctrl+C 停止）：

```bash
python -m imirror record out.h264 out.wav
python -m imirror record out.h264 out.wav --duration 30   # 限时 30 秒
```

录制过程中每 5 秒打印一次统计（视频帧数/fps/数据量、音频帧数）。
如果会话结束时没有收到任何视频帧，`record` 会返回非 0，并提示按 `-v` 日志排查 USB/协议链路。

播放录制出的视频流：

```bash
ffplay -f h264 out.h264
```

启动实时预览：

```bash
python -m imirror gui
```

Windows 有线主线内置了 `chotgpt/quicktime_video_hack_windows` 的 tools。先执行 POC 预检：

```powershell
python -m imirror windows-poc-check
```

预检通过后，开一个终端保持参考 `usbmuxd.exe` 运行：

```powershell
python -m imirror windows-usbmuxd
```

`windows-usbmuxd` 会启动参考项目修改过的 `usbmuxd.exe`，它监听 37015 并辅助设备进入
QuickTime 模式。保持它运行后，再另开终端跑 raw USB 录制/预览。

启动 raw USB 实时预览：

```powershell
python -m imirror gui --udid 设备序列号
```

macOS 原生后端（实验性，不走 raw USB bulk；需要 Screen Recording 权限）：

```bash
python -m imirror macos-devices
python -m imirror macos-record out.mov --duration 10
python -m imirror macos-gui
```

安装为 editable 包后，也可以直接使用 console script：

```bash
imirror devices
imirror record out.h264 out.wav
```

## CLI

| 命令 | 用途 |
| --- | --- |
| `imirror doctor` | 环境自检，逐项检查并给出当前系统的修复建议 |
| `imirror devices [--json]` | 列出 iOS 设备以及 QuickTime 配置状态 |
| `imirror activate [--udid SERIAL]` | 激活指定设备的 QuickTime 配置 |
| `imirror reset [--udid SERIAL]` | USB reset 指定设备, 恢复半激活状态 |
| `imirror record out.h264 out.wav [--udid SERIAL] [--duration 秒]` | 录制视频和音频 |
| `imirror gui [--backend auto\|raw-usb] [--udid SERIAL]` | 打开实时预览窗口；默认 raw USB 有线 |
| `imirror windows-poc-check [--udid SERIAL]` | 用内置 chotgpt tools 执行 Windows 有线 POC 预检 |
| `imirror windows-tools-doctor` | 检查 chotgpt 参考项目 tools 是否可用 |
| `imirror windows-usbmuxd` | 启动 chotgpt 参考项目修改过的 usbmuxd |
| `imirror windows-ideviceinfo` | 运行 chotgpt tools 中的 ideviceinfo |
| `imirror windows-driver-installer` | 打开 chotgpt tools 中的驱动安装器 |
| `imirror macos-devices [--json]` | macOS 原生后端列出 iOS 屏幕源 |
| `imirror macos-record out.mov [--udid SERIAL] [--duration 秒]` | macOS 原生后端录制 `.mov` |
| `imirror macos-gui [--udid SERIAL]` | macOS 原生后端预览窗口 |
| `imirror --version` | 显示版本号 |

可以添加 `-v` 或 `--verbose` 输出更详细日志（观察协议握手细节）。
如果同时识别到多台 iOS 设备，`record` / `gui` / `activate` 会要求显式传入
`--udid SERIAL`，避免默认选错设备。

## Troubleshooting

| 现象 | 原因与处理 |
| --- | --- |
| Windows 有线投屏不出画面 | 先跑 `windows-poc-check` 和 `windows-usbmuxd`，再用 `record -v` 收集 PING/SYNC/FEED 日志 |
| `windows-tools-doctor` 提示缺 tools | 内部仓库应已带 `tools\usbmuxd.exe` 等工具；若缺失，运行 `scripts\fetch-qvh-windows-tools.ps1` 刷新，或设置 `IMIRROR_QVH_TOOLS` 指向工具目录 |
| `devices` 列不出设备 | raw USB 模式下检查数据线、手机信任、Windows 驱动准备和 `tools\usbmuxd.exe` 是否运行 |
| `Access denied / insufficient permissions` | Linux 缺 udev 规则，先用 `sudo` 验证，再加规则：`SUBSYSTEM=="usb", ATTR{idVendor}=="05ac", MODE="0666"` |
| `Resource busy` | 接口被占用：Linux 上是 `usbmuxd`，可 `systemctl stop usbmuxd` 试验；macOS 上是系统服务占用（macOS 建议直接用 QuickTime） |
| 激活后设备"消失"又出现 | 正常现象：激活触发重新枚举，`record` 会自动等待并重连 |
| `devices` 显示 `可用但未激活` | macOS 上 QT 描述符可能保留但当前 active config 已回普通配置；`record`/`activate` 会自动切回 QT |
| macOS claim 成功但 0 帧 / bulk 超时 | 保持手机解锁并已信任；退出 QuickTime 等占用程序；换 Mac 直连或高速 USB 口；必要时先跑 `python -m imirror reset` 清掉半激活状态；现代 macOS 可能需要 CoreMediaIO/AVFoundation 原生路径和 Screen Recording 权限 |
| `macos-record` 报 `recording failed before start` / `valeria connection not seen` | 系统 iOSScreenCaptureAssistant 未能让手机进入 Valeria 出流态；保持手机解锁，重插数据线，退出 QuickTime/录屏占用程序后重试 |
| QuickTime Player 选择 iPhone 也报“这项操作无法完成” | Apple 原生投屏链路本身失败，常见日志为 `StartStream throwing valeria connection not seen` / `AVFoundationErrorDomain -11800`。先 `python -m imirror reset`，再重启 Mac/iPhone、换直连口/数据线复验；QuickTime 仍失败时 iMirror 暂无可绕过的系统级通道 |
| 某台设备突然 `valeria connection not seen`，但其他设备可投屏 | 优先视为设备/macOS 的 Valeria 临时状态卡死；先 `python -m imirror reset`、重插线，再重启 iPhone 和 Mac。重启后恢复时，不要归因到 iOS 大版本兼容性 |
| 录下的 .h264 无法播放 | 大概率没写入 SPS/PPS——正是真机联调要验证的 TODO，用 `-v` 看"写入参数集"日志是否出现 |
| 录制中途停止收帧 | NEED 流控断了（每个 FEED 必须回 NEED），`-v` 观察 FEED/NEED 是否成对 |

## Protocol Notes

协议实现以 `reference/quicktime_video_hack/screencapture/` 中的 Go 源码为权威参考。Python
模块的 docstring 标注了对应的 Go 文件，修改协议逻辑前应先对照 Go 版。

关键约定：

- 发给设备的 HPD1、HPA1、RPLY、NEED 等报文必须与 Go 版逐字节一致。
- USB bulk 流使用 4 字节小端长度前缀分帧。
- `ASYN FEED` 视频帧消费后必须回 `NEED`，否则设备会停止继续推流。

更多细节（含会话时序图、fixture 前缀约定、与 Go 版的已知差异）见
[docs/协议速查.md](docs/协议速查.md)。

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

请不要修改 `reference/` 目录，它是只读参考副本，且不入 git。需要对照 Go 源码时自行克隆：

```bash
git clone --depth 1 https://github.com/danielpaulus/quicktime_video_hack reference/quicktime_video_hack
```

## Project Layout

```text
imirror/
├── imirror/
│   ├── cli.py                  # 命令行入口
│   ├── macos_native.py         # macOS CoreMediaIO/AVFoundation 原生后端
│   ├── session.py              # 消息状态机
│   ├── protocol/               # QuickTime 协议分帧和报文
│   ├── coremedia/              # CoreMedia 二进制结构解析
│   ├── usb/                    # pyusb 设备发现、激活和读写
│   ├── consumers/              # H.264/WAV 输出
│   └── gui/                    # 实时预览
├── tests/                      # pytest 测试
│   └── fixtures/               # 真机抓包 fixture(拷贝自 Go 原版, MIT), 开箱即跑
├── scripts/
│   ├── setup-windows.bat       # Windows 一键环境安装
│   └── setup-macos.sh          # macOS 一键环境安装
├── docs/
│   ├── 协议速查.md             # 协议速查 + 会话时序图
│   └── 真机联调手册.md         # 联调分步操作 + 验收清单
└── reference/                  # 上游 Go/C++ 参考实现，只读，不入 git
```

## Roadmap

- **Windows 有线产品路线**：主攻 chotgpt QuickTime 工具链，内置 `tools/`，先用参考
  `usbmuxd`、驱动安装器和参考产物验证有线投屏与 WDA 控制共存；成功后再决定直接调用
  exe/DLL、接入 MSCA，或把关键逻辑移植回 iMirror。
- 在 Linux/macOS 上跑通 `record`/`gui`；Ubuntu 首轮按手册第 4.1 节先排除
  libusb/udev/usbmuxd 权限占用。macOS 当前测试机上 iOS 14.4.2、15.1、
  16.7.8、17.7.4、18.3、26.2 均可经 Apple QuickTime 成功投屏；iOS 18.3 重启恢复后
  `imirror macos-gui` 原生预览已成功启动。此前 `valeria connection not seen`
  后续按临时 Valeria 状态卡死排障。
- 进一步确认 `formatdescriptor.py` 中 SPS/PPS 提取位置。
- 优化 GUI 延迟、解码进程和丢帧策略。
- 增加音画同步、RTMP/WebRTC 推流和虚拟摄像头输出。
- 支持多设备并行采集。

## Credits

- Protocol reverse engineering: Daniel Paulus
- Windows adaptation reference: chotgpt
- Python port: iMirror contributors

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
