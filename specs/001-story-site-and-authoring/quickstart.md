# Quickstart & Validation Guide

Scenarios map to user stories and success criteria; details live in [contracts/](./contracts/)
and [data-model.md](./data-model.md). No media scenarios appear here — that work is deferred to
[002-character-media](../002-character-media/spec.md).

## Prerequisites

```bash
python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

## Build and run

```bash
sunday build      # site/index.html, site/network/, site/archive/, site/stories/*/
sunday portal     # http://127.0.0.1:5000
```

## Validation scenarios

### 1. The published site is exactly four page kinds (FR-009a, SC-017)

```bash
sunday build
find site -name "*.html" | sed 's|site/||'
```

Pass: only `index.html`, `network/index.html`, `archive/index.html`, and one
`stories/<slug>/index.html` per published story. Nothing under `characters/`, `locations/`, or
`tags/`.

### 2. Story pages carry only the story (FR-010a)

Open any story page. Pass: no character, location, or tag names appear anywhere on it.

### 3. The diagram leads to the feed (User Story 2, SC-001)

Open `/network/`, select a character node. Pass: lands on `/?character=<slug>`, listing exactly
that character's published stories.

### 4. The feed degrades to complete, not broken (FR-011b)

Disable JavaScript and load a filtered URL. Pass: the full unfiltered collection displays — never
empty, never broken.

### 5. Every story is reachable without JavaScript (FR-021, SC-005)

Disable JS. Browse `/` and `/archive/`. Pass: every published story is reachable from at least
one of the two. Open `/network/`. Pass: a message plus links to `/` and `/archive/`, not a blank
page.

### 6. Drafts stay hidden everywhere (FR-012)

Set `draft: true`, rebuild:

```bash
grep -ri "<title>" site/index.html site/archive/index.html site/graph.json ; echo "exit=$?"
```

Pass: the draft's title appears in none of the feed, archive, or graph. Its own URL 404s.

### 7. Determinism (FR-016, SC-008)

```bash
sunday build --output /tmp/a && sunday build --output /tmp/b && diff -r /tmp/a /tmp/b
```

Pass: no differences.

### 8. Structural errors fail loudly; naming problems never do (FR-017, FR-017a/b)

Broken frontmatter and duplicate slugs exit 1 and name the file(s). A near-duplicate character
name exits 0 with a warning; `--strict` makes it exit 1.

### 9. The cast page (User Story 4, FR-053–FR-057)

In the portal, open `/cast/character/<slug>` for a character with stories, a relationship, and
notes. Pass: the page shows their stories in publication order, derived context (locations,
co-appearing characters, first/last appearance), stated relationships linking to the other
character, a per-character diagram, and notes — all in one place.

### 10. Nothing from the cast page reaches the site (FR-046, SC-014, SC-018)

With that same character's page populated:

```bash
sunday build
grep -ri "<description text>" site/ cast.yml
grep -ri "<note text>" site/ cast.yml stories/ sunday.yml
```

Pass: both empty.

### 11. Only relationships and display names export (FR-038a/b)

```bash
cat cast.yml
```

Pass: `display_names` and `relationships` only — no `description` field anywhere in the file.

### 12. Conflict detection (FR-041, SC-013)

Edit a story outside the portal, reload it, see both versions, choose a side. `git checkout`
produces no false conflicts.

### 13. The boundary holds structurally (Constitution II)

```bash
grep -n "^import\|^from" sunday/build.py | grep -E "store"; echo "exit=$?"
```

Pass: `exit=1` — `build.py` imports neither `store`. Also enforced by a test.

### 14. The site builds with no store present (SC-012)

```bash
git clone . /tmp/fresh && cd /tmp/fresh && sunday build
```

Pass: builds completely — including the diagram's stated edges and display names — in a checkout
where `.sunday/` has never existed.

### 15. Tags get the same naming consistency as characters and locations (FR-030–032b)

Add two stories using `epistolary` and `Epistolary` as a tag on each. Open `/cast/`.

Pass: the pair is flagged as a probable duplicate, exactly as a near-duplicate character name
would be. Rename one into the other from the portal.

```bash
grep -rn "epistolary" stories/ | grep -v "^stories/.*epistolary:" | wc -l
```

Pass: every story now carries the same spelling; zero occurrences of the discarded one remain.
Open the tag's own page at `/cast/tag/<slug>`. Pass: it lists the stories carrying it and nothing
else — no profile field, no relationships section, no diagram, no notes anywhere on the page.

### 16. Round-trip safety, rename, timeline-as-archive

Unrecognized frontmatter keys survive a no-op portal save; a rename leaves zero occurrences of the
old name and updates hashes so it never self-conflicts; the archive orders by in-world date with
undated stories grouped separately and imprecise dates displayed at their true precision.

### 17. Local build from the portal (User Story 7)

`POST /build` succeeds, is browsable, and matches CI output from the same sources; a broken story
reports its cause in the browser.

## Test suite

```bash
pytest
```

Mandatory per Constitution III and this plan: `test_corpus.py`, `test_graph.py`,
`test_review.py`, `test_store.py`, `test_export.py`. `test_review.py`'s fixtures must include a
tag near-duplicate pair, not just character/location ones. Scenarios 1, 6, 7, 10, and 13 above
should exist as automated tests, not just manual checks — they're the ones protecting the
boundary and the survival guarantees.
