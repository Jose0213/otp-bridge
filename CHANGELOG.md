# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-10-15

### Added
- Tray app that receives forwarded text messages, extracts the one-time code, copies it, and shows a notification.
- Global hotkey (Ctrl+Alt+O by default) that types the latest code into the focused field.
- Direct mode: HTTP endpoint with a shared token and a private/Tailscale IP allowlist.
- Relay mode through an ntfy topic, which works from anywhere without opening a port.
- Previous clipboard text is restored when a code expires.
- Standalone `OtpBridge.exe` attached to each GitHub release.
- `otp-bridge setup`, `test`, `install-startup`, and `uninstall-startup` commands, plus a Phone setup page in the tray menu.

[0.1.0]: https://github.com/Jose0213/otp-bridge/releases/tag/v0.1.0
