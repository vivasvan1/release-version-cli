from __future__ import annotations

import re
import subprocess


def build_release_notes(commits: list[str], model: str = "gemma4", use_ai: bool = True) -> str:
    change_commits = _change_commits(commits)
    changes = ""
    if use_ai and change_commits:
        changes = _ollama_changes(change_commits, model)
    if not changes:
        changes = _deterministic_changes(change_commits)
    return changes.rstrip() + "\n\n## Commits\n\n" + _commit_lines(commits) + "\n"


def _ollama_changes(commits: list[str], model: str) -> str:
    prompt = _ollama_prompt(commits)
    try:
        result = subprocess.run(
            ["ollama", "run", model],
            input=prompt,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    output = result.stdout.strip()
    if result.returncode != 0 or not output.startswith("## Changes"):
        return ""
    return output


def _ollama_prompt(commits: list[str]) -> str:
    return (
        "Generate concise, human-written GitHub release notes from commit subjects.\n"
        "Write for project users and maintainers who want to understand the impact of the change.\n"
        "Translate terse commit messages into clear outcomes in different words.\n"
        "Do not copy commit subjects verbatim unless a product name, API name, flag, file path, or version must stay exact.\n"
        "Do not mention commit hashes.\n"
        "Ignore synthetic release bookkeeping commits such as '<release> chore: release vX.Y.Z'.\n"
        "Use only evidence from these commits. Be specific when the subject provides enough context, but do not invent details.\n\n"
        "Use this exact markdown shape:\n"
        "## Changes\n\n"
        "### Features\n- ...\n\n"
        "### Fixes\n- ...\n\n"
        "### Performance\n- ...\n\n"
        "### Docs\n- ...\n\n"
        "### Maintenance\n- ...\n\n"
        "### Other\n- ...\n\n"
        "Use only these commit subjects. Omit empty categories. No intro.\n\n"
        + "\n".join(f"- {_subject(commit)}" for commit in commits)
    )


def _deterministic_changes(commits: list[str]) -> str:
    groups: dict[str, list[str]] = {
        "Features": [],
        "Fixes": [],
        "Docs": [],
        "Tests": [],
        "Maintenance": [],
        "Other": [],
    }
    for commit in commits:
        subject = _subject(commit)
        lowered = subject.lower()
        if lowered.startswith(("feat:", "feature:")):
            groups["Features"].append(_clean_subject(subject))
        elif lowered.startswith(("fix:", "bugfix:")):
            groups["Fixes"].append(_clean_subject(subject))
        elif lowered.startswith("docs:"):
            groups["Docs"].append(_clean_subject(subject))
        elif lowered.startswith("test:"):
            groups["Tests"].append(_clean_subject(subject))
        elif lowered.startswith(("refactor:", "perf:", "chore:")):
            groups["Maintenance"].append(_clean_subject(subject))
        else:
            groups["Other"].append(_clean_subject(subject))

    lines = ["## Changes", ""]
    wrote_group = False
    for name, items in groups.items():
        if not items:
            continue
        wrote_group = True
        lines.extend([f"### {name}"])
        lines.extend(f"- {item}" for item in items)
        lines.append("")
    if not wrote_group:
        lines.extend(["### Other", "- No commit subjects found.", ""])
    return "\n".join(lines).rstrip()


def _change_commits(commits: list[str]) -> list[str]:
    return [commit for commit in commits if not _is_release_bookkeeping(commit)]


def _is_release_bookkeeping(commit: str) -> bool:
    subject = _subject(commit).lower()
    return bool(re.fullmatch(r"chore: release v\d+\.\d+\.\d+", subject))


def _subject(commit: str) -> str:
    return commit.split(" ", 1)[1] if " " in commit else commit


def _commit_lines(commits: list[str]) -> str:
    if not commits:
        return "- No commits found."
    return "\n".join(f"- {commit}" for commit in commits)


def _clean_subject(subject: str) -> str:
    if ":" in subject:
        subject = subject.split(":", 1)[1].strip()
    else:
        subject = subject.strip()
    if not subject:
        return subject
    return subject[0].upper() + subject[1:]
