# MSCA iMirror 投屏集成计划（iMirror 侧）

> 状态：方案留档，尚未实施
> 制定日期：2026-07-10
> 对应主计划：MSCA `doc/iOS-iMirror投屏集成计划.md`
> 本文定位：定义 iMirror 为 MSCA 提供 macOS 实时 H.264 视频能力时的实施范围、接口契约、测试门槛和交接方式。

## 1. 目标

MSCA 计划将 iOS 能力拆分为：

- 控制继续使用 WebDriverAgent（WDA）；
- 视频在 macOS 上优先使用 iMirror；
- iMirror 启动失败或运行中断时，由 MSCA 降级到现有 WDA MJPEG/截图方案。

iMirror 只负责“取得可复用的视频流”，不负责 MSCA 的控制和产品策略。

目标调用关系：

```text
iPhone/iPad
   ↓ CoreMediaIO / AVFoundation .muxed
Swift headless capture helper
   ↓ framed IPC
Python CaptureSession
   ↓ Annex-B H.264 VideoFrame
MSCA ImirrorH264VideoBackend
   ↓ WebSocket
MSCA 前端 WebCodecs
```

## 2. 与 MSCA 主计划的关系

两个仓库使用同一组阶段编号：

| 阶段 ID | 主要工作仓库 | iMirror 侧职责 |
| :--- | :--- | :--- |
| `IMIRROR-MSCA-P0` | 两边只读/真机 | 配合验证现有 `macos-gui` 与 WDA 控制能否共存，不改代码 |
| `IMIRROR-MSCA-P1` | iMirror | 实现 macOS headless H.264 POC，不接 MSCA |
| `IMIRROR-MSCA-P2` | iMirror | 收敛公共 Python API、错误模型、测试和文档 |
| `IMIRROR-MSCA-P3` | MSCA | iMirror 仅提供已冻结版本和问题支持 |
| `IMIRROR-MSCA-P4` | MSCA | 配合验证首帧超时、运行中断和 fallback |
| `IMIRROR-MSCA-P5` | 两边 | macOS 打包、TCC、签名、多设备和长稳验收 |

主计划负责跨项目总体决策；本文负责 iMirror 采集侧细节。任何接口或阶段决策变化都要同步两边相关章节。

## 3. 硬性边界

### 3.1 iMirror 应提供

- 按 UDID 选择 `.muxed` iPhone/iPad；
- 无窗口实时采集；
- 可独立验证的 H.264 输出；
- SPS/PPS、IDR、宽高、PTS 和格式变化；
- Python async queue/iterator；
- 首帧等待、超时、停止、取消和异常；
- helper 退出、设备断开和权限失败的明确错误；
- bounded queue 和不会无限积压的读取链路；
- 无真机测试及 macOS 真机验收步骤。

### 3.2 iMirror 不应提供

- WDA 启动或 Session；
- 点击、滑动、输入和按键；
- FastAPI 或 MSCA WebSocket；
- `auto / imirror / wda` 选择策略；
- WDA MJPEG fallback；
- MSCA 前端组件和配置页面；
- Windows 生产环境的默认启用策略。

### 3.3 禁止的耦合方式

- MSCA 直接解析 Swift helper 私有二进制协议；
- MSCA 复制 iMirror 的 Swift 或 Python 源码；
- iMirror 导入 MSCA 的 driver、配置或 WebSocket 模块；
- 为了接入 MSCA 改变 raw USB 协议字节；
- 使用增长中的 `.mov` 文件作为实时视频管道；
- 将原始 BGRA 帧跨进程交给 Python 再软件编码。

## 4. 当前能力与缺口

当前 macOS native 路线位于 `imirror/macos_native.py`，已具备：

- CoreMediaIO 开启 screen capture device；
- `.muxed` 设备发现和 UDID 选择；
- `AVCaptureMovieFileOutput` 录制；
- `AVCaptureVideoPreviewLayer` 独立窗口预览；
- 缓存的 ad-hoc 签名 Swift helper。

接入 MSCA 前尚缺：

