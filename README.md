# release-version-cli

Safe GitHub release version bumper for Python and Node projects.

## Install

```bash
pipx install release-version-cli
```

## Usage

```bash
release-version patch
release-version minor
release-version major
release-version patch --dry-run
release-version patch --file packages/api/pyproject.toml
release-version patch --cwd packages/api --file pyproject.toml
release-version patch --initial
release-version patch --yes
```

## Behavior

- Supports static Python `[project].version` in `pyproject.toml`.
- Supports top-level `package.json.version`.
- Requires clean semver `X.Y.Z`.
- Uses strict git tags `vX.Y.Z`.
- Fetches remote tags before release.
- Requires clean worktree.
- Requires local HEAD to match upstream HEAD.
- Requires manifest version to match latest remote version tag unless `--initial` is used.
- Creates release commit containing only selected manifest bump.
- Pushes commit and tag before creating GitHub release.
- Creates GitHub release through `gh`.
- Uses Ollama `gemma4` for grouped notes when available.
- Falls back to deterministic grouped notes when Ollama fails.
- Always appends raw commits.

## Development

```bash
uv run --extra dev pytest
```

## Publishing this package

```bash
uv build
uv publish
```
