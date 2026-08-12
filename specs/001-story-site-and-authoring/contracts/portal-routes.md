# Contract: Authoring Portal Routes

Local only, `127.0.0.1`, single author. Holds everything the published site doesn't: full cast
pages, notes, and relationships.

## Routes

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Dashboard: recent stories, conflicts, review findings, candidate profiles |
| GET | `/stories/` | Every story, drafts and conflicts marked |
| GET | `/stories/new`, `GET /stories/<slug>/edit` | Story forms |
| POST | `/stories/<slug>` | Save: write file, update store, re-export if needed |
| GET/POST | `/stories/<slug>/conflict` | View and resolve a divergence |
| GET | `/cast/` | Every name: kind, story count, profile state, findings |
| GET | `/cast/<kind>/<slug>` | **The cast page** — see below |
| POST | `/cast/<kind>/<slug>/profile` | Create or edit a profile |
| POST | `/cast/<kind>/<slug>/dismiss` | Decline a candidate; remembered |
| POST | `/cast/<kind>/<slug>/rename` | Rename across the corpus |
| POST | `/notes/`, `POST /notes/<id>` | Attach, edit, delete a note |
| GET | `/relationships/` | Every recorded relationship |
| POST | `/relationships/`, `POST /relationships/<id>` | Record, edit, delete |
| GET | `/review/` | All findings in one place |
| POST | `/build` | Run a local build; report in-browser |
| GET | `/build/output` | Browse the most recent local build |

## The cast page — `GET /cast/<kind>/<slug>`

Shape depends on `kind`.

**For `character` and `location`**, assembles:

| Section | Source | FR |
|---|---|---|
| Stories | Corpus, publication order, newest first, drafts marked | FR-053a |
| Derived context | Locations appeared in, co-appearing characters, first/last appearance | FR-054 |
| Stated relationships | Store, each linking to the other character | FR-055 |
| Per-character diagram | Co-appearances + relationships, centred on this subject | FR-056 |
| Profile | Store — description and display name | — |
| Notes | Store | FR-045 |

Locations get every section except relationships and the diagram's stated edges (relationships
are character-to-character).

**For `tag`**, assembles only:

| Section | Source | FR |
|---|---|---|
| Stories | Corpus, publication order, newest first, drafts marked | FR-053a, FR-053b |

No derived context, no relationships, no diagram, no profile, no notes — none of those concepts
apply to a tag.

## Save contract (stories)

File write, store update with new hash, `cast.yml` re-export if relationships or display names
changed. Unrecognized frontmatter keys preserved. Missing required fields block the save with a
specific message. Never blocked by a naming finding.

## Conflict contract

Content-hash comparison against `last_written_hash`; clean, diverged, untracked, or missing; both
versions shown on divergence; neither side overwritten without the author's choice; detection by
hash, not mtime.

## Review contract

`probable_duplicate` and `single_use` run over characters, locations, and tags alike (FR-032,
FR-032b). `orphaned_profile` and `unprofiled_name` remain character/location-only, since a tag
never has a profile to be orphaned or a candidate for. All findings are non-blocking, all shared
with the build at lower severity.

## Candidate profiles

Computed for any unprofiled, undismissed name; accept writes to the store; dismiss persists and
does not resurface; accepted profiles visually distinct.

## Notes and relationships

Notes attach to a story, character, or location; never exported, never published, survive renames
(FR-045–047). Relationships are character-to-character, maintained independently of what stories
state, exported to `cast.yml`, and drive the per-character diagram on the cast page as well as the
published one.

## Rename contract

For **character or location**: rewrites every story, updates the subject row, re-exports
`cast.yml`. Notes and relationships follow the subject id and are untouched by the rename. Updates
`last_written_hash` for every rewritten file so the rename never manufactures its own conflicts.

For **tag**: rewrites every story referencing the old name; there is no subject row to update and
no `cast.yml` re-export, since a tag's rename has no store-side state at all. File hashes are
still updated so the rename never manufactures its own conflicts.

Both cases report how many files changed and leave zero occurrences of the old name anywhere in
the corpus (SC-010).

## Local build

`POST /build` runs the same code path as `sunday build`, reading committed files only. Output
matches what CI would produce from the same sources.

## What the portal does not do

- No git operations.
- No deploying.
- No revision history, no autosave.
- Never part of the published site; the site is readable if the portal never runs.
- No accounts, sessions, or multi-user support.
- **No image handling of any kind.** Character media was split into
  [002-character-media](../../002-character-media/spec.md); this portal has no upload route, no
  image storage, and no image-processing dependency.