- `AVCaptureVideoDataOutput` sample buffer delegate；
- headless stream mode；
- 压缩 H.264 能力探测；
- 必要时的 VideoToolbox 编码；
- Annex-B access unit 输出；
- helper 与 Python 的结构化 IPC；
- 公共 `CaptureSession`；
- 首帧、旋转、断线和清理测试。

raw USB 路线已有 `Consumer.consume(CMSampleBuffer)`、AVCC/Annex-B 处理和 H.264 writer，可复用帧语义和序列化经验，但 macOS native 路线不得假设会直接复用 raw USB 会话。

## 5. 阶段 P0：无代码共存验证

### 5.1 目的

在投入开发前确认：同一台 iPhone 上，MSCA 的 WDA 控制与 iMirror 的 macOS 原生视频可以同时稳定工作。

### 5.2 操作

1. 记录环境：Mac 型号、macOS、Xcode/Swift、设备型号、iOS、线缆和接口；
2. 按 MSCA 当前方式启动 WDA 控制；
3. 不连接或关闭 WDA MJPEG 画面读取，只保留控制；
4. 在 iMirror 环境运行：

```bash
.venv/bin/python -m imirror macos-gui --udid <UDID>
```

5. 连续执行点击、滑动、输入、Home、锁屏/解锁；
6. 横竖屏往返切换；
7. 停止并重启 iMirror 预览；
8. 拔线重连；
9. 连续运行至少 30 分钟。

### 5.3 PASS 条件

- iMirror 画面持续更新；
- WDA 控制无明显延迟增长；
- 旋转后画面和控制均恢复；
- 没有 `valeria connection not seen`、设备被占用或 WDA tunnel 中断；
- 停止后 helper 和采集会话释放；
- 结果能够稳定复现，不是单次偶然成功。

P0 为硬决策门。失败时先归因资源冲突，不得绕过并直接开发 MSCA backend。

## 6. 阶段 P1：headless H.264 POC

### 6.1 实施顺序

#### 第一步：探测直接压缩输出

- 为 `AVCaptureSession` 增加 `AVCaptureVideoDataOutput`；
- 枚举连接可用 codec；
- 真机记录 `.muxed` 是否提供 H.264；
- 如果提供，直接处理压缩 `CMSampleBuffer`；
- 提取 SPS/PPS，将 AVCC NAL 转为 Annex-B。

#### 第二步：VideoToolbox fallback

直接 H.264 不可用时：

- 获取 NV12/CVPixelBuffer；
- Swift 内创建 `VTCompressionSession`；
- 设置 real-time；
- 禁止 frame reordering/B 帧；
- IDR 初始间隔设为 1～2 秒并通过实测调整；
- 旋转或尺寸变化时安全重建编码器；
- 输出 SPS/PPS + IDR。

### 6.2 POC 输出协议

建议 helper stdout 只承载长度前缀二进制记录，stderr 只输出日志。

记录类型：

| 类型 | 内容 |
| :--- | :--- |
| `CONFIG` | codec、宽高、SPS/PPS、时间基 |
| `FRAME` | PTS、keyframe 标记、Annex-B access unit |
| `ERROR` | 稳定错误码、阶段和可读错误信息 |
| `EOS` | 正常结束或设备断开原因 |

要求：

- 支持半包和粘包；
- payload 长度有上限检查；
- helper 异常退出时 Python 不永久阻塞；
- 取消时能够打断读取；
- 不使用逐帧 JSON/base64；
- 每个 IDR 建议附加 SPS/PPS；
- stdout 中不得混入 `print` 调试日志。

### 6.3 POC 验收

- 独立消费者可连续解码；
- 输出是完整 access unit，而不是任意 chunk；
- 首个 SPS/PPS + IDR 在目标时间内到达；
- 旋转后重新获得正确配置和关键帧；
- 连续运行 30～60 分钟；
- 拔线、锁屏、helper kill 均能返回明确结果；
- 停止后没有 Swift helper、编码器或 reader task 残留。

P1 不接入 MSCA，也不在 MSCA 中临时解析 POC 协议。

## 7. 阶段 P2：公共 Python API

### 7.1 建议 API

