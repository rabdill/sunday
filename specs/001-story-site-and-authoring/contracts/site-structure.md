# Contract: Generated Site Structure

The published site is small and enumerable. Four page kinds, and the build must produce nothing
else (FR-009a, SC-017).

## URL layout

| URL | Contents |
|---|---|
| `/` | The feed: every published story, newest first, filterable by `?character=<slug>` or `?location=<slug>` |
| `/network/` | The diagram, plus `graph.json` |
| `/archive/` | Every published story in in-world chronology, undated stories in a separate group |
| `/stories/<slug>/` | Full rendered text, title, both dates. **No characters, locations, or tags shown.** |
| `/graph.json` | Machine-readable graph data |
| `/site.css`, `/feed-filter.js`, `/network.js`, `/vendor/cytoscape.min.js` | Static assets |

**No other page exists.** No `/characters/`, no `/locations/`, no `/tags/` — that material lives
entirely in the portal.

## The feed and its filter

- Every published story is a list item, annotated with its characters and locations as data
  attributes so `feed-filter.js` can narrow the list from a query string (FR-011a).
- **With JavaScript disabled, the feed shows the complete unfiltered collection** (FR-011b).
- Clearing the filter returns to the full list without leaving the page.
- A filter naming a character with no published stories yields an empty (not broken) result.

## The diagram

- Nodes are characters and locations in at least one published story, plus any subject named in
  an exported relationship.
- Selecting a node navigates to `/?character=<slug>` or `/?location=<slug>` (FR-015a).
- With JavaScript disabled, the page states plainly that the diagram needs JavaScript and links to
  `/` and `/archive/` (FR-022).

## The archive

- Fully usable without JavaScript (FR-014a).
- Chronological section by `occurs`, then an undated section.

## `graph.json`

```json
{
  "nodes": [
    { "id": "character:mara-vance", "label": "Mara Vance", "kind": "character",
      "slug": "mara-vance", "url": "/?character=mara-vance", "stories": 4 }
  ],
  "edges": [
    { "kind": "co_appearance", "source": "character:mara-vance",
      "target": "location:portsmouth", "weight": 3 },
    { "kind": "stated", "source": "character:mara-vance",
      "target": "character:elias-doyle", "description": "sister", "directed": false }
  ]
}
```

`url` points at the feed filter. `label` uses the `display_name` override from `cast.yml` when
present.

## Guarantees

- **Drafts appear nowhere** — feed, archive, filter data, graph, or their own URL.
- **No authoring material leaks** — no description or note in any generated file (FR-046,
  SC-014, SC-018).
- **Every published story is reachable without JavaScript**, through the feed and the archive
  (FR-021). The diagram and the feed filter are the only scripted features (FR-021a), and neither
  is the only route to a story (FR-021b).
- **Story pages carry only the story** (FR-010a).
- **The site builds with no store present** (SC-012).
- **Rebuilds are byte-identical.**
- **The generated tree contains no page beyond the four kinds above** — tested directly.
