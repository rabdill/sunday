# Sunday

A short fiction publishing system: a **static site generator** that turns a folder of
Markdown stories into a website, and a **local authoring portal** for writing them.

The stories are the product. Everything else is a view onto them.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Python 3.11 or newer.

## Running it locally

```bash
scripts/dev.sh
```

One command: it creates the virtualenv if there isn't one, seeds a scratch collection in
`dev/` from the test fixtures the first time, builds the site, and leaves two servers
running —

| | |
|---|---|
| `http://127.0.0.1:5000/` | the authoring portal |
| `http://127.0.0.1:5001/` | the generated site, served as a reader would meet it |

The site is static, so a change made in the portal appears there after a build — its
Build page, or `sunday build`. The portal also serves the last build at
`/build/output/`, which is enough for a quick check without switching ports.

Ports are overridable (`PORTAL_PORT`, `SITE_PORT`), as is the collection
(`COLLECTION=path`) if you would rather work in your own. `dev/` is gitignored; delete
it to start over.

Both servers bind `127.0.0.1` only. The portal writes files and has no authentication,
so reaching it from another machine means a tunnel, never a wider bind.

## The three commands

```bash
sunday build            # generate the site into site/
sunday portal           # open the authoring tool at http://127.0.0.1:5000
sunday store rebuild    # rebuild the local store from committed files
```

`sunday build` is what CI runs on every push. It reads committed files only and never
touches the authoring store — which is why it works in CI, where no store exists.

## How a collection is laid out

| Path | Who owns it | Committed? |
|---|---|---|
| `stories/*.md` | Shared — you and the portal both write here | Yes |
| `sunday.yml` | **You.** The portal never rewrites it | Yes |
| `cast.yml` | **The portal.** Generated; do not hand-edit | Yes |
| `.sunday/store.db` | The portal | No — gitignored |
| `site/` | The generator | No — gitignored |

The split matters. A file that is partly hand-owned and partly generated needs a merge
strategy, and merge strategies are where sync bugs live.

## Writing a story

A story is one Markdown file with its metadata in frontmatter:

```markdown
---
slug: the-lighthouse          # permanent address; changing the title never changes it
title: The Lighthouse
published: 2026-08-04         # when you released it — orders the feed
occurs: 1921-03               # when it happens in the fiction — orders the archive
characters: [Mara Vance, Elias Doyle]
locations: [Portsmouth]
tags: [epistolary]
draft: false                  # true removes it from the site entirely
---

The fog came in early that year, and with it the letters.
```

`occurs` tolerates imprecision — `1921`, `1921-03`, or `1921-03-04`. Fiction rarely
carries an exact day, and a partial date is displayed at its true precision rather than
padded into a date you never wrote.

Adding a story requires changing **no other file**, even when it introduces characters
the collection has never used. A name exists because a story names it.

## What gets published

Four kinds of page, and nothing else:

- **`/`** — the feed, newest first. Narrowable to one character via `?character=…`.
- **`/network/`** — the diagram: characters and locations, and how they connect.
- **`/archive/`** — every story in the fiction's own chronology.
- **`/stories/<slug>/`** — one page per story, carrying only the story.

Every story is reachable without JavaScript through the feed and the archive. The
diagram and the feed filter are the only scripted features, and neither is the only way
to reach anything.

## What stays in the portal

Cast pages, profile descriptions, private notes, and per-character diagrams are
authoring surfaces. They are never generated into the site. The export carries only what
the diagram consumes — stated relationships and display names — so nothing in a
committed file is invisible to readers.

## Editing outside the portal

Supported, deliberately. Open a story in any text editor. If the portal later finds the
file changed since it last wrote it, it shows you both versions and asks which to keep.
Detection is by content hash, not timestamp, so `git checkout` does not manufacture
false conflicts.

## Naming consistency

Because a name exists by being used, a typo silently creates a second character rather
than an error. The portal's **Cast** and **Review** pages catch that after the fact:
near-duplicate spellings, names used only once, and profiles describing names no story
uses — across characters, locations, and tags alike.

None of it blocks a build. A publication step that refused to publish over a spelling
question would be the wrong shape for this. `sunday build --strict` opts into the
opposite, and CI does not pass it.

## Losing the store

`.sunday/store.db` is disposable by design. Delete it and the portal rebuilds from the
committed files, recovering stories, subjects, relationships, and display names.

It cannot recover **notes, dismissed candidates, or profile descriptions** — none of the
three is exported. That is the accepted trade for keeping a binary out of git. No story
text is ever at risk: the portal writes the file on every save, so the corpus on disk is
never behind.

## Tests

```bash
pytest
```

Coverage concentrates where silent corruption is possible: frontmatter parsing, name
normalization, the connection graph, conflict detection, and the export boundary. Two
structural guards assert the architecture rather than trusting it — that `build.py`
never imports the store, and that the generated tree contains only the four page kinds.

## Not here yet

Character portraits and moodboards are specified in
[`specs/002-character-media`](specs/002-character-media/spec.md) and deliberately left
out of this first version, so it ships without an image-processing dependency.
