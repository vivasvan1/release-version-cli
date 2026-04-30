from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from release_version_cli.versioning import Version, parse_version_tags


@dataclass(frozen=True)
class GitState:
    repo_root: Path
    branch: str
    head: str
    upstream: str
    previous_tag: str | None
    previous_version: Version | None


def run_git(repo_root: Path | None, args: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["git"]
    if repo_root is not None:
        cmd.extend(["-C", str(repo_root)])
    cmd.extend(args)
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or f"git {' '.join(args)} failed"
        raise RuntimeError(message)
    return result


def repo_root(start: Path) -> Path:
    result = run_git(start, ["rev-parse", "--show-toplevel"])
    return Path(result.stdout.strip())


def preflight(start: Path, initial: bool) -> GitState:
    root = repo_root(start)
    run_git(root, ["fetch", "--tags", "origin"])

    status = run_git(root, ["status", "--porcelain"]).stdout.strip()
    if status:
        raise RuntimeError("Worktree must be clean before release.")

    head = run_git(root, ["rev-parse", "HEAD"]).stdout.strip()
    upstream = run_git(root, ["rev-parse", "@{u}"]).stdout.strip()
    if head != upstream:
        raise RuntimeError("Local HEAD must match upstream HEAD before release.")

    branch = run_git(root, ["rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    remote_tags = _remote_version_tags(root)
    merged_tags = run_git(root, ["tag", "--merged", "HEAD"]).stdout.splitlines()
    candidates = {tag: version for tag, version in parse_version_tags(merged_tags).items() if tag in remote_tags}
    previous_tag: str | None = None
    previous_version: Version | None = None
    if candidates:
        previous_tag, previous_version = max(candidates.items(), key=lambda item: item[1])
    elif not initial:
        raise RuntimeError("No remote vX.Y.Z tag found. Re-run with --initial to create first release.")

    return GitState(root, branch, head, upstream, previous_tag, previous_version)


def ensure_new_tag_absent(repo_root: Path, tag: str) -> None:
    local = run_git(repo_root, ["tag", "--list", tag]).stdout.strip()
    remote = run_git(repo_root, ["ls-remote", "--tags", "origin", tag]).stdout.strip()
    if local or remote:
        raise RuntimeError(f"Tag already exists: {tag}")


def commit_tag_push(repo_root: Path, manifest_path: Path, version: Version, branch: str) -> None:
    rel_manifest = manifest_path.relative_to(repo_root)
    run_git(repo_root, ["add", str(rel_manifest)])
    status = run_git(repo_root, ["status", "--porcelain"]).stdout.splitlines()
    expected = {f"M  {rel_manifest}", f" M {rel_manifest}", f"MM {rel_manifest}"}
    unexpected = [line for line in status if line not in expected]
    if unexpected:
        raise RuntimeError("Release commit may only include selected manifest version bump.")
    run_git(repo_root, ["commit", "-m", f"chore: release {version.tag}"])
    run_git(repo_root, ["tag", version.tag])
    run_git(repo_root, ["push", "origin", branch])
    run_git(repo_root, ["push", "origin", version.tag])


def log_commits(repo_root: Path, previous_tag: str | None, new_tag_or_head: str) -> list[str]:
    if previous_tag:
        range_spec = f"{previous_tag}..{new_tag_or_head}"
    else:
        range_spec = new_tag_or_head
    output = run_git(repo_root, ["log", "--pretty=format:%h %s", range_spec]).stdout
    return [line for line in output.splitlines() if line.strip()]


def _remote_version_tags(repo_root: Path) -> set[str]:
    output = run_git(repo_root, ["ls-remote", "--tags", "origin", "v*"]).stdout
    tags: set[str] = set()
    for line in output.splitlines():
        if not line.strip() or line.endswith("^{}"):
            continue
        ref = line.rsplit("/", 1)[-1]
        try:
            Version.parse_tag(ref)
        except ValueError:
            continue
        tags.add(ref)
    return tags
