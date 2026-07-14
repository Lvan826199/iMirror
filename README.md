# iMirror

iMirror 是一个 iOS 有线投屏采集实验项目。协议层参考
[danielpaulus/quicktime_video_hack](https://github.com/danielpaulus/quicktime_video_hack)
的 QuickTime/Valeria raw USB 思路，并额外提供 macOS 原生
CoreMediaIO/AVFoundation 后端。

## 当前状态

截至目前，**只跑通并验收 macOS 系统**：

- macOS 可通过 `macos-devices` 枚举 iPhone/iPad 屏幕源。
- macOS 可通过 `macos-record` 录制 `.mov`。
- macOS 可通过 `macos-gui` 打开原生预览窗口。
- 协议解析、CoreMedia 解析和 fixture 测试仍保留，方便后续研究 raw USB 路线。

**Windows 暂时不做兼容，也不作为当前交付目标。**
之前的 Windows QuickTime raw USB、第三方工具链、爱思/Rayren/MSCA 共存探索均已暂停。
后续文档不再指导普通用户配置 Windows 驱动或 Windows 投屏链路。

Linux 也暂未完成真机投屏验收，只保留开发/研究可能性。

## 文档

| 内容 | 文件 |
| --- | --- |
| 真机联调步骤 | [docs/真机联调手册.md](docs/真机联调手册.md) |
| 协议速查 | [docs/协议速查.md](docs/协议速查.md) |
| 已知问题和归因 | [docs/已知问题与归因.md](docs/已知问题与归因.md) |

## 安装

macOS 推荐：

```bash
git clone https://gitee.com/xiaozai-van-liu/imirror.git
cd imirror
bash scripts/setup-macos.sh
```

手动安装：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev,gui]"
```

首次使用 macOS 原生后端需要 Xcode Command Line Tools 提供 `swiftc`/`swift`。

## macOS 使用

列出可用的 iOS 屏幕源：

```bash
.venv/bin/python -m imirror macos-devices
```

录制 10 秒：

```bash
.venv/bin/python -m imirror macos-record out.mov --duration 10
```

打开预览：

```bash
.venv/bin/python -m imirror macos-gui
```

如果首次运行提示屏幕录制权限，请到 macOS:

`系统设置 -> 隐私与安全性 -> 屏幕录制`

给当前终端或启动 iMirror 的 App 授权，然后重启终端/App 再试。

## 开发命令

离线测试不需要连接 iPhone：

```bash
.venv/bin/python -m pytest tests -q
```

raw USB 研究命令仍保留，但目前不作为用户交付路径：

```bash
.venv/bin/python -m imirror doctor
.venv/bin/python -m imirror devices
.venv/bin/python -m imirror record out.h264 out.wav --duration 10
```

## CLI 摘要

| 命令 | 用途 |
| --- | --- |
| `imirror macos-devices [--json]` | macOS 原生后端列出 iOS 屏幕源 |
| `imirror macos-record out.mov [--udid SERIAL] [--duration 秒]` | macOS 原生后端录制 `.mov` |
| `imirror macos-gui [--udid SERIAL]` | macOS 原生后端预览窗口 |
| `imirror doctor` | raw USB 环境自检，主要用于研究和排障 |
| `imirror devices [--json]` | raw USB 设备列表 |
| `imirror record out.h264 out.wav` | raw USB 录制，暂非主线交付能力 |
| `imirror reset` | USB reset，清理半激活状态 |

## 重要边界

- 当前交付目标：macOS 原生投屏。
- 当前不交付：Windows 投屏兼容、Windows 驱动配置、Windows 与 MSCA/WDA 共存方案。
- iMirror 不负责 WDA 控屏，不集成 MSCA。
- `reference/` 是只读参考，不要修改。

## License

MIT. See [LICENSE](LICENSE).
