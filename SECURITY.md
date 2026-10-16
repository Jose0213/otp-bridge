# Security policy

OTP Bridge handles one-time login codes, so security reports are taken seriously.

## Reporting a vulnerability

Please **don't open a public issue**. Report it privately through [GitHub's private vulnerability reporting](../../security/advisories/new). You'll get a response within a week.

## What OTP Bridge does to protect codes

- **Direct mode** accepts a request only if it carries the shared token (compared in constant time) and comes from a loopback, private-network, or Tailscale (100.64.0.0/10) address.
- **Codes are held in memory only.** They are never written to disk and expire after `ttl_seconds` (5 minutes by default).
- **The log never contains message text or codes.** It records only that a code arrived and how long it was.
- **Relay mode** sends messages through an ntfy topic, so anyone who learns the topic URL can read them. The topic name is 24 random hex characters. Self-host ntfy if that isn't acceptable.

## Known limitations

- Direct mode uses plain HTTP. On a home network or over Tailscale (which encrypts traffic itself) this is fine, but don't expose the port to the internet.
- Any app running as your Windows user can read the clipboard while a code is on it.
- On Android, an SMS forwarder may send every text to OTP Bridge, not only texts that contain codes. Filter in the forwarder if your app supports it.
