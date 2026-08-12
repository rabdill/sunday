---

description: "Task list for Story Site Generator and Authoring Portal"
---

# Tasks: Story Site Generator and Authoring Portal

**Input**: Design documents from `/specs/001-story-site-and-authoring/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Supersedes**: the prior task list, generated when this spec still included character portraits
and moodboards. That material was split into
[002-character-media](../002-character-media/spec.md) on 2026-08-11, and this list is regenerated
against the media-free spec and plan — it is shorter, not longer, than the one it replaces.

**Sequencing**: Ordered generator-first, per the same explicit direction that shaped the prior
list. Phases 1–6 build and finish the **entire generator** — every user story that only touches
`sunday/build.py`, `sunday/graph.py`, `sunday/render.py`, and `sunday/templates/site/` — before
any portal work begins. Within the portal half, US7 (a thin local-build trigger) comes first as a
low-risk smoke test of the Flask shell, then US3 (the store, without which nothing else in the
portal can exist), then US4 and US8 (both need only the store), then US9 last, since it is the
only story needing the store *and* the diagram code from US6. This departs from strict spec
priority order (US3/US4/US8 are P3/P4/P8 but run after US5/US6/US2, which are P5/P6/P2)
specifically so the four-page published site is complete and deployable before the portal is
touched. Story priorities in spec.md are unchanged; only the build order here is reordered.

**Tests**: Included but not blanket TDD. Constitution III mandates coverage on parsing, tag
normalization, linking, and detection; the plan extends that to conflict detection and export
round-trip. Tests outside those areas are optional and marked as such.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story the task serves (US1–US9, per spec.md priorities)
- Paths are repository-relative, per the structure in plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project skeleton and tooling. Nothing here is feature behavior.

- [X] T001 Create the package skeleton `sunday/__init__.py` and the directory tree
      `sunday/templates/site/`, `sunday/templates/portal/`, `tests/fixtures/` per plan.md
- [X] T002 Create `pyproject.toml` declaring Python 3.11+, runtime dependencies (flask, jinja2,
      pyyaml, markdown-it-py), a `[dev]` extra (pytest), and console script
      `sunday = "sunday.cli:main"`
- [X] T003 [P] Create `.gitignore` excluding `site/`, `.sunday/`, `.venv/`, `__pycache__/`
- [X] T004 [P] Vendor Cytoscape.js into `sunday/static/vendor/cytoscape.min.js` and record its
      version in `sunday/static/vendor/VERSION.txt`
- [X] T005 [P] Create the demonstration corpus in `tests/fixtures/corpus/stories/` — at least six
      stories sharing characters, locations, and tags, including one draft, one with no
      `occurs`, one with `occurs` as a bare year, and one pair of near-duplicate character
      spellings
- [X] T006 [P] Create `tests/fixtures/broken/` holding deliberately invalid story files:
      unparseable frontmatter, missing `title`, empty body, and two files sharing one `slug`

**Checkpoint**: `pip install -e ".[dev]"` succeeds and `pytest` collects zero tests without error.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Corpus loading and rendering. Both programs depend on every task here.

- [X] T007 Implement partial-date parsing and the `PartialDate` type in `sunday/corpus.py` —
      accepts `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, retains precision, exposes a sort key, per
      data-model.md
- [X] T008 Implement frontmatter splitting and YAML parsing in `sunday/corpus.py` — split on
      leading `---` fences, `yaml.safe_load` the metadata, body is the remainder
- [X] T009 Implement the `Story` dataclass in `sunday/corpus.py` with all fields from
      data-model.md, preserving unrecognized frontmatter keys in `extra`
- [X] T010 Implement structural validation in `sunday/corpus.py` raising a typed error naming
      file and problem for: unparseable frontmatter, missing `slug`/`title`/`published`/body,
      malformed dates, `slug` not matching `[a-z0-9-]+`
- [X] T011 Implement corpus loading in `sunday/corpus.py` — read every `.md` under the stories
      directory, detect duplicate slugs and raise an error naming **both** files
