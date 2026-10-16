# Contributing to OTP Bridge

Thanks for helping. Bug reports, missed-code samples, and pull requests are all welcome.

## Reporting a code that wasn't detected

The most useful contribution is a message that OTP Bridge got wrong. Open a [missed code issue](../../issues/new?template=missed_code.yml) with the message text. **Replace the real code and any personal details first**, for example by changing `Your code is 482913` to `Your code is 111222`. Keep the wording and layout exactly as it was.

## Development setup

```bash
git clone https://github.com/Jose0213/otp-bridge
cd otp-bridge
pip install -e ".[dev]"
pytest
```

To build `OtpBridge.exe` yourself:

```bash
pip install -e ".[build]"
pyinstaller packaging/OtpBridge.spec
```

The exe lands in `dist/`.

Run the app from source with `python -m otp_bridge`. Settings and the log are in `%APPDATA%\otp-bridge\`.

## Project layout

| File | What it does |
|---|---|
| `src/otp_bridge/extract.py` | Finds the code in a message. Pure Python, fully unit-tested. |
| `src/otp_bridge/server.py` | Direct-mode HTTP endpoint: token check and private-IP allowlist |
| `src/otp_bridge/relay.py` | Relay mode: subscribes to an ntfy topic |
| `src/otp_bridge/app.py` | Tray icon, clipboard, notifications, code expiry |
| `src/otp_bridge/win.py` | Windows-only: global hotkey and typing into the focused window |
| `src/otp_bridge/setup_info.py` | The values a phone needs, as text or a local HTML page |

## Pull requests

- Keep changes focused. One fix or feature per PR.
- Add or update tests. Every change to `extract.py` needs a test case in `tests/test_extract.py`.
- Run `pytest` and `ruff check --select E4,E7,E9,F src tests` before opening the PR.
- Never log, store, or send message text or codes anywhere other than the local clipboard and the focused window.

## Porting to macOS or Linux

Only `win.py` is Windows-specific: the global hotkey, typing into the focused window, and the startup shortcut in `__main__.py`. A port needs those three for the new platform, and everything else should work unchanged. Open an issue first so we can agree on the approach.

## Releases

Maintainers bump `__version__` in `src/otp_bridge/__init__.py`, update `CHANGELOG.md`, and push a `vX.Y.Z` tag. CI builds the `.exe` and attaches it to the GitHub release.
