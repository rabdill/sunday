"""Writing story files: fidelity, atomicity, and rename.

A round trip through the portal must not quietly change what a file means. The
unmanaged-key case is the one most likely to rot — a key the system does not
recognise is exactly the kind of thing an implementation drops without noticing.
"""

from __future__ import annotations

import pytest

from sunday.corpus import load_corpus, parse_story
from sunday.writer import atomic_write, rename_across_corpus, serialize_story, write_story


# ------------------------------------------------------------------ round trip


def test_a_round_trip_preserves_every_managed_field(stories_dir, tmp_path):
    original = parse_story(stories_dir / "the-lighthouse.md")
    target = tmp_path / "out.md"
    write_story(target, original)
    reparsed = parse_story(target)

    assert reparsed.slug == original.slug
    assert reparsed.title == original.title
    assert reparsed.published == original.published
    assert str(reparsed.occurs) == str(original.occurs)
    assert reparsed.characters == original.characters
    assert reparsed.locations == original.locations
    assert reparsed.tags == original.tags
    assert reparsed.draft == original.draft
    assert reparsed.body.strip() == original.body.strip()


def test_a_round_trip_preserves_unmanaged_keys(stories_dir, tmp_path):
    """FR-027: a key the system does not manage is still the author's."""
    original = parse_story(stories_dir / "the-lighthouse.md")
    target = tmp_path / "out.md"
    write_story(target, original)

    assert parse_story(target).extra == {"mood": "bleak"}


def test_serialization_is_stable(stories_dir):
    """Writing twice from the same story yields the same text."""
    story = parse_story(stories_dir / "the-lighthouse.md")
    assert serialize_story(story) == serialize_story(story)


def test_a_partial_in_world_date_is_written_back_at_its_own_precision(stories_dir, tmp_path):
    story = parse_story(stories_dir / "the-fog.md")
    target = tmp_path / "out.md"
    write_story(target, story)

    assert "occurs: '1921'" in target.read_text(encoding="utf-8") or "occurs: 1921" in target.read_text(
        encoding="utf-8"
    )
    assert str(parse_story(target).occurs) == "1921"


def test_an_undated_story_writes_no_occurs_field(stories_dir, tmp_path):
    story = parse_story(stories_dir / "the-keeper.md")
    target = tmp_path / "out.md"
    write_story(target, story)

    assert "occurs:" not in target.read_text(encoding="utf-8")
    assert parse_story(target).occurs is None


def test_non_ascii_names_survive_a_round_trip(stories_dir, tmp_path):
    """T111 — accents must not be mangled into escapes or stripped."""
    story = parse_story(stories_dir / "winter-crossing.md")
    target = tmp_path / "out.md"
    write_story(target, story)

    text = target.read_text(encoding="utf-8")
    assert "Café Verlaine" in text
    assert parse_story(target).locations == ("Café Verlaine",)


# -------------------------------------------------------------------- atomicity


def test_atomic_write_returns_exactly_the_bytes_written(tmp_path):
    target = tmp_path / "out.md"
    written = atomic_write(target, "hello\n")
    assert written == target.read_bytes()


def test_atomic_write_leaves_no_temporary_files_behind(tmp_path):
    atomic_write(tmp_path / "out.md", "hello\n")
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".sunday-")]
    assert leftovers == []


# ----------------------------------------------------------------------- rename


def test_rename_leaves_zero_occurrences_of_the_old_name(scratch_corpus):
    """SC-010."""
    stories = scratch_corpus / "stories"
    result = rename_across_corpus(stories, "character", "Mara Vanse", "Mara Vance")

    assert result.count == 1
    remaining = [p.name for p in stories.glob("*.md") if "Mara Vanse" in p.read_text(encoding="utf-8")]
    assert remaining == []


def test_rename_works_identically_for_tags(scratch_corpus):
    """FR-031: the rename logic does not branch on kind."""
    stories = scratch_corpus / "stories"
    result = rename_across_corpus(stories, "tag", "Epistolary", "epistolary")

    assert result.count == 1
    remaining = [p.name for p in stories.glob("*.md") if "Epistolary" in p.read_text(encoding="utf-8")]
    assert remaining == []


def test_rename_does_not_duplicate_an_already_present_name(scratch_corpus, tmp_path):
    """Folding a typo into a name the same story already carries must not double it."""
    stories = scratch_corpus / "stories"
    (stories / "both.md").write_text(
        "---\nslug: both\ntitle: Both\npublished: 2026-01-01\n"
        "characters:\n  - Mara Vance\n  - Mara Vanse\n---\n\nBody.\n",
        encoding="utf-8",
    )

    rename_across_corpus(stories, "character", "Mara Vanse", "Mara Vance")

    assert parse_story(stories / "both.md").characters == ("Mara Vance",)


def test_rename_leaves_unrelated_stories_untouched(scratch_corpus):
    stories = scratch_corpus / "stories"
    before = (stories / "letters-home.md").read_bytes()

    rename_across_corpus(stories, "character", "Mara Vanse", "Mara Vance")

    assert (stories / "letters-home.md").read_bytes() == before


def test_rename_returns_the_bytes_it_wrote(scratch_corpus):
    """The caller needs these to update hashes, so a rename never self-conflicts."""
    stories = scratch_corpus / "stories"
    result = rename_across_corpus(stories, "character", "Mara Vanse", "Mara Vance")

    for path, written in result.written.items():
        assert path.read_bytes() == written


def test_rename_rejects_an_empty_name(scratch_corpus):
    with pytest.raises(ValueError, match="cannot be empty"):
        rename_across_corpus(scratch_corpus / "stories", "character", "Mara Vance", "   ")
