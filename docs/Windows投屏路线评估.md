# Windows 投屏路线评估

更新时间：2026-07-10

结论：Windows 小白版不再把 raw USB QuickTime 作为默认主线。默认路线改为
AirPlay Receiver；Apple 官方驱动/USB Live Screen 作为第二阶段调研；现有
raw USB QuickTime 保留为高级/实验模式。

## 路线对比

| 路线 | 用户门槛 | 成功案例 | 难度 | 当前结论 |
| --- | --- | --- | --- | --- |
| AirPlay Receiver | 低：手机控制中心点“屏幕镜像” | UxPlay、iDescriptor | 中 | Windows 默认主线 |
| Apple 官方驱动 + USB Live Screen | 中：不换驱动，但需摸清 Apple/Windows 私有入口 | iDescriptor 标注支持 Live Screen | 高 | 第二阶段验证 |
| raw USB QuickTime + libusb-win32 | 高：Zadig、禁用服务、驱动冲突、重枚举 | quicktime_video_hack_windows、ios-screen-record | 高 | 保留为高级模式 |
| QuickTime for Windows | 中：旧组件、安全风险 | 官方已停止支持 | 高且不稳定 | 放弃 |

## 外部成功案例

- UxPlay：开源 AirPlay Mirror/Audio receiver，上游项目支持 AirPlay 镜像，适合先作为
  Windows AirPlay backend 的外部 helper。参考：https://github.com/FDH2/UxPlay
- UxPlay Windows 打包：提供 Windows 版 UxPlay 发行包，适合第一阶段快速验证。
  参考：https://github.com/leapbtw/uxplay-windows/releases
- iDescriptor：跨平台 iDevice 管理工具，功能表包含 AirPlay 和 Live Screen，Windows 安装说明
  依赖 Apple mobile device drivers，而不是要求普通用户换 Zadig 驱动。参考：
  https://idescriptor.com/ 与 https://github.com/iDescriptor/iDescriptor
- quicktime_video_hack_windows：证明 Windows raw USB QuickTime 可以做成，但需要 usbmuxd、
  libusb0/libusb 驱动路径，用户门槛高。参考：https://github.com/chotgpt/quicktime_video_hack_windows
- ios-screen-record：Windows 文档走 libusb-win32 + usbmuxd，进一步说明 raw USB 路线绕不开
  驱动安装/服务处理。参考：https://github.com/YueChen-C/ios-screen-record

## 难度评估

### 第一阶段：AirPlay MVP

目标：`python -m imirror gui` 在 Windows 上启动 AirPlay receiver，iPhone 控制中心能看到
`iMirror` 并投屏。

预估：2-4 天完成可验证 MVP；1-2 周做成相对稳定的预览/录制/打包体验。

技术策略：先用 UxPlay 作为外部 helper，iMirror 负责检查、启动和后续打包集成。这样能最快
验证 Windows 防火墙、mDNS/Bonjour、手机发现链路是否顺。

### 第二阶段：Apple 官方驱动 / USB Live Screen

目标：保留 Apple 官方驱动，不碰 Zadig，通过 Apple Mobile Device Support 或类似 iDescriptor
的 Live Screen 路径拿到画面。

预估：2-4 周起步，风险高。关键不确定性是 Windows 上可调用的 Apple 私有入口、授权/签名、
是否需要 native helper。

### 保留路线：raw USB QuickTime

目标：继续作为开发者实验路径，保留现有 `devices`/`activate`/`record`/`gui --backend raw-usb`。

预估：能继续推进，但不适合默认产品体验。Zadig、libusb-win32、Apple Mobile Device Service、
重枚举后驱动绑定等问题会制造大量售后成本。

## 当前实现决策

- Windows 上 `imirror gui` 默认等价于 `imirror gui --backend airplay`。
- 老 USB 预览显式使用：`imirror gui --backend raw-usb`。
- 新增 `imirror windows-doctor` 检查 Bonjour/mDNS 和 UxPlay。
- 新增 `imirror windows-airplay` 启动 UxPlay receiver。
- `record out.h264 out.wav` 暂时仍是 raw USB 录制；AirPlay 录制会在 AirPlay 预览跑通后再接。
