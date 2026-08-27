# Sunday — working notes for Claude

A short-fiction publishing system: a **static site generator** that turns a folder
of Markdown stories into a website, and a **local Flask authoring portal** for
writing them. The stories are the product; everything else is a view onto them.

Design rationale and trade-offs live in [`docs/DESIGN.md`](docs/DESIGN.md). The
original feature specs are in [`specs/`](specs/) (historical — the code, tests, and
this file are the current authority).

## Commands

```bash
pip install -e ".[dev]"     # Python 3.11+
pytest                      # full suite; fast
sunday build                # generate the site into site/ (what CI runs)
sunday portal               # local authoring tool at http://127.0.0.1:5000
sunday store rebuild        # discard and rebuild the local store from files
```

## Architecture

Two programs share one read-only corpus loader (`corpus.py`):

- **Generator** (`build.py`, `graph.py`, `render.py`): committed files in, four kinds
  of static page out — feed, per-story, archive, network. Deterministic.
- **Portal** (`portal/`): a local Flask app that edits story files and keeps a
  SQLite **store** (`store.py`) of material no file represents.

The store's outbound half is `cast.yml` (`export.py`) — the only channel by which
portal-authored data (relationships, display names) reaches the generator.

## Invariants — do not break these (tests guard them)

1. **`build.py` never imports or references the store.** The published site derives
   from committed files alone, so it builds in CI where no store exists.
   (`tests/test_build.py` asserts this via AST.)
2. **The site is exactly four page kinds** — feed, story, archive, network — and no
   character/location/tag pages. That material is portal-only.
3. **Builds are deterministic:** every collection is sorted before it is written; no
   timestamps or random order reach output. Two builds of unchanged sources are
   byte-identical.
4. **Losing the store loses no story text.** The store holds only a hash of what the
   portal last wrote, never the story body. Files on disk are the authority.
5. **The portal runs no version-control operations** and **never writes `sunday.yml`.**
6. **Nothing private is published:** notes and profile descriptions never reach the
   site or any committed file. `cast.yml` carries only relationships and display
   names.
7. **A name exists by being used, not by being declared.** Adding a story with new
   names changes no other file. Names are compared normalized but stored verbatim.

## Conventions

- **Comments/docstrings are terse.** State what a thing does in a line; explain a
  *why* only where the code cannot and a reader would otherwise get it wrong. Design
  rationale belongs in `docs/DESIGN.md`, not in the source. Do not cite spec IDs
  (FR-xxx / SC-xxx) in code.
- **No new dependencies without a real reason.** Runtime deps are flask, jinja2,
  pyyaml, markdown-it-py, and nothing else.
- **Store schema is disposable.** To change it, edit `SCHEMA` and bump
  `SCHEMA_VERSION`; existing stores rebuild from committed files on next open.
- Markdown is CommonMark only (`render.py`), for byte-identical output.