- [X] T012 Implement name normalization in `sunday/corpus.py` — casefold, collapse whitespace,
      strip punctuation and apostrophes, for comparison only; the display form is never rewritten
- [X] T013 Implement the `Name` type and name extraction in `sunday/corpus.py` — gather
      characters, locations, and tags from the corpus, keyed by `(kind, display)` — one distinct
      spelling is one name, so a case-only typo stays visible to review — treating
      the same string under two kinds as two names
- [X] T014 [P] Implement Markdown rendering in `sunday/render.py` using markdown-it-py with
      CommonMark defaults and no extensions enabled
- [X] T015 [P] Implement precision-aware date display in `sunday/render.py` — "1921", "March
      1921", "4 March 1921" — never padding a partial date into a fabricated exact day
- [X] T016 [P] Implement settings loading in `sunday/settings.py` — read `sunday.yml`, require
      `title`, never write the file
- [X] T017 [P] Implement `cast.yml` import in `sunday/export.py` — parse `display_names` and
      `relationships` only (no other fields exist in this file, per FR-038a/b); a missing file is
      not an error
- [X] T018 **[MANDATORY per Constitution III]** Write `tests/test_corpus.py` covering: valid
      parse, every failure mode from T010 using `tests/fixtures/broken/`, duplicate-slug error
      naming both files, `extra` key preservation, all three partial-date forms and their sort
      keys, and normalization folding case/punctuation/whitespace while leaving `display`
      untouched
- [X] T019 [P] Implement CLI skeleton in `sunday/cli.py` — `argparse` with `build`, `portal`, and
      `store rebuild` subcommands and the options listed in contracts/cli.md, dispatching to stubs

**Checkpoint**: `pytest tests/test_corpus.py` passes. The corpus fixture loads; the broken
fixture raises named errors.

---

## Phase 3: User Story 1 — Publish the collection as a browsable site (P1) 🎯 generator MVP

**Goal**: Files in, static site out — the feed and story pages.

**Independent test**: Build the fixture corpus; the feed lists every published story, each has a
readable page, drafts appear nowhere.

- [X] T020 [US1] Implement `sunday/templates/site/base.html` — semantic HTML, no JavaScript
- [X] T021 [P] [US1] Implement `sunday/templates/site/index.html` — the feed: every published
      story, newest first by `published`, each item annotated with its characters/locations as
      data attributes (feed-filter groundwork per FR-011a, no filtering logic yet)
- [X] T022 [P] [US1] Implement `sunday/templates/site/story.html` — title, both dates, rendered
      body. **No characters, locations, or tags displayed** (FR-010a)
- [X] T023 [P] [US1] Write `sunday/static/site.css` — single stylesheet, readable long-form
      measure, no framework
- [X] T024 [US1] Implement output-directory preparation in `sunday/build.py` — remove stale
      output so deleted or renamed stories leave no orphaned URL (FR-018)
- [X] T025 [US1] Implement story-page generation in `sunday/build.py` → `site/stories/<slug>/`,
      excluding drafts entirely (FR-012)
- [X] T026 [US1] Implement feed generation in `sunday/build.py` → `site/index.html`, ordered by
      `published` descending (FR-011)
- [X] T027 [US1] Implement deterministic emission across `sunday/build.py` — sort every
      collection before writing; no timestamps, build ids, or hashes (FR-016)
- [X] T028 [US1] Wire `sunday build` in `sunday/cli.py` — exit codes 0/1/2 per contracts/cli.md,
      structural errors to stderr, nothing published on failure
- [X] T029 [US1] Copy `sunday/static/site.css` into the output tree during build
- [X] T030 [US1] Write `tests/test_build.py` covering: draft exclusion from feed and its own URL,
      stale-output removal, build-twice-byte-identical determinism (SC-008), and story-page HTML
      containing no character, location, or tag names anywhere (FR-010a)
- [X] T031 [US1] **[Structural guard]** Add a test to `tests/test_build.py` asserting
      `sunday/build.py` neither imports nor references `sunday.store` — the export boundary as an
      import rule (Constitution II)
