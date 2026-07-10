from imirror import windows_airplay


def test_find_uxplay_uses_explicit_env(monkeypatch):
    exe = r"C:\tools\uxplay.exe"
    monkeypatch.setenv("IMIRROR_UXPLAY", exe)
    monkeypatch.setattr(windows_airplay.shutil, "which", lambda name: None)
    monkeypatch.setattr(windows_airplay.Path, "exists", lambda self: str(self) == exe)

    assert windows_airplay.find_uxplay() == exe


def test_find_uxplay_uses_path(monkeypatch):
    monkeypatch.delenv("IMIRROR_UXPLAY", raising=False)
    monkeypatch.setattr(windows_airplay.shutil, "which", lambda name: "C:/bin/uxplay.exe")

    assert windows_airplay.find_uxplay() == "C:/bin/uxplay.exe"


def test_doctor_reports_missing_uxplay_on_windows(monkeypatch, capsys):
    monkeypatch.setattr(windows_airplay.sys, "platform", "win32")
    monkeypatch.setattr(windows_airplay, "find_uxplay", lambda: None)
    monkeypatch.setattr(windows_airplay, "_has_bonjour", lambda: False)
    monkeypatch.setattr(windows_airplay.socket, "gethostname", lambda: "pc")
    monkeypatch.setattr(windows_airplay.Path, "exists", lambda self: False)

    assert windows_airplay.doctor() == 1
    out = capsys.readouterr().out
    assert "Windows AirPlay 后端检查" in out
    assert "未找到 UxPlay" in out
