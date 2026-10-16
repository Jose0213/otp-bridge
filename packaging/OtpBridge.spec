# Build with:  pyinstaller packaging/OtpBridge.spec
# Produces dist/OtpBridge.exe, a single windowed (no console) executable.
from pathlib import Path

from otp_bridge.app import _icon_image

ico = Path(workpath) / "otp-bridge.ico"
ico.parent.mkdir(parents=True, exist_ok=True)
_icon_image().save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

a = Analysis(
    [str(Path(SPECPATH) / "entry.py")],
    hiddenimports=["pystray._win32", "win32com.client"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="OtpBridge",
    console=False,
    icon=str(ico),
    upx=False,
)
