"""The connection graph and the archive's chronology.

The character/location graph is exactly where a filtering bug that drops a story
from a character's page is invisible — nothing errors, the reader simply never
sees it.
"""

from __future__ import annotations

import pytest

from sunday.export import CastExport, RelationshipEntry
from sunday.graph import archive_order, build_graph, derived_context, node_id


@pytest.fixture
def graph(corpus):
    return build_graph(corpus)


def edges_of(graph, kind):
    return [e for e in graph.edges if e.kind == kind]


def node_ids(graph):
    return {n.id for n in graph.nodes}


# ------------------------------------------------------------------------- nodes


def test_nodes_cover_published_characters_and_locations(graph):
    ids = node_ids(graph)
    assert "character:mara-vance" in ids
    assert "location:portsmouth" in ids


def test_draft_only_names_are_absent(graph):
    """A character seen only in an unpublished story is not part of the world yet."""
    ids = node_ids(graph)
    assert "character:ghost-character" not in ids
    assert "location:nowhere" not in ids


def test_tags_are_not_nodes(graph):
    """Tags are managed in the portal but are not part of the published world."""
    assert not any(n.kind == "tag" for n in graph.nodes)


def test_isolated_nodes_are_retained(corpus):
    """A character who shares no story with anyone is still shown."""
    graph = build_graph(corpus)
    silas = next(n for n in graph.nodes if n.slug == "silas-thorne")
    assert silas.stories == 1

    touching = [e for e in graph.edges if silas.id in (e.source, e.target)]
    co = [e for e in touching if e.kind == "co_appearance"]
    assert co, "Silas shares his story with a location, so he is not orphaned"


def test_node_story_counts_exclude_drafts(graph):
    mara = next(n for n in graph.nodes if n.slug == "mara-vance")
    assert mara.stories == 3, "four stories reference her, but one is a draft"


def test_node_urls_point_at_the_filtered_feed(graph):
    """Selecting a node takes the reader to the feed, narrowed."""
    mara = next(n for n in graph.nodes if n.slug == "mara-vance")
    assert mara.url == "/?character=mara-vance"

    portsmouth = next(n for n in graph.nodes if n.slug == "portsmouth")
    assert portsmouth.url == "/?location=portsmouth"


# ------------------------------------------------------------------------- edges


def test_co_appearance_edges_are_weighted_by_shared_stories(graph):
    mara = node_id("character", "mara-vance")
    portsmouth = node_id("location", "portsmouth")
    edge = next(
        e
        for e in edges_of(graph, "co_appearance")
        if {e.source, e.target} == {mara, portsmouth}
    )
    assert edge.weight == 2, "Mara and Portsmouth share two published stories"


def test_a_pair_produces_one_co_appearance_edge_not_two(graph):
    """Endpoints are stored canonically, so an undirected pair appears once."""
    pairs = [frozenset({e.source, e.target}) for e in edges_of(graph, "co_appearance")]
    assert len(pairs) == len(set(pairs))


def test_stated_and_co_appearance_between_one_pair_stay_two_edges(corpus):
    """The author's claim and the filing's implication are different claims."""
    cast = CastExport(
        relationships=(
            RelationshipEntry(
                from_name="Mara Vance", to_name="Elias Doyle", description="sister"
            ),
        )
    )
    graph = build_graph(corpus, cast)

    pair = {node_id("character", "mara-vance"), node_id("character", "elias-doyle")}
    matching = [e for e in graph.edges if {e.source, e.target} == pair]

    kinds = sorted(e.kind for e in matching)
    assert kinds == ["co_appearance", "stated"], "both survive, neither absorbs the other"


def test_a_stated_edge_connects_characters_who_share_no_story(corpus):
    """The diagram reflects the world, not only the filing."""
    cast = CastExport(
        relationships=(
            RelationshipEntry(
                from_name="Silas Thorne", to_name="Elias Doyle", description="rival"
            ),
        )
    )
    graph = build_graph(corpus, cast)

    pair = {node_id("character", "silas-thorne"), node_id("character", "elias-doyle")}
    stated = [e for e in graph.edges if e.kind == "stated" and {e.source, e.target} == pair]
    assert len(stated) == 1
    assert stated[0].description == "rival"

    co = [e for e in graph.edges if e.kind == "co_appearance" and {e.source, e.target} == pair]
    assert co == [], "they genuinely share no story"


