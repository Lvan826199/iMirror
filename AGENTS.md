# iMirror 项目说明（给 AI 编码助手的上下文）

> 本文件是唯一维护的助手说明（AGENTS.md 标准，Codex/Cursor 等直接读取）；
> `CLAUDE.md` 仅是对本文件的引用，内容改这里即可。

iOS 投屏采集的 Python 实验项目；raw USB 后端移植自 Go 版 quicktime_video_hack，
Windows 产品主线是 QuickTime raw USB 有线投屏，并优先复用内置 chotgpt Windows tools。
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

## 当前状态（2026-07-10）

- 项目于 2026-07-07 由 pyqvh 更名为 iMirror（包名 imirror），旧名已全部替换
- 代码托管: https://gitee.com/xiaozai-van-liu/imirror
- 协议层/CoreMedia 层完成并通过 fixture 测试（含真机数据端到端解析），当前测试总数 41
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
  路由不到子接口(Windows 复合设备驱动模型固有问题, 非协议 bug)。C++ 参考的关键
  差异不是用 usbmuxd 承载视频, 而是读超时时发 vendor `0x40/0x40/0x6400/0x6400`
  + 主动 PING 的“唤醒敲门”; Python 已按该路径给 Windows 加兜底, 并给 bulk OUT
  写入加 2s 显式超时、把敲门 PING 失败降为 DEBUG 探测日志；2026-07-10 真机日志
  已证明首个设备 PING 收发成功后不应继续敲门, 现改为只在尚未收到任何设备数据前敲门；
  另一轮日志证明失败会话会残留 active QT 配置但不再出首包, Windows record/gui 现会强制
  重发 QT enable 重新武装会话；若 QT 描述符已暴露但 active config 仍是普通配置, Windows
  也会优先重发 Apple QT enable, 避免直接 set_configuration 后能 claim 但无首个 PING 的假激活态。
  详见 docs/已知问题与归因.md C类#5。
- 2026-07-10 macOS 真机实测: macOS 15.7.7 + iPhone `05ac:12a8`/iOS 18.3
  环境自检/设备发现/QT 激活成功(config #6), 可 claim QuickTime 接口 #2
  (`in:0x86 out:0x05`), 但 bulk 读 10s 无 PING/数据、bulk 写 HPA0/主动 PING
  均超时, 0 帧。已修复: 0帧误报成功、停止时报 traceback、QT 配置描述符存在但
  active config 已回 #5 时误报“已激活”、QT 配置 #6 覆盖 mux 配置 #5、重新激活
  超时。已新增实验性 macOS CoreMediaIO/AVFoundation 原生命令:
  `macos-devices` 可枚举到 iPhone `.muxed` 设备; `macos-record` 已进入 Apple
  `iOSScreenCaptureAssistant` 的 StartStream, 但当前真机返回
  `valeria connection not seen`, native 录制仍未完成。新增 `imirror reset` 可把
  macOS 残留 QT 描述符/半激活状态恢复到干净普通枚举; `macos-*` 优先使用缓存的
  ad-hoc 签名 Swift helper, 避免每次以 `swift-frontend` 临时脚本身份触发 TCC。
  同机 QuickTime Player 在重置信任后选择 iPhone 也弹「这项操作无法完成」；
  日志为 `AVFoundationErrorDomain -11800`/`OSStatus -308`，后台
  `iOSScreenCaptureAssistant` 先发现 Octavia USB 设备后报
  `StartStream throwing valeria connection not seen`。因此该轮阻塞已确认在
  macOS/iPhone 系统 Valeria 链路，不是 Python 报文序列化或端点选择。同机换 iOS
  14.4.2、15.1、16.7.8、17.7.4 的 iPad、iOS 26.2 都可 QuickTime 投屏；此前失败的
  iOS 18.3 设备重启后也恢复成功，并已用 `imirror macos-gui --udid
  00008110-000275943EEB801E` 成功启动原生预览。结论修正为：这是设备/macOS 的临时
  Valeria 状态卡死，重启可恢复，不是 iOS 18.x 大版本兼容问题。
  详见 docs/已知问题与归因.md G/H 类。
- 2026-07-10 Windows 方向纠偏: 主攻 QuickTime raw USB 有线投屏, chotgpt/quicktime_video_hack_windows
  不只是源码参考, 也是 Windows 工具链和产品化交付参考。项目已内置 `tools/` 并新增
  `windows-tools-doctor` / `windows-usbmuxd` / `windows-ideviceinfo` / `windows-driver-installer`。
  `gui` 默认 raw USB；当前只维护有线 QuickTime 路线。下一步按 docs/Windows投屏实施计划.md
  的 W1/W2 先复现 chotgpt 工具链和 Python raw USB 10s 录制；若卡住, W3 直接跑 chotgpt
  Windows 产物验证有线视频 + MSCA/WDA 控制共存。Ubuntu 仍按 raw USB 链路排查。
- 未销案的验证项: SPS/PPS 提取位置(formatdescriptor.py avcC 递归扫描 vs Go 固定 key,
  真机日志里"写入参数集"出现即销案)
- 剩余工作优先级见 README.md 末尾
