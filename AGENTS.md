# iMirror 项目说明（给 AI 编码助手的上下文）

> 本文件是唯一维护的助手说明（AGENTS.md 标准，Codex/Cursor 等直接读取）；
> `CLAUDE.md` 仅是对本文件的引用，内容改这里即可。

iOS 有线投屏采集的 Python 实现，移植自 Go 版 quicktime_video_hack。
先读 `README.md`（现状与剩余工作）和 `docs/协议速查.md`（协议速查）；
真机联调按 `docs/真机联调手册.md` 的步骤和验收清单执行；
改代码前必读 `docs/已知问题与归因.md`（真机 bug 的根因与防复发规约）。

## 两条硬性流程（务必遵守）

- **改代码必同步文档**：动了 CLI 参数/行为、依赖分组、协议逻辑，同一次提交里
  改掉 README / 手册 / 协议速查 / 本文件 对应处，不留文档漂移。
- **每个 bug 必归因**：修 bug 时在 `docs/已知问题与归因.md` 对应类别追加一行
  （现象+根因+commit），新根因就新开一类，目的是让同类错误一次绝根。
  尤其：任何 pyusb 调用点捕获异常一律写全 `(usb.core.USBError,
  NotImplementedError, ValueError)`（A 类根因，最高频）。

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

## 当前状态（2026-07-09）

- 项目于 2026-07-07 由 pyqvh 更名为 iMirror（包名 imirror），旧名已全部替换
- 代码托管: https://gitee.com/xiaozai-van-liu/imirror
- 协议层/CoreMedia 层完成并通过 22 个 fixture 测试（含真机数据端到端解析）
- v0.2.0: fixture 入库开箱即跑、record --duration/实时统计、devices --json、--version
- 2026-07-08 全量对照审计(4 个 sub-agent)后修复: close_session 时序对齐 Go
  (HPA0/HPD0 背靠背+结尾补发 HPD0, RELS 用计数信号量)、--duration 向上取整偏差;
  ssiz/SPS-PPS 与 Go 的有意差异记录在 docs/协议速查.md 第 9 节
- 跨平台就绪: imirror doctor 环境自检命令、scripts/ 下 Windows(bat)/macOS(sh)
  一键安装脚本、USB 枚举优先 libusb-package 后端(.[windows] 附加项)
- 文档: docs/ 用中文文件名(协议速查.md/真机联调手册.md/已知问题与归因.md), 安装命令统一用 uv
- 真机联调(Windows)撞墙, 根因已确认: 已打通 设备发现→换 libusb-win32 驱动→
  切配置#5→claim接口→set_altsetting 全成功, 但复合子接口的 bulk 读写全超时。
  根因=QT 接口是复合子接口, libusb-win32 装在复合父设备上时控制传输能用但 bulk
  路由不到子接口(Windows 复合设备驱动模型固有问题, 非协议 bug)。参考 C++ 版靠
  定制 usbmuxd/lockdown 让设备以 QT 为默认配置重新枚举来绕过。详见
  docs/已知问题与归因.md C类#5。**协议实现本身正确(Go 版忠实移植), Linux/macOS
  理论直接可用**; Windows 完整支持需移植 usbmuxd 进 QT 模式(大工程, 见 Roadmap)
- 未销案的验证项: SPS/PPS 提取位置(formatdescriptor.py avcC 递归扫描 vs Go 固定 key,
  真机日志里"写入参数集"出现即销案)
- 剩余工作优先级见 README.md 末尾
