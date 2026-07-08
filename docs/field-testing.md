# 真机联调手册

一步一步照做即可。每一步都写了**预期结果**和**不对时看什么**。
遇到卡住的地方，按最后一节收集信息。

## 0. 你需要什么

- 一台 iPhone 或 iPad（不需要越狱，系统版本不限，越新越有验证价值）
- 一根**支持数据传输**的数据线（纯充电线不行，这是最常见的坑）
- 一台 Linux 或 Windows 电脑（不需要 Mac）

## 1. 环境准备

### Linux（推荐先在 Linux 上联调）

本仓库目录下已有 `.venv` 就绪（没有就按 README 的 Installation 一节装）。

USB 权限二选一：

**方式 A：临时用 sudo（先跑通再说）**

```bash
sudo .venv/bin/python -m imirror devices
```

**方式 B：udev 规则（一次配置，永久生效）**

```bash
sudo tee /etc/udev/rules.d/39-imirror.rules <<'EOF'
SUBSYSTEM=="usb", ATTR{idVendor}=="05ac", MODE="0666"
EOF
sudo udevadm control --reload-rules && sudo udevadm trigger
```

之后重新插拔手机，就能免 sudo 运行。

### Windows

按 README「Windows Driver Setup」操作（Zadig 换驱动为 libusbK/WinUSB +
`pip install libusb-package`），命令里的 `.venv/bin/python` 换成
`.venv\Scripts\python.exe`。

## 2. 分步联调

### 第 1 步：连接并信任

用数据线连接手机 → 解锁手机 → 弹出「信任此电脑？」→ 点信任。

> Linux 上信任弹窗依赖 usbmuxd 服务（一般随系统自带）。**先完成信任再进行后面的步骤**；
> 如果后面报 `Resource busy` 再回来 `sudo systemctl stop usbmuxd`。

### 第 2 步：确认能看到设备

```bash
.venv/bin/python -m imirror devices
```

**预期输出**（一行一台设备）：

```
00008110-000A1B2C3D4E5F  iPhone  vid:pid=05ac:12a8  QT配置: 未激活
```

**不对时**：
- 什么都列不出 → 换根数据线；确认手机解锁且已信任；Linux 下先加 `sudo` 试
- 报 `No backend available` → libusb 运行库没装（Linux: `apt install libusb-1.0-0`）

### 第 3 步：激活 QuickTime 配置 ⚠️ 联调重点 1

```bash
.venv/bin/python -m imirror -v activate
```

**预期**：手机会「断开又出现」一次（系统可能有提示音），几秒内打印：

```
xxx QT 配置已激活 (config #N)
```

再跑一次 `devices`，QT配置 应显示「已激活」。

**这一步验证的是代码里的第一个 TODO**：激活请求发出后设备重新枚举，
`activation.py` 轮询 10 次 × 0.5 秒等它回来。**不对时**：
- 报「无法激活」→ 重枚举比 5 秒慢。把 `-v` 日志发出来，
  并告知从手机断开到重新出现大概几秒（可以看 `lsusb` 或 `dmesg -w`）
- 激活成功但下一步打不开 → 记录 `dmesg` 里该时间段的 USB 日志

### 第 4 步：录制 10 秒 ⚠️ 联调重点 2（最关键的一步）

```bash
.venv/bin/python -m imirror -v record out.h264 out.wav --duration 10
```

**预期 `-v` 日志按这个顺序出现**（顺序就是协议握手）：

```
已 claim QuickTime 接口 #N (in:0x8x out:0x0x)
收到 PING, 回复 PING
发送 ASYN HPD1 x2
回复 CWPA clockRef=xxxx
发送 ASYN HPA1
发送首个 NEED, clockRef=xxxx
音频格式: AudioStreamBasicDescription{...48000...}
写入参数集: FormatDescriptor{video 886x1920, codec:avc1, sps:xxB, pps:xxB}   ← 最重要的一行
  [    5s] 视频 xxx 帧 (~30.0fps, x.xMB)  音频 xxx 帧 (xxxKB)
  [   10s] ...
请求设备停止推流...
会话已关闭 (视频帧:N 音频帧:M)
```

