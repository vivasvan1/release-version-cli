from __future__ import annotations

import subprocess
from pathlib import Path


def create_release(tag: str, notes_file: Path) -> None:
    auth = subprocess.run(["gh", "auth", "status"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if auth.returncode != 0:
        raise RuntimeError(auth.stderr.strip() or auth.stdout.strip() or "gh auth status failed")

    base = ["gh", "release", "create", tag, "--title", tag, "--notes-file", str(notes_file)]
    result = subprocess.run(base + ["--latest"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        return
    unsupported_latest = "unknown flag" in result.stderr.lower() and "--latest" in result.stderr
    if not unsupported_latest:
        raise RuntimeError(result.stderr.strip() or "gh release create failed")
    fallback = subprocess.run(base, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if fallback.returncode != 0:
        raise RuntimeError(fallback.stderr.strip() or "gh release create failed")
