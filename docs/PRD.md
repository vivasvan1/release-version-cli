# PRD: release-version-cli

## Problem Statement

Developers need reusable GitHub release automation for Python and Node projects. Current manual flow requires editing version files, computing changelog ranges, creating release commits, creating tags, pushing commits/tags, and creating GitHub releases. Manual steps are error-prone, especially when local HEAD is not pushed, tags are stale, or worktree contains unrelated changes.

## Solution

Build standalone public PyPI package `release-version-cli` exposing command `release-version`.

CLI bumps `major`, `minor`, or `patch` in static Python `pyproject.toml` project versions or top-level `package.json.version`. It fetches remote tags, verifies release state, auto-commits manifest-only version bump, creates strict `vX.Y.Z` tag, pushes commit/tag, and creates GitHub release through `gh`.

Release notes contain AI-generated grouped `## Changes` via local Ollama model `gemma4` when available. If Ollama fails, CLI falls back to deterministic grouped notes. Raw commits always append under `## Commits`.

## User Stories

1. As a developer, I want to run `release-version patch`, so that I can create patch release without manual version edits.
2. As a developer, I want to run `release-version minor`, so that I can create minor release explicitly.
3. As a developer, I want to run `release-version major`, so that I can create major release explicitly.
4. As a developer, I want remote tags fetched before release, so that stale local tags do not define release range.
5. As a developer, I want strict `vX.Y.Z` tags, so that release boundaries stay predictable.
6. As a developer, I want manifest version and latest remote tag to match, so that ambiguous release state fails.
7. As a developer, I want local HEAD to equal upstream HEAD, so that unpublished commits are not released.
8. As a developer, I want clean worktree preflight, so that unrelated changes never enter release commit.
9. As a developer, I want release commit to contain only manifest bump, so that release commits stay auditable.
10. As a release reader, I want release notes to include release commit, so that tag commit is visible.
11. As a developer, I want `--dry-run`, so that I can preview plan and notes without mutation.
12. As a developer, I want prompt before mutation by default, so that pushes require explicit confirmation.
13. As automation, I want `--yes`, so that non-interactive release can run.
14. As Python maintainer, I want static `[project].version` support, so that PEP 621 projects work.
15. As Python maintainer, I want dynamic versions rejected, so that backend-specific versioning is not corrupted.
16. As Node maintainer, I want top-level `package.json.version` support, so that common Node packages work.
17. As monorepo maintainer, I want `--file`, so that exact manifest can be selected.
18. As monorepo maintainer, I want `--cwd`, so that manifest discovery can start in subdirectories.
19. As mixed repo maintainer, I want failure when both manifests exist without `--file`, so that tool never guesses.
20. As GitHub user, I want `gh` release creation, so that existing auth and host config work.
21. As GitHub Enterprise user, I want `gh` host inference, so that enterprise remotes work.
22. As release owner, I want push before release creation, so that GitHub release uses existing remote tag.
23. As release owner, I want `--latest` used when supported, so that release is marked latest.
24. As release owner, I want fallback if `gh --latest` is unsupported, so that older `gh` versions still work.
25. As release owner, I want temp notes deleted on success, so that local temp files stay clean.
26. As release owner, I want temp notes kept on failure, so that release creation can be retried.
27. As first-release maintainer, I want `--initial`, so that repos without previous tags can start using tool.
28. As first-release maintainer, I want arbitrary current semver accepted with `--initial`, so that existing package versions work.
29. As first-release maintainer, I want all commits included, so that first release captures full history.
30. As release reader, I want grouped AI changes, so that notes are scannable.
31. As release reader, I want raw commits appended, so that complete trail stays visible.
32. As release owner, I want AI fallback, so that Ollama outage never blocks release.
33. As package user, I want Python 3.11+, so that tool can use built-in `tomllib`.
34. As contributor, I want Click CLI, so that command UX is maintainable.
35. As contributor, I want plain output, so that deps stay small.
36. As PyPI user, I want public package `release-version-cli`, so that install works anywhere.
37. As maintainer, I want modern packaging only, so that project avoids legacy setup files.
38. As maintainer, I want manual PyPI publishing docs, so that package publishing stays separate from runtime release CLI.

## Implementation Decisions

- Standalone Python package named `release-version-cli`.
- Console command `release-version`.
- Modern `pyproject.toml` packaging only.
- Python `>=3.11`.
- Click for CLI.
- Plain terminal output.
- `tomllib` for TOML reads.
- `tomlkit` for TOML writes with formatting/comment preservation.
- Bump args only: `major`, `minor`, `patch`.
- Clean semver only: `X.Y.Z`.
- Strict release tags only: `vX.Y.Z`.
- Fetch remote tags every run.
- Require clean worktree.
- Require local HEAD equals upstream HEAD.
- Require latest remote tag version equals manifest version, except `--initial`.
- Support `--initial` when no prior remote version tag exists.
- In `--initial`, bump from current manifest version and include all commits.
- Auto-commit manifest-only bump.
- Include release commit in release notes.
- Push commit and tag before GitHub release creation.
- Use `gh release create`.
- Use explicit `--latest` with fallback when unsupported.
- Use Ollama `gemma4` for grouped release notes when available.
- Fall back to deterministic grouped changelog when Ollama fails.
- Always append raw commits.
- Support `--dry-run` with changelog preview and no mutation.
- Prompt by default; support `--yes`.
- Support `--file` and `--cwd`.
- Ignore lockfiles.
- Skip build/test checks.
- Do not write local changelog files.
- Delete temp notes on success, keep temp notes on failure.
- Include manual PyPI publishing docs only.

## Testing Decisions

- Test public CLI behavior through Click runner and temporary git repos.
- Use real git repositories and local bare remotes for release preflight and push behavior.
- Mock external `gh` and `ollama` commands through temporary PATH entries.
- Test dry-run preview without mutations.
- Test real release commit/tag/push/release behavior.
- Test manifest ambiguity and explicit `--file`.
- Test `--initial` no-tag release behavior.
- Test Ollama failure fallback plus raw commit append.
- Avoid testing private helper functions where CLI behavior covers outcome.

## Out of Scope

- Commit-message-based bump inference.
- Prerelease/build metadata.
- Lockfile updates.
- Build/test command execution.
- PR-based protected-branch release flow.
- Direct GitHub API auth.
- Local `CHANGELOG.md` updates.
- Dynamic Python versioning.
- Workspace-aware monorepo releases.
- Publishing target package to PyPI/npm.
- Self-publishing automation.
- Rich output.
- AI as hard dependency.

## Further Notes

Project scaffold lives at `/Users/vivasvan.patel/ev/release-version-cli`.