**核对点**：
1. `写入参数集` 这行必须出现，且 sps/pps 字节数 > 0
   —— 这验证 `formatdescriptor.py` 的 SPS/PPS 提取位置（代码里标了 TODO 的地方）
2. 统计行的视频帧数持续增长（说明 FEED→NEED 流控正常）
3. 结束时「会话已关闭」前**没有** RELS 超时告警
   —— 这验证刚按 Go 版修正过的 `close_session` 关闭时序

**不对时**：
- 卡在 claim 接口 / 报 `Resource busy` → `sudo systemctl stop usbmuxd` 后重试
- 收到 PING 后没有下文 → 把完整日志发出来（可能是分帧或首包问题）
- 没有「写入参数集」→ **这就是 TODO 命中的情况**，执行
  `.venv/bin/python -m imirror -v record ... 2>&1 | tee record.log` 保留日志，
  这是修 `formatdescriptor.py` 需要的第一手数据
- 帧数不增长/几秒后停 → FEED/NEED 流控问题，同样保留完整日志

### 第 5 步：验证录制产物

```bash
ffplay -f h264 out.h264        # 应该能看到手机屏幕画面
ffprobe -f h264 out.h264       # 应显示正确分辨率, h264 (High) 之类
ffplay out.wav                 # 应该有手机的声音(录制时放段音乐)
```

**核对点**：画面不花屏、分辨率与手机匹配、音频时长 ≈ 10 秒。

- 画面花屏/绿屏但能播 → SPS/PPS 内容可能不对，保留 out.h264 前 1KB：
  `xxd out.h264 | head -60 > h264head.txt`
- wav 是静音 → 录的时候手机放点声音再试一次；仍静音则保留 wav 和日志

### 第 6 步：实时预览（可选）

```bash
.venv/bin/python -m pip install av opencv-python   # 首次需要
.venv/bin/python -m imirror gui                      # 按 q 退出
```

**预期**：弹出窗口显示手机画面，延迟 < 1 秒。卡顿属于已知待优化项（README Roadmap）。

### 第 7 步：恢复手机正常模式

正常退出（Ctrl+C 或 --duration 到时）后设备会自动释放；如果手机的 USB
行为异常（比如电脑不识别了），重新插拔一次数据线即可恢复。

## 3. 联调验收清单

全部打勾即可宣布真机联调完成，把结果同步到 AGENTS.md 的「当前状态」：

- [ ] `devices` 能列出设备
- [ ] `activate` 激活成功（重枚举 ≤ 5 秒）
- [ ] `record` 完整跑通 10 秒无报错
- [ ] 日志出现「写入参数集」且 sps/pps > 0 字节（formatdescriptor.py TODO 销案）
- [ ] `ffplay` 能正常播放 out.h264，画面正确
- [ ] out.wav 有声音
- [ ] 结束时无 RELS 超时告警（close_session 时序验证）
- [ ] 连续录 3 分钟以上不断流（SKEW 应答验证）

## 4. 出问题时收集什么

把以下内容打包，能极大加快远程定位：

```bash
# 1. 完整 DEBUG 日志
.venv/bin/python -m imirror -v record out.h264 out.wav --duration 10 2>&1 | tee record.log
# 2. 设备 USB 描述符
lsusb -d 05ac: -v > lsusb.txt 2>/dev/null
# 3. 内核 USB 日志(激活前后各插拔一次)
dmesg | tail -100 > dmesg.txt
# 4. 环境信息
uname -a > env.txt; .venv/bin/python --version >> env.txt
```

外加一句话描述：卡在第几步、现象是什么、手机型号和 iOS 版本。