- [X] T032 [US1] **[Page-inventory guard]** Add a test to `tests/test_build.py` asserting the
      generated tree contains only `index.html`, `network/`, `archive/`, and `stories/<slug>/` —
      no `characters/`, `locations/`, or `tags/` (FR-009a, SC-017)
- [X] T033 [US1] Create `.github/workflows/build.yml` — install, `sunday build` without
      `--strict`, publish `site/` to GitHub Pages on push, fail the job on non-zero exit

**Checkpoint**: A complete site builds from the fixture corpus and deploys from CI. Feed and
story pages work.

---

## Phase 4: User Story 6 — Explore the tag network (P6, built before P2 — see note)

**Note on ordering**: US2 is "click a diagram node → see filtered stories." Without a diagram
there's nothing to click, so this story's structural work has to land first; US2 becomes the
thin filtering layer on top of it.

**Goal**: The published diagram — the centrepiece of the site.

**Independent test**: Build an interconnected fixture corpus; `/network/` shows the expected
nodes and edges; the page degrades sensibly without JavaScript.

- [X] T034 [US6] Implement co-appearance graph construction in `sunday/graph.py` — nodes for
      characters/locations in published stories, weighted `co_appearance` edges, isolated nodes
      retained
- [X] T035 [US6] Implement `stated` edges in `sunday/graph.py` from imported `cast.yml`
      relationships (T017), adding nodes for any subject named in one; a pair with both a
      co-appearance and a stated edge yields **two** edges, never merged (FR-051)
- [X] T036 [US6] Implement display-name label overrides in `sunday/graph.py` from `cast.yml`
- [X] T037 [US6] Implement canonical ordering in `sunday/graph.py` — sort nodes/edges by id,
      store undirected endpoints in canonical order so a pair appears once per kind
- [X] T038 [US6] Implement node URLs in `sunday/graph.py` — `/?character=<slug>` or
      `/?location=<slug>` (FR-015a)
- [X] T039 [US6] Implement `graph.json` serialization in `sunday/build.py` to the schema in
      contracts/site-structure.md
- [X] T040 [P] [US6] Implement `sunday/templates/site/network.html` loading the vendored
      Cytoscape.js and `graph.json`
- [X] T041 [P] [US6] Write `sunday/static/network.js` — layout, node sizing by story count,
      click-through to the node's feed URL
- [X] T042 [US6] Implement the no-JavaScript fallback in `sunday/templates/site/network.html` —
      message plus links to `/` and `/archive/`, never a blank page (FR-022)
- [X] T043 [US6] Generate `site/network/index.html` in `sunday/build.py`; copy the vendored
      library and `network.js` into the output tree
- [X] T044 [US6] **[MANDATORY per Constitution III]** Write `tests/test_graph.py` covering: co-occurring names produce a weighted
      edge, isolated nodes survive, stated + co-appearance on the same pair stay two edges, node
      and edge ordering is deterministic; extend `tests/test_build.py` asserting `graph.json` is
      byte-identical across two builds

**Checkpoint**: The diagram is explorable and every other page still works without JavaScript.

---

## Phase 5: User Story 2 — Follow a character from the diagram to their stories (P2)

**Goal**: Make the diagram and the feed the same navigational system.

**Independent test**: Select a node; the feed narrows to exactly that character's published
stories; clearing the filter restores the full list; the feed degrades to complete, not broken,
without JavaScript.

- [X] T045 [US2] Write `sunday/static/feed-filter.js` — read `?character=<slug>` or
      `?location=<slug>` from the URL, hide non-matching feed items using the data attributes
      from T021, provide a "clear filter" control
- [X] T046 [US2] Wire `feed-filter.js` into `sunday/templates/site/index.html` and copy it into
      the output tree in `sunday/build.py`
- [X] T047 [US2] Confirm (and if needed adjust) that `sunday/templates/site/index.html` renders
      the complete, correctly formatted feed with no script present — the JS-disabled path is the
      same markup, filtering is purely an overlay (FR-011b)
