# Windows iOS 有线投屏实施计划

更新时间：2026-07-10

目标：在 Windows 上优先跑通 **QuickTime raw USB 有线投屏**，并验证它能否与 MSCA/WDA 控制共存。

## 总体判断

- **当前主线**：chotgpt QuickTime 工具链直接验证。项目已内置 `tools/usbmuxd.exe`、`ideviceinfo.exe`、驱动安装器等配套工具。
- **第一目标**：不先写大量新代码，先用现成 Windows 工具链跑通有线投屏。
- **第二目标**：有线投屏成功后，同时运行 MSCA/WDA 控制，验证点击、滑动、输入是否共存。
- **第三目标**：根据 POC 结果决定直接调用 exe、集成 DLL/核心库，还是把逻辑逐步移植回 iMirror。

## W0：准备和基线

目的：确认当前仓库、内置工具和 Python 环境可用。

命令：

```powershell
git pull
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m imirror windows-poc-check
```

验收：

- 测试通过，当前预期 `39 passed`；
- `windows-poc-check` 找到 `tools/usbmuxd.exe`、`ideviceinfo.exe`、驱动安装器，并能跑 chotgpt 设备预检；
- 不要求用户自行下载驱动工具、usbmuxd、ideviceinfo 或 DLL。

## W1：复现 chotgpt raw USB 工具链

目的：先照成功案例走，确认内置 `tools/` 能把设备带到 QuickTime raw USB 路线。

步骤：

1. 连接 iPhone，解锁并信任电脑；
2. 使用内置工具检查设备：

```powershell
.venv\Scripts\python.exe -m imirror windows-poc-check
```

3. 如需驱动准备，优先打开内置参考驱动安装器：

```powershell
.venv\Scripts\python.exe -m imirror windows-driver-installer
```

4. 开一个终端启动参考 usbmuxd，并保持运行：

```powershell
.venv\Scripts\python.exe -m imirror windows-usbmuxd
```

5. 另开终端检查 iMirror 看到的设备状态：

```powershell
.venv\Scripts\python.exe -m imirror devices --json
```

验收：

- `windows-usbmuxd` 保持运行，不立即退出；
- `windows-poc-check` 能通过 `idevice_id` / `ideviceinfo` 输出设备信息；
- `devices --json` 能看到目标设备和 QT 状态；
- 若失败，记录 usbmuxd 控制台输出、设备管理器驱动名、手机是否弹信任。

## W2：Python raw USB 录制最小闭环

目的：在参考 usbmuxd 运行时，验证 iMirror Python raw USB 是否能收到首个 PING 和视频帧。

命令：

```powershell
.venv\Scripts\python.exe -m imirror -v record out.h264 out.wav --duration 10 --udid 设备序列号
```

重点看日志：

- `QT 配置已激活`；
- `已 claim QuickTime 接口`；
- `收到 PING, 回复 PING`；
- `SYNC OG/CWPA/CVRP`；
- `写入参数集`；
- 视频帧数增长。

验收：

- 10 秒内收到至少 1 个视频帧；
- `out.h264` 可用 `ffplay -f h264 out.h264` 播放；
- 失败时保存完整 `record.log`，并按 `docs/已知问题与归因.md` 追加根因。

## W3：chotgpt 产物 / MSCA 共存 POC

目的：如果 Python raw USB 仍卡住，不继续硬啃；直接用 chotgpt 的 Windows 程序或核心库验证“有线视频 + WDA 控制”是否共存。

验证内容：

1. 使用 chotgpt release/Qt 示例或命令行测试程序跑通 iPhone 有线投屏；
2. 同时启动 MSCA/WDA 控制；
3. 连续执行点击、滑动、输入、横竖屏切换；
4. 记录视频流畅度、控制延迟、设备断开和恢复情况。

验收：

- 有线画面稳定；
- WDA 控制不中断；
- 横竖屏后画面和控制均恢复；
- 至少连续运行 10 分钟；
- 明确下一步集成方式：exe、DLL/库，或移植到 iMirror。

## W4：收敛成内部交付体验

任务：

- `setup-windows.bat` 默认检查内置 chotgpt tools；
- 驱动准备优先调用 chotgpt 内置工具，第三方驱动工具仅作为开发者排障兜底；
- raw USB 成功后接 `gui --backend raw-usb` 预览；
- 若 chotgpt exe/DLL 路线更快，先作为 MSCA Windows POC 视频源；
- 写内部使用手册：普通用户只看到“信任设备 → 跑脚本 → 启动程序”。

验收：

- 新电脑拉私有仓库即可获得 tools；
- 15 分钟内完成有线 POC 环境准备；
- 失败路径有明确日志和下一步，不要求用户到处下载工具；
- MSCA 能基于 POC 结果选择集成方式。

## 当前优先级

1. 执行 W1：先跑 `windows-poc-check`，再启动内置 `windows-usbmuxd`，确认参考工具链可跑；
2. 执行 W2：用 Python raw USB 录制 10 秒，看是否进到 PING/视频帧；
3. 若 W2 卡住，执行 W3：直接跑 chotgpt Windows 产物验证视频 + WDA 共存；
4. 执行 W4：把成功路径收敛成内部一键交付流程。

## 本轮需要用户反馈的日志

- `windows-usbmuxd` 终端完整输出；
- `windows-poc-check` 输出；
- `record -v` 完整日志；
- 设备管理器中 iPhone 当前驱动名；
- 如果跑 chotgpt 产物：画面是否出现、WDA 控制是否还能点击/滑动。
