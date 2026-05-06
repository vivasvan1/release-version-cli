import os
import subprocess
from importlib.metadata import version
from pathlib import Path

from click.testing import CliRunner

from release_version_cli.changelog import _extract_changes_markdown, _ollama_prompt, build_release_notes, build_release_notes_result
from release_version_cli.cli import main
from release_version_cli.github import _host_from_git_url


def test_version_flags_print_installed_package_version():
    expected = f"release-version, version {version('release-version-cli')}\n"

    assert CliRunner().invoke(main, ["--version"]).output == expected
    assert CliRunner().invoke(main, ["-v"]).output == expected


def test_help_includes_ollama_timeout_option():
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "--ollama-timeout INTEGER RANGE" in result.output


def test_dry_run_previews_patch_release(tmp_path, monkeypatch):
    repo = make_python_repo(tmp_path, version="0.3.4", tag="v0.3.4")
    commit(repo, "feat: add release validation")
    push(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(main, ["patch", "--dry-run", "--no-ai"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Release plan" in result.output
    assert "Current:  0.3.4" in result.output
    assert "New:      0.3.5" in result.output
    assert "Previous: v0.3.4" in result.output
    assert "## Changes" in result.output
    assert "Add release validation" in result.output
    assert "chore: release v0.3.5" in result.output
    assert (repo / "pyproject.toml").read_text().count('version = "0.3.4"') == 1


def test_release_commits_manifest_bump_pushes_tag_and_creates_github_release(tmp_path, monkeypatch):
    repo = make_python_repo(tmp_path, version="0.3.4", tag="v0.3.4")
    commit(repo, "fix: handle missing package lock files")
    push(repo)
    gh_log = install_fake_gh(tmp_path, monkeypatch)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(main, ["patch", "--yes", "--no-ai"], catch_exceptions=False)

    assert result.exit_code == 0
    assert 'version = "0.3.5"' in (repo / "pyproject.toml").read_text()
    assert run(["git", "log", "-1", "--pretty=%s"], repo) == "chore: release v0.3.5"
    assert run(["git", "tag", "--points-at", "HEAD"], repo) == "v0.3.5"
    assert run(["git", "ls-remote", "--tags", "origin", "v0.3.5"], repo)
    assert "release create v0.3.5 --title v0.3.5 --notes-file" in gh_log.read_text()
    assert "--latest" in gh_log.read_text()


def test_release_can_prepend_notes_when_github_release_already_exists(tmp_path, monkeypatch):
    repo = make_python_repo(tmp_path, version="0.3.4", tag="v0.3.4")
    commit(repo, "fix: update existing github release")
    push(repo)
    gh_log = install_fake_existing_release_gh(tmp_path, monkeypatch)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(main, ["patch", "--yes", "--no-ai"], input="start\n", catch_exceptions=False)

    assert result.exit_code == 0
    assert "GitHub release v0.3.5 already exists" in result.output
    assert "Updated existing GitHub release v0.3.5" in result.output
    log = gh_log.read_text()
    assert "release view v0.3.5 --json body --jq .body" in log
    assert "release edit v0.3.5 --title v0.3.5 --notes-file" in log
    assert "--latest" in log
    notes_path = tmp_path / "edited-notes.md"
    edited_notes = notes_path.read_text()
    assert edited_notes.index("Update existing github release") < edited_notes.index("Existing release notes")


def test_git_remote_host_parsing_supports_github_url_shapes():
    assert _host_from_git_url("https://github.com/vivasvan1/release-version-cli.git") == "github.com"
    assert _host_from_git_url("git@github.eagleview.com:org/repo.git") == "github.eagleview.com"
    assert _host_from_git_url("/tmp/origin.git") is None


def test_requires_file_when_both_manifests_exist(tmp_path, monkeypatch):
    repo = make_python_repo(tmp_path, version="1.2.3", tag="v1.2.3")
    (repo / "package.json").write_text('{"name": "demo", "version": "1.2.3"}\n')
    run(["git", "add", "package.json"], repo)
    run(["git", "commit", "-m", "chore: add package manifest"], repo)
    push(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(main, ["patch", "--dry-run", "--no-ai"])

    assert result.exit_code != 0
    assert "Both pyproject.toml and package.json found. Pass --file." in result.output


def test_file_option_can_release_package_json(tmp_path, monkeypatch):
    repo = make_python_repo(tmp_path, version="1.2.3", tag="v1.2.3")
    (repo / "package.json").write_text('{"name": "demo", "version": "1.2.3"}\n')
    run(["git", "add", "package.json"], repo)
    run(["git", "commit", "-m", "chore: add package manifest"], repo)
    push(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(main, ["minor", "--dry-run", "--file", "package.json", "--no-ai"])

    assert result.exit_code == 0
    assert "Current:  1.2.3" in result.output
    assert "New:      1.3.0" in result.output


def test_initial_release_allows_no_previous_tag_and_uses_all_commits(tmp_path, monkeypatch):
    repo = make_python_repo_without_tag(tmp_path, version="0.3.4")
    commit(repo, "feat: first public release")
    push(repo)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(main, ["patch", "--initial", "--dry-run", "--no-ai"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "Previous: <initial>" in result.output
    assert "New:      0.3.5" in result.output
    assert "First public release" in result.output
    assert "chore: initial" in result.output


def test_ollama_failure_falls_back_to_deterministic_notes(tmp_path, monkeypatch):
    repo = make_python_repo(tmp_path, version="2.0.0", tag="v2.0.0")
    commit(repo, "fix: handle ollama outage")
    push(repo)
    install_fake_ollama(tmp_path, monkeypatch, exit_code=1)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(main, ["patch", "--dry-run"], catch_exceptions=False)

    assert result.exit_code == 0
    assert "### Fixes" in result.output
    assert "Handle ollama outage" in result.output
    assert "fix: handle ollama outage" in result.output
    assert "WARNING: Ollama release notes failed; using deterministic fallback." in result.output
    assert "Cause: ollama exited with code 1" in result.output
    assert "===PROMPT===\n" in result.output
    assert "===PROMPT END===" in result.output


def test_ollama_timeout_is_configurable(monkeypatch):
    captured = {}

    def timeout_run(*args, **kwargs):
        captured["timeout"] = kwargs["timeout"]
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr("release_version_cli.changelog.subprocess.run", timeout_run)

    result = build_release_notes_result(["1234567 fix: slow ollama model"], timeout=123)

    assert captured["timeout"] == 123
    assert result.ollama_warning == "ollama timed out after 123 seconds"
    assert "Slow ollama model" in result.notes


def test_ollama_prompt_asks_for_human_release_notes_without_release_bookkeeping():
    prompt = _ollama_prompt(["04b6890 auto maximum use of gpu"])

    assert "human-written GitHub release notes" in prompt
    assert "Translate terse commit messages into clear outcomes in different words" in prompt
    assert "Do not copy commit subjects verbatim" in prompt
    assert "Ignore synthetic release bookkeeping commits" in prompt
    assert "### Performance" in prompt
    assert "- auto maximum use of gpu" in prompt
    assert "04b6890" not in prompt


def test_release_bookkeeping_is_not_summarized_as_a_change():
    notes = build_release_notes(
        ["<release> chore: release v0.3.6", "04b6890 auto maximum use of gpu"],
        use_ai=False,
    )

    changes = notes.split("## Commits", 1)[0]
    assert "Release v0.3.6" not in changes
    assert "Auto maximum use of gpu" in changes
    assert "<release> chore: release v0.3.6" in notes


def test_extract_changes_markdown_keeps_model_output_after_thinking_text():
    output = (
        "Thinking...\n"
        "planning around ## Changes and headings\n"
        "some chain of thought with terminal control \x1b[4D\x1b[K\n"
        "...done thinking.\n\n"
        "## Changes\n\n"
        "### Features\n"
        "- Introduces clearer release notes.\n"
    )

    assert _extract_changes_markdown(output) == (
        "## Changes\n\n"
        "### Features\n"
        "- Introduces clearer release notes."
    )


def run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout.strip()


def make_python_repo(tmp_path: Path, version: str, tag: str) -> Path:
    repo = make_python_repo_without_tag(tmp_path, version)
    run(["git", "tag", tag], repo)
    run(["git", "push", "origin", tag], repo)
    return repo


def make_python_repo_without_tag(tmp_path: Path, version: str) -> Path:
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(origin)], check=True, stdout=subprocess.PIPE)
    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", str(origin), str(repo)], check=True, stdout=subprocess.PIPE)
    run(["git", "config", "user.email", "test@example.com"], repo)
    run(["git", "config", "user.name", "Test User"], repo)
    (repo / "pyproject.toml").write_text(
        "[project]\n"
        'name = "demo"\n'
        f'version = "{version}"\n'
    )
    run(["git", "add", "pyproject.toml"], repo)
    run(["git", "commit", "-m", "chore: initial"], repo)
    push(repo)
    return repo


def commit(repo: Path, message: str) -> None:
    marker = repo / "marker.txt"
    marker.write_text(marker.read_text() + "x" if marker.exists() else "x")
    run(["git", "add", "marker.txt"], repo)
    run(["git", "commit", "-m", message], repo)


def push(repo: Path) -> None:
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    run(["git", "push", "-u", "origin", branch], repo)


def install_fake_gh(tmp_path: Path, monkeypatch) -> Path:
    log = tmp_path / "gh.log"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f"echo \"$@\" >> {log}\n"
        "exit 0\n"
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    return log


def install_fake_existing_release_gh(tmp_path: Path, monkeypatch) -> Path:
    log = tmp_path / "gh-existing.log"
    notes = tmp_path / "edited-notes.md"
    bin_dir = tmp_path / "existing-gh-bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text(
        "#!/bin/sh\n"
        f"echo \"$@\" >> {log}\n"
        "if [ \"$1 $2 $3\" = \"release create v0.3.5\" ]; then\n"
        "  echo 'HTTP 422: Validation Failed' >&2\n"
        "  echo 'Release.tag_name already exists' >&2\n"
        "  exit 1\n"
        "fi\n"
        "if [ \"$1 $2 $3\" = \"release view v0.3.5\" ]; then\n"
        "  echo 'Existing release notes'\n"
        "  exit 0\n"
        "fi\n"
        "if [ \"$1 $2 $3\" = \"release edit v0.3.5\" ]; then\n"
        f"  cp \"$7\" {notes}\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n"
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    return log


def install_fake_ollama(tmp_path: Path, monkeypatch, exit_code: int) -> None:
    bin_dir = tmp_path / "ollama-bin"
    bin_dir.mkdir()
    ollama = bin_dir / "ollama"
    ollama.write_text(
        "#!/bin/sh\n"
        f"exit {exit_code}\n"
    )
    ollama.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