- [X] T048 [US2] Extend `tests/test_build.py` asserting the feed HTML for a filtered-URL request
      contains every story's markup regardless of query string — proving the "complete when
      unfiltered" guarantee holds at the HTML level, independent of the JS that narrows it

**Checkpoint**: The diagram is a way to read, not a picture (SC-001).

---

## Phase 6: User Story 5 — Read the collection in in-world order (P5)

**Goal**: The archive — the collection's chronology, and the second complete no-JavaScript route.

**Independent test**: Build from stories with mixed in-world dates; the archive orders correctly,
undated stories are grouped separately, and it's fully usable with JavaScript disabled.

- [X] T049 [US5] Implement archive ordering in `sunday/graph.py` — sort by `(sort_date,
      precision_rank, published, slug)`, partition out stories with no `occurs` (FR-023,
      FR-023a)
- [X] T050 [P] [US5] Implement `sunday/templates/site/archive.html` — chronological section, then
      an undated section, using the precision-aware display from T015
- [X] T051 [US5] Generate `site/archive/index.html` in `sunday/build.py`
- [X] T052 [US5] Extend `tests/test_graph.py` covering archive ordering: mixed precisions sort
      correctly, tie-breaks are deterministic, undated stories are excluded from the chronology
      and appear in their own group

**Checkpoint**: **The generator is complete.** All four page kinds exist: feed, diagram, archive,
story pages. `sunday build` on the fixture corpus produces the entire published site, deployable
from CI, fully tested for determinism, drafts, the import boundary, and the page inventory. This
is a natural point to stop, deploy, and only then start the portal.

---

## Phase 7: User Story 7 — Check the site locally before publishing (P7, generator-adjacent)

**Note on ordering**: This needs `sunday build` (done) but only a minimal `sunday portal`
process to trigger it — moved here, ahead of the heavier portal work, as an early smoke test of
the Flask app shell before the portal's real complexity (store, cast, review) begins.

**Goal**: Trigger a build from a browser and see the result.

**Independent test**: Start a minimal portal, trigger a build, see it succeed and be browsable.
Break a story and confirm the failure appears in the browser.

- [X] T053 [US7] Implement the Flask app factory in `sunday/portal/__init__.py` — bind
      `127.0.0.1` only, refuse to start when the target is not a recognizable collection
      (FR-036); no store wiring yet, just enough to serve routes
- [X] T054 [P] [US7] Implement `sunday/templates/portal/base.html` and a minimal dashboard
- [X] T055 [US7] Implement `sunday/portal/build_routes.py` — `POST /build` invoking the same code
      path as `sunday build`, reading committed files only, never `store`
- [X] T056 [P] [US7] Implement `sunday/templates/portal/build.html` reporting success, warnings,
      and structural failures with the offending file and message (FR-034)
- [X] T057 [US7] Implement `GET /build/output` serving the most recent local build for browsing
- [X] T058 [US7] Wire `sunday portal` in `sunday/cli.py` per contracts/cli.md (`--port`,
      `--no-browser`)
- [X] T059 [US7] Add an optional test asserting a portal-triggered build and a CLI build produce
      identical output from identical sources

**Checkpoint**: The generator can be exercised from a browser.

---

## Phase 8: User Story 3 — Write and edit stories in the portal (P3)

**Goal**: The authoritative store, atomic writes, and conflict detection — the foundation every
remaining portal story depends on.

**Independent test**: Create a story through the portal; the generator accepts the resulting
file. Edit that file in a text editor; the portal reports a conflict rather than overwriting.

- [X] T060 [US3] Implement store schema creation in `sunday/store.py` — the six tables from
      data-model.md (`meta`, `stories`, `subjects`, `notes`, `relationships`, `conflicts`) plus
      `schema_version`, hand-written SQL over stdlib `sqlite3`
- [X] T061 [US3] Implement store open/create in `sunday/store.py`, rebuilding when the file is
      missing, empty, or version-mismatched
