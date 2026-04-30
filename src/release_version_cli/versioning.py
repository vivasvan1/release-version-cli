from __future__ import annotations

import re
from dataclasses import dataclass


VERSION_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")
TAG_RE = re.compile(r"^v(?P<version>(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*))$")


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, value: str) -> "Version":
        match = VERSION_RE.fullmatch(value)
        if not match:
            raise ValueError(f"Version must be clean semver X.Y.Z: {value}")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
        )

    @classmethod
    def parse_tag(cls, tag: str) -> "Version":
        match = TAG_RE.fullmatch(tag)
        if not match:
            raise ValueError(f"Tag must be strict vX.Y.Z: {tag}")
        return cls.parse(match.group("version"))

    def bump(self, part: str) -> "Version":
        if part == "major":
            return Version(self.major + 1, 0, 0)
        if part == "minor":
            return Version(self.major, self.minor + 1, 0)
        if part == "patch":
            return Version(self.major, self.minor, self.patch + 1)
        raise ValueError(f"Unknown bump part: {part}")

    @property
    def tag(self) -> str:
        return f"v{self}"

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def parse_version_tags(tags: list[str]) -> dict[str, Version]:
    parsed: dict[str, Version] = {}
    for tag in tags:
        try:
            parsed[tag] = Version.parse_tag(tag)
        except ValueError:
            continue
    return parsed
