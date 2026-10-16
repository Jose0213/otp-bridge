"""Run the project's checks: lint, then tests. Run this before opening a pull request.

    python tools/check.py
"""
import subprocess
import sys

CHECKS = [
    ("lint", [sys.executable, "-m", "ruff", "check", "--select", "E4,E7,E9,F", "src", "tests", "tools"]),
    ("tests", [sys.executable, "-m", "pytest", "-q"]),
]


def main() -> int:
    failed = []
    for name, cmd in CHECKS:
        print(f"==> {name}", flush=True)
        try:
            if subprocess.run(cmd, check=False).returncode != 0:
                failed.append(name)
        except FileNotFoundError:
            failed.append(name)
    if failed:
        print(f"\nFailed: {', '.join(failed)}")
        return 1
    print("\nAll checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