- [X] T062 [US3] Implement subject upsert in `sunday/store.py` — ensure a `subjects` row per
      character/location name used by the corpus, preserving existing ids (**not** tags — see
      data-model.md's Name section for why)
- [X] T063 [US3] Implement atomic story writing in `sunday/writer.py` — serialize frontmatter
      plus body, write to a temp file, `os.replace` into place, and return the exact bytes
      written
- [X] T064 [US3] Implement frontmatter serialization in `sunday/writer.py` preserving
      unrecognized keys from `Story.extra` (FR-027)
- [X] T065 [US3] Implement hash recording in `sunday/store.py` — store the SHA-256 of the bytes
      written by T063 as `last_written_hash` with its path
- [X] T066 [US3] Implement conflict detection in `sunday/store.py` — hash each story file on
      load and classify as clean, diverged, untracked, or missing per contracts/portal-routes.md
- [X] T067 [US3] Wire store creation/reload into `sunday/portal/__init__.py` startup (extending
      T053)
- [X] T068 [P] [US3] Implement `sunday/templates/portal/story_form.html` — title, both dates,
      slug, draft flag, character/location/tag inputs, body
- [X] T069 [US3] Implement `sunday/portal/stories.py` — `GET /stories/`, `GET /stories/new`,
      `GET /stories/<slug>/edit`
- [X] T070 [US3] Implement `POST /stories/<slug>` in `sunday/portal/stories.py` — validate, write
      the file, update the store row and hash, redisplay the form with a specific message when a
      required field is missing (FR-028)
- [X] T071 [US3] Implement name autocompletion in `sunday/portal/stories.py` and the story form,
      offering names already in the corpus while allowing any new name without registration
      (FR-029, FR-008a)
- [X] T072 [P] [US3] Implement `sunday/templates/portal/conflict.html` — disk version and store
      version side by side
- [X] T073 [US3] Implement `GET`/`POST /stories/<slug>/conflict` in `sunday/portal/stories.py` —
      resolve as keep-disk or keep-store, never writing either side until the author chooses
      (FR-041)
- [X] T074 [US3] Block editing of a diverged story in `sunday/portal/stories.py` until its
      conflict is resolved
- [X] T075 [US3] Wire `sunday portal`'s remaining options (`--stories`, `--settings`, `--cast`,
      `--store`) in `sunday/cli.py`
- [X] T076 [US3] **[MANDATORY per plan.md]** Write `tests/test_store.py` covering conflict
      detection in both directions: an untouched file stays clean, an externally modified file is
      diverged, resolution clears the conflict and records the new hash, a file rewritten by the
      portal never self-reports a conflict, and rewriting a file with identical bytes stays clean

**Checkpoint**: Stories can be written in the browser and edited in a text editor, and divergence
is always caught.

---

## Phase 9: User Story 4 — Keep the shared cast consistent (P4)

**Goal**: Surface probable naming mistakes in the portal, ahead of the build, across characters,
locations, *and* tags. Establish the base cast page — story list and derived context — that US9
extends later.

**Independent test**: Load a corpus with a misspelled name and an orphaned profile; the portal
reports both, and a rename removes every occurrence of the old spelling. Open a tag's page and
confirm it shows only a story list — nothing character-specific.

- [X] T077 [US4] Implement bounded edit distance over normalized names in `sunday/review.py`
- [X] T078 [US4] Implement finding detection in `sunday/review.py` for `probable_duplicate` and
      `single_use` over **all three** `Name.kind` values, and `orphaned_profile` /
      `unprofiled_name` restricted to character/location only, per data-model.md's Review
      Findings table (FR-030–032b)
- [X] T079 [US4] Implement corpus-wide rename in `sunday/writer.py` — rewrite every story
      referencing the old name (character, location, or tag), update `last_written_hash` for
      each rewritten file so the rename never manufactures conflicts, and return the count of
      files changed
- [X] T080 [US4] Implement subject rename in `sunday/store.py` — update `subjects.name` in place
      for character/location renames so notes and relationships keep following the id; tag
      renames touch no store row (FR-030, FR-050)
- [X] T081 [US4] Implement the derived-context computation in `sunday/graph.py` — for a
      character: the locations they appear in, the other characters they appear alongside, and
      their first and last appearance by publication date (FR-054)
