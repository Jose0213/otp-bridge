"""Command line: `otp-bridge [run|setup|test|install-startup|uninstall-startup]`."""
import argparse
import logging
import os
import secrets
import sys
from pathlib import Path

from . import __version__, config, setup_info
from .extract import extract_code

STARTUP_LINK = Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup/OTP Bridge.lnk"


def cmd_setup(cfg, args):
    if args.relay:
        server = args.relay_server.rstrip("/")
        cfg["relay_url"] = f"{server}/otp-{secrets.token_hex(12)}"
        config.save(cfg)
    elif args.direct_only:
        cfg["relay_url"] = ""
        config.save(cfg)
    print(setup_info.as_text(cfg))
    if args.relay or args.direct_only:
        print("\nRestart OTP Bridge for the change to take effect.")


def startup_command():
    """(target, arguments) that start the tray app: the exe itself when frozen, else pythonw -m."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable), ""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return (pythonw if pythonw.exists() else Path(sys.executable)), "-m otp_bridge"


def attach_parent_console():
    """The .exe is built without a console, so print() goes nowhere. When it's run from a
    terminal, write to that terminal instead."""
    if not getattr(sys, "frozen", False) or sys.stdout is not None:
        return
    import ctypes

    if ctypes.windll.kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
        sys.stdout = open("CONOUT$", "w", encoding="utf-8")
        sys.stderr = sys.stdout


def cmd_install_startup():
    import win32com.client  # pywin32

    target, arguments = startup_command()
    link = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(STARTUP_LINK))
    link.TargetPath = str(target)
    link.Arguments = arguments
    link.WorkingDirectory = str(Path.home())
    link.Description = "OTP Bridge"
    link.Save()
    print(f"OTP Bridge will start when you sign in ({STARTUP_LINK})")


def main(argv=None):
    if (sys.argv[1:] if argv is None else argv):
        attach_parent_console()
    parser = argparse.ArgumentParser(prog="otp-bridge", description="Autofill one-time codes from your phone's texts.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("run", help="start the tray app (default)")
    st = sub.add_parser("setup", help="print the URL and token for your phone")
    st.add_argument("--relay", action="store_true", help="turn on relay mode with a new random ntfy topic")
    st.add_argument("--relay-server", default="https://ntfy.sh", help="ntfy server for --relay (default ntfy.sh)")
    st.add_argument("--direct-only", action="store_true", help="turn relay mode off")
    t = sub.add_parser("test", help="show which code would be pulled out of a message")
    t.add_argument("message")
    sub.add_parser("install-startup", help="start OTP Bridge when you sign in")
    sub.add_parser("uninstall-startup", help="stop starting OTP Bridge at sign-in")
    args = parser.parse_args(argv)

    if args.cmd == "test":
        print(extract_code(args.message) or "(no code found)")
        return
    if args.cmd == "uninstall-startup":
        STARTUP_LINK.unlink(missing_ok=True)
        print("Removed from startup.")
        return
    if args.cmd == "install-startup":
        cmd_install_startup()
        return

    cfg = config.load()
    if args.cmd == "setup":
        cmd_setup(cfg, args)
        return

    logging.basicConfig(
        filename=config.config_dir() / "otp-bridge.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    from .app import OtpBridge

    try:
        OtpBridge(cfg).run()
    except OSError as e:
        logging.getLogger("otp_bridge").error("could not start: %s (already running?)", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
