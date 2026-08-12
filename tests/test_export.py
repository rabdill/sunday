"""The `cast.yml` export: what crosses the boundary, and what must not.

MANDATORY per plan.md. This file is the only thing the store sends to the published
site, so a mistake here either breaks the diagram or leaks private writing into a
committed file.
"""

from __future__ import annotations

import pytest

from sunday.corpus import load_corpus
from sunday.export import (
    CastExport,
    RelationshipEntry,
    dump_cast,
    export_from_store,
    load_cast,
    write_cast,
)
from sunday.store import Store, rebuild_store


@pytest.fixture
def populated(scratch_corpus, tmp_path):
    """A store with a profile, a display-name override, and a relationship."""
    corpus = load_corpus(scratch_corpus / "stories")
    store = Store.open(tmp_path / "store.db")
    store.sync_subjects(corpus)
    store.set_profile(
        "character", "Elias Doyle", description="A private note about him.", display_name="Doyle"
    )
    mara = store.subject("character", "Mara Vance")
    elias = store.subject("character", "Elias Doyle")
    store.add_relationship(mara.id, elias.id, "sister", False)
    yield store
    store.close()


# ------------------------------------------------------------------ round trip


def test_export_then_import_reproduces_relationships_and_display_names(populated, tmp_path):
    path = tmp_path / "cast.yml"
    write_cast(path, export_from_store(populated))

    reloaded = load_cast(path)
    assert reloaded.display_names == {"Elias Doyle": "Doyle"}
    assert len(reloaded.relationships) == 1

    relationship = reloaded.relationships[0]
    assert (relationship.from_name, relationship.to_name) == ("Mara Vance", "Elias Doyle")
    assert relationship.description == "sister"
    assert relationship.directed is False


def test_a_missing_file_imports_as_empty_rather_than_erroring(tmp_path):
    """A collection with no profiles and no relationships is perfectly normal."""
    empty = load_cast(tmp_path / "nothing-here.yml")
    assert empty.display_names == {}
    assert empty.relationships == ()


def test_an_empty_export_still_carries_the_generated_warning(tmp_path):
    path = tmp_path / "cast.yml"
    write_cast(path, CastExport())
    assert "DO NOT EDIT" in path.read_text(encoding="utf-8")


# --------------------------------------------------------------- what leaks
#
# FR-038b / SC-018. Nothing published displays a description, so exporting one
# would put private writing into a committed file for no reader's benefit.


def test_a_profile_description_is_never_exported(populated, tmp_path):
    path = tmp_path / "cast.yml"
    write_cast(path, export_from_store(populated))
    text = path.read_text(encoding="utf-8")

    assert "A private note about him." not in text
    assert "description:" not in text.split("relationships:")[0], (
        "no description field may appear in the display_names block"
    )


def test_the_export_contains_only_display_names_and_relationships(populated):
    export = export_from_store(populated)
    rendered = dump_cast(export)

    keys = {
        line.split(":")[0]
        for line in rendered.splitlines()
        if line and not line.startswith((" ", "-", "#"))
    }
    assert keys <= {"display_names", "relationships"}


def test_a_subject_with_only_a_description_exports_nothing(scratch_corpus, tmp_path):
    """A description alone gives the published site nothing to show."""
    corpus = load_corpus(scratch_corpus / "stories")
    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        store.set_profile("character", "Mara Vance", description="Private.", display_name=None)
        export = export_from_store(store)

    assert export.display_names == {}


# ------------------------------------------------------------------ determinism


def test_export_output_is_sorted_and_deterministic(populated, tmp_path):
    first = dump_cast(export_from_store(populated))
    second = dump_cast(export_from_store(populated))
    assert first == second


def test_relationships_are_emitted_in_sorted_order(tmp_path):
    export = CastExport(
        relationships=(
            RelationshipEntry("Zoe", "Adam", "knew"),
            RelationshipEntry("Adam", "Beth", "sister"),
        )
    )
    rendered = dump_cast(export)
    assert rendered.index("Adam\n") < rendered.index("Zoe")


# --------------------------------------------------------------------- rebuild


def test_rebuild_recovers_relationships_and_display_names(scratch_corpus, tmp_path):
    """T106 / SC-011 — what survives losing the store, and what does not."""
    store_path = tmp_path / "store.db"
    cast_path = scratch_corpus / "cast.yml"

    with Store.open(store_path) as store:
        corpus = load_corpus(scratch_corpus / "stories")
        store.sync_subjects(corpus)
        store.set_profile(
            "character", "Elias Doyle", description="Lost on rebuild.", display_name="Doyle"
        )
        mara = store.subject("character", "Mara Vance")
        elias = store.subject("character", "Elias Doyle")
        store.add_relationship(mara.id, elias.id, "sister", False)
        store.add_note("subject", mara.id, "Also lost on rebuild.")
        store.dismiss("character", "Silas Thorne")
        write_cast(cast_path, export_from_store(store))

    report = rebuild_store(
        store_path=store_path,
        stories_dir=scratch_corpus / "stories",
        cast_path=cast_path,
    )
    assert report.rebuilt

    with Store.open(store_path) as store:
        # Recovered, because both crossed the boundary into cast.yml.
        assert store.subject("character", "Elias Doyle").display_name == "Doyle"
        assert len(store.relationships()) == 1

        # Not recovered, because none of these are ever exported.
        mara = store.subject("character", "Mara Vance")
        assert store.notes_for("subject", mara.id) == ()
        assert store.subject("character", "Elias Doyle").description is None
        assert store.subject("character", "Silas Thorne").dismissed is False

    assert set(report.lost) == {"notes", "dismissed candidates", "profile descriptions"}
