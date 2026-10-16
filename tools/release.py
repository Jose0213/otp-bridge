"""Build OtpBridge.exe and publish a GitHub release, from a maintainer's Windows machine.

    python tools/release.py --dry-run   # check and build only
    python tools/release.py             # also tag, push, and publish

Needs a clean checkout of main, `pip install -e ".[dev,build]" ruff`, and the GitHub
CLI (`gh`) signed in as someone who can publish releases. If `GH_TOKEN` is set, it is
used for both the tag push and the release.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
EXE = DIST / "OtpBridge.exe"
SUMS = DIST / "SHA256SUMS.txt"


def run(*cmd, capture=False):
    result = subprocess.run(cmd, cwd=ROOT, check=False, text=True,
                            capture_output=capture)
    if result.returncode != 0:
        if capture:
            sys.stderr.write(result.stderr)
        shown = " ".join(cmd)
        if os.environ.get("GH_TOKEN"):
            shown = shown.replace(os.environ["GH_TOKEN"], "***")
        sys.exit(f"Failed: {shown}")
    return result.stdout.strip() if capture else ""


def version() -> str:
    text = (ROOT / "src/otp_bridge/__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', text).group(1)


def changelog_section(ver: str) -> str:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(rf"^## \[{re.escape(ver)}\][^\n]*\n(.*?)(?=^## \[|^\[[^\]]+\]: |\Z)", text, re.S | re.M)
    if not match:
        sys.exit(f"CHANGELOG.md has no '## [{ver}]' section.")
    return match.group(1).strip()


def git_auth_args() -> list:
    """With GH_TOKEN set, have git read it from the environment through a credential
    helper, so the token never appears in a command line or remote URL."""
    if not os.environ.get("GH_TOKEN"):
        return []
    helper = '!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f'
    return ["-c", "credential.helper=", "-c", f"credential.helper={helper}"]


def repo_slug() -> str:
    url = run("git", "remote", "get-url", "origin", capture=True)
    match = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    if not match:
        sys.exit(f"origin isn't a GitHub remote: {url}")
    return match.group(1)


def preflight(tag: str):
    if run("git", "status", "--porcelain", capture=True):
        sys.exit("Working tree isn't clean. Commit or stash first.")
    if run("git", "rev-parse", "--abbrev-ref", "HEAD", capture=True) != "main":
        sys.exit("Release from main.")
    run("git", "fetch", "-q", "origin", "main", "--tags")
    if run("git", "rev-parse", "HEAD", capture=True) != run("git", "rev-parse", "origin/main", capture=True):
        sys.exit("main isn't in sync with origin/main. Push or pull first.")
    if run("git", "tag", "-l", tag, capture=True):
        sys.exit(f"Tag {tag} already exists. Bump __version__ first.")


def build():
    run(sys.executable, str(ROOT / "tools/check.py"))
    run(sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "packaging/OtpBridge.spec")
    digest = hashlib.sha256(EXE.read_bytes()).hexdigest()
    SUMS.write_text(f"{digest}  {EXE.name}\n", encoding="utf-8")
    # Smoke test: the frozen exe must start and parse a message.
    out = subprocess.run([str(EXE), "test", "Your code is 482913"], capture_output=True, text=True, timeout=60, check=False)
    if "482913" not in out.stdout:
        sys.exit("Smoke test failed: the built exe didn't extract a code.")
    print(f"Built {EXE.relative_to(ROOT)} ({EXE.stat().st_size // 1_000_000} MB), sha256 {digest}")


def release_notes(ver: str, slug: str) -> str:
    return f"""{changelog_section(ver)}

## Install

Download **OtpBridge.exe** below, put it somewhere permanent, and double-click it. To start it at sign-in, run `.\\OtpBridge.exe install-startup`. Then follow the [phone setup](https://github.com/{slug}#phone-setup).

The exe isn't code-signed, so Windows SmartScreen may warn the first time. Choose **More info**, then **Run anyway**. To check your download, compare `Get-FileHash .\\OtpBridge.exe` with `SHA256SUMS.txt`.
"""


def publish(tag: str, ver: str, slug: str):
    run("git", "tag", "-a", tag, "-m", f"OTP Bridge {ver}")
    run("git", *git_auth_args(), "push", f"https://github.com/{slug}.git", tag)
    notes = DIST / "release-notes.md"
    notes.write_text(release_notes(ver, slug), encoding="utf-8")
    run("gh", "release", "create", tag, str(EXE), str(SUMS), "-R", slug,
        "--title", f"OTP Bridge {ver}", "--notes-file", str(notes), "--verify-tag")
    print(f"Published https://github.com/{slug}/releases/tag/{tag}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="check and build, but don't tag or publish")
    args = parser.parse_args()

    ver = version()
    tag = f"v{ver}"
    slug = repo_slug()
    changelog_section(ver)
    if not args.dry_run:
        preflight(tag)
    build()
    if args.dry_run:
        print("\nDry run: release notes would be:\n")
        print(release_notes(ver, slug))
        return
    publish(tag, ver, slug)


if __name__ == "__main__":
    main()
