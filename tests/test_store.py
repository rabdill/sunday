"""The authoring store: conflict detection, subjects, and rename survival.

MANDATORY per plan.md. Conflict detection is where a wrong answer costs someone
their writing — either by overwriting an edit they made elsewhere, or by crying
wolf until they stop reading the prompt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sunday.corpus import load_corpus
from sunday.store import ConflictState, Store, content_hash, rebuild_store
from sunday.writer import write_story


@pytest.fixture
def store(tmp_path):
    with Store.open(tmp_path / ".sunday" / "store.db") as opened:
        yield opened


@pytest.fixture
def tracked(scratch_corpus, store):
    """A corpus the store has already adopted — every story clean."""
    corpus = load_corpus(scratch_corpus / "stories")
    store.scan(corpus)
    return corpus


def story_file(scratch_corpus: Path, slug: str) -> Path:
    return scratch_corpus / "stories" / f"{slug}.md"


# ------------------------------------------------------------------------ schema


def test_schema_is_created_with_all_six_tables(store):
    names = {
        row["name"]
        for row in store.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {"meta", "stories", "subjects", "notes", "relationships", "conflicts"} <= names


def test_schema_version_is_recorded(store):
    from sunday.store import SCHEMA_VERSION

    assert store.schema_version() == SCHEMA_VERSION


# ------------------------------------------------------- conflict detection
#
# Both directions matter: a file the portal wrote must stay clean, and a file
# someone else changed must be caught.


def test_an_untouched_file_stays_clean(scratch_corpus, tracked, store):
    state = store.state_of("the-fog", story_file(scratch_corpus, "the-fog"))
    assert state.state is ConflictState.CLEAN
    assert not state.blocked


def test_an_externally_modified_file_is_diverged(scratch_corpus, tracked, store):
    path = story_file(scratch_corpus, "the-fog")
    path.write_text(path.read_text(encoding="utf-8") + "\nA line added elsewhere.\n", encoding="utf-8")

    state = store.state_of("the-fog", path)
    assert state.state is ConflictState.DIVERGED
    assert state.blocked, "editing must be blocked until the author chooses"


def test_a_file_the_portal_wrote_never_self_reports_a_conflict(scratch_corpus, tracked, store):
    """The portal's own save must not look like someone else's edit."""
    corpus = load_corpus(scratch_corpus / "stories")
    story = corpus.by_slug("the-fog")
    path = story.source_path

    written = write_story(path, story)
    store.record_write("the-fog", path, written)

    assert store.state_of("the-fog", path).state is ConflictState.CLEAN


def test_rewriting_identical_bytes_stays_clean(scratch_corpus, tracked, store):
    path = story_file(scratch_corpus, "the-fog")
    original = path.read_bytes()
    path.write_bytes(original)

    assert store.state_of("the-fog", path).state is ConflictState.CLEAN


def test_resolution_clears_the_conflict_and_records_the_new_hash(scratch_corpus, tracked, store):
    path = story_file(scratch_corpus, "the-fog")
    path.write_text(path.read_text(encoding="utf-8") + "\nEdited elsewhere.\n", encoding="utf-8")
    assert store.state_of("the-fog", path).state is ConflictState.DIVERGED

    # "Keep disk" adopts the file exactly as it stands.
    store.record_write("the-fog", path, path.read_bytes())

    state = store.state_of("the-fog", path)
    assert state.state is ConflictState.CLEAN
    assert store.story_row("the-fog")["last_written_hash"] == content_hash(path.read_bytes())


def test_detection_is_by_content_not_timestamp(scratch_corpus, tracked, store):
    """A `git checkout` rewrites mtimes on every file; that must not be a conflict."""
    import os
    import time

    path = story_file(scratch_corpus, "the-fog")
    future = time.time() + 10_000
    os.utime(path, (future, future))

    assert store.state_of("the-fog", path).state is ConflictState.CLEAN


def test_an_unknown_file_is_untracked_then_adopted(scratch_corpus, store):
    """A story the portal never wrote has no earlier version to disagree with."""
    path = story_file(scratch_corpus, "the-fog")
    assert store.state_of("the-fog", path).state is ConflictState.UNTRACKED

    corpus = load_corpus(scratch_corpus / "stories")
    states = store.scan(corpus)
    assert states["the-fog"].state is ConflictState.CLEAN


def test_a_vanished_file_is_reported_missing(scratch_corpus, tracked, store):
    story_file(scratch_corpus, "the-fog").unlink()
    corpus = load_corpus(scratch_corpus / "stories")

    states = store.scan(corpus)
    assert states["the-fog"].state is ConflictState.MISSING


def test_scan_reports_every_diverged_story(scratch_corpus, tracked, store):
    for slug in ("the-fog", "letters-home"):
        path = story_file(scratch_corpus, slug)
        path.write_text(path.read_text(encoding="utf-8") + "\nchanged\n", encoding="utf-8")

    corpus = load_corpus(scratch_corpus / "stories")
    diverged = {state.slug for state in store.conflicts(corpus)}
    assert diverged == {"the-fog", "letters-home"}


# ---------------------------------------------------------------------- subjects


def test_subjects_are_created_for_characters_and_locations(scratch_corpus, store):
    corpus = load_corpus(scratch_corpus / "stories")
    store.sync_subjects(corpus)

    names = {(s.kind, s.name) for s in store.subjects()}
    assert ("character", "Mara Vance") in names
    assert ("location", "Portsmouth") in names


def test_tags_never_get_a_subject_row(scratch_corpus, store):
    """A subject row exists for notes and relationships to follow; tags have neither."""
    corpus = load_corpus(scratch_corpus / "stories")
    store.sync_subjects(corpus)

    kinds = {s.kind for s in store.subjects()}
    assert kinds <= {"character", "location"}
    assert store.subject("tag", "epistolary") is None


def test_syncing_twice_preserves_subject_ids(scratch_corpus, store):
    """Notes and relationships point at ids; a reload must not renumber them."""
    corpus = load_corpus(scratch_corpus / "stories")
    store.sync_subjects(corpus)
    before = store.subject("character", "Mara Vance").id

    store.sync_subjects(corpus)
    assert store.subject("character", "Mara Vance").id == before


def test_dismissal_is_remembered(scratch_corpus, store):
    """FR-044: a declined suggestion must not resurface every session."""
    store.dismiss("character", "Mara Vanse")
    assert store.subject("character", "Mara Vanse").dismissed is True


def test_a_dismissal_alone_is_not_a_profile(store):
    store.dismiss("character", "Someone")
    assert store.subject("character", "Someone").has_profile is False


def test_rename_moves_the_subject_in_place(scratch_corpus, store):
    """In place, so notes and relationships keep following the id (FR-047, FR-050)."""
    corpus = load_corpus(scratch_corpus / "stories")
    store.sync_subjects(corpus)
    original = store.subject("character", "Mara Vanse").id

    store.rename_subject("character", "Mara Vanse", "Mara Vance Renamed")

    assert store.subject("character", "Mara Vanse") is None
    assert store.subject("character", "Mara Vance Renamed").id == original


# ------------------------------------------------------- notes and relationships
#
# Both attach to a subject id rather than a name string, which is the whole reason
# a rename cannot orphan them (FR-047, FR-050).


def test_a_note_survives_renaming_its_subject(scratch_corpus, store):
    corpus = load_corpus(scratch_corpus / "stories")
    store.sync_subjects(corpus)

    mara = store.subject("character", "Mara Vance")
    store.add_note("subject", mara.id, "She never answers the second letter.")

    store.rename_subject("character", "Mara Vance", "Mara Vance-Doyle")

    renamed = store.subject("character", "Mara Vance-Doyle")
    assert renamed.id == mara.id, "the id is what the note follows"
    notes = store.notes_for("subject", renamed.id)
    assert [n.body for n in notes] == ["She never answers the second letter."]


def test_a_relationship_survives_renaming_either_character(scratch_corpus, store):
    corpus = load_corpus(scratch_corpus / "stories")
    store.sync_subjects(corpus)

    mara = store.subject("character", "Mara Vance")
    elias = store.subject("character", "Elias Doyle")
    store.add_relationship(mara.id, elias.id, "sister", False)

    store.rename_subject("character", "Elias Doyle", "E. Doyle")

    relationships = store.relationships()
    assert len(relationships) == 1
    assert relationships[0].to_subject.name == "E. Doyle"
    assert relationships[0].description == "sister"


def test_merging_a_rename_into_an_existing_name_keeps_dependents(scratch_corpus, store):
    """Folding a typo into the real name must not drop its notes."""
    corpus = load_corpus(scratch_corpus / "stories")
    store.sync_subjects(corpus)

    typo = store.subject("character", "Mara Vanse")
    store.add_note("subject", typo.id, "Attached to the misspelling.")

    store.rename_subject("character", "Mara Vanse", "Mara Vance")

    real = store.subject("character", "Mara Vance")
    assert store.subject("character", "Mara Vanse") is None
    assert any(
        n.body == "Attached to the misspelling." for n in store.notes_for("subject", real.id)
    )


# ----------------------------------------------------------------------- rebuild


def test_rebuild_recovers_stories_and_subjects(scratch_corpus, tmp_path):
    store_path = tmp_path / "store.db"
    report = rebuild_store(
        store_path=store_path,
        stories_dir=scratch_corpus / "stories",
        cast_path=scratch_corpus / "cast.yml",
    )

    assert report.rebuilt is True
    assert report.stories == 7
    assert report.subjects > 0
    assert "notes" in " ".join(report.lost)


def test_rebuild_leaves_every_story_clean(scratch_corpus, tmp_path):
    """After a rebuild the files *are* the truth; nothing should look conflicted."""
    store_path = tmp_path / "store.db"
    rebuild_store(
        store_path=store_path,
        stories_dir=scratch_corpus / "stories",
        cast_path=scratch_corpus / "cast.yml",
    )

    corpus = load_corpus(scratch_corpus / "stories")
    with Store.open(store_path) as store:
        states = store.scan(corpus)
    assert {s.state for s in states.values()} == {ConflictState.CLEAN}


def test_rebuild_loses_no_story_text(scratch_corpus, tmp_path):
    """SC-011 / FR-042: the store is disposable; fiction is not."""
    before = {p.name: p.read_text(encoding="utf-8") for p in (scratch_corpus / "stories").glob("*.md")}

    rebuild_store(
        store_path=tmp_path / "store.db",
        stories_dir=scratch_corpus / "stories",
        cast_path=scratch_corpus / "cast.yml",
    )

    after = {p.name: p.read_text(encoding="utf-8") for p in (scratch_corpus / "stories").glob("*.md")}
    assert before == after
