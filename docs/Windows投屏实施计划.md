# Windows iOS 投屏实施计划

更新时间：2026-07-10

目标：在 Windows 上尽快跑通 iOS 投屏，并把可产品化路线和高级 raw USB 路线分开推进。

## 总体判断

- **默认产品路线**：AirPlay backend。用户不换驱动，不碰 Zadig，通过控制中心“屏幕镜像”连接 iMirror。
- **当前重点验证路线**：raw USB + chotgpt tools。项目已内置 `tools/usbmuxd.exe` 等参考工具，先复现成功案例，再决定是否把 raw USB 做成内部高级功能。
- **后续研究路线**：Apple 官方驱动 + USB Live Screen。目标是不换驱动拿到有线画面，但不作为当前阻塞项。

## W0：准备和基线

目的：确认当前仓库、工具、Python 环境全部可用。

命令：

```powershell
git pull
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m imirror windows-tools-doctor
.venv\Scripts\python.exe -m imirror windows-doctor
```

验收：

- 测试通过，当前预期 `40 passed`；
- `windows-tools-doctor` 找到 `tools/usbmuxd.exe`、`ideviceinfo.exe`、驱动安装器；
- `windows-doctor` 能说明 AirPlay/UxPlay 缺口或通过。

## W1：复现 chotgpt raw USB 工具链

目的：先照成功案例走，确认内置 `usbmuxd.exe` 是否能让设备进入 QuickTime 模式。

步骤：

1. 保持 Apple 官方驱动可用，连接手机并信任；
2. 如需 raw USB，按高级模式使用参考驱动安装器或 Zadig 切到 libusb0/libusb-win32；
3. 开一个终端启动参考 usbmuxd：

```powershell
.venv\Scripts\python.exe -m imirror windows-usbmuxd
```

4. 另开终端检查设备：

```powershell
.venv\Scripts\python.exe -m imirror windows-ideviceinfo
.venv\Scripts\python.exe -m imirror devices --json
```

验收：

- `windows-usbmuxd` 保持运行，不立即退出；
- `windows-ideviceinfo` 能输出设备信息；
- `devices --json` 能看到目标设备和 QT 状态；
- 若失败，记录 usbmuxd 控制台输出、设备管理器驱动名、手机是否弹信任。

## W2：raw USB 录制最小闭环

目的：在参考 usbmuxd 运行时，验证 Python raw USB 是否能收到首个 PING 和视频帧。

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
- 失败时必须保存完整 `record.log`，按 `docs/已知问题与归因.md` 追加根因。

## W3：Windows AirPlay MVP

目的：给小白用户准备不换驱动的默认路线。

步骤：

1. 准备 UxPlay：优先安装 Windows 版 MSI；portable zip 则把 `uxplay-windows.exe` 放到
   `tools/uxplay/uxplay-windows.exe`，或设置 `IMIRROR_UXPLAY`；
2. 启动检查和接收端：

```powershell
.venv\Scripts\python.exe -m imirror windows-doctor
.venv\Scripts\python.exe -m imirror windows-airplay
```

3. iPhone 控制中心 → 屏幕镜像 → 选择 `iMirror`。

验收：

- 手机能发现 `iMirror`；
- Windows 能显示镜像窗口；
- 防火墙、Bonjour、同网问题有明确提示；
- 能稳定预览 10 分钟。

## W4：收敛成可交付 Windows 体验

目的：把验证结果变成内部可用工具。

任务：

- `setup-windows.bat` 检查内置 tools 和 AirPlay helper；
- `windows-gui` 或 `gui --backend airplay/raw-usb` 的提示文案统一；
- raw USB 成功后接 `gui --backend raw-usb` 预览；
- AirPlay 成功后评估录制能力；
- 写一份内部使用手册，分“小白 AirPlay”和“高级 raw USB”。

验收：

- 新电脑按手册 15 分钟内完成 AirPlay 投屏；
- 高级模式有明确驱动/服务/日志要求；
- 失败路径不会让用户盲目重装驱动；
- GitHub/Gitee 私有仓库拉取后 tools 可直接使用。

## 当前优先级

1. 先执行 W1：启动内置 `windows-usbmuxd`，确认参考工具链可跑。
2. 再执行 W2：用 Python raw USB 录制 10 秒，看是否进到 PING/视频帧。
3. 同时准备 W3：补齐 UxPlay helper，验证 AirPlay 发现链路。

## 本轮需要用户反馈的日志

- `windows-usbmuxd` 终端完整输出；
- `windows-ideviceinfo` 输出；
- `record -v` 完整日志；
- 设备管理器中 iPhone 当前驱动名；
- 如果走 AirPlay：手机是否能看到 `iMirror`、Windows 防火墙是否弹窗。
