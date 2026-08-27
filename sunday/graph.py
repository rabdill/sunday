"""The connection graph, and the archive's chronology.

Derived, rebuildable, disposable — everything here is computed from the corpus and
the `cast.yml` export on every build, and nothing is cached (Constitution II).

The one rule worth stating twice: a co-appearance and a stated relationship between
the same pair are **two edges, never merged** (FR-051). "These two people appear in
a story together" and "the author says they are siblings" are different claims, and
collapsing them would silently assert something nobody wrote.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Iterable

from .corpus import Corpus, Kind, Name, Story
from .export import CastExport

#: Kinds that become diagram nodes. Tags are managed in the portal but are not part
#: of the published world (FR-015).
NODE_KINDS: tuple[Kind, ...] = ("character", "location")


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    kind: str
    slug: str
    url: str
    stories: int

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "slug": self.slug,
            "url": self.url,
            "stories": self.stories,
        }


@dataclass(frozen=True)
class Edge:
    kind: str  # "co_appearance" | "stated"
    source: str
    target: str
    weight: int | None = None
    description: str | None = None
    directed: bool | None = None

    @property
    def sort_key(self) -> tuple[str, str, str]:
        return (self.kind, self.source, self.target)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": self.kind,
            "source": self.source,
            "target": self.target,
        }
        if self.kind == "co_appearance":
            payload["weight"] = self.weight
        else:
            payload["description"] = self.description or ""
            payload["directed"] = bool(self.directed)
        return payload


@dataclass(frozen=True)
class ConnectionGraph:
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "nodes": [n.to_json() for n in self.nodes],
            "edges": [e.to_json() for e in self.edges],
        }


def node_id(kind: str, slug: str) -> str:
    return f"{kind}:{slug}"


def node_url(kind: str, slug: str) -> str:
    """Where selecting this node takes the reader: the feed, narrowed (FR-015a)."""
    return f"/?{kind}={slug}"


# ------------------------------------------------------------------ graph building


def _published_names(corpus: Corpus, story: Story) -> list[Name]:
    """Every diagram-eligible name a story references, de-duplicated and ordered."""
    found: list[Name] = []
    for kind in NODE_KINDS:
        for display in story.names_of_kind(kind):
            name = corpus.name(kind, display)
            if name is not None and name not in found:
                found.append(name)
    return found


def build_graph(corpus: Corpus, cast: CastExport | None = None) -> ConnectionGraph:
    """Assemble the published connection graph.

    Nodes are characters and locations appearing in at least one *published* story,
    plus any subject named in an exported relationship — so a stated edge is never
    drawn to a node that does not exist. Isolated nodes are retained: a character in
    one story with no one else is still part of the world.
    """
    cast = cast or CastExport()
    published = corpus.published()

    # Story counts and co-appearance, from published stories only (FR-012).
    counts: dict[tuple[str, str], int] = {}
    pair_weights: dict[tuple[str, str], int] = {}
    display_for: dict[tuple[str, str], str] = {}

    for story in published:
        names = _published_names(corpus, story)
        for name in names:
            key = (name.kind, name.slug)
            counts[key] = counts.get(key, 0) + 1
            display_for[key] = name.display
        for left, right in combinations(sorted(names, key=lambda n: (n.kind, n.slug)), 2):
            a, b = node_id(left.kind, left.slug), node_id(right.kind, right.slug)
            pair = (a, b) if a <= b else (b, a)  # canonical, so a pair appears once
            pair_weights[pair] = pair_weights.get(pair, 0) + 1

    # Stated relationships may introduce subjects the published corpus never names.
    stated: list[Edge] = []
    for rel in cast.relationships:
        endpoints = []
        for display in (rel.from_name, rel.to_name):
            name = corpus.name("character", display) or corpus.name("location", display)
            if name is not None:
                key = (name.kind, name.slug)
                display_for.setdefault(key, name.display)
                counts.setdefault(key, 0)
                endpoints.append(node_id(name.kind, name.slug))
            else:
                from .corpus import slugify

                key = ("character", slugify(display))
                display_for.setdefault(key, display)
                counts.setdefault(key, 0)
                endpoints.append(node_id(*key))

        source, target = endpoints
        if not rel.directed and source > target:
            source, target = target, source
        stated.append(
            Edge(
                kind="stated",
                source=source,
                target=target,
                description=rel.description,
                directed=rel.directed,
            )
        )

    nodes = tuple(
        sorted(
            (
                Node(
                    id=node_id(kind, slug),
                    label=cast.label_for(display_for[(kind, slug)]),
                    kind=kind,
                    slug=slug,
                    url=node_url(kind, slug),
                    stories=count,
                )
                for (kind, slug), count in counts.items()
            ),
            key=lambda n: n.id,
        )
    )

    co_appearance = [
        Edge(kind="co_appearance", source=a, target=b, weight=w)
        for (a, b), w in pair_weights.items()
    ]

    edges = tuple(sorted([*co_appearance, *stated], key=lambda e: e.sort_key))
    return ConnectionGraph(nodes=nodes, edges=edges)


# ---------------------------------------------------------------------- the archive


def archive_order(corpus: Corpus) -> tuple[tuple[Story, ...], tuple[Story, ...]]:
    """Split published stories into in-world chronology and an undated group.

    A story with no `occurs` is not given a guessed position — it is set aside and
    listed separately (FR-023a). Ties inside the chronology break by publication
    date then slug, so repeated builds agree (FR-023).
    """
    published = corpus.published()
    dated = tuple(sorted((s for s in published if s.occurs), key=lambda s: s.archive_sort_key))
    undated = tuple(
        sorted((s for s in published if not s.occurs), key=lambda s: (s.published, s.slug), reverse=True)
    )
    return dated, undated


# ------------------------------------------------------------------ derived context


@dataclass(frozen=True)
class DerivedContext:
    """What the corpus itself says about a character (FR-054)."""

    locations: tuple[Name, ...]
    co_appearing: tuple[Name, ...]
    first_appearance: Story | None
    last_appearance: Story | None


def derived_context(corpus: Corpus, name: Name, *, include_drafts: bool = True) -> DerivedContext:
    """Compute a subject's context from the stories that reference it."""
    stories = corpus.stories_for(name, include_drafts=include_drafts)

    locations: list[Name] = []
    co_appearing: list[Name] = []
    for story in stories:
        for other_kind in NODE_KINDS:
            for display in story.names_of_kind(other_kind):
                other = corpus.name(other_kind, display)
                if other is None or other == name:
                    continue
                bucket = locations if other_kind == "location" else co_appearing
                if other not in bucket:
                    bucket.append(other)

    ordered = sorted(stories, key=lambda s: (s.published, s.slug))
    return DerivedContext(
        locations=tuple(sorted(locations, key=lambda n: n.normalized)),
        co_appearing=tuple(sorted(co_appearing, key=lambda n: n.normalized)),
        first_appearance=ordered[0] if ordered else None,
        last_appearance=ordered[-1] if ordered else None,
    )
