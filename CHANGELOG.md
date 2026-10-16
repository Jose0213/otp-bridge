# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- A browser extension for Edge and Chrome (Manifest V3, in `extension/`) that fills one-time-code fields as soon as a code arrives. It recognizes `autocomplete="one-time-code"`, split single-digit boxes, and common field names, fills each field once, only in the visible tab, and shows a small confirmation.
- `GET /latest`, a loopback-only endpoint the extension long-polls for the current code. It needs a per-install pairing key, and refuses web page origins and rebinding hostnames.
- "Copy browser pairing key" in the tray menu, `otp-bridge pair-extension`, and the `extension_key` setting.

### Changed
- The Phone setup page shows the token on its own and asks for a `token` body field, the setup that works on iOS 27. The `Authorization` header is described as an alternative.
- The README shows screenshots of the PC notification and the Phone setup page.

## [0.1.1] - 2026-10-15

### Added
- The token can also be sent as a `token` field in the JSON body, because iOS 27 Shortcuts can drop the `Authorization` header.
- An illustrated iOS 27 setup guide, where the trigger lives inside the shortcut, and a ready-made shared shortcut that includes the message trigger.
- Requests with no code are logged with their body and text lengths (never the content), to help diagnose empty forwards.

### Changed
- The README no longer suggests turning off Shortcuts notifications, which stops message automations from running.
- The iPhone setup steps match iOS 27, and the iOS 17 to 26 steps are kept in a collapsible section.

### Fixed
- JSON keys from the phone are matched in any letter case. iOS Shortcuts capitalizes them, so `Text` and `Sender` were ignored and every code came back `null`.
- Phone setup no longer lists virtual adapters (WSL, Hyper-V, Docker, VMs) that a phone can't reach, and the Tailscale address is listed first.
- Stray spaces or line breaks around the token are ignored.

### Security
- The client address allowlist is checked before the request body is read, and a missing, invalid, or oversized `Content-Length` is rejected.
- Rejected requests log only which headers arrived and a fixed scheme label, never any part of the token.

## [0.1.0] - 2026-10-15

### Added
- Tray app that receives forwarded text messages, extracts the one-time code, copies it, and shows a notification.
- Global hotkey (Ctrl+Alt+O by default) that types the latest code into the focused field.
- Direct mode: HTTP endpoint with a shared token and a private/Tailscale IP allowlist.
- Relay mode through an ntfy topic, which works from anywhere without opening a port.
- Previous clipboard text is restored when a code expires.
- Standalone `OtpBridge.exe` attached to each GitHub release.
- `otp-bridge setup`, `test`, `install-startup`, and `uninstall-startup` commands, plus a Phone setup page in the tray menu.

[Unreleased]: https://github.com/Jose0213/otp-bridge/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/Jose0213/otp-bridge/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Jose0213/otp-bridge/releases/tag/v0.1.0
