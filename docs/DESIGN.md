# Sunday — design notes

Why the system is shaped the way it is. For how to work in the code, see
[`CLAUDE.md`](../CLAUDE.md); for the original requirements, see [`specs/`](../specs/)
(historical). Where this document and the specs disagree, this document and the code
win.

## Guiding principles

Three principles govern the project (the "constitution" the specs refer to; its text
is summarized here):

1. **Simplicity / YAGNI.** Every dependency must justify itself. Frontmatter
   splitting, the store's SQL, and the CLI are hand-written rather than pulling in a
   library. Deliberately *not* adopted: an ORM, a migration framework, a CSS
   framework, a task runner, file-watching, a build cache. The one heavy dependency,
   Cytoscape.js, exists solely for the network diagram.
2. **Stories are files.** The corpus on disk is always the complete, authoritative
   collection. Deleting everything but the committed files loses no fiction. The
   store holds only what no file represents.
3. **Test the parsing and the links.** Coverage concentrates where silent corruption
   is possible: frontmatter parsing, name normalization, the connection graph,
   conflict detection, and the export boundary.

## Two programs, one boundary

The generator and the portal share the corpus loader but nothing else. The generator
**cannot** read the store — a test asserts `build.py` imports no store identifier —
because the published site must build in CI, where no store exists. Anything the
portal authors that the site needs must therefore cross as a committed file. That
file is `cast.yml`, and it carries only what the diagram consumes: stated
relationships and display-name overrides.

Profile descriptions and notes deliberately do **not** cross. Nothing on the
published site shows a character biography, so exporting one would place private
writing into a committed file for no reader's benefit. `cast.yml` is generated;
hand edits are overwritten on the next portal save.

## Files and ownership

| Path | Owner | Committed |
|---|---|---|
| `stories/*.md` | Shared — you and the portal both write here | Yes |
| `sunday.yml` | You. The portal never rewrites it | Yes |
| `cast.yml` | The portal. Generated; do not hand-edit | Yes |
| `.sunday/store.db` | The portal | No — gitignored |
| `site/` | The generator | No — gitignored |

`sunday.yml` is hand-owned and `cast.yml` is generated, and they are separate files
on purpose: a file that is partly hand-owned and partly generated needs a merge
strategy, and merge strategies are where sync bugs live.

## Names: compared normalized, stored verbatim

A character, location, or tag exists because a story names it — never because it was
declared. Adding a story that introduces new names changes no other file.

One distinct spelling is one name. "epistolary" and "Epistolary" are two names, not
one, because a typo silently creates a second character rather than an error, and
catching that pair is the whole point of the review tools. `normalize_name` (casefold,
strip accents and punctuation, collapse whitespace) exists only so review can
recognize two spellings as *probably* the same; it is never a name's identity, and
the display form the author typed is never rewritten by the system.

Distinct names that would slugify identically get a deterministic numeric suffix, so
two names never collide on one URL (which would silently merge their stories).

## Editorial review is never fatal

A misspelled name is valid input. Nothing can prevent it at write time, so detection
after the fact — near-duplicate spellings, single-use names, profiles describing an
unused name — lives in the portal, ahead of the build, where the author is already
working. None of it blocks a build: a publication step that refused to publish over a
spelling question would be the wrong shape for this system. `sunday build --strict`
opts into the opposite; CI does not use it.

## Conflict detection: content hash, detect-and-adopt

Editing a story in a plain text editor is a supported workflow, so the portal reloads
the corpus from disk on every request and must reconcile files it did not write.

- Divergence is detected by **content hash, not modification time** — a `git checkout`
  rewrites timestamps on every file, and an author trained to click through a false
  conflict is worse off than one who never sees one.
- When a story on disk differs from what the portal last wrote, editing is **blocked**
  until the author acknowledges it. The portal never silently overwrites an outside
  edit. Acknowledging **adopts the on-disk version**; deeper history lives in git.

The store keeps only the hash of the last write, never the story body — so no story
ever exists only in the store.

## The authoring store

SQLite, hand-written SQL, five tables (`meta`, `stories`, `subjects`, `notes`,
`relationships`). It is gitignored and rebuildable from committed files, which is the
trade that keeps a binary out of git. Because it is reconstructible, schema changes
**rebuild rather than migrate**: bump `SCHEMA_VERSION` and the store is discarded and
rebuilt on next open.

Characters and locations get a `subjects` row with a stable integer id, so notes and
relationships follow the id across a rename. Tags get no subject row — they have no
profile, notes, or relationships, so a row for one would be state with no consumer.

A rebuild recovers stories, subjects, relationships, and display names from the
committed files. It **cannot** recover notes, dismissed suggestions, or profile
descriptions — none is exported — and the rebuild report says so rather than letting
the author find out later. No story text is ever at risk: the portal writes the file
on every save.

## Determinism and partial dates

The generator sorts every collection before emitting it, with documented tie-breaks
(publication date then slug), so repeated builds agree. Markdown is CommonMark with
no extensions, for the same reason.

In-world dates tolerate imprecision: `1921`, `1921-03`, and `1921-03-04` are all
first-class and displayed at the precision the author gave, never padded into a
fabricated day. Padding exists only inside the sort key, for ordering. Undated
stories are set aside in the archive rather than given a guessed position.

## Decisions log — removed before 1.0

The following were removed as complexity that had lost (or never earned) its
justification. Recorded here so the reasoning is not lost:

- **Write-only `conflicts` table** — persisted on every scan, deleted on every write,
  but never read; divergence is recomputed live from hashes. Pure vestige.
- **`last_written_text`** — an in-DB copy of every story body, kept so the conflict
  screen could offer "restore what the portal last wrote." It duplicated the whole
  corpus into the store and edged into the revision-history role that belongs to git.
  Cut in favor of detect-and-adopt (above).
- **Per-character portal diagram** (`subject_graph`) — a mini network drawn on each
  cast page, largely redundant with the text neighbor-list already on that page. The
  published `/network/` diagram is unaffected.
- **`has_*` blueprint flags** — chrome that showed nav/sections only for "wired-up"
  surfaces, from a phased rollout that is complete. All blueprints always register, so
  every guard was permanently true.
- **`stories.last_written_at`, `render.format_occurs`, `render.render_inline`,
  `corpus.iter_story_files`** — written-but-never-read state and unreferenced
  functions.

## Deferred, not dropped

Character portraits and moodboards are specified in
[`specs/002-character-media`](../specs/002-character-media/spec.md) and deliberately
left out of 1.0, so it ships without an image-processing dependency. No code, schema,
or configuration for that feature exists yet.
