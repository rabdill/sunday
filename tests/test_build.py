"""The generator: what it emits, what it refuses to emit, and what it never merges.

Two of these are structural guards rather than behaviour tests — the import
boundary and the page inventory. Both are a few lines and both protect properties
the whole architecture rests on, which makes them the first things a well-meaning
refactor breaks.
"""

from __future__ import annotations

import filecmp
import json
from pathlib import Path

import pytest

from conftest import PUBLISHED_SLUGS, build_into, module_identifiers
from sunday.build import BuildError

PACKAGE = Path(__file__).parent.parent / "sunday"


@pytest.fixture
def site(tmp_path, scratch_corpus) -> Path:
    out = tmp_path / "site"
    build_into(out, scratch_corpus)
    return out


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------- what gets emitted


def test_markdown_is_rendered_not_shown_as_markup(site):
    page = read(site / "stories" / "the-lighthouse" / "index.html")
    assert "<em>him</em>" in page
    assert "<blockquote>" in page
    assert "<li>One light</li>" in page
    assert "*him*" not in page


# --------------------------------------------------------------------- page inventory
#
# Exactly four kinds of page, and nothing else.


def test_only_the_four_page_kinds_are_generated(site):
    pages = {p.relative_to(site).as_posix() for p in site.rglob("*.html")}
    expected = {"index.html", "archive/index.html", "network/index.html"} | {
        f"stories/{slug}/index.html" for slug in PUBLISHED_SLUGS
    }
    assert pages == expected


def test_no_character_location_or_tag_pages_exist(site):
    """Cast material belongs to the portal, not the published site."""
    for forbidden in ("characters", "locations", "tags"):
        assert not (site / forbidden).exists(), f"/{forbidden}/ must not be generated"


# --------------------------------------------------------------------------- drafts


def test_a_draft_appears_nowhere_in_the_output(site):
    """Not the feed, not the archive, not the graph, not its own address."""
    assert not (site / "stories" / "unfinished").exists()

    for page in ("index.html", "archive/index.html", "graph.json"):
        text = read(site / page)
        assert "Unfinished" not in text
        assert "unfinished" not in text

    graph = json.loads(read(site / "graph.json"))
    labels = {n["label"] for n in graph["nodes"]}
    assert "Ghost Character" not in labels, "a character seen only in a draft is not published"
    assert "Nowhere" not in labels


# ------------------------------------------------------------------ story page rules


def test_story_pages_never_display_characters_locations_or_tags(site):
    """A story page carries only the story."""
    page = read(site / "stories" / "the-lighthouse" / "index.html")
    body = page.split('<article class="story"', 1)[1].split("</article>", 1)[0]

    for name in ("Mara Vance", "Elias Doyle", "Portsmouth", "epistolary"):
        assert name not in body, f"{name!r} must not appear on the story page itself"


# ------------------------------------------------------------------------ the feed


def test_feed_is_newest_published_first(site):
    page = read(site / "index.html")
    positions = [page.index(title) for title in ("The Lighthouse", "The Fog", "Letters Home")]
    assert positions == sorted(positions)


def test_feed_html_contains_every_story_regardless_of_filter(site):
    """The filter is a browser-side overlay over markup that already holds the whole
    collection. There is one feed document, so a reader arriving at
    `/?character=anything` with JavaScript off sees everything rather than nothing.
    """
    page = read(site / "index.html")
    for title in ("The Lighthouse", "The Fog", "Letters Home", "The Keeper", "Winter Crossing"):
        assert title in page

    assert 'id="feed-filter-banner"' in page and "hidden" in page, (
        "the filter banner starts hidden, so no-script readers never see a stale filter state"
    )


def test_feed_items_carry_filter_data_attributes(site):
    page = read(site / "index.html")
    assert 'data-characters="' in page
    assert 'data-locations="' in page
    assert "mara-vance" in page


# ----------------------------------------------------------------------- determinism


def test_two_builds_of_unchanged_sources_are_byte_identical(tmp_path, scratch_corpus):
    first, second = tmp_path / "a", tmp_path / "b"
    build_into(first, scratch_corpus)
    build_into(second, scratch_corpus)

    left = {p.relative_to(first).as_posix() for p in first.rglob("*") if p.is_file()}
    right = {p.relative_to(second).as_posix() for p in second.rglob("*") if p.is_file()}
    assert left == right

    mismatches = [
        rel for rel in sorted(left) if not filecmp.cmp(first / rel, second / rel, shallow=False)
    ]
    assert mismatches == [], f"non-deterministic output: {mismatches}"


# ------------------------------------------------------------------- stale output


