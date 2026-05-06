from __future__ import annotations

import tempfile
from pathlib import Path

import click

from release_version_cli.changelog import ReleaseNotesResult, build_release_notes_result
from release_version_cli.git_ops import commit_tag_push, ensure_new_tag_absent, log_commits, preflight
from release_version_cli.github import ReleaseAlreadyExistsError, create_release, update_release_notes
from release_version_cli.manifest import read_manifest, select_manifest, write_manifest_version

#this is for the command line
@click.command()
@click.version_option(None, "--version", "-v", package_name="release-version-cli", prog_name="release-version")
@click.argument("part", type=click.Choice(["major", "minor", "patch"]))
@click.option("--dry-run", is_flag=True, help="Preview release without mutating files, git, or GitHub.")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt.")
@click.option("--initial", is_flag=True, help="Create first vX.Y.Z release when no remote version tag exists.")
@click.option("--file", "manifest_file", type=click.Path(), help="Manifest file to bump.")
@click.option("--cwd", "cwd", type=click.Path(file_okay=False), help="Working directory for manifest discovery.")
@click.option("--ollama-model", default="gemma4", show_default=True, help="Ollama model for release notes.")
@click.option(
    "--ollama-timeout",
    default=300,
    show_default=True,
    type=click.IntRange(min=1),
    help="Seconds to wait for Ollama release notes.",
)
@click.option("--no-ai", is_flag=True, help="Skip Ollama and use deterministic changelog.")
def main(
    part: str,
    dry_run: bool,
    yes: bool,
    initial: bool,
    manifest_file: str | None,
    cwd: str | None,
    ollama_model: str,
    ollama_timeout: int,
    no_ai: bool,
) -> None:
    try:
        _main(part, dry_run, yes, initial, manifest_file, cwd, ollama_model, ollama_timeout, no_ai)
    except click.ClickException:
        raise
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc


def _main(
    part: str,
    dry_run: bool,
    yes: bool,
    initial: bool,
    manifest_file: str | None,
    cwd: str | None,
    ollama_model: str,
    ollama_timeout: int,
    no_ai: bool,
) -> None:
    workdir = Path(cwd).resolve() if cwd else Path.cwd()
    state = preflight(workdir, initial)
    manifest_path = select_manifest(state.repo_root, manifest_file, workdir)
    manifest = read_manifest(manifest_path)

    if state.previous_version and manifest.version != state.previous_version:
        raise click.ClickException(
            f"Manifest version {manifest.version} does not match latest remote tag {state.previous_tag}."
        )

    new_version = manifest.version.bump(part)
    ensure_new_tag_absent(state.repo_root, new_version.tag)

    commits = log_commits(state.repo_root, state.previous_tag, "HEAD")
    commits = [f"<release> chore: release {new_version.tag}", *commits]
    notes_result = build_release_notes_result(
        commits,
        model=ollama_model,
        use_ai=not no_ai,
        timeout=ollama_timeout,
    )

    _print_plan(manifest_path, manifest.version, new_version, state.previous_tag, state.branch, dry_run)
    _print_ollama_warning(notes_result)
    click.echo("\nRelease notes preview\n")
    click.echo(notes_result.notes)

    if dry_run:
        return

    if not yes and not click.confirm("Continue?", default=False):
        raise click.Abort()

    write_manifest_version(manifest, new_version)
    commit_tag_push(state.repo_root, manifest.path, new_version, state.branch)
    final_commits = log_commits(state.repo_root, state.previous_tag, new_version.tag)
    final_notes_result = build_release_notes_result(
        final_commits,
        model=ollama_model,
        use_ai=not no_ai,
        timeout=ollama_timeout,
    )
    _print_ollama_warning(final_notes_result)

    notes_file: Path | None = None
    try:
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=f"-{new_version.tag}-notes.md") as handle:
            handle.write(final_notes_result.notes)
            notes_file = Path(handle.name)
        create_release(new_version.tag, notes_file)
    except ReleaseAlreadyExistsError as exc:
        if notes_file is None:
            raise click.ClickException(str(exc)) from exc
        action = click.prompt(
            f"GitHub release {new_version.tag} already exists. Append these release notes to the existing description?",
            type=click.Choice(["start", "end", "skip"], case_sensitive=False),
            default="skip",
            show_choices=True,
        ).lower()
        if action == "skip":
            click.echo(f"Release notes kept at: {notes_file}", err=True)
            raise click.ClickException(str(exc)) from exc
        update_release_notes(new_version.tag, notes_file, action)
        notes_file.unlink(missing_ok=True)
        click.echo(f"Updated existing GitHub release {new_version.tag}")
    except Exception as exc:
        if notes_file:
            click.echo(f"Release notes kept at: {notes_file}", err=True)
            click.echo(
                f"Retry: gh release create {new_version.tag} --title {new_version.tag} --notes-file {notes_file} --latest",
                err=True,
            )
        raise click.ClickException(str(exc)) from exc
    else:
        if notes_file:
            notes_file.unlink(missing_ok=True)
        click.echo(f"Released {new_version.tag}")


def _print_plan(
    manifest_path: Path,
    current_version: object,
    new_version: object,
    previous_tag: str | None,
    branch: str,
    dry_run: bool,
) -> None:
    click.echo("Release plan")
    click.echo(f"  Manifest: {manifest_path}")
    click.echo(f"  Current:  {current_version}")
    click.echo(f"  New:      {new_version}")
    click.echo(f"  Previous: {previous_tag or '<initial>'}")
    click.echo(f"  Tag:      v{new_version}")
    click.echo(f"  Branch:   {branch}")
    click.echo(f"  Mode:     {'dry-run' if dry_run else 'release'}")


def _print_ollama_warning(result: ReleaseNotesResult) -> None:
    if not result.ollama_warning:
        return
    click.echo(f"WARNING: Ollama release notes failed; using deterministic fallback. Cause: {result.ollama_warning}", err=True)
    if result.ollama_prompt:
        click.echo("===PROMPT===", err=True)
        click.echo(result.ollama_prompt, err=True)
        click.echo("===PROMPT END===", err=True)
