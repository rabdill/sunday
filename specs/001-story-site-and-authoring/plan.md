# Implementation Plan: Story Site Generator and Authoring Portal

**Branch**: `001-story-site-and-authoring` | **Date**: 2026-08-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-story-site-and-authoring/spec.md`

**Supersedes**: the prior plan, written when this spec still included character portraits and
moodboards. On 2026-08-11 that material was split out into
[002-character-media](../002-character-media/spec.md) as a deferred stub, and this document is
regenerated against the spec with it removed — rather than trying to surgically undo the
media-related edits from two planning passes ago, which had themselves just reversed an
architectural decision to accommodate it.

## Summary

Sunday remains two programs separated by an export boundary made of files. A **generator** reads
committed files and emits exactly four kinds of published page — a homepage feed, a network
diagram, an archive, and a page per story. A local **authoring portal**, a Flask app over a
SQLite store, is where the author writes, reviews naming consistency across characters, locations,
and tags, records relationships, and keeps private notes.

**What changed this pass, concretely**: no image handling anywhere. No upload route, no image
library, no media directory, no manifest, no HEIC conversion, no resize option. The portal's
richest surface — the cast page — now gathers story list, derived context, relationships, and
notes; nothing about pictures. This is a genuine simplification, not a deferral in name only: the
dependency list shrinks by one real (and previously reversed-into, then reversed-out-of) addition,
`portal/` loses a whole route module, and the store schema loses a table.

The core architectural shape is unchanged: files are the export boundary, the store is
authoritative for authoring and disposable, the build never reads the store, and tags now share
the same naming-consistency machinery as characters and locations (added the same day media was
removed, and unaffected by removing it).

## Technical Context

**Language/Version**: Python 3.11+

**Primary Dependencies**: Flask (portal), Jinja2 (both), PyYAML (frontmatter, settings, export),
markdown-it-py (CommonMark). `sqlite3` is stdlib. One vendored client-side library, Cytoscape.js,
used by the published diagram and the portal's per-character diagram. **No image-processing
library.** That dependency was added in the previous planning pass specifically to support
portraits and moodboards and is removed along with them.

**Storage**: Two tiers, not three. *Committed files* — `stories/*.md`, `sunday.yml`, `cast.yml` —
are the export boundary and the generator's only input. *Local store* — `.sunday/store.db`,
SQLite, gitignored — is authoritative for authoring. There is no media directory.

**Testing**: pytest. Constitution III mandates parsing, linking, and detection coverage; the plan
extends that to conflict detection and export round-trip. No media test module.

**Target Platform**: Generator — any Python 3.11+ environment including CI runners. Portal — the
author's machine, bound to `127.0.0.1`.

**Project Type**: Small static site generator + local companion web app.

**Performance Goals**: Full build under 60 seconds (SC-002); realistically seconds.

**Constraints**: Byte-identical output for identical input (FR-016). Every published story
reachable without JavaScript via feed and archive (FR-021); the diagram and the feed filter are
the only scripted features (FR-021a/b). The generator MUST NOT read the store (FR-007). Losing the
store MUST NOT lose story text or exported relationships/display names (FR-042).

**Scale/Scope**: A bounded personal collection. Whole corpus in memory; no pagination, no search
index, no incremental rebuild.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. Simplicity / YAGNI (NON-NEGOTIABLE)

| Dependency | Why | Simpler alternative rejected because |
|---|---|---|
| Flask | Constitutionally fixed for the portal | — |
| Jinja2 | Templating for site and portal | Ships with Flask |
| PyYAML | Frontmatter, settings, export | Hand-rolling YAML is a known trap |
| markdown-it-py | CommonMark rendering | Spec-defined output matters for byte-identical rebuilds |
| Cytoscape.js (vendored) | Both diagrams | The constitution's acknowledged JS exception |
| `sqlite3` | The store | Stdlib. No dependency added. |

Explicitly not adopted: no ORM, no migration framework, no image library (removed this pass — see
below), no upload library, no `python-frontmatter`, no build cache, no CSS framework, no task
runner, no `watchdog`.

**A dependency added, then removed, in successive planning passes.** Two passes ago this table
carried Pillow + `pillow-heif` to support HEIC conversion and resize-on-upload. That entire
feature is now out of this spec. Recorded here rather than silently dropped, because it's the
clearest evidence Constitution I's "justify every dependency" test actually functions: the
requirement changed, the dependency followed it, twice.

**Tags remain fully managed, unaffected by this change.** `review.py` and `writer.py` are still
generic over `Name.kind` across character/location/tag — that decision has nothing to do with
media and is untouched.

Cut and staying cut: revision history, autosave, live preview, per-name generated pages, image
handling of any kind.

**Gate: PASS.**

### II. Stories Are Files

- Corpus on disk always complete and current; portal writes Markdown on every save. ✅
- Deleting everything but committed files costs no fiction. ✅
- Published site derives from committed files alone — `build.py` never imports `store.py`; a test
  asserts it. ✅
- Store limited to material no story file represents: profiles, notes, relationships, dismissal
  decisions. ✅
- Export carries only what the site consumes: stated relationships and display-name overrides
  (FR-038a/b). Profile descriptions stay private. ✅

**Gate: PASS.**

### III. Test the Parsing and the Links

Mandatory targets: `corpus.py` (parsing, required fields, failure modes), normalization
(compare-normalized, store-verbatim, now exercised across character/location/tag fixtures alike),
`graph.py` (linking, archive ordering, tie-breaks, undated), `review.py` (near-duplicate, orphan
detection — tag fixtures included), `store.py` (conflict detection), `export.py` (round-trip,
rebuild). **No `test_media.py`** — there is nothing left for it to test.

**Gate: PASS.**

### Technology Constraints (two programs)

- Generator emits static files; readers depend on no running process. ✅
- Portal is local-only, not deployed; site readable if the portal never runs. ✅
- **Standing note, carried from the previous plan and still accurate**: the constitution's
  "diagram is the single JavaScript exception" reading is amended in practice by the feed filter
  (FR-021a/b), a deliberate spec-level trade recorded there and not revisited by this pass.

**Gate: PASS.**

## Project Structure

### Documentation (this feature)

```text
specs/001-story-site-and-authoring/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/            # Phase 1 output
│   ├── file-formats.md      # stories/*.md, sunday.yml, cast.yml
│   ├── cli.md               # build | portal | store rebuild
│   ├── site-structure.md    # The four page kinds, filter, graph.json
│   └── portal-routes.md     # Local HTTP surface
├── checklists/requirements.md
└── tasks.md             # Owned by /speckit-tasks; not regenerated by this pass
```

### Source Code (repository root)

```text
stories/                     # Corpus. Committed. Hand-editable.
sunday.yml                   # Settings. Committed. Hand-owned.
cast.yml                     # Relationships + display names. Committed. GENERATED.
.sunday/store.db             # SQLite store. Gitignored.

sunday/
├── __init__.py
├── cli.py                   # argparse: build | portal | store rebuild
├── settings.py              # Load sunday.yml
├── corpus.py                # Frontmatter parsing, Story model, corpus loading
├── render.py                # Markdown → HTML, date display
├── graph.py                 # Name index, connection graph, archive ordering
├── review.py                # Near-duplicate, orphan, unprofiled, single-use detection —
                              #   runs uniformly over characters, locations, AND tags
├── build.py                 # Corpus + cast.yml → four page kinds.  NO store
├── store.py                 # SQLite: schema, conflicts, profiles, notes, relationships
├── export.py                # Store → cast.yml;  cast.yml → store
├── writer.py                # Atomic story writes, corpus-wide rename (character, location,
                              #   or tag — the rename logic does not distinguish kinds)
├── portal/                  # A package, split by surface
│   ├── __init__.py          # Flask app factory, startup checks, conflict scan
│   ├── stories.py           # Write/edit routes, conflict resolution
│   ├── cast.py              # Character/location pages (context, profiles, candidates,
│   │                        #   diagram) AND tag pages (listing only); rename and review
│   │                        #   span all three kinds
│   ├── notes.py             # Notes routes
│   ├── relationships.py     # Relationship routes
│   └── build_routes.py      # Local build trigger and output browsing
├── templates/
│   ├── site/                # base, index (feed), story, archive, network
│   └── portal/              # base, dashboard, story_form, conflict, cast, review, …
└── static/
    ├── site.css
    ├── feed-filter.js       # Narrow the feed from a query string
    ├── network.js           # Shared by the published and portal diagrams
    └── vendor/cytoscape.min.js

tests/
├── test_corpus.py           # MANDATORY
├── test_graph.py            # MANDATORY
├── test_review.py           # MANDATORY — fixtures include tag near-duplicates
├── test_store.py            # MANDATORY — conflict detection
├── test_export.py           # MANDATORY — round-trip, rebuild
├── test_build.py            # Determinism, draft exclusion, boundary guard, page inventory
├── test_writer.py           # Round-trip, rename
└── fixtures/

site/                        # Generated. Gitignored.
.github/workflows/build.yml
```

**What's gone from the previous structure**: `sunday/media.py`, `sunday/portal/media_routes.py`,
`tests/test_media.py`, `.sunday/media/` and its manifest, and every media-format asset. The
`media` table drops out of the store schema (data-model.md). `portal/cast.py` no longer serves a
portrait/moodboard section; its character-page assembly is shorter than it was two passes ago.

**Structure Decision**: The generator's shape is unchanged — four page kinds, no store import.
The portal package retains its per-surface split, now with one fewer module. Tags still needed no
new module (`review.py`/`writer.py` were already generic over `Name.kind`); that reasoning from
the prior pass stands untouched by this one.

## Post-Design Constitution Re-Check

Re-evaluated after Phase 1 ([research.md](./research.md), [data-model.md](./data-model.md),
[contracts/](./contracts/), [quickstart.md](./quickstart.md)).

**I. Simplicity — PASS, and simpler than either prior pass.** One dependency removed entirely
(the reversed-then-re-reversed image library), one module removed (`media.py`), one route file
removed (`portal/media_routes.py`), one store table removed (`media`), one mandatory test module
removed (`test_media.py`). Nothing new was added to compensate — this pass is a pure subtraction.

**II. Stories Are Files — PASS.** Unaffected by the removal; the boundary was never about media
specifically.

**III. Test the Parsing and the Links — PASS.** Five mandatory test modules, down from six.

**Two programs — PASS.** Unaffected.

**No violations. Complexity Tracking empty.**

## Complexity Tracking

> No constitutional violations. Table intentionally empty.