- [X] T082 [P] [US4] Implement `sunday/templates/portal/cast_index.html` — every name with kind,
      story count, profile state, and its findings
- [X] T083 [P] [US4] Implement `sunday/templates/portal/review.html` presenting all findings in
      one place (SC-007)
- [X] T084 [P] [US4] Implement `sunday/templates/portal/cast_page.html` with two branches: the
      character/location branch (stories, derived context, profile — relationships and the
      diagram are added by US9) and the tag branch (story list only, per FR-053b)
- [X] T085 [US4] Implement `sunday/portal/cast.py` — `GET /cast/`, `GET /cast/<kind>/<slug>`
      (dispatching by `kind` to the correct template branch from T084), and `GET /review/`,
      marking drafts in listed stories
- [X] T086 [US4] Implement `POST /cast/<kind>/<slug>/rename` in `sunday/portal/cast.py` wiring
      T079 and T080 and reporting the file count
- [X] T087 [US4] Implement `POST /cast/<kind>/<slug>/profile` in `sunday/portal/cast.py` —
      create or edit a profile (character/location only)
- [X] T088 [US4] Implement candidate profiles and `POST /cast/<kind>/<slug>/dismiss` in
      `sunday/portal/cast.py` — a pre-filled draft for any unprofiled, undismissed
      character/location name; dismissal persists so the suggestion does not return (FR-044);
      accepted profiles render visually distinct from unprofiled names (FR-033c)
- [X] T089 [US4] Emit findings as non-fatal warnings on stderr in `sunday/build.py`, exiting 0
      regardless, with `--strict` promoting them to exit 1 (FR-017a/b)
- [X] T090 [US4] **[MANDATORY per Constitution III]** Write `tests/test_review.py` covering:
      case-only and punctuation-only duplicates detected for characters, locations, **and tags**,
      a small misspelling detected, unrelated names not flagged, orphaned profiles detected
      (character/location only), dismissed names excluded from candidates, and a build with
      findings still exiting 0

**Checkpoint**: Editorial review happens in the portal while writing, across all three name
kinds; publication is never blocked by it.

---

## Phase 10: User Story 8 — Keep private notes on the world (P8)

**Goal**: Private authoring text, structurally incapable of reaching the site.

**Independent test**: Attach a note to a character, rebuild the site, and confirm the note text
appears nowhere in the generated output or any committed file.

- [X] T091 [US8] Implement note CRUD in `sunday/store.py` against the `notes` table, targeting a
      story id or a subject id
- [X] T092 [P] [US8] Implement `sunday/templates/portal/notes.html` — attach, edit, and delete
      notes inline on a story or subject
- [X] T093 [US8] Implement `sunday/portal/notes.py` — `POST /notes/`, `POST /notes/<id>`
- [X] T094 [US8] Surface notes on the story edit page and the cast page in
      `sunday/portal/stories.py` and `sunday/portal/cast.py`
- [X] T095 [US8] Add a leak guard to `tests/test_build.py` asserting note text appears in no
      generated file, in `cast.yml`, in any story file, or in `sunday.yml` (FR-046, SC-014)
- [X] T096 [US8] Extend `tests/test_store.py` asserting a note survives renaming the subject it
      is attached to (FR-047)

**Checkpoint**: Private material is usable and structurally incapable of reaching the site.

---

## Phase 11: User Story 9 — Record how the cast is connected (P9)

**Goal**: Author-stated relationships, exported to the site, and the completed cast page —
relationships and a per-character diagram added to the base built in US4.

**Independent test**: Record a relationship between two characters who share no story; the
diagram connects them and marks the edge as stated. The character's cast page now shows the
relationship and a diagram centred on them.

- [X] T097 [US9] Implement relationship CRUD in `sunday/store.py` against the `relationships`
      table, referencing subject ids with a description and a `directed` flag
- [X] T098 [P] [US9] Implement `sunday/templates/portal/relationships.html` — record, edit, and
      delete, selecting both subjects from the existing cast
- [X] T099 [US9] Implement `sunday/portal/relationships.py` — `GET /relationships/`,
      `POST /relationships/`, `POST /relationships/<id>`
