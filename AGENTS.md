# iMirror 项目说明（给 AI 编码助手的上下文）

> 本文件是唯一维护的助手说明（AGENTS.md 标准，Codex/Cursor 等直接读取）；
> `CLAUDE.md` 仅是对本文件的引用，内容改这里即可。

iOS 有线投屏采集的 Python 实现，移植自 Go 版 quicktime_video_hack。
先读 `README.md`（现状与剩余工作）和 `docs/protocol.md`（协议速查）；
真机联调按 `docs/field-testing.md` 的步骤和验收清单执行。

## 关键约定

- **协议实现以 `reference/quicktime_video_hack/screencapture/` 的 Go 源码为权威参考**，
  每个 Python 模块的 docstring 标了对应的 Go 文件；改协议逻辑前先对照 Go 版。
- `reference/` 是只读参考副本，不要修改。
- 发给设备的报文（HPD1/HPA1/RPLY 等）必须与 Go 版**逐字节一致**，
  tests/ 里有基于真机抓包 fixture 的字节级测试兜底，改序列化代码后必须跑测试。
- fixture 已拷贝进 `tests/fixtures/`（packet/coremedia 两组），测试开箱即跑，
  `reference/` 不入 git、缺失时测试回退用它。
- fixture 注意点：大部分带 4 字节长度前缀（解析时用 `load_stripped`），
  但 `asyn-eat` 和 `asyn-feed-nofdsc` 不带（Go 测试也是整文件直接传）。

## 常用命令

```bash
.venv/bin/python -m pytest tests/ -q     # 跑测试(不需要 iPhone)
.venv/bin/python -m imirror devices        # 列设备
.venv/bin/python -m imirror record out.h264 out.wav   # 录制
```

环境用 `uv`（系统 python3 没有 pip/venv）：`uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"`

## 当前状态（2026-07-08）

- 项目于 2026-07-07 由 pyqvh 更名为 iMirror（包名 imirror），旧名已全部替换
- 代码托管: https://gitee.com/xiaozai-van-liu/imirror
- 协议层/CoreMedia 层完成并通过 22 个 fixture 测试（含真机数据端到端解析）
- v0.2.0: fixture 入库开箱即跑、record --duration/实时统计、devices --json、--version
- 未做真机联调：USB 激活时序、SPS/PPS 提取位置（formatdescriptor.py 的 avcC 递归扫描
  与 Go 版固定 key 的实现不同，fixture 上已验证，真机上待确认）
- 剩余工作优先级见 README.md 末尾
