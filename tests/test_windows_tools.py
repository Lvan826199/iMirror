from imirror import windows_tools


def test_find_tool_dir_requires_all_reference_tools(monkeypatch):
    base = r"C:\qvh\tools"
    present = {base + "\\" + rel for rel in windows_tools.TOOL_FILES.values()}
    monkeypatch.setenv("IMIRROR_QVH_TOOLS", base)
    monkeypatch.setattr(windows_tools.Path, "exists", lambda self: str(self) in present)

    assert str(windows_tools.find_tool_dir()) == base


def test_tool_path_does_not_fall_back_to_path(monkeypatch):
    monkeypatch.delenv("IMIRROR_QVH_TOOLS", raising=False)
    monkeypatch.setattr(windows_tools, "find_tool_dir", lambda: None)

    assert windows_tools.tool_path("usbmuxd") is None


def test_doctor_reports_missing_tool_dir(monkeypatch, capsys):
    monkeypatch.setattr(windows_tools.sys, "platform", "win32")
    monkeypatch.setattr(windows_tools, "find_tool_dir", lambda: None)

    assert windows_tools.doctor() == 1
    out = capsys.readouterr().out
    assert "quicktime_video_hack_windows tools check" in out
    assert "tool directory not found" in out


def test_poc_check_runs_bundled_tools(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(windows_tools, "doctor", lambda **kwargs: 0)
    monkeypatch.setattr(windows_tools, "idevice_id", lambda args: calls.append(("id", args)) or 0)
    monkeypatch.setattr(windows_tools, "ideviceinfo", lambda args: calls.append(("info", args)) or 0)

    assert windows_tools.poc_check("serial") == 0

    assert calls == [("id", ["-l"]), ("info", ["-u", "serial"])]
    out = capsys.readouterr().out
    assert "windows-usbmuxd" in out
    assert "--udid serial" in out


def test_poc_check_stops_when_tools_missing(monkeypatch):
    calls = []
    monkeypatch.setattr(windows_tools, "doctor", lambda **kwargs: 1)
    monkeypatch.setattr(windows_tools, "idevice_id", lambda args: calls.append(("id", args)) or 0)
    monkeypatch.setattr(windows_tools, "ideviceinfo", lambda args: calls.append(("info", args)) or 0)

    assert windows_tools.poc_check() == 1
    assert calls == []
