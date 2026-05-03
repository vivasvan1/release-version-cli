from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse


def create_release(tag: str, notes_file: Path) -> None:
    auth_cmd = ["gh", "auth", "status"]
    host = _origin_host()
    if host:
        auth_cmd.extend(["--hostname", host])

    auth = subprocess.run(auth_cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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


def _origin_host() -> str | None:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        return None
    return _host_from_git_url(result.stdout.strip())


def _host_from_git_url(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname:
        return parsed.hostname

    if "@" in url and ":" in url:
        host = url.split("@", 1)[1].split(":", 1)[0]
        return host or None

    return None