名称实施时可调整，但语义应稳定：

```python
session = await open_video_stream(
    udid="...",
    backend="macos-native",
    queue_size=30,
)

await session.wait_first_frame(timeout=5.0)

async for frame in session.frames():
    ...

await session.stop()
```

帧模型建议：

```python
@dataclass(frozen=True)
class VideoFrame:
    data: bytes
    is_keyframe: bool
    width: int
    height: int
    pts_ns: int
```

### 7.2 生命周期约定

- `start/open` 成功不等于视频成功，必须等待可解码关键帧；
- `wait_first_frame` 只有收到 SPS/PPS + IDR 后才成功；
- `stop` 必须幂等；
- 调用方取消时 helper 必须退出；
- queue 满时不能无限阻塞采集 delegate；
- 设备断开、权限拒绝、首帧超时和编码失败必须区分；
- 错误信息中保留底层诊断，但对外提供稳定错误类别；
- Python API 不暴露 Swift 进程 stdout 的私有格式。

### 7.3 错误类别建议

| 类别 | 示例 |
| :--- | :--- |
| `unsupported_platform` | 非 macOS 调用 native backend |
| `permission_denied` | Screen Recording/TCC 未授权 |
| `device_not_found` | UDID 不存在或 `.muxed` 不可见 |
| `device_busy` | 其他 ScreenCapture 客户端占用 |
| `stream_start_failed` | Valeria/StartStream 失败 |
| `first_frame_timeout` | 会话启动但未获得可解码关键帧 |
| `encoder_failed` | VideoToolbox 创建或编码失败 |
| `device_disconnected` | 运行中拔线或设备离线 |
| `helper_crashed` | Swift helper 非正常退出 |
| `protocol_error` | IPC 记录损坏或超限 |

### 7.4 P2 测试要求

无真机测试至少覆盖：

- IPC 半包/粘包；
- 非法长度和未知记录；
- CONFIG/FRAME/ERROR/EOS；
- SPS/PPS + IDR 首帧门；
- helper 正常退出和异常退出；
- 首帧超时；
- stop 幂等；
- task 取消；
- bounded queue；
- 多订阅者策略（如果公共 API 支持）。

必须运行：

```bash
.venv/bin/python -m pytest tests/ -q
```

真机测试需记录：

- 直接 H.264 或 VideoToolbox 路径；
- 首帧时间；
- FPS、延迟、CPU 和内存；
- 旋转恢复；
- 断线和重连；
- 30～60 分钟长稳；
- helper 清理结果。

## 8. 向 MSCA 的交接契约

P2 通过后，iMirror 应向 MSCA 提供一份固定交接记录：

| 项目 | 要求 |
| :--- | :--- |
| iMirror 版本 | tag、版本号或完整 commit |
| Python 版本范围 | 与 MSCA 后端环境兼容 |
| 平台范围 | 首版明确为 macOS native |
| API 示例 | 最小 start/read/stop 示例 |
| 帧格式 | Annex-B、一个 queue item 对应一个 access unit |
| 首帧定义 | SPS/PPS + IDR |
| 尺寸变化 | 事件或帧字段的更新规则 |
| 错误类型 | 稳定错误类别和是否可重试 |
| 线程/async 约定 | 回调线程和事件循环边界 |
| 资源清理 | stop、取消、进程退出保证 |
| 测试结果 | pytest、真机环境和长稳结论 |
| 已知限制 | TCC、设备占用、平台和多设备限制 |

MSCA 只依赖这份公共契约，不依赖 `macos_native.py` 内部 Swift 源码结构。

## 9. 依赖和版本策略

- POC 阶段允许 MSCA 与 iMirror 使用相邻工作区和 editable install；
- 正式接入前 iMirror 必须先形成独立 commit；
- 推荐发布新的 iMirror 版本/tag 后，由 MSCA 固定版本或 commit；
- MSCA 的锁文件必须记录确切版本，不能长期指向浮动分支；
- 破坏公共 API 时升级版本并同步迁移说明；
- MSCA 回滚到 WDA 时不要求删除 iMirror，但应能完全不启动 helper。