def test_stale_output_is_removed(tmp_path, scratch_corpus):
    """A deleted or renamed story must leave no orphaned page behind."""
    out = tmp_path / "site"
    build_into(out, scratch_corpus)
    assert (out / "stories" / "the-fog").exists()

    (scratch_corpus / "stories" / "the-fog.md").unlink()
    build_into(out, scratch_corpus)

    assert not (out / "stories" / "the-fog").exists()
    assert "The Fog" not in read(out / "index.html")


def test_refuses_to_clear_a_directory_it_did_not_generate(tmp_path, scratch_corpus):
    """`--output` is user-supplied; a mistyped flag must not delete someone's files."""
    occupied = tmp_path / "not-ours"
    occupied.mkdir()
    (occupied / "important.txt").write_text("please do not delete me", encoding="utf-8")

    with pytest.raises(BuildError, match="refusing to clear"):
        build_into(occupied, scratch_corpus)

    assert (occupied / "important.txt").exists()


# -------------------------------------------------------------------- no leakage
#
# Private authoring material must reach neither the generated site nor any
# committed file.


def test_notes_and_descriptions_reach_neither_the_site_nor_a_committed_file(
    tmp_path, scratch_corpus
):
    from sunday.corpus import load_corpus
    from sunday.export import export_from_store, write_cast
    from sunday.store import Store

    note_text = "SECRET-NOTE-nobody-should-ever-read-this"
    description_text = "SECRET-DESCRIPTION-also-private"

    with Store.open(tmp_path / "store.db") as store:
        corpus = load_corpus(scratch_corpus / "stories")
        store.sync_subjects(corpus)
        mara = store.subject("character", "Mara Vance")
        store.add_note("subject", mara.id, note_text)
        store.set_profile(
            "character", "Mara Vance", description=description_text, display_name="Mara"
        )
        write_cast(scratch_corpus / "cast.yml", export_from_store(store))

    out = tmp_path / "site"
    build_into(out, scratch_corpus)

    searched = [*out.rglob("*"), *(scratch_corpus).rglob("*")]
    for path in searched:
        if not path.is_file() or path.suffix in {".db"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert note_text not in text, f"note text leaked into {path}"
        assert description_text not in text, f"description leaked into {path}"

    # The display name *is* exported — it labels a diagram node.
    assert "Mara" in (scratch_corpus / "cast.yml").read_text(encoding="utf-8")


# -------------------------------------------------------------------- resilience


def test_an_empty_corpus_builds_an_empty_but_valid_site(tmp_path):
    """A collection with no stories yet is a normal state, not an error."""
    corpus_dir = tmp_path / "empty"
    (corpus_dir / "stories").mkdir(parents=True)
    (corpus_dir / "sunday.yml").write_text("title: Nothing Yet\n", encoding="utf-8")

    out = tmp_path / "site"
    build_into(out, corpus_dir)

    assert (out / "index.html").exists()
    assert (out / "archive" / "index.html").exists()
    assert json.loads(read(out / "graph.json")) == {"nodes": [], "edges": []}
    assert "No stories published yet" in read(out / "archive" / "index.html")


def test_a_missing_settings_file_is_a_named_error(tmp_path):
    from sunday.settings import SettingsError

    corpus_dir = tmp_path / "no-settings"
    (corpus_dir / "stories").mkdir(parents=True)

    with pytest.raises(SettingsError, match="settings file not found"):
        build_into(tmp_path / "site", corpus_dir)


def test_the_site_builds_where_no_store_has_ever_existed(tmp_path, scratch_corpus):
    """Exactly what CI does on every push: no store exists."""
    assert not (scratch_corpus / ".sunday").exists()

    out = tmp_path / "site"
    build_into(out, scratch_corpus)

    assert (out / "index.html").exists()
    assert not (scratch_corpus / ".sunday").exists(), "the build must not create a store"


# ------------------------------------------------------------- the export boundary
#
# The generator reads committed files alone; it must not reach into the authoring
# store, which does not exist in CI at all.


def test_build_module_does_not_import_the_store():
    imported = module_identifiers(PACKAGE / "build.py").imports
    offending = {m for m in imported if "store" in m}
    assert offending == set(), f"build.py must not import the authoring store: {offending}"


def test_build_module_names_no_store_identifier():
    """Belt and braces: no *code* identifier mentions the store either.

    Deliberately AST-based rather than a text search — build.py's own docstring
    explains the boundary, and prose describing a rule must not be mistaken for
    breaking it. (`names_attrs_defs` excludes string constants for that reason.)
    """
    identifiers = module_identifiers(PACKAGE / "build.py").names_attrs_defs
    offending = {
        name
        for name in identifiers
        if "store" in name.lower() and "stories" not in name.lower()
    }
    assert offending == set(), f"build.py must not touch the authoring store: {offending}"
