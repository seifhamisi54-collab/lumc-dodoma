"""
Server moja kwa GIS Portal (Django tu).
Fungua: http://localhost:8000
"""
from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

GIS_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_PORT = 8000

child_process: subprocess.Popen | None = None


def _python() -> Path:
    return GIS_ROOT / "venv" / "Scripts" / "python.exe"


def start_django() -> subprocess.Popen:
    return subprocess.Popen(
        [
            str(_python()),
            "manage.py",
            "runserver",
            f"0.0.0.0:{PUBLIC_PORT}",
        ],
        cwd=GIS_ROOT,
    )


def _shutdown(*_args) -> None:
    global child_process
    if child_process and child_process.poll() is None:
        child_process.terminate()
    raise SystemExit(0)


def main() -> None:
    global child_process

    if not _python().exists():
        raise SystemExit(f"Python venv haipo: {_python()}")

    print("Inaanza GIS Portal...")
    child_process = start_django()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"\nServer iko tayari: http://localhost:{PUBLIC_PORT}")
    print(f"  GIS Portal:  http://localhost:{PUBLIC_PORT}/\n")

    child_process.wait()
    sys.exit(child_process.returncode or 0)


if __name__ == "__main__":
    main()