## 10. 跨项目评估表

同一设备至少完成以下对照：

| 组别 | 视频源 | 控制 | 目的 |
| :--- | :--- | :--- | :--- |
| A | WDA MJPEG/截图 | WDA | 当前生产基线 |
| B | iMirror | 无或只观察 | iMirror 自身采集基线 |
| C | iMirror | WDA | 最终目标组合 |

记录指标：

- 首个可解码关键帧耗时；
- FPS；
- 真机与画面延迟；
- 是否出现持续累计延迟；
- helper/Python/MSCA CPU 和内存；
- 丢帧和关键帧重同步；
- 横竖屏恢复时间；
- 控制成功率和明显延迟；
- 拔线、锁屏、helper 崩溃后的恢复；
- 停止后的进程、任务和端口清理。

结论规则：

- `PASS`：阻塞项全部通过；
- `CONDITIONAL PASS`：仅有不阻塞下一阶段且已记录的问题；
- `FAIL`：资源冲突、无法稳定解码、控制失效、泄漏或不可恢复；
- 偶发一次成功但无法稳定复现，按 FAIL 或待复测处理。

## 11. 后续执行指令模板

### P0：只验证，不改代码

```text
按 docs/MSCA-iMirror投屏集成计划.md 执行 IMIRROR-MSCA-P0。
只做 macOS 真机共存测试，不修改代码。
输出环境、步骤、日志、运行时长和 PASS/FAIL 结论。
```

### P1：只改 iMirror

```text
执行 IMIRROR-MSCA-P1，只修改 iMirror，不修改 MSCA。
先避让工作区已有改动，实现并验证 headless H.264 POC，
同步 README/联调手册/已知问题等受影响文档，不接 MSCA。
```

### P2：冻结 iMirror API

```text
执行 IMIRROR-MSCA-P2，只修改 iMirror。
将 POC 收敛为公共 Python API，补全无真机测试和 macOS 真机验收，
输出版本/commit、接口契约、错误类型和 MSCA 交接清单。
```

P2 通过后再切换到 MSCA 仓库执行 P3，禁止两个项目在接口未定时同时大范围开工。

## 12. 实施时的 iMirror 文档纪律

实施代码时继续遵守项目根目录 `AGENTS.md`：

- 修改 CLI 参数/行为、依赖分组或协议逻辑时，同一提交同步文档；
- 修复 bug 时更新 `docs/已知问题与归因.md`；
- raw USB 协议逻辑以 Go 参考实现为权威；
- `reference/` 只读；
- 报文序列化改动必须运行字节级测试；
- pyusb 调用点捕获异常必须包含 `(usb.core.USBError, NotImplementedError, ValueError)`。

本专项优先修改 macOS native 采集能力，不应为了 MSCA 集成顺带重写 raw USB 协议。

## 13. 实施前检查清单

- [ ] 确认当前 iMirror 工作区已有改动及归属，避免覆盖用户工作；
- [ ] P0 共存测试通过；
- [ ] 确认 macOS 和真机版本；
- [ ] 确认 Screen Recording 权限和 helper 签名状态；
- [ ] 确认直接 H.264 能力探测方式；
- [ ] 明确 P1 只做 POC、不承诺稳定 API；
- [ ] P1 通过后再设计 P2 API；
- [ ] P2 API 冻结后再通知 MSCA 开始 P3；
- [ ] iMirror 和 MSCA 分别提交、分别记录测试；
- [ ] Windows/Linux 不纳入 macOS 首版默认启用范围。

## 14. 参考

- MSCA 主计划：本机 `E:\Y_pythonProject\MSCA\doc\iOS-iMirror投屏集成计划.md`
- `README.md`
- `docs/协议速查.md`
- `docs/真机联调手册.md`
- `docs/已知问题与归因.md`
- [Apple AVCaptureVideoDataOutput](https://developer.apple.com/documentation/avfoundation/avcapturevideodataoutput)
- [Apple VideoToolbox](https://developer.apple.com/documentation/videotoolbox)
- [Appium WebDriverAgent](https://github.com/appium/WebDriverAgent)
