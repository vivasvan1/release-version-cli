from __future__ import annotations

import subprocess


def build_release_notes(commits: list[str], model: str = "gemma4", use_ai: bool = True) -> str:
    changes = ""
    if use_ai and commits:
        changes = _ollama_changes(commits, model)
    if not changes:
        changes = _deterministic_changes(commits)
    return changes.rstrip() + "\n\n## Commits\n\n" + _commit_lines(commits) + "\n"


def _ollama_changes(commits: list[str], model: str) -> str:
    prompt = (
        "Generate concise GitHub release notes in this exact markdown shape:\n"
        "## Changes\n\n"
        "### Features\n- ...\n\n"
        "### Fixes\n- ...\n\n"
        "### Other\n- ...\n\n"
        "Use only these commits. Omit empty categories. No intro.\n\n"
        + "\n".join(commits)
    )
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
        subject = commit.split(" ", 1)[1] if " " in commit else commit
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
