"""Editorial review: probable naming mistakes, surfaced while writing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from .corpus import Corpus, Kind, Name

FindingKind = Literal[
    "probable_duplicate", "single_use", "orphaned_profile", "unprofiled_name"
]

#: Names this short are compared by exact normalized form only. One edit away from
#: a three-letter name is usually a different name, not a typo.
MIN_FUZZY_LENGTH = 4


@dataclass(frozen=True)
class Finding:
    kind: FindingKind
    name: Name
    other: Name | None = None
    detail: str = ""

    @property
    def sort_key(self) -> tuple[str, str, str, str]:
        return (self.kind, self.name.kind, self.name.normalized, self.other.normalized if self.other else "")


def edit_distance(left: str, right: str, *, limit: int = 2) -> int:
    """Levenshtein distance, abandoned once it exceeds `limit`."""
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    if left == right:
        return 0

    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, start=1):
        current = [i]
        for j, b in enumerate(right, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (a != b),
                )
            )
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def _threshold_for(text: str) -> int:
    return 1 if len(text) < 8 else 2


def probable_duplicates(corpus: Corpus, kind: Kind | None = None) -> list[Finding]:
    """Names close enough that one is probably a misspelling of the other."""
    findings: list[Finding] = []
    kinds = (kind,) if kind else ("character", "location", "tag")

    for current_kind in kinds:
        names = corpus.names_of_kind(current_kind)  # type: ignore[arg-type]
        for i, left in enumerate(names):
            for right in names[i + 1 :]:
                if left.normalized == right.normalized:
                    findings.append(
                        Finding(
                            "probable_duplicate",
                            left,
                            right,
                            "identical apart from case, punctuation, or accents",
                        )
                    )
                    continue

                if min(len(left.normalized), len(right.normalized)) < MIN_FUZZY_LENGTH:
                    continue
                limit = _threshold_for(left.normalized)
                distance = edit_distance(left.normalized, right.normalized, limit=limit)
                if distance <= limit:
                    findings.append(
                        Finding(
                            "probable_duplicate",
                            left,
                            right,
                            f"{distance} character{'' if distance == 1 else 's'} apart",
                        )
                    )
    return findings


def single_use(corpus: Corpus) -> list[Finding]:
    """Names used by exactly one story — the usual shape of a typo."""
    return [
        Finding("single_use", name, detail="used by one story")
        for name in corpus.all_names()
        if corpus.use_count(name) == 1
    ]


def orphaned_profiles(corpus: Corpus, subjects: Iterable) -> list[Finding]:
    """Profiles describing a name no story uses."""
    findings: list[Finding] = []
    for subject in subjects:
        if not subject.has_profile:
            continue
        if corpus.name(subject.kind, subject.name) is None:
            findings.append(
                Finding(
                    "orphaned_profile",
                    Name(
                        display=subject.name,
                        normalized=subject.name.casefold(),
                        kind=subject.kind,
                        slug="",
                    ),
                    detail="a profile describes this name, but no story uses it",
                )
            )
    return findings


def unprofiled_names(corpus: Corpus, subjects: Iterable) -> list[Finding]:
    """Characters and locations with no profile and no recorded dismissal."""
    by_key = {(s.kind, s.name): s for s in subjects}
    findings: list[Finding] = []

    for kind in ("character", "location"):
        for name in corpus.names_of_kind(kind):  # type: ignore[arg-type]
            subject = by_key.get((kind, name.display))
            if subject is not None and (subject.has_profile or subject.dismissed):
                continue
            findings.append(Finding("unprofiled_name", name, detail="no profile yet"))
    return findings


def findings(corpus: Corpus, subjects: Iterable | None = None) -> list[Finding]:
    """Every finding, sorted deterministically."""
    subjects = list(subjects or ())
    collected = [
        *probable_duplicates(corpus),
        *single_use(corpus),
        *orphaned_profiles(corpus, subjects),
        *unprofiled_names(corpus, subjects),
    ]
    return sorted(collected, key=lambda f: f.sort_key)


def describe_finding(finding: Finding) -> str:
    """A one-line description, used for build warnings."""
    if finding.kind == "probable_duplicate" and finding.other is not None:
        return (
            f"probable duplicate {finding.name.kind}: "
            f"{finding.name.display!r} and {finding.other.display!r} "
            f"({finding.detail})"
        )
    if finding.kind == "orphaned_profile":
        return f"orphaned profile: {finding.name.display!r} is described but unused"
    if finding.kind == "single_use":
        return f"single-use {finding.name.kind}: {finding.name.display!r}"
    return f"unprofiled {finding.name.kind}: {finding.name.display!r}"