- [X] T100 [US9] Implement `cast.yml` export in `sunday/export.py` — `display_names` and
      `relationships` only, sorted, with the generated-do-not-edit header from
      contracts/file-formats.md
- [X] T101 [US9] Trigger re-export on every save that changes relationships or display names in
      `sunday/portal/cast.py` and `sunday/portal/relationships.py` (FR-038). Note: this is also
      the answer to "what happens if `cast.yml` was hand-edited despite the generated marking
      (FR-039)" — the next re-export silently overwrites it. No separate detection needed; this
      is the same behavior as any other regeneration.
- [X] T102 [US9] Extend `sunday/templates/portal/cast_page.html`'s character/location branch to
      show stated relationships (FR-055) and a per-character diagram reusing
      `sunday/static/network.js` against a subject-scoped payload built from co-appearances and
      relationships (FR-056) — completing the page assembly begun in US4 (FR-057). Note: a
      character with neither co-appearances nor relationships gets a payload with zero nodes,
      which `network.js` already renders as an empty canvas — no special-case handling needed.
- [X] T103 [US9] **[MANDATORY per plan.md]** Write `tests/test_export.py` covering the
      `cast.yml` round-trip: export then import reproduces relationships and display names,
      output is sorted and deterministic, a missing file imports as empty rather than erroring,
      and **no `description` field is ever written** (FR-038b)
- [X] T104 [US9] Extend `tests/test_graph.py` asserting a pair with both co-appearance and a
      stated relationship yields two edges sourced from a real `cast.yml` fixture, and that a
      stated edge exists between characters sharing no story

**Checkpoint**: The published diagram, and the portal's cast page, both describe relationships
the author has stated, not only ones the filing implies.

---

## Phase 12: Polish & Cross-Cutting Concerns

- [X] T105 Implement `sunday store rebuild` in `sunday/cli.py` and `sunday/export.py` — recover
      stories, subjects, relationships, and display names from committed files, requiring
      confirmation unless `--yes` and stating that notes, dismissals, and profile descriptions
      are not recoverable
- [X] T106 **[MANDATORY per plan.md]** Extend `tests/test_export.py` covering rebuild-from-files:
      delete the store, rebuild, confirm every story/relationship/display-name returns and that
      notes/dismissals/descriptions are reported as lost (SC-011)
- [X] T107 Add a test to `tests/test_build.py` building the fixture corpus in a directory where
      `.sunday/` has never existed, proving CI never needs the store (SC-012)
- [X] T108 [P] Write `tests/test_writer.py` covering round-trip fidelity, unknown-key
      preservation, and a rename leaving zero occurrences of the old name (SC-010)
- [X] T109 [P] Implement the untracked and missing story cases from contracts/portal-routes.md in
      `sunday/portal/stories.py` — adopt files with no store row, report store rows whose file
      has vanished
- [X] T110 [P] Handle the empty corpus and missing settings file gracefully in `sunday/build.py`
      and `sunday/settings.py`
- [X] T111 [P] Verify non-ASCII names, accents, and apostrophes survive parsing, slug derivation,
      rename, and export; add cases to `tests/test_corpus.py`
- [X] T112 Add `--quiet` and `--strict` handling to `sunday/cli.py` per contracts/cli.md
- [X] T113 [P] Write `README.md` covering install, the three commands, the two-tier file/store
      model, which files are hand-owned versus generated, and a pointer to
      [002-character-media](../002-character-media/spec.md) for the deferred image feature
- [X] T114 Walk every scenario in [quickstart.md](./quickstart.md) end to end against the fixture
      corpus and fix what fails
- [X] T115 Measure a full build and confirm it completes well under 60 seconds (SC-002)
- [X] T116 [P] Add a structural guard test asserting no module under `sunday/portal/` imports
      `subprocess`, calls out to `git`, or otherwise performs a version control operation
      (FR-035). Same pattern as T031's import-boundary guard, added to `tests/test_store.py` or a
      new `tests/test_portal.py` — whichever already exists by the time this is picked up.