def test_a_relationship_naming_an_unknown_subject_still_gets_a_node(corpus):
    """A stated edge must never be drawn to a node that does not exist."""
    cast = CastExport(
        relationships=(
            RelationshipEntry(from_name="Mara Vance", to_name="Someone Unwritten"),
        )
    )
    graph = build_graph(corpus, cast)
    assert "character:someone-unwritten" in node_ids(graph)


def test_display_name_overrides_relabel_nodes(corpus):
    cast = CastExport(display_names={"Elias Doyle": "Doyle"})
    graph = build_graph(corpus, cast)
    elias = next(n for n in graph.nodes if n.slug == "elias-doyle")
    assert elias.label == "Doyle"


def test_a_stated_edge_survives_a_real_export_round_trip(scratch_corpus, tmp_path):
    """End to end, sourced from a `cast.yml` the portal actually wrote."""
    from sunday.corpus import load_corpus
    from sunday.export import export_from_store, load_cast, write_cast
    from sunday.store import Store

    corpus = load_corpus(scratch_corpus / "stories")
    cast_path = scratch_corpus / "cast.yml"

    with Store.open(tmp_path / "store.db") as store:
        store.sync_subjects(corpus)
        silas = store.subject("character", "Silas Thorne")
        elias = store.subject("character", "Elias Doyle")
        store.add_relationship(silas.id, elias.id, "rival", True)
        write_cast(cast_path, export_from_store(store))

    graph = build_graph(corpus, load_cast(cast_path))
    pair = {node_id("character", "silas-thorne"), node_id("character", "elias-doyle")}
    stated = [e for e in graph.edges if e.kind == "stated" and {e.source, e.target} == pair]

    assert len(stated) == 1
    assert stated[0].description == "rival"
    assert stated[0].directed is True


# -------------------------------------------------------------------- determinism


def test_nodes_and_edges_are_deterministically_ordered(corpus):
    cast = CastExport(
        relationships=(RelationshipEntry(from_name="Mara Vance", to_name="Elias Doyle"),)
    )
    first = build_graph(corpus, cast)
    second = build_graph(corpus, cast)

    assert [n.id for n in first.nodes] == [n.id for n in second.nodes]
    assert [e.sort_key for e in first.edges] == [e.sort_key for e in second.edges]
    assert [n.id for n in first.nodes] == sorted(n.id for n in first.nodes)


# ------------------------------------------------------------------- the archive


def test_archive_orders_by_in_world_chronology_not_publication(corpus):
    dated, _ = archive_order(corpus)
    assert [s.slug for s in dated] == [
        "winter-crossing",   # 1919
        "the-fog",           # 1921
        "the-lighthouse",    # 1921-03
        "the-second-letter", # 1922-06-14, published earlier
        "letters-home",      # 1922-06-14, published later
    ]


def test_undated_stories_are_set_aside_not_guessed_into_place(corpus):
    """No fabricated position for a story the author has not placed."""
    dated, undated = archive_order(corpus)
    assert [s.slug for s in undated] == ["the-keeper"]
    assert all(s.occurs is not None for s in dated)


def test_archive_excludes_drafts(corpus):
    dated, undated = archive_order(corpus)
    assert "unfinished" not in {s.slug for s in (*dated, *undated)}


# -------------------------------------------------------------- derived context


def test_derived_context_reports_locations_and_co_appearances(corpus):
    """The portal's cast page is built from this."""
    mara = corpus.name("character", "Mara Vance")
    context = derived_context(corpus, mara)

    assert "Portsmouth" in {n.display for n in context.locations}
    assert "Elias Doyle" in {n.display for n in context.co_appearing}
    assert mara not in context.co_appearing, "a character does not co-appear with herself"


def test_derived_context_reports_first_and_last_appearance(corpus):
    mara = corpus.name("character", "Mara Vance")
    context = derived_context(corpus, mara, include_drafts=False)

    assert context.first_appearance.slug == "the-keeper"      # published 2026-07-10
    assert context.last_appearance.slug == "the-lighthouse"   # published 2026-08-04
