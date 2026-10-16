import sys
from pathlib import Path

from otp_bridge import __main__ as cli


def test_startup_shortcut_targets_frozen_exe(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\OtpBridge.exe")
    assert cli.startup_command() == (Path(r"C:\Apps\OtpBridge.exe"), "")


def test_startup_shortcut_uses_module_when_not_frozen(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    target, arguments = cli.startup_command()
    assert arguments == "-m otp_bridge"
    assert target.parent == Path(sys.executable).parent
