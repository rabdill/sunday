# Phase 0 Research: Story Site Generator and Authoring Portal

Regenerated 2026-08-11 against the spec with character media removed. Decisions on Markdown,
frontmatter, SQLite, conflict detection, rename survival, the four-page site, tag management, and
export scope are unchanged from the previous pass and restated here; every decision about media
storage, image processing, and media safety is deleted — that work now lives entirely in
[002-character-media](../002-character-media/spec.md), to be re-researched when that spec is
picked up.

## Markdown rendering

- **Decision**: `markdown-it-py`, CommonMark defaults, no extensions enabled.
- **Rationale**: Spec-defined output matters because FR-016 demands byte-identical rebuilds. Pure
  Python, nothing enabled beyond what stories actually use (FR-004).
- **Alternatives**: `python-markdown` (less predictable across versions), `mistune` (speed
  irrelevant here), hand-rolling (no).

## Frontmatter parsing

- **Decision**: Split on `---` fences ourselves; `yaml.safe_load` the metadata block.
- **Rationale**: A dozen lines with a clear failure mode. A dependency to avoid writing them
  fails Constitution I, especially with PyYAML required regardless for settings and export.
- **Alternatives**: `python-frontmatter` (thin wrapper, not worth it); TOML via `tomllib` (splits
  the author's mental model across two syntaxes for no gain).

## Store technology

- **Decision**: SQLite via stdlib `sqlite3`, hand-written SQL, no ORM, no migration framework —
  `schema_version` plus a rebuild path.
- **Rationale**: The store is explicitly disposable (FR-040, FR-042), so "delete and rebuild" is
  a legitimate, cheap upgrade path a migration framework would exist to avoid. A handful of tables
  doesn't justify an ORM.
- **Alternatives**: SQLAlchemy + Alembic (disproportionate); pickled state (opaque, unqueryable).

## Conflict detection

- **Decision**: SHA-256 of the exact bytes the portal last wrote per story. Compare on load;
  divergence means an outside edit; present both, let the author choose.
- **Rationale**: Content hashing is exact and immune to the clock. Modification times are
  unreliable across editors and checkouts, and false conflicts on every `git checkout` would train
  the author to click through the prompt — worse than no detection.
- **Alternatives**: mtime/size comparison (the exact failure mode above); a filesystem watcher
  (dependency, background thread, races, no benefit at request-time granularity); file locking
  (hostile to the plain-text-editor workflow FR-005 protects).

## Rename survival for notes and relationships

- **Decision**: A `subjects` table gives every character and location a stable integer id. Notes
  and relationships reference that id, never the name string.
- **Rationale**: FR-047 and FR-050 require survival across rename. One indirection removes the
  whole class of "which of these three places do I need to update" bug.
- **Alternatives**: name-keyed rows with cascade updates (the bug farm this avoids); a UUID in
  frontmatter (leaks internal identity into files the author has to read).

## Tag management

- **Decision**: `review.py` and `writer.py` run identically over characters, locations, and tags.
  No new module. `cast.py` grows a tag-page branch reusing the story-listing logic and skipping
  everything character-specific.
- **Rationale**: `Name` (data-model.md) already carries `kind` as a plain enum value across all
  three cases — normalization, comparison, and slug derivation never branched on it. Extending
  duplicate detection, rename, and a listing page to tags (FR-030–032b, FR-053b) is a requirements
  widening onto code that was already generic, not a new subsystem.
- **What tags still don't get, and why**: no profile (FR-008b scopes profiles to character/
  location — a tag has no biography), no relationships (inherently character-to-character,
  FR-048), no diagram (the network diagram's nodes are characters and locations per FR-015, tags
  remain outside it), and — since character media never applied to tags in the first place —
  media was never a consideration for them either.
- **Data model consequence**: tags get no `subjects` row. That row exists to give notes,
  relationships, and (previously) media something stable to attach to across a rename; tags have
  none of those. A tag rename is a pure corpus-wide find-and-replace against the current files,
  computed fresh each time — nothing for a persistent id to protect.

## What gets exported, and what does not

- **Decision**: `cast.yml` carries stated relationships and display-name overrides. Nothing else.
- **Rationale**: FR-038a/b. With cast pages unpublished, no reader-facing page displays a
  description, so exporting one would place private writing in a committed file for nobody's
  benefit. The export should be exactly what the site consumes.
- **Consequence, unchanged by removing media**: a store rebuild recovers relationships and display
  names from `cast.yml`, but profile descriptions are store-only and lost with it. Accepted, per
  FR-042.

## Portal package split

- **Decision**: `portal/` is a package with one module per surface — stories, cast, notes,
  relationships, build. (Previously six modules, including `media_routes.py`; now five.)
- **Rationale**: The portal absorbed everything the site doesn't publish. A single module would
  carry several unrelated surfaces and be the largest file in the project by a wide margin.
  Splitting by surface keeps each readable without introducing a layered architecture nobody
  needs.
- **Alternatives**: one `portal.py` (unreadable at this size); models/services/views tiering
  (indirection for its own sake at this scale); Flask blueprints with separate template roots (the
  split is for humans, not URL mounting).

## Testing approach

- **Decision**: pytest over a fixture corpus including broken files, plus store and export tests.
  Two structural guards: `build.py` imports neither `store` (there is no `media` module left to
  guard against); the generated tree contains only the four page kinds.
- **Rationale**: Constitution III, extended to the boundary. The site's contents are a short,
  checkable list — worth asserting while short. Review/rename tests include a tag fixture
  alongside character/location ones, since FR-030–032b treats all three uniformly.

## What this pass removed, for the record

The previous planning pass (before this spec split off 002-character-media) contained decisions
titled "Media storage," "Image processing — reversed 2026-08-10," "Media safety," and export-scope
notes about media never crossing the boundary. All of that reasoning is deleted here, not because
it was wrong, but because it belongs to 002 now. Anyone picking up 002 should expect to redo this
research from scratch against that spec's own requirements — the storage-location and
image-processing decisions made for *this* spec's earlier draft are a reasonable starting point,
not a binding one.
