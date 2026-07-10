"""macOS CoreMediaIO/AVFoundation backend for iOS screen capture.

This backend uses Apple's iOSScreenCapture CoreMediaIO plugin instead of the raw
QuickTime/Valeria USB bulk protocol. It is macOS-only and requires Screen
Recording permission for the process that launches it.
"""
from __future__ import annotations

import os
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass


SWIFT_SOURCE = r'''
import AVFoundation
import CoreGraphics
import CoreMediaIO
import Foundation

#if canImport(AppKit)
import AppKit
#endif

struct Options {
    var mode = ""
    var udid: String?
    var output: String?
    var duration = 10.0
    var json = false
}

func die(_ message: String, _ code: Int32) -> Never {
    fputs("ERROR: \(message)\n", stderr)
    exit(code)
}

func parseOptions() -> Options {
    var options = Options()
    var i = 1
    let args = CommandLine.arguments
    while i < args.count {
        let arg = args[i]
        switch arg {
        case "--mode":
            i += 1
            if i >= args.count { die("missing value for --mode", 64) }
            options.mode = args[i]
        case "--udid":
            i += 1
            if i >= args.count { die("missing value for --udid", 64) }
            options.udid = args[i]
        case "--output":
            i += 1
            if i >= args.count { die("missing value for --output", 64) }
            options.output = args[i]
        case "--duration":
            i += 1
            if i >= args.count { die("missing value for --duration", 64) }
            options.duration = Double(args[i]) ?? 10.0
        case "--json":
            options.json = true
        default:
            die("unknown argument \(arg)", 64)
        }
        i += 1
    }
    return options
}

func normalizeUDID(_ value: String) -> String {
    return value.replacingOccurrences(of: "-", with: "").lowercased()
}

func enableScreenCaptureDevices() {
    var allow: UInt32 = 1
    var address = CMIOObjectPropertyAddress(
        mSelector: CMIOObjectPropertySelector(kCMIOHardwarePropertyAllowScreenCaptureDevices),
        mScope: CMIOObjectPropertyScope(kCMIOObjectPropertyScopeGlobal),
        mElement: CMIOObjectPropertyElement(kCMIOObjectPropertyElementMain)
    )
    let status = CMIOObjectSetPropertyData(
        CMIOObjectID(kCMIOObjectSystemObject),
        &address,
        0,
        nil,
        UInt32(MemoryLayout<UInt32>.size),
        &allow
    )
    if status != 0 {
        die("CMIO AllowScreenCaptureDevices failed: \(status)", 70)
    }
}

func discoverDevices(timeout: Double = 5.0) -> [AVCaptureDevice] {
    enableScreenCaptureDevices()
    let deadline = Date().addingTimeInterval(timeout)
    var devices: [AVCaptureDevice] = []
    repeat {
        devices = AVCaptureDevice.devices(for: .muxed)
        if !devices.isEmpty { break }
        RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.2))
    } while Date() < deadline
    return devices
}

func selectDevice(_ devices: [AVCaptureDevice], udid: String?) -> AVCaptureDevice {
    guard !devices.isEmpty else {
        let access = CGPreflightScreenCaptureAccess()
        if !access {
            die("no iOS screen capture device; Screen Recording permission is not granted for this launcher", 13)
        }
        die("no iOS screen capture device found", 2)
    }
    guard let udid = udid else {
        return devices[0]
    }
    let wanted = normalizeUDID(udid)
    if let found = devices.first(where: { normalizeUDID($0.uniqueID) == wanted }) {
        return found
    }
    let seen = devices.map { "\($0.localizedName) \($0.uniqueID)" }.joined(separator: ", ")
    die("device \(udid) not found; visible devices: \(seen)", 2)
}

func ensureScreenRecordingAccess() {
    if CGPreflightScreenCaptureAccess() {
        return
    }
    let granted = CGRequestScreenCaptureAccess()
    if !granted || !CGPreflightScreenCaptureAccess() {
        die("Screen Recording permission denied. Grant permission to the app/terminal launching iMirror, then restart it.", 13)
    }
}

func printDevices(_ devices: [AVCaptureDevice], json: Bool) {
    if json {
        let rows = devices.map {
            [
                "name": $0.localizedName,
                "unique_id": $0.uniqueID,
                "model_id": $0.modelID,
                "device_type": $0.deviceType.rawValue,
                "has_muxed": $0.hasMediaType(.muxed),
                "has_video": $0.hasMediaType(.video),
                "has_audio": $0.hasMediaType(.audio),
            ] as [String : Any]
        }
        let data = try! JSONSerialization.data(withJSONObject: rows, options: [.prettyPrinted, .sortedKeys])
        print(String(data: data, encoding: .utf8)!)
        return
    }
    if devices.isEmpty {
        print("No macOS native iOS screen capture devices.")
        if !CGPreflightScreenCaptureAccess() {
            print("Screen Recording permission is not granted for this launcher.")
        }
        return
    }
    for device in devices {
        print("\(device.uniqueID)  \(device.localizedName)  model=\(device.modelID)  type=\(device.deviceType.rawValue)")
    }
}

final class RecordingDelegate: NSObject, AVCaptureFileOutputRecordingDelegate {
    var done = false
    var started = false
    var error: Error?

    func fileOutput(_ output: AVCaptureFileOutput, didStartRecordingTo fileURL: URL, from connections: [AVCaptureConnection]) {
        started = true
        print("recording started: \(fileURL.path)")
    }

    func fileOutput(_ output: AVCaptureFileOutput, didFinishRecordingTo outputFileURL: URL, from connections: [AVCaptureConnection], error: Error?) {
        self.error = error
        if let error = error {
            fputs("recording error: \(error)\n", stderr)
        }
        print("recording finished: \(outputFileURL.path)")
        done = true
    }
}

func makeSession(device: AVCaptureDevice) -> (AVCaptureSession, AVCaptureDeviceInput) {
    let session = AVCaptureSession()
    session.beginConfiguration()
    if session.canSetSessionPreset(.high) {
        session.sessionPreset = .high
    }
    let input: AVCaptureDeviceInput
    do {
        input = try AVCaptureDeviceInput(device: device)
    } catch {
        die("cannot open capture device: \(error)", 71)
    }
    if !session.canAddInput(input) {
        die("cannot add capture input", 72)
    }
    session.addInput(input)
    session.commitConfiguration()
    return (session, input)
}

func record(options: Options) {
    ensureScreenRecordingAccess()
    let devices = discoverDevices()
    let device = selectDevice(devices, udid: options.udid)
    guard let outputPath = options.output else {
        die("missing --output for record mode", 64)
    }
    let outputURL = URL(fileURLWithPath: outputPath)
    try? FileManager.default.removeItem(at: outputURL)

    let (session, _) = makeSession(device: device)
    let output = AVCaptureMovieFileOutput()
    if !session.canAddOutput(output) {
        die("cannot add movie output", 73)
    }
    session.addOutput(output)

    let delegate = RecordingDelegate()
    session.startRunning()
    if !session.isRunning {
        die("capture session did not start", 74)
    }
    print("using device: \(device.localizedName) \(device.uniqueID)")
    output.startRecording(to: outputURL, recordingDelegate: delegate)

    let startDeadline = Date().addingTimeInterval(5)
    while !delegate.started && Date() < startDeadline {
        RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.1))
    }
    if !delegate.started {
        session.stopRunning()
        if let error = delegate.error {
            die("recording failed before start: \(error). The macOS iOSScreenCaptureAssistant could not start the Valeria stream; keep the iPhone unlocked/trusted, reconnect the cable, and make sure no other app is using iPhone screen capture.", 75)
        }
        die("recording did not start", 75)
    }

    let stopAt = Date().addingTimeInterval(max(0.1, options.duration))
    while Date() < stopAt && !delegate.done {
        RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.1))
    }
    if output.isRecording {
        output.stopRecording()
    }
    let finishDeadline = Date().addingTimeInterval(10)
    while !delegate.done && Date() < finishDeadline {
        RunLoop.current.run(mode: .default, before: Date().addingTimeInterval(0.1))
    }
    session.stopRunning()
    if let error = delegate.error {
        die("recording failed: \(error)", 76)
    }
    if !delegate.done {
        die("recording did not finish", 77)
    }
    let size = (try? FileManager.default.attributesOfItem(atPath: outputPath)[.size] as? NSNumber)?.intValue ?? 0
    if size <= 0 {
        die("recording output is empty", 78)
    }
    print("saved: \(outputPath) (\(size) bytes)")
}

#if canImport(AppKit)
final class PreviewController: NSObject, NSWindowDelegate {
    let session: AVCaptureSession

    init(session: AVCaptureSession) {
        self.session = session
    }

    func windowWillClose(_ notification: Notification) {
        session.stopRunning()
        NSApplication.shared.terminate(nil)
    }
}

var retainedPreviewController: PreviewController?

func preview(options: Options) {
    ensureScreenRecordingAccess()
    let devices = discoverDevices()
    let device = selectDevice(devices, udid: options.udid)
    let (session, _) = makeSession(device: device)

    let app = NSApplication.shared
    app.setActivationPolicy(.regular)

    let contentRect = NSRect(x: 0, y: 0, width: 430, height: 820)
    let window = NSWindow(
        contentRect: contentRect,
        styleMask: [.titled, .closable, .miniaturizable, .resizable],
        backing: .buffered,
        defer: false
    )
    window.title = "iMirror - \(device.localizedName)"
    window.center()

    let view = NSView(frame: contentRect)
    view.wantsLayer = true
    let previewLayer = AVCaptureVideoPreviewLayer(session: session)
    previewLayer.videoGravity = .resizeAspect
    previewLayer.frame = view.bounds
    previewLayer.autoresizingMask = [.layerWidthSizable, .layerHeightSizable]
    view.layer = previewLayer
    window.contentView = view

    let controller = PreviewController(session: session)
    window.delegate = controller
    retainedPreviewController = controller

    session.startRunning()
    if !session.isRunning {
        die("capture session did not start", 74)
    }
    print("previewing device: \(device.localizedName) \(device.uniqueID)")
    window.makeKeyAndOrderFront(nil)
    app.activate(ignoringOtherApps: true)
    app.run()
}
#endif

let options = parseOptions()
switch options.mode {
case "list":
    printDevices(discoverDevices(), json: options.json)
case "record":
    record(options: options)
case "preview":
    #if canImport(AppKit)
    preview(options: options)
    #else
    die("preview is not available without AppKit", 65)
    #endif
default:
    die("missing or unsupported --mode", 64)
}
'''