- [X] T117 [P] Add a structural guard test asserting no module under `sunday/portal/` opens
      `sunday.yml` for writing (FR-006) — the settings file stays hand-owned. Same file as T116.

---

## Dependencies

```text
Phase 1 Setup
   ↓
Phase 2 Foundational  ← blocks everything below
   ↓
Phase 3 US1 (P1)  ← feed + story pages                ┐
   ↓                                                    │
Phase 4 US6 (P6)  ← network diagram (built early)        │  GENERATOR
   ↓                                                    │  (complete and
Phase 5 US2 (P2)  ← diagram → filtered feed               │  deployable at
   ↓                                                    │  the Phase 6
Phase 6 US5 (P5)  ← archive                               │  checkpoint)
   ↓                                                    ┘
Phase 7 US7 (P7)  ← local build trigger (thin portal shell)
   ↓
Phase 8 US3 (P3)  ← store, atomic writes, conflicts     ┐
   ↓                                                    │
Phase 9 US4 (P4)  ← review, rename, base cast page        │  PORTAL
   ↓                                                    │  (everything
Phase 10 US8 (P8) ← notes (needs only the store)          │  after the
   ↓                                                    │  generator
Phase 11 US9 (P9) ← relationships, export, finishes        │  is done)
             the cast page (needs US4 + US6)            ┘
   ↓
Phase 12 Polish
```

**Why US6 before US2**: unchanged from the prior list — there is nothing to click until the
diagram exists.

**Why US7 before US3/US4/US8/US9**: unchanged — a cheap smoke test of the portal process before
its real complexity begins.

**Why US8 moved earlier than in the prior list**: US8 (notes) previously came last because it was
the only story touching every subsystem — store, export, graph, *and media*. With media gone, US8
needs only the store (US3). It has no dependency on relationships, the diagram, or export, so it
now runs right after US4 rather than at the end.

**Why US9 is still last**: it needs both the store (US3, for relationships) and the diagram code
(US6, reused for the per-character diagram), and it completes the cast page assembly that US4
started. No other story has that combination of dependencies.

**Genuinely independent after Phase 8**: US4 and US8 both depend only on US3 and touch different
files (`cast.py`/`review.py` vs. `notes.py`) — they can proceed in parallel once the store exists.

## Parallel Execution Examples

**Phase 1**: T003, T004, T005, T006 are four separate files — run together after T001.

**Phase 2**: T014, T015 (render), T016 (settings), T017 (cast import), T019 (CLI skeleton) are
independent of the T007–T013 corpus chain and of each other.

**Phase 3**: T021 (feed template), T022 (story template), T023 (stylesheet) run alongside T020.

**Phase 4**: T040, T041 (templates/JS) run alongside the T034–T038 graph-construction chain.

**Phase 8**: T068, T072 (templates) run alongside the T060–T066 store chain.

**Phases 9 and 10 in parallel**: one developer on US4 (review, rename, base cast page), another
on US8 (notes) — both depend only on Phase 8 and share no files.

## Implementation Strategy

**MVP is Phase 6.** Stop there and the collection is published, readable, and deploying from CI
with all four page kinds — feed, diagram (with filtering), archive, and story pages. Everything
after that is an authoring convenience.

**Suggested increments**:

1. **Publish** — Phases 1–6. Stories are online, cross-referenced through the diagram and feed
   filter, with a chronological archive.
2. **Preview** — Phase 7. Local builds from the browser.
3. **Author** — Phase 8. Writing moves into the browser, with conflict safety.
4. **Curate & record** — Phases 9–10 in parallel. Naming stays consistent (including tags); notes
   capture what isn't written yet.
5. **Connect** — Phase 11. Relationships reach the published diagram and complete the cast page.

**Watch for**: T031/T032 (the boundary and page-inventory guards) are a few lines each and belong
in Phase 3, not polish — they're the first things a well-meaning refactor breaks. T062's note on
why tags get no `subjects` row is worth reading before touching `store.py`; it's the one place a
future contributor might reasonably (and incorrectly) assume tags need the same treatment as
characters and locations.
