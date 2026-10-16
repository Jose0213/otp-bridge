# OTP Bridge

Get one-time codes from your phone's text messages onto your PC, the way a Mac gets them from an iPhone.

When a text with a code arrives, your phone forwards it to OTP Bridge on your computer. OTP Bridge pulls the code out of the message, copies it to the clipboard, and shows a notification. Press **Ctrl+Alt+O** to type it into whatever field has focus.

- Works with **iPhone** (Shortcuts automation) and **Android** (any SMS-to-webhook forwarder)
- Runs in the system tray, no console window
- Codes are never written to disk and expire after 5 minutes. When a code expires, your previous clipboard text is put back.
- Windows for now. macOS and Linux support is welcome; see [Contributing](#contributing).

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

## Choose how your phone reaches your PC

| Mode | Works when | Setup |
|---|---|---|
| **Direct, home network** | Phone and PC are on the same Wi-Fi | Nothing extra |
| **Direct, Tailscale** | Anywhere, both devices on your [Tailscale](https://tailscale.com) network | Install Tailscale on both |
| **Relay** | Anywhere, no VPN or firewall changes | `otp-bridge setup --relay` |

Direct mode is the most private: messages go straight from your phone to your PC, and OTP Bridge rejects requests that lack your token or come from outside private or Tailscale addresses.

Relay mode sends messages through an [ntfy](https://ntfy.sh) topic. Your PC only connects outward, so it works from any network. The topic name is long and random, but anyone who learns it can read what's posted there. For full control, [self-host ntfy](https://docs.ntfy.sh/install/) and run `otp-bridge setup --relay --relay-server https://ntfy.example.com`.

To see the URL and token for your phone, right-click the tray icon and choose **Phone setup…**, or run `otp-bridge setup`.

## Phone setup

### iPhone (iOS 17 or later)

1. Open **Shortcuts**, go to the **Automation** tab, tap **+**, and choose **Message**.
2. Under **Message Contains**, enter `code`. This also matches "passcode". Leave **Sender** as anyone.
3. Choose **Run Immediately** and turn off **Notify When Run**. Tap **Next**, then **New Blank Automation**.
4. Add the **Get Contents of URL** action and paste the URL from Phone setup.
5. Tap the arrow to show more options and set:
   - **Method**: `POST`
   - **Headers**: add `Authorization` with value `Bearer <your token>` (direct mode only)
   - **Request Body**: `JSON`, with two Text fields:
     - `text`: tap the value, choose **Shortcut Input**, then **Content**
     - `sender`: **Shortcut Input**, then **Sender** (optional)
6. Tap **Done**.

To also catch texts like "Your OTP is…", add a second automation with `OTP` as the word. Duplicate forwards of the same code are ignored. If you use Tailscale, turn on **VPN On Demand** in the Tailscale app so the phone stays connected.

### Android

Use any app that forwards incoming SMS to a URL, such as the open-source [Incoming SMS to URL forwarder](https://github.com/bogkonstantin/android_income_sms_gateway_webhook). Configure it to:

- send to the URL from Phone setup
- add the header `Authorization: Bearer <your token>` (direct mode only)
- send a JSON body that includes the message as `text` (the `from` field is read as the sender), or the raw message as plain text

## Test it

```bash
otp-bridge test "Your verification code is 482913"
```

This prints which code would be pulled out of a message. To exercise the whole path, send yourself a text containing "code 123456".

## Settings

Settings are stored in `%APPDATA%\otp-bridge\config.json`. Open that folder from the tray menu. Restart OTP Bridge after editing.

| Key | Default | Meaning |
|---|---|---|
| `port` | `9233` | Port for direct mode |
| `hotkey` | `ctrl+alt+o` | Types the latest code. Modifiers: `ctrl`, `alt`, `shift`, `win` |
| `ttl_seconds` | `300` | How long a code stays usable |
| `restore_clipboard` | `true` | Put your previous clipboard text back when a code expires |
| `allow_public_ips` | `false` | Accept direct requests from non-private addresses (not recommended) |
| `relay_url` | `""` | ntfy topic URL; empty means direct only |
| `token` | random | Shared secret for direct mode. Delete it to generate a new one. |

The log, `otp-bridge.log`, records when codes arrive but never the codes or message text.

## API

`POST /otp` with `Authorization: Bearer <token>` and either JSON `{"text": "...", "sender": "..."}` or a plain-text body. The response is `{"code": "482913"}`, or `{"code": null}` when the message has no code. `GET /health` returns `{"ok": true}`.

## Contributing

Pull requests are welcome, especially for:

- better code detection: add the message to `tests/test_extract.py`, with any personal details replaced
- macOS and Linux support for the tray, hotkey, and typing (`win.py` is the only Windows-specific module)
- a one-click iOS shortcut

Run the tests with:

```bash
pip install -e ".[dev]"
pytest
```

To build `OtpBridge.exe` yourself:

```bash
pip install -e ".[build]"
pyinstaller packaging/OtpBridge.spec
```

The exe lands in `dist/`. Pushing a `v*` tag builds it on GitHub Actions and attaches it to a release.

## License

[MIT](LICENSE)
