#!/usr/bin/env python3
"""Run Flask + Next.js together for local development."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NEXT_DIR = ROOT / "next_app"


def _next_bin_path() -> Path:
    bin_name = "next.cmd" if os.name == "nt" else "next"
    return NEXT_DIR / "node_modules" / ".bin" / bin_name


def _resolve_npm() -> str:
    if os.name == "nt":
        return shutil.which("npm.cmd") or "npm.cmd"
    return shutil.which("npm") or "npm"


def _terminate(proc: subprocess.Popen[object]) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            proc.terminate()
        else:
            proc.send_signal(signal.SIGINT)
    except OSError:
        return


def _kill(proc: subprocess.Popen[object]) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.kill()
    except OSError:
        return


def main() -> int:
    if not NEXT_DIR.exists():
        print("next_app 디렉터리를 찾을 수 없습니다.", file=sys.stderr)
        return 1

    if not _next_bin_path().exists():
        print(
            "next_app/node_modules를 찾을 수 없습니다. 먼저 다음을 실행하세요:\n"
            "  cd next_app && npm install",
            file=sys.stderr,
        )
        return 1

    npm = _resolve_npm()
    if shutil.which(npm) is None and npm not in {"npm", "npm.cmd"}:
        print("npm 실행 파일을 찾을 수 없습니다.", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env.setdefault("APP_MODE", "full")
    env.setdefault("FLASK_BASE_URL", "http://127.0.0.1:5000")

    processes: list[subprocess.Popen[object]] = []
    try:
        processes.append(
            subprocess.Popen(
                [sys.executable, "run.py"],
                cwd=str(ROOT),
                env=env,
            )
        )
        processes.append(
            subprocess.Popen(
                [npm, "run", "dev"],
                cwd=str(NEXT_DIR),
                env=env,
            )
        )

        while True:
            for proc in processes:
                code = proc.poll()
                if code is not None:
                    return code
            time.sleep(0.4)
    except KeyboardInterrupt:
        return 0
    finally:
        for proc in processes:
            _terminate(proc)
        deadline = time.time() + 3
        while time.time() < deadline:
            if all(proc.poll() is not None for proc in processes):
                return 0
            time.sleep(0.1)
        for proc in processes:
            _kill(proc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