@dataclass
class NativeResult:
    returncode: int


def _cache_dir() -> Path:
    return Path.home() / "Library" / "Caches" / "imirror"


def _run_script_with_swift(swift: str, args: list[str]) -> NativeResult:
    fd, path = tempfile.mkstemp(prefix="imirror_macos_native_", suffix=".swift")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(SWIFT_SOURCE)
        proc = subprocess.run([swift, "-suppress-warnings", path, *args], check=False)
        return NativeResult(proc.returncode)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _ad_hoc_codesign(helper: Path) -> None:
    codesign = shutil.which("codesign")
    if codesign is None:
        return
    verify = subprocess.run(
        [codesign, "--verify", str(helper)],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if verify.returncode == 0:
        return
    proc = subprocess.run(
        [codesign, "--force", "--sign", "-", str(helper)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0 and proc.stderr:
        print(f"macOS 原生 helper ad-hoc 签名失败: {proc.stderr.strip()}", file=sys.stderr)


def _build_helper(swiftc: str) -> Path | None:
    digest = hashlib.sha256(SWIFT_SOURCE.encode("utf-8")).hexdigest()[:16]
    cache = _cache_dir()
    source = cache / f"macos_native_{digest}.swift"
    helper = cache / f"macos_native_{digest}"
    try:
        cache.mkdir(parents=True, exist_ok=True)
        if not source.exists() or source.read_text(encoding="utf-8") != SWIFT_SOURCE:
            source.write_text(SWIFT_SOURCE, encoding="utf-8")
        if helper.exists() and os.access(helper, os.X_OK):
            _ad_hoc_codesign(helper)
            return helper
        proc = subprocess.run(
            [swiftc, "-suppress-warnings", str(source), "-o", str(helper)],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            proc = subprocess.run(
                [swiftc, str(source), "-o", str(helper)],
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        if proc.returncode != 0:
            if proc.stdout:
                print(proc.stdout, end="")
            if proc.stderr:
                print(proc.stderr, end="", file=sys.stderr)
            return None
        helper.chmod(0o755)
        _ad_hoc_codesign(helper)
        return helper
    except OSError as e:
        print(f"构建 macOS 原生 helper 失败: {e}", file=sys.stderr)
        return None


def _run_swift(args: list[str]) -> NativeResult:
    if sys.platform != "darwin":
        print("macOS 原生后端只支持 macOS。")
        return NativeResult(1)
    swiftc = shutil.which("swiftc")
    swift = shutil.which("swift")
    if swiftc is None and swift is None:
        print("找不到 swift。请先安装 Xcode Command Line Tools: xcode-select --install")
        return NativeResult(1)
    if swiftc is not None:
        helper = _build_helper(swiftc)
        if helper is not None:
            proc = subprocess.run([str(helper), *args], check=False)
            return NativeResult(proc.returncode)
        print("macOS 原生 helper 编译失败, 回退到 swift 解释执行。", file=sys.stderr)
    if swift is not None:
        return _run_script_with_swift(swift, args)
    print("找不到 swift。请先安装 Xcode Command Line Tools: xcode-select --install")
    return NativeResult(1)


def list_devices(json_output: bool = False) -> int:
    args = ["--mode", "list"]
    if json_output:
        args.append("--json")
    return _run_swift(args).returncode


def record(output: str, udid: str | None, duration: float) -> int:
    args = ["--mode", "record", "--output", output, "--duration", str(duration)]
    if udid:
        args.extend(["--udid", udid])
    return _run_swift(args).returncode


def preview(udid: str | None) -> int:
    args = ["--mode", "preview"]
    if udid:
        args.extend(["--udid", udid])
    return _run_swift(args).returncode
