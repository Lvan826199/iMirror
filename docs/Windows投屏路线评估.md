# Windows 投屏路线评估

更新时间：2026-07-10

结论：Windows 方案重新聚焦 **QuickTime raw USB 有线投屏**。`chotgpt/quicktime_video_hack_windows` 不只是源码参考，更是 Windows 工具链和产品化交付参考；当前只维护这条有线 QuickTime 路线。

## 路线优先级

| 优先级 | 路线 | 用户门槛 | 成功案例 | 当前结论 |
| --- | --- | --- | --- | --- |
| 1 | chotgpt QuickTime 工具链直接验证 | 中：内置 tools，少下载少选择 | quicktime_video_hack_windows | **当前主线** |
| 2 | 集成 chotgpt exe/DLL/核心库 | 中：最快接入 MSCA POC | quicktime_video_hack_windows | POC 成功后评估 |
| 3 | 移植关键逻辑到 iMirror Python | 高：长期最干净，但 Windows 坑最多 | iMirror raw USB | 后续收敛路线 |
| 4 | Apple 官方驱动 + USB Live Screen | 中：不换驱动但私有入口不明 | iDescriptor 标注支持 Live Screen | 第二阶段研究 |

## chotgpt 项目的三层价值

### 1. 协议层参考

- QuickTime raw USB 激活流程；
- bulk 读写与接口选择；
- PING/SYNC/ASYN/NEED；
- Windows 读超时后的 vendor `0x40/0x40/0x6400/0x6400` 唤醒敲门；
- 音视频回调与 Qt 预览示例。

### 2. Windows 工具链参考

仓库 `tool/` 目录包含：

- 修改过的 `usbmuxd.exe`，用于监听 37015 并辅助设备进入 QuickTime 模式；
- `ideviceinfo.exe` / `idevice_id.exe` / `iproxy.exe`；
- 驱动安装器和 libusb 运行库；
- 可用于验证的 Qt 示例和 release 产物。

本项目是私有化内部使用，已将这些 tools 直接 vendor 到 `tools/`，并保留上游 `LICENSE` / `README.md` 作为来源记录。

### 3. 产品化交付参考

产品化方向不应要求用户自行拼驱动工具、libusb、DLL 和 usbmuxd。Windows 内部版应优先做到：

```text
信任设备 → 一键脚本检查/准备工具 → 启动有线投屏程序
```

第三方驱动工具只作为开发者排障兜底，不作为默认用户路径。

## 对 MSCA 的意义

Windows QuickTime POC 不应先从“Python 纯复现所有 Windows libusb 行为”开始，而应先验证：

1. 用 `tools/` 内置工具完成驱动/服务准备；
2. 用 chotgpt Windows 程序或工具链跑通 iPhone 有线投屏；
3. 同时启动 MSCA 的 WDA 控制，验证点击/滑动是否仍然生效；
4. 成功后再选择集成方式。

集成方式评估：

| 方式 | 优点 | 缺点 |
| --- | --- | --- |
| 直接调用 chotgpt exe | 最快验证，改动小 | 视频帧接入 MSCA 可能麻烦 |
| 调 chotgpt DLL/核心库 | 更适合产品化 | 要确认导出接口和编译方式 |
| 移植关键逻辑到 iMirror | 长期最干净 | 最慢，Windows 坑最多 |
| iMirror 复用工具链、保留 Python 协议 | 折中 | 需要维护边界 |

当前更倾向：先用 chotgpt 工具/产物做 Windows POC，不急着让 iMirror 纯 Python 复现全部 Windows 行为。

## 当前实现决策

- 内置 chotgpt 参考 tools 到 `tools/`；
- 新增 `imirror windows-tools-doctor` / `windows-usbmuxd` / `windows-ideviceinfo` / `windows-driver-installer`；
- `imirror gui` 默认 raw USB，有线优先；
- 下一阶段优先执行 `docs/Windows投屏实施计划.md` 的 W1/W2：先跑 chotgpt 工具链，再跑 Python raw USB 录制。

## 参考

- https://github.com/chotgpt/quicktime_video_hack_windows
- https://github.com/YueChen-C/ios-screen-record
