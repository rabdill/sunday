# Phase 1 Data Model

Two tiers. Regenerated 2026-08-11 with the `media` table and the media directory removed — that
material now belongs to [002-character-media](../002-character-media/spec.md).

- **Committed files** — `stories/*.md`, `sunday.yml`, `cast.yml`. The export boundary. The
  generator's only input.
- **Local store** — `.sunday/store.db`. Authoritative for authoring. Gitignored, rebuildable.

## Tier 1: In-memory shapes

### Story

| Field | Type | Required | Notes |
|---|---|---|---|
| `slug` | string | yes | Stable address (FR-003). |
| `title` | string | yes | Display title. |
| `published` | date | yes | Orders the feed. |
| `occurs` | partial date | no | In-world date; orders the archive. |
| `characters` | list of names | no | Verbatim. Drives the diagram and the feed filter — **not shown on the story page** (FR-010a). |
| `locations` | list of names | no | Verbatim. Same role. |
| `tags` | list of names | no | Managed identically to characters/locations for naming consistency; unpublished. |
| `draft` | bool | no, default false | Excluded from all output (FR-012). |
| `body` | Markdown | yes | Non-empty. |
| `extra` | mapping | derived | Unrecognized frontmatter keys, preserved on round-trip. |
| `source_path` | path | derived | For error messages. |

**Structural validation — fails the build (FR-017)**: frontmatter parses as a mapping; `slug`,
`title`, `published`, non-empty `body` present; `slug` matches `[a-z0-9-]+` and is unique
(collision names both files); dates well-formed; `draft` boolean if present.

**Not validated — editorial (FR-017a)**: name resemblance, single use, missing profile. Surfaced
in the portal; at most a build warning.

### Partial date (`occurs`)

| Form | Example | Sorts as | Displays as |
|---|---|---|---|
| Year | `1921` | 1921-01-01, precision=year | "1921" |
| Year-month | `1921-03` | 1921-03-01, precision=month | "March 1921" |
| Full | `1921-03-04` | 1921-03-04, precision=day | "4 March 1921" |

Archive sort key `(sort_date, precision_rank, published, slug)`. No `occurs` → excluded from the
chronology, grouped as undated (FR-023a).

### Name

Exists because a story names it (FR-008).

| Field | Type | Notes |
|---|---|---|
| `display` | string | Exactly as written. Never rewritten by the system. |
| `normalized` | string | Casefolded, whitespace-collapsed, punctuation-stripped. **Comparison only.** |
| `kind` | character \| location \| tag | Source frontmatter field. |
| `slug` | string | Used in filter query strings and diagram node ids. |

The `display`/`normalized` split enables duplicate detection without altering the author's
spelling. Mandatory test target.

**Identity is the exact spelling, not the normalized form.** The name index is keyed by
`(kind, display)`, so "epistolary" and "Epistolary" are two names. Keying by `normalized`
would collapse them into one and make a case-only typo structurally undetectable — which
would defeat User Story 4 entirely, and contradicts the spec's own framing that a typo
"silently produc[es] two characters where one was meant". `normalized` is a comparison
tool that review reaches for; it is never a name's identity.

