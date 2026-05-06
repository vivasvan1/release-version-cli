from __future__ import annotations

import subprocess
from pathlib import Path
from urllib.parse import urlparse


class ReleaseAlreadyExistsError(RuntimeError):
    pass


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
    if _is_release_already_exists(result):
        raise ReleaseAlreadyExistsError(_command_error(result) or f"GitHub release {tag} already exists")
    if not unsupported_latest:
        raise RuntimeError(_command_error(result) or "gh release create failed")
    fallback = subprocess.run(base, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if fallback.returncode != 0:
        if _is_release_already_exists(fallback):
            raise ReleaseAlreadyExistsError(_command_error(fallback) or f"GitHub release {tag} already exists")
        raise RuntimeError(_command_error(fallback) or "gh release create failed")


def update_release_notes(tag: str, notes_file: Path, position: str) -> None:
    existing = _release_body(tag)
    new_notes = notes_file.read_text()
    if position == "start":
        combined = _join_notes(new_notes, existing)
    elif position == "end":
        combined = _join_notes(existing, new_notes)
    else:
        raise ValueError(f"Unsupported release notes position: {position}")

    notes_file.write_text(combined)
    base = ["gh", "release", "edit", tag, "--title", tag, "--notes-file", str(notes_file)]
    result = subprocess.run(base + ["--latest"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode == 0:
        return
    unsupported_latest = "unknown flag" in result.stderr.lower() and "--latest" in result.stderr
    if not unsupported_latest:
        raise RuntimeError(_command_error(result) or "gh release edit failed")
    fallback = subprocess.run(base, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if fallback.returncode != 0:
        raise RuntimeError(_command_error(fallback) or "gh release edit failed")


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


def _release_body(tag: str) -> str:
    result = subprocess.run(
        ["gh", "release", "view", tag, "--json", "body", "--jq", ".body"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(_command_error(result) or "gh release view failed")
    return result.stdout.strip()


def _join_notes(first: str, second: str) -> str:
    first = first.strip()
    second = second.strip()
    if first and second:
        return f"{first}\n\n{second}\n"
    return f"{first or second}\n"


def _is_release_already_exists(result: subprocess.CompletedProcess[str]) -> bool:
    error = _command_error(result).lower()
    return "tag_name already exists" in error or "release.tag_name already exists" in error


def _command_error(result: subprocess.CompletedProcess[str]) -> str:
    return (result.stderr.strip() or result.stdout.strip()).strip()
