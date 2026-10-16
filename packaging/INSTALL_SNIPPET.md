<!-- For merging into README.md. Two blocks: the Install section, and an addition to Contributing. -->

## Install

### Download the .exe (no Python needed)

1. Download `OtpBridge.exe` from the [latest release](https://github.com/Jose0213/otp-bridge/releases/latest) and put it somewhere permanent, such as `%LOCALAPPDATA%\Programs\OTP Bridge\`.
2. Double-click it. Look for the blue icon in the tray.
3. To start it when you sign in, open a terminal in that folder and run:

   ```powershell
   .\OtpBridge.exe install-startup
   ```

Every command below works the same way: use `.\OtpBridge.exe` in place of `otp-bridge`. Windows SmartScreen may warn the first time because the exe isn't code-signed; choose **More info**, then **Run anyway**.

### Install with Python

You need Python 3.9 or newer.

```bash
pipx install git+https://github.com/Jose0213/otp-bridge
```

(`pip install` works too.) Then:

```bash
otp-bridge install-startup
otp-bridge
```

The first command makes OTP Bridge start when you sign in. The second starts it now; look for the blue icon in the tray.

The first time OTP Bridge runs, Windows Firewall may ask whether to allow it on networks. Allow it on **private** networks. Relay mode doesn't need this.

<!-- Contributing: drop "a packaged .exe" from the wishlist, and add after the pytest block: -->

To build `OtpBridge.exe` yourself:

```bash
pip install -e ".[build]"
pyinstaller packaging/OtpBridge.spec
```

The exe lands in `dist/`. Pushing a `v*` tag builds it on GitHub Actions and attaches it to a release.
