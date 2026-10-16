# Contributing to OTP Bridge

Thanks for helping. Bug reports, missed-code samples, and pull requests are all welcome.

## Reporting a code that wasn't detected

The most useful contribution is a message that OTP Bridge got wrong. Open a [missed code issue](../../issues/new?template=missed_code.yml) with the message text. **Replace the real code and any personal details first**, for example by changing `Your code is 482913` to `Your code is 111222`. Keep the wording and layout exactly as it was.

## Development setup

```bash
git clone https://github.com/Jose0213/otp-bridge
cd otp-bridge
pip install -e ".[dev]" ruff
python tools/check.py
```

To build `OtpBridge.exe` yourself:

```bash
pip install -e ".[build]"
pyinstaller packaging/OtpBridge.spec
```

The exe lands in `dist/`. `python tools/release.py --dry-run` does the same after running the checks, and also smoke-tests the build.

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
- Run `python tools/check.py` (lint and tests) before opening the PR, and paste its last line into the PR. The project doesn't use hosted CI, so this is how changes get checked.
- Never log, store, or send message text or codes anywhere other than the local clipboard and the focused window.

## Porting to macOS or Linux

Only `win.py` is Windows-specific: the global hotkey, typing into the focused window, and the startup shortcut in `__main__.py`. A port needs those three for the new platform, and everything else should work unchanged. Open an issue first so we can agree on the approach.

## Releases

Releases are built on a maintainer's Windows machine:

1. Bump `__version__` in `src/otp_bridge/__init__.py` and add a matching `## [X.Y.Z]` section to `CHANGELOG.md`. Commit and push to `main`.
2. Run `python tools/release.py --dry-run` to run the checks, build the exe, and preview the release notes.
3. Run `python tools/release.py` to tag `vX.Y.Z`, push the tag, and publish the GitHub release with `OtpBridge.exe` and `SHA256SUMS.txt`.
