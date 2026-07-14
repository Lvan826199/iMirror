# iMirror 项目说明（给 AI 编码助手的上下文）

> 本文件是唯一维护的助手说明（AGENTS.md 标准，Codex/Cursor 等直接读取）；
> `CLAUDE.md` 仅是对本文件的引用，内容改这里即可。

iMirror 是 iOS 投屏采集的 Python 实验项目。协议层/CoreMedia 层保留 raw USB
QuickTime/Valeria 研究实现，但当前产品和文档主线已经收敛为：

**只验收 macOS 原生 CoreMediaIO/AVFoundation 投屏。**

Windows 方向已经暂停，暂时不做兼容；不要继续推进 Windows 驱动、爱思/Rayren、
chotgpt tools 或 MSCA/WDA 共存方案。MSCA 集成文档已删除，iMirror 不负责 WDA 控屏。

改动前先读：

- `README.md`：当前状态、安装和 macOS 使用方式
- `docs/协议速查.md`：QuickTime/Valeria 协议速查
- `docs/真机联调手册.md`：当前 macOS 真机联调步骤
- `docs/已知问题与归因.md`：历史真机问题与防复发规约

## 硬性流程

- **改代码必同步文档**：动了 CLI 参数/行为、依赖分组、协议逻辑，同一次提交里同步
  README / 手册 / 协议速查 / 本文件 对应处。
- **每个 bug 必归因**：修 bug 时在 `docs/已知问题与归因.md` 对应类别追加一行
  现象、根因和 commit；新根因就新开一类。
- **pyusb 异常捕获要完整**：任何 pyusb 调用点捕获异常一律写全
  `(usb.core.USBError, NotImplementedError, ValueError)`。

## 当前可用范围

- macOS：已通过原生 `macos-devices` / `macos-record` / `macos-gui` 路线验证。
- Windows：暂不兼容，不写普通用户 Windows 驱动/投屏教程。
- Linux：暂未完成真机投屏验收，只保留研究可能性。
- MSCA：当前不集成，相关计划文档已删除。

## 关键约定

- 协议实现仍以 `reference/quicktime_video_hack/screencapture/` 的 Go 源码为权威参考。
- `reference/` 是只读参考副本，不要修改。
- 发给设备的 HPD1/HPA1/RPLY/NEED 等报文必须与 Go 版逐字节一致。
- fixture 已拷贝进 `tests/fixtures/`，测试应开箱即跑。

## 常用命令

```bash
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m imirror macos-devices
.venv/bin/python -m imirror macos-record out.mov --duration 10
.venv/bin/python -m imirror macos-gui
```

环境用 `uv`：

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e ".[dev,gui]"
```

## 当前状态摘要

- 项目于 2026-07-07 由 pyqvh 更名为 iMirror（包名 `imirror`）。
- 协议层/CoreMedia 层完成并通过 fixture 测试。
- macOS 原生后端使用系统 CoreMediaIO/AVFoundation 和缓存的 ad-hoc 签名 Swift helper。
- 某些设备可能出现 `valeria connection not seen`；若 QuickTime Player 也失败，优先按
  设备/macOS 临时 Valeria 状态卡死处理：`imirror reset`、重插线、重启 iPhone 或 Mac。
- Windows raw USB、爱思/Rayren、MSCA/WDA 共存探索均已暂停，不再作为当前主线。