Two distinct names whose `display` values slugify identically ("Café Verlaine" and "Cafe
Verlaine") receive a deterministic numeric suffix on the second and subsequent slug, so
they never collide on one URL and silently merge their story lists.

`review.py` and `writer.py` treat all three `kind` values identically for duplicate detection,
single-use flagging, and rename (FR-030–032b). What differs is what else a name can carry: only
`character` and `location` ever gain a `subjects` row (below); a `tag` never does, because
nothing in the store attaches to a tag.

## Tier 2: Store schema (`.sunday/store.db`)

SQLite, hand-written SQL. **Six tables** — the previous `media` table (a seventh) is gone.

### `meta`

`key` / `value`. Holds `schema_version`; an unrecognized version triggers rebuild.

### `stories`

| Column | Notes |
|---|---|
| `id` | Stable across slug renames; notes attach here. |
| `slug` | Unique. |
| `source_path` | Relative path. |
| `last_written_hash` | SHA-256 of the exact bytes the portal last wrote. |
| `last_written_text` | The exact text last written — the version a conflict offers to restore. |
| `last_written_at` | Informational. |

**Amended during implementation (2026-08-11).** This table originally held only the hash, on the
principle that story content should not be duplicated. That made FR-041 unimplementable: with
only a hash, the portal cannot show "both versions" or let the author *choose* — the disk copy
is the sole surviving version, so a conflict degrades into a notification. Retaining the last
written text restores the choice the requirement asks for.

The invariant it was protecting still holds. The portal writes the file on every save, so the
corpus on disk is never behind and no story exists only in the store; losing the store still
loses no fiction (FR-042). What is lost with it is the ability to *undo* an outside edit — a
superseded version, never the current one.

### `subjects`

Stable identity for characters and locations. What makes rename survival work.

| Column | Notes |
|---|---|
| `id` | Referenced by notes and relationships. |
| `kind` | `character` \| `location`. Deliberately excludes `tag` — see the Name section above. |
| `name` | Current name, matching what stories write. Unique per kind. |
| `display_name` | Optional override. **Exported** — the diagram labels nodes with it. |
| `description` | Markdown profile prose. **Not exported** (FR-038b); store-only. |
| `dismissed` | 1 = candidate declined; do not suggest again (FR-044). |

### `notes`

| Column | Notes |
|---|---|
| `id`, `target_kind` (`story`\|`subject`), `target_id`, `body`, `updated_at` | |

Never exported, never published (FR-046). Survives renames via id. Lost on store rebuild.

### `relationships`

| Column | Notes |
|---|---|
| `id`, `from_subject_id`, `to_subject_id`, `description`, `directed` | |

Maintained independently of stories (FR-049). Exported, so it survives store loss.

### `conflicts`

| Column | Notes |
|---|---|
| `story_id`, `detected_at`, `disk_hash` | A row means the file diverged from `last_written_hash`. |

## The export: `cast.yml`

Generated; never hand-edited (FR-039). Carries **only what the site consumes**:

| Exported | Why |
|---|---|
| Stated relationships | The diagram renders them (FR-052) |
| Display-name overrides | The diagram labels nodes with them |

| Not exported | Why |
|---|---|
| Profile descriptions | Nothing published displays them (FR-038b) |
| Notes | Must never reach readers (FR-046) |
| Dismissals | Private editorial decisions |

## Derived structures (generator only)

### Feed data

Each feed item carries its story's characters and locations as data attributes so
`feed-filter.js` can narrow the list from a query string. This is filter machinery, not displayed
content — story pages themselves show no names (FR-010a).

### Archive ordering

Published stories by in-world chronology, undated grouped separately. Replaces the timeline.

### Connection Graph

Derived, rebuildable, disposable. Serialized to `graph.json`.

- **Node**: one per character and location in at least one published story, plus any subject named
  in an exported relationship. Carries display label, kind, slug, story count, and the filtered
  feed URL it links to (FR-015a).
- **Edge**: two kinds, never merged (FR-051) — `co_appearance` (weighted by shared published
  stories) and `stated` (from `cast.yml`, with description and direction).
- Isolated nodes retained. Nodes and edges sorted; undirected endpoints canonically ordered.

### Review Findings

From `review.py`, consumed at different severity by each program (FR-017a, FR-032c).

| Finding | Trigger | Portal | Build |
|---|---|---|---|
| `probable_duplicate` | Same kind, identical normalized form or edit distance ≤ threshold | Offer rename | Warning |
| `single_use` | Used by exactly one story | Flag as likely typo | Silent |
| `orphaned_profile` | Profile whose name no story uses | Offer removal | Warning |
| `unprofiled_name` | No profile and not dismissed | Offer candidate | Silent |

`probable_duplicate` and `single_use` run over all three `Name.kind` values, tags included.
`orphaned_profile` and `unprofiled_name` are meaningless for tags, since tags have no profile to
be orphaned or a candidate for; both simply never fire for `kind == tag`.

None ever fails a build.

## Rebuild from files

| Recovered | From | Lost |
|---|---|---|
| Story rows, hashes | `stories/*.md` | — |
| Subjects | Names used across the corpus | — |
| Relationships, display names | `cast.yml` | — |
| — | — | **Notes** |
| — | — | **Profile descriptions** (not exported) |
| — | — | **Dismissals** |

No story text is ever at risk (FR-042, SC-011). The portal reports what could not be recovered
rather than rebuilding silently.
