"""Naming review: finding the typo that would otherwise publish quietly.

A misspelled name produces a plausible-looking page that is wrong — nothing errors,
the reader simply never sees the story under the name they were looking for. Every
check runs over characters, locations, and tags alike.
"""

from __future__ import annotations

import pytest

from conftest import build_into
from sunday.corpus import load_corpus
from sunday.review import (
    describe_finding,
    edit_distance,
    findings,
    orphaned_profiles,
    probable_duplicates,
    single_use,
    unprofiled_names,
)
from sunday.store import Store


def pairs(results):
    return {
        frozenset({f.name.display, f.other.display})
        for f in results
        if f.other is not None
    }


def corpus_with(tmp_path, **fields):
    """A one-story corpus, for isolating a single naming situation."""
    body = ["---", "slug: s", "title: S", "published: 2026-01-01"]
    for key, values in fields.items():
        body.append(f"{key}:")
        body.extend(f"  - {value}" for value in values)
    body += ["---", "", "Body."]
    (tmp_path / "s.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    return load_corpus(tmp_path)


# ------------------------------------------------------------- edit distance


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [
        ("mara vance", "mara vance", 0),
        ("mara vance", "mara vanse", 1),
        ("portsmouth", "portsmuth", 1),
        ("mara", "sara", 1),
        ("mara vance", "elias doyle", 3),  # bounded: reported as over the limit
    ],
)
def test_edit_distance_is_bounded(left, right, expected):
    result = edit_distance(left, right, limit=2)
    if expected <= 2:
        assert result == expected
    else:
        assert result > 2, "distance past the limit is abandoned, not computed exactly"


# ----------------------------------------------------------- probable duplicates


@pytest.mark.parametrize(
    ("kind", "first", "second"),
    [
        pytest.param("characters", "Mara Vance", "mara vance", id="case-only"),
        pytest.param("characters", "O'Brien", "OBrien", id="punctuation-only"),
        pytest.param("locations", "Café Verlaine", "Cafe Verlaine", id="accent-only"),
        pytest.param("locations", "Portsmouth", "Portsmuth", id="misspelling"),
    ],
)
def test_a_near_duplicate_pair_is_detected(tmp_path, kind, first, second):
    """The exact case/punctuation/accent variation the name index was almost too clever to preserve."""
    corpus = corpus_with(tmp_path, **{kind: [first, second]})
    assert pairs(probable_duplicates(corpus)) == {frozenset({first, second})}


def test_a_small_misspelling_is_detected(corpus):
    found = pairs(probable_duplicates(corpus, "character"))
    assert frozenset({"Mara Vance", "Mara Vanse"}) in found


def test_unrelated_names_are_not_flagged(corpus):
    found = pairs(probable_duplicates(corpus, "character"))
    assert frozenset({"Mara Vance", "Elias Doyle"}) not in found
    assert frozenset({"Silas Thorne", "Elias Doyle"}) not in found


def test_short_names_are_not_fuzzily_matched(tmp_path):
    """One edit away from a three-letter name is usually a different name."""
    corpus = corpus_with(tmp_path, characters=["Ada", "Ida"])
    assert pairs(probable_duplicates(corpus)) == set()


def test_duplicates_are_detected_for_tags_too(corpus):
    """The same machinery, across all three kinds."""
    found = pairs(probable_duplicates(corpus, "tag"))
    assert frozenset({"epistolary", "Epistolary"}) in found


def test_the_same_spelling_under_two_kinds_is_not_a_duplicate(tmp_path):
    """A character and a location may legitimately share a name."""
    corpus = corpus_with(tmp_path, characters=["Avon"], locations=["Avon"])
    assert probable_duplicates(corpus) == []


# ---------------------------------------------------------------- single use


def test_single_use_names_are_flagged_across_all_kinds(corpus):
    flagged = {(f.name.kind, f.name.display) for f in single_use(corpus)}

    assert ("character", "Mara Vanse") in flagged, "the typo is used once"
    assert ("character", "Silas Thorne") in flagged
    assert ("tag", "Epistolary") in flagged
    assert ("character", "Mara Vance") not in flagged, "used by several stories"


# ------------------------------------------------------------------ profiles


def test_orphaned_profiles_are_reported(corpus, tmp_path):
    """A profile describing a name no story uses."""
    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        store.set_profile(
            "character", "Someone Deleted", description="Was cut.", display_name=None
        )
        found = orphaned_profiles(corpus, store.subjects())

    assert {f.name.display for f in found} == {"Someone Deleted"}


def test_a_dismissal_alone_is_not_an_orphaned_profile(corpus, tmp_path):
    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        store.dismiss("character", "Nobody At All")
        assert orphaned_profiles(corpus, store.subjects()) == []


def test_tags_never_produce_orphaned_profile_findings(corpus, tmp_path):
    """Tags have no profiles, so the finding cannot apply to them."""
    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        found = orphaned_profiles(corpus, store.subjects())
    assert all(f.name.kind != "tag" for f in found)


def test_unprofiled_names_become_candidates(corpus, tmp_path):
    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        found = unprofiled_names(corpus, store.subjects())

    assert "Mara Vance" in {f.name.display for f in found}
    assert all(f.name.kind != "tag" for f in found), "tags never get profiles"


def test_dismissed_names_are_excluded_from_candidates(corpus, tmp_path):
    """A declined suggestion must not come back."""
    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        store.dismiss("character", "Mara Vanse")
        found = unprofiled_names(corpus, store.subjects())

    assert "Mara Vanse" not in {f.name.display for f in found}


def test_profiled_names_are_excluded_from_candidates(corpus, tmp_path):
    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        store.set_profile("character", "Mara Vance", description="The keeper.", display_name=None)
        found = unprofiled_names(corpus, store.subjects())

    assert "Mara Vance" not in {f.name.display for f in found}


# ------------------------------------------------------------ never fatal


def test_a_build_with_findings_still_succeeds(tmp_path, scratch_corpus):
    """Naming findings warn, and the site publishes anyway."""
    result = build_into(tmp_path / "site", scratch_corpus)

    assert result.warnings, "the fixture corpus contains a deliberate near-duplicate"
    assert (tmp_path / "site" / "index.html").exists(), "and it published regardless"


def test_build_warnings_name_both_spellings(tmp_path, scratch_corpus):
    result = build_into(tmp_path / "site", scratch_corpus)

    joined = " ".join(result.warnings)
    assert "Mara Vance" in joined and "Mara Vanse" in joined


def test_cli_build_exits_zero_with_warnings_and_one_under_strict(scratch_corpus, tmp_path):
    from sunday.cli import main

    args = [
        "build",
        "--stories", str(scratch_corpus / "stories"),
        "--settings", str(scratch_corpus / "sunday.yml"),
        "--cast", str(scratch_corpus / "cast.yml"),
        "--output", str(tmp_path / "site"),
    ]
    assert main([*args, "--quiet"]) == 0

    assert main([*args, "--strict"]) == 1, "--strict is opt-in, and CI does not pass it"


# -------------------------------------------------------------- descriptions


def test_findings_are_described_legibly(corpus, tmp_path):
    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        described = [describe_finding(f) for f in findings(corpus, store.subjects())]

    duplicate_lines = [line for line in described if line.startswith("probable duplicate")]
    assert duplicate_lines
    assert any("Mara Vanse" in line for line in duplicate_lines)


def test_findings_are_deterministically_ordered(corpus, tmp_path):
    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        first = [f.sort_key for f in findings(corpus, store.subjects())]
        second = [f.sort_key for f in findings(corpus, store.subjects())]

    assert first == second == sorted(first)
