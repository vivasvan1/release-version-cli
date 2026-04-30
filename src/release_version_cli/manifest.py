from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomlkit

from release_version_cli.versioning import Version


@dataclass(frozen=True)
class Manifest:
    path: Path
    kind: str
    version: Version


def select_manifest(repo_root: Path, manifest_file: str | None, workdir: Path) -> Path:
    if manifest_file:
        candidate = Path(manifest_file)
        if not candidate.is_absolute():
            candidate = workdir / candidate
        resolved = candidate.resolve()
        _ensure_inside_repo(repo_root, resolved)
        return resolved

    candidates = [workdir / "pyproject.toml", workdir / "package.json"]
    existing = [path.resolve() for path in candidates if path.exists()]
    if not existing:
        raise RuntimeError("No pyproject.toml or package.json found. Pass --file.")
    if len(existing) > 1:
        raise RuntimeError("Both pyproject.toml and package.json found. Pass --file.")
    _ensure_inside_repo(repo_root, existing[0])
    return existing[0]


def read_manifest(path: Path) -> Manifest:
    if path.name == "pyproject.toml":
        return _read_pyproject(path)
    if path.name == "package.json":
        return _read_package_json(path)
    raise RuntimeError("Manifest must be pyproject.toml or package.json.")


def write_manifest_version(manifest: Manifest, version: Version) -> None:
    if manifest.kind == "pyproject":
        _write_pyproject(manifest.path, version)
        return
    if manifest.kind == "package-json":
        _write_package_json(manifest.path, version)
        return
    raise RuntimeError(f"Unsupported manifest kind: {manifest.kind}")


def _read_pyproject(path: Path) -> Manifest:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project")
    if not isinstance(project, dict):
        raise RuntimeError("pyproject.toml missing [project].")
    dynamic = project.get("dynamic", [])
    if isinstance(dynamic, list) and "version" in dynamic:
        raise RuntimeError("Dynamic pyproject.toml versions are not supported.")
    value = project.get("version")
    if not isinstance(value, str):
        raise RuntimeError("pyproject.toml missing static [project].version.")
    return Manifest(path=path, kind="pyproject", version=Version.parse(value))


def _write_pyproject(path: Path, version: Version) -> None:
    doc = tomlkit.parse(path.read_text())
    project = doc.get("project")
    if project is None:
        raise RuntimeError("pyproject.toml missing [project].")
    project["version"] = str(version)
    path.write_text(tomlkit.dumps(doc))


def _read_package_json(path: Path) -> Manifest:
    data = json.loads(path.read_text())
    value = data.get("version")
    if not isinstance(value, str):
        raise RuntimeError("package.json missing top-level version.")
    return Manifest(path=path, kind="package-json", version=Version.parse(value))


def _write_package_json(path: Path, version: Version) -> None:
    original = path.read_text()
    indent = 2
    data = json.loads(original)
    data["version"] = str(version)
    newline = "\n" if original.endswith("\n") else ""
    path.write_text(json.dumps(data, indent=indent) + newline)


def _ensure_inside_repo(repo_root: Path, path: Path) -> None:
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise RuntimeError("Manifest must be inside the git repository.") from exc
