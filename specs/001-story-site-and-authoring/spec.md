# Feature Specification: Story Site Generator and Authoring Portal

**Feature Branch**: `001-story-site-and-authoring`

**Created**: 2026-08-10

**Status**: Draft

**Input**: A short fiction publishing system with two components. A **site generator** takes a
directory of Markdown story files plus configuration and produces a complete static website,
run automatically as a continuous integration step on push. A **local authoring portal**, run
on the author's own machine and opened in a browser, is used to write and edit stories, manage
the shared cast of characters and locations, and build the site locally before publishing. The
published site emphasizes reading niceties: cross-referencing stories by character and
location, a timeline view, and a diagram of the interconnected tag network.

## Clarifications

**2026-08-11 note**: the portrait/moodboard-related answers below (image types, HEIC conversion,
resize option, media storage location) remain an accurate historical record of what was decided,
but the feature they describe was split out into
[002-character-media](../002-character-media/spec.md) the same day, to keep this spec's first
build free of an image-processing dependency. This spec no longer requires or references media in
any form; see Assumptions for the pointer to where that work now lives.

### Session 2026-08-10

- Q: When you edit a story, which copy is the real one — the Markdown file, or a record inside
  the portal's database that gets written out to Markdown? → A: The database is canonical for
  authoring. Every save also writes the Markdown file, so the corpus on disk stays current. A
  file edited outside the portal is a conflict the portal must detect and reconcile.
- Q: If you edit a story file in a text editor and then open that story in the portal, what
  should the portal do with your outside edit? → A: Detect the divergence, present both versions,
  and let the author choose. Never overwrite either side silently.
- Q: If the portal's database file were deleted tomorrow, what would you expect to lose? → A:
  Revision history, dismissed candidates, and notes — but no stories, since every save writes the
  file. The database is gitignored and rebuilt from the corpus on next launch; that loss is
  accepted.
- Q: Character and location profiles currently live in `sunday.yml`. Should that file still be
  hand-editable? → A: No — profiles belong in the database. Consequence, since the generator runs
  in CI where the database does not exist: the portal exports profiles to a committed,
  generated-and-not-hand-edited file that the build reads, and re-imports from it when rebuilding
  the database. To avoid a file that is half hand-owned and half generated, the hand-owned
  collection settings and the generated profile export are separate files.
- Q: Beyond profiles and conflict tracking, what else should the portal's database hold in the
  first version? → A: Authoring notes and structured character relationships — but explicitly
  *not* revision history or autosave. Git already versions the always-current files, so an
  in-app history would be a second, worse copy.
- Q: What should someone actually see on a character's page? → A: The story list, plus context
  derived from the corpus (locations, co-appearing characters, first and last appearance), plus
  stated relationships, plus a small network diagram centred on that character.
- Q: In what order should a character's stories be listed on their page? → A: Publication order,
  newest first.
- Q: Should a character be able to have a portrait or image on their page? → A: A moodboard per
  character plus an optional portrait — but see below.
- Q: Should the moodboard be visible to readers on the character's page, or is it reference
  material? → A: Nothing public. Portrait and moodboard are both authoring material, portal-only,
  never exported and never published. The generator handles no images at all.
- Q: Where should those private images physically live? → A: A gitignored media directory beside
  the store; the store records which image belongs to whom, along with captions.
- Q: When a reader clicks a character in the big network diagram, what should happen? → A: They
  go to the homepage feed, narrowed to that character.
- Q: Should each character's filtered feed be a real page the generator writes out, or filtered in
  the browser? → A: Filtered in the browser, via a query string on the single feed. No per-name
  pages are generated.
- Q: What's in the archive? → A: Every story in in-world chronology. The archive absorbs the
  timeline; there is no separate timeline page.
- Q: Should a story page still show which characters and locations appear in it? → A: No. A story
  page carries only the story.
- Q: Now that character pages are gone, should their descriptions still be exported to the
  published site at all? → A: No. Only what the diagram needs — relationships and display names —
  crosses the export boundary. Descriptions stay in the store with the notes and moodboards.
- Q: Should tag naming get the same duplicate-detection and rename treatment characters and
  locations get, or is tag consistency out of scope? → A: Full treatment. Tags get duplicate
  detection, single-use flagging, rename-across-corpus, and their own listing page in the portal
  — the same naming-consistency machinery as characters and locations. They do not get profiles,
  relationships, media, or derived context; those stay character-specific.
- Q: What image types and size should the portal accept for portraits and moodboard uploads? → A:
  JPEG, PNG, WebP, GIF, and HEIC — HEIC specifically to support iPhone photos directly. Since
  HEIC is not reliably displayable in most non-Safari browsers, an uploaded HEIC image MUST be
  converted to a displayable format so it always renders in the portal. Because format conversion
  now requires image-processing capability regardless, the portal MUST also offer a "standardize
  size to save space" option, on by default, that resizes an image above a size threshold down to
  that threshold on upload. This reverses the earlier decision to avoid an image-processing
  dependency entirely; the plan and research documents need to reflect that at the next planning
  pass.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Publish the collection as a browsable site (Priority: P1)

The author has a directory of Markdown story files with metadata in each file's frontmatter.
On pushing that directory to the repository, a build runs automatically and produces a complete
static website: a landing page listing the collection, and a readable page for every published
story. No manual build step, no server to keep running, and no database behind the published
site — the authoring store stays on the author's machine and is never deployed.

**Why this priority**: Nothing else in the system has value without this. It is the smallest
slice that puts stories in front of readers, and every later story builds on the same generated
output.

**Independent Test**: Point the generator at a sample corpus of story files and run it. Open the
resulting output directory in a browser and confirm the index lists every published story and
each story page renders its full text with correct formatting.

**Acceptance Scenarios**:

1. **Given** a directory containing valid story files, **When** the build runs, **Then** a
   complete static site is produced containing the homepage feed, the network diagram, the
   archive, and one page per published story — and nothing else.
2. **Given** a story whose body uses standard Markdown, **When** its page is generated, **Then**
   the formatting is rendered as HTML rather than shown as literal markup.
3. **Given** a story marked as a draft in its metadata, **When** the build runs, **Then** the
   story appears nowhere in the generated site — not in the feed, not in the archive, not in the
   diagram or its filter data, and not at its own address.
4. **Given** the build has run once, **When** it runs again with no source changes, **Then** the
   generated site is identical.
5. **Given** a change is pushed to the repository, **When** the automated build completes,
   **Then** the published site reflects that change without any manual intervention.

---

### User Story 2 - Follow a character from the diagram to their stories (Priority: P2)

A reader explores the network diagram, notices a character at the centre of a cluster, and clicks
them. They land on the feed narrowed to that character and read what that person appears in.

**Why this priority**: The diagram is the centrepiece of the published site, and a diagram you
cannot act on is decoration. This is what turns it into a way to read.

**Independent Test**: Generate a site from a corpus where several stories share characters.
Select a node in the diagram and confirm the feed narrows to exactly that character's published
stories.

**Acceptance Scenarios**:

1. **Given** the network diagram, **When** a reader selects a character node, **Then** they arrive
   at the feed narrowed to that character.
2. **Given** the narrowed feed, **When** it renders, **Then** it lists exactly that character's
   published stories, newest first, and no others.
3. **Given** a character referenced only by draft stories, **When** the site is generated,
   **Then** they appear in neither the diagram nor any filter.
4. **Given** a reader with JavaScript disabled, **When** they open the feed, **Then** they see the
   complete unfiltered collection rather than an empty page, and can still reach every story
   through the feed and the archive.
5. **Given** the narrowed feed, **When** the reader clears the filter, **Then** the full
   collection returns without leaving the page.

---

### User Story 3 - Write and edit stories in the portal (Priority: P3)

The author runs the portal locally, opens it in a browser, and writes a new story: title, date,
body text, and the characters and locations it involves. On save, a correctly formatted Markdown
file appears in the stories directory. Opening an existing story loads it back for editing.

**Why this priority**: Stories can always be written in a plain text editor, so this is a
convenience rather than a prerequisite — but it is the convenience that prevents malformed
metadata, which is the main source of silent errors elsewhere in the system.

**Independent Test**: Start the portal, create a story through the browser, and confirm a valid
file is written to the stories directory that the generator accepts without error. Reopen the
same story in the portal and confirm every field round-trips unchanged.

**Acceptance Scenarios**:

1. **Given** the portal is running, **When** the author saves a new story, **Then** a Markdown
   file with valid metadata is written to the stories directory.
2. **Given** an existing story file, **When** it is opened in the portal and saved again with no
   edits, **Then** the file's meaning is unchanged and no metadata is lost.
3. **Given** the author is assigning characters to a story, **When** they choose a name already
   used elsewhere in the corpus, **Then** it is recorded with exactly the same spelling as its
   existing uses.
4. **Given** a story file that was hand-edited outside the portal since the portal last wrote
   it, **When** it is opened in the portal, **Then** the divergence is reported, both versions
   are shown, and neither is overwritten until the author chooses.
5. **Given** a required field is missing, **When** the author attempts to save, **Then** the
   portal refuses and explains what is missing.

---

### User Story 4 - Keep the shared cast consistent (Priority: P4)

Because a character, location, or tag exists simply by being named in a story, a typo silently
creates a second one rather than an error. The author opens the portal's cast view to see every
name the corpus uses — across all three kinds — how many stories use each, and which names are
suspiciously similar to one another — then renames the misspelling, and every story referencing
it is corrected at once.

**Why this priority**: With stories as the source of truth, nothing prevents a typo at write
time, so detection after the fact is the only safeguard. A misspelled name produces a
plausible-looking page that is quietly wrong — the exact failure the constitution singles out as
worth testing against. It matters most once the corpus is large enough to lose track of, which
is after stories exist.

**Independent Test**: Load a corpus containing one deliberately misspelled character reference
and one profile describing a name no story uses. Confirm the portal reports both,
then rename the misspelling and confirm the affected stories are updated.

**Acceptance Scenarios**:

1. **Given** the corpus uses two names differing only by case, punctuation, or a small spelling
   variation, **When** the author views the cast, **Then** the pair is flagged as a probable
   duplicate along with the stories using each.
2. **Given** a name used by exactly one story, **When** the author views the cast, **Then** it is
   distinguishable from established names, since a single use is the usual shape of a typo.
3. **Given** a profile describes a name no story uses, **When** the author views the
   cast, **Then** that entry is flagged as orphaned.
4. **Given** the author renames a character, **When** the rename is applied, **Then** every story
   referencing the old name is updated to the new one, and the old name no longer appears
   anywhere in the corpus.
5. **Given** the author views a character, **When** the page loads, **Then** every story
   referencing that character is listed, drafts included and marked as such.
6. **Given** the corpus uses two tags differing only by case or spelling, **When** the author
   reviews and renames the misspelling, **Then** the tag duplicate is flagged and corrected
   exactly as a character or location would be, and the tag's own page shows only the stories
   carrying it — no profile, relationships, or diagram.

---

### User Story 5 - Read the collection in in-world order (Priority: P5)

A reader who wants the fiction's own chronology rather than the order it was posted opens the
archive: every story, arranged by when it happens in the world.

**Why this priority**: One of the three published pages, and the complete no-JavaScript route to
everything. But the feed alone already makes the collection readable.

**Independent Test**: Generate a site from stories with a spread of in-world dates and confirm the
archive presents them in correct chronological order with each entry linking to its story.

**Acceptance Scenarios**:

1. **Given** published stories carrying in-world dates, **When** the site is generated, **Then**
   the archive orders them by in-world chronology and links each to its story.
2. **Given** two stories sharing an in-world date, **When** the archive is generated, **Then**
   both appear in a stable, repeatable order.
3. **Given** a published story with no in-world date, **When** the archive is generated,
   **Then** it is excluded from the chronology and listed separately as undated rather than
   being placed at an arbitrary point.
4. **Given** the archive, **When** a reader opens it with JavaScript disabled, **Then** every
   published story is present and reachable.

---

### User Story 6 - Explore the tag network (Priority: P6)

A reader opens a diagram of the collection showing characters and locations as connected nodes,
revealing which parts of the shared world cluster together, and can click through from any node
to the feed narrowed to that character or location.

**Why this priority**: The most distinctive feature of the site and the most technically
involved. It depends on everything above it and delivers no value until the corpus is
interconnected enough to be interesting.

**Independent Test**: Generate a site from an interconnected corpus, open the network page, and
confirm the diagram shows the expected nodes and connections and that clicking a node navigates
to its page.

**Acceptance Scenarios**:

1. **Given** a corpus where characters and locations co-occur across stories, **When** the site
   is generated, **Then** a network page presents them as nodes connected by their shared
   stories.
2. **Given** the network page, **When** a reader selects a node, **Then** they are taken to the
   feed narrowed to that character or location.
3. **Given** a character appearing in no story alongside any other tag, **When** the network is
   generated, **Then** that isolated node is still shown.
4. **Given** the network page, **When** a reader with JavaScript disabled opens it, **Then** they
   are told the diagram requires JavaScript and are offered links to the feed and the archive,
   through which every published story remains reachable.

---

### User Story 7 - Check the site locally before publishing (Priority: P7)

Before committing, the author triggers a build from the portal and views the generated site on
their own machine, confirming stories read correctly and the diagram and archive reflect the
current corpus as expected.

**Why this priority**: Reduces the push-and-check cycle, but the same result is achievable by
pushing and waiting for the automated build.

**Independent Test**: With the portal running, trigger a build and confirm the generated site
appears locally, reflects the current contents of the stories directory, and matches what the
automated build would produce from the same sources.

**Acceptance Scenarios**:

1. **Given** the portal is running, **When** the author triggers a build, **Then** the full static
   site is generated locally from the current source files.
2. **Given** a build fails, **When** the author triggers it from the portal, **Then** the failure
   and its cause are reported in the browser rather than only on a terminal.
3. **Given** a local build has completed, **When** the author views the result, **Then** it
   matches what the automated build would produce from the same sources.

---

### User Story 8 - Keep private notes on the world (Priority: P8)

The author records something true of a character that has not been written into any story yet —
an unresolved thread, a continuity detail, a reminder. It stays in the portal and never reaches
the published site.

**Why this priority**: Genuinely useful for a shared-world collection, and impossible to do in
the story files without it leaking to readers. But nothing else depends on it.

**Independent Test**: Attach a note to a character, rebuild the site, and confirm the note text
appears nowhere in the generated output.

**Acceptance Scenarios**:

1. **Given** a story, character, or location, **When** the author attaches a note, **Then** it is
   retained and shown next time they view that subject.
2. **Given** notes exist, **When** the site is generated, **Then** no note text appears anywhere
   in the output or in any committed file.
3. **Given** a note attached to a character, **When** that character is renamed, **Then** the note
   remains attached.

---

### User Story 9 - Record how the cast is connected (Priority: P9)

The author records that two characters are siblings, or that one betrayed the other — regardless
of whether any story has said so yet — and the network diagram reflects those stated
relationships alongside the connections inferred from co-appearance.

**Why this priority**: The richest use of the store and the thing that makes the network diagram
about the world rather than about the filing. It depends on everything above it.

**Independent Test**: Record a relationship between two characters who share no story, generate
the site, and confirm the diagram connects them and marks the connection as stated rather than
inferred.

**Acceptance Scenarios**:

1. **Given** two characters, **When** the author records a relationship with a description,
   **Then** it is retained and shown on both characters.
2. **Given** a relationship between characters who appear in no story together, **When** the site
   is generated, **Then** the network diagram still connects them.
3. **Given** both a recorded relationship and a co-appearance between the same two characters,
   **When** the diagram is generated, **Then** the two are distinguishable and not merged.
4. **Given** a relationship, **When** either character is renamed, **Then** the relationship
   survives intact.

---

### Edge Cases

- A story file has malformed or unparseable frontmatter. The build fails loudly, naming the file
  and the problem; it does not skip the story silently or publish it with empty metadata.
- Two stories resolve to the same address. The build fails and names both files rather than
  letting one overwrite the other.
- A story is missing a title, or the body is empty.
- Two names in the corpus differ only by case, punctuation, or an apostrophe, silently producing
  two characters where one was meant.
- A profile describes a character or location that no story references.
- A story carries an in-world date but no publication date, or the reverse.
- An in-world date is imprecise (a year alone), or falls in a calendar unlike the real one.
- The stories directory is empty, or the settings file is missing entirely.
- A story file is deleted or renamed between builds; its old page must not persist in the output.
- A character is renamed after the site has been published, changing the address of their page.
- A story's body contains raw HTML, or Markdown that is valid but unsupported.
- Non-ASCII characters, accents, and apostrophes appear in names, titles, and tags.
- A single story is dramatically longer than the rest of the collection.
- The portal is started with its working directory pointing somewhere that is not a story
  collection.
- The portal writes a file at the same moment a build is reading it.
- A story file is edited outside the portal while the portal is running.
- A story file is deleted outside the portal while the portal's store still holds it.
- The portal's store is missing, empty, or unreadable at launch and must rebuild from the corpus.
- The exported profile file is hand-edited despite being marked generated.
- A note or relationship refers to a character who is renamed, or who stops appearing in any
  story at all.
- A relationship is recorded between two characters who have never appeared in a story together.
- A character's portal diagram would be empty because they have neither co-appearances nor stated
  relationships.
- The feed is opened with a filter naming a character who does not exist, or who has no published
  stories.
- Every published story lacks an in-world date, leaving the archive's chronology empty and only
  the undated group populated.
- A reader arrives at a filtered feed URL directly, without passing through the diagram.

## Requirements *(mandatory)*

### Functional Requirements

#### Story and configuration format

- **FR-001**: A story MUST exist as a single Markdown file whose metadata is carried in
  frontmatter at the top of that same file. The portal MUST write that file on every save, so the
  on-disk corpus is always current and complete even though the portal's store arbitrates
  authoring.
- **FR-002**: Story metadata MUST support at minimum: a title, a publication date, an optional
  in-world date, the characters appearing in the story, the locations it takes place in, a draft
  flag, and a stable address slug.
- **FR-002a**: The two dates MUST be distinct fields with distinct meanings — when the story was
  written and released, versus when it takes place in the fiction. Neither MUST be inferred from
  the other.
- **FR-003**: A story's address on the published site MUST be derived from an explicit slug in
  its metadata, so that renaming a title does not break existing links.
- **FR-004**: The story body MUST support standard Markdown, covering at minimum headings,
  emphasis, paragraph breaks, blockquotes, lists, and links.
- **FR-005**: A story file MUST remain fully readable and editable in a plain text editor, with
  no export or conversion step. Editing one outside the portal MUST remain a supported workflow,
  reconciled per FR-041.
- **FR-006**: Hand-owned collection settings — the site title and anything else the author
  maintains directly — MUST live in a settings file that the portal never rewrites.
- **FR-006a**: Character and location profiles MUST NOT live in the hand-owned settings file.
  They are owned by the portal's store and exported (FR-038). No file may be partly hand-owned
  and partly generated.
- **FR-007**: Every artifact the *published site* consists of MUST be reproducible from the
  committed files alone — stories, settings, and the exported profiles — and MUST be safe to
  delete. The generator MUST NOT read the portal's store.
- **FR-008**: Story files MUST be the source of truth for the cast. A character, location, or
  tag exists because a story names it; the set of characters, locations, and tags is gathered
  from the corpus, not declared in advance.
- **FR-008a**: A name used by a story MUST NOT require any prior registration, and an unknown
  name MUST NOT be an error.
- **FR-008b**: Profiles MUST be optional enrichment — a description, display name, or ordering
  for a name the stories already use. A profile MUST NOT bring a character or location into
  existence on its own.

#### Authoring store

- **FR-037**: The portal MUST maintain a local store that is authoritative for authoring: it
  arbitrates conflicts, and it holds material with no representation in any story file.
- **FR-038**: The store MUST export everything the generator needs into committed files on every
  save. The generator MUST remain able to build with the store absent, as it is in continuous
  integration.
- **FR-038a**: The export MUST carry only what the published site consumes: stated relationships,
  and display-name overrides for diagram labels.
- **FR-038b**: Profile descriptions MUST NOT be exported. Nothing on the published site displays
  them, and exporting unread material would put private writing into a committed file for no
  reader's benefit.
- **FR-039**: The exported profile file MUST be marked as generated and MUST NOT be hand-edited.
- **FR-040**: The store MUST be excluded from version control and MUST be rebuildable from the
  committed files. Rebuilding MUST restore profiles from the exported file.
- **FR-041**: The portal MUST detect that a story file changed on disk since it last wrote it,
  MUST present both versions, and MUST let the author choose. It MUST NOT silently overwrite
  either side.
- **FR-042**: Losing the store MUST NOT lose any story text. It MAY lose notes, profile
  descriptions, and dismissal decisions — none of which are exported. Relationships and
  display-name overrides survive store loss, since FR-038a exports them.
- **FR-043**: The store MUST NOT hold revision history or autosaved drafts. Version history is
  git's job, over files the portal keeps current.
- **FR-044**: The store MUST persist dismissed candidate profiles, so a dismissed name does not
  resurface as a suggestion.

#### Authoring notes

- **FR-045**: The portal MUST allow attaching private notes to a story, a character, or a
  location.
- **FR-046**: Notes MUST NOT appear anywhere in the generated site, and MUST NOT be exported into
  any committed file.
- **FR-047**: Notes MUST survive renaming the character, location, or story they are attached to.

#### Cast pages (portal only)

- **FR-053**: The portal MUST provide a page for every character, location, and tag. These pages
  are authoring surfaces and MUST NOT be generated into the published site.
- **FR-053b**: A tag's page MUST list every story carrying it, in the same shape as FR-053a. A
  tag page MUST NOT include derived context, relationships, a diagram, or a profile — none of
  those concepts apply to a tag.
- **FR-053a**: A cast page MUST list every story referencing that name in publication order,
  newest first, with drafts marked.
- **FR-054**: A character's page MUST show context derived from the corpus: the locations they
  appear in, the other characters they appear alongside, and their first and last appearance.
- **FR-055**: A character's page MUST show every stated relationship involving them, with its
  description, each linking to the other character.
- **FR-056**: A character's page MUST include a network diagram centred on that character.
- **FR-057**: A character's page MUST gather everything known about them in one place: profile,
  derived context, relationships, and notes.

#### Character relationships

- **FR-048**: The portal MUST allow recording a relationship between two characters, with a
  described nature and a direction where the relationship is not mutual.
- **FR-049**: Relationships MUST be maintainable independently of what any story states, so the
  author can record what is true of the world before it has been written down.
- **FR-050**: Relationships MUST survive renaming either character involved.
- **FR-051**: The system MUST distinguish relationships the author recorded from co-appearances
  derived from stories, and MUST NOT silently merge the two.
- **FR-052**: Recorded relationships MUST be exportable to the published network diagram, and the
  diagram MUST distinguish them from co-appearance connections.

#### Generator

- **FR-009**: The generator MUST accept a directory of story files plus configuration and produce
  a complete static site requiring no application server to view.
- **FR-009a**: The published site MUST consist of exactly four kinds of page: the homepage feed,
  the network diagram, the archive, and one page per published story. The generator MUST NOT
  produce any other page.
- **FR-010**: The generator MUST produce a page for every published story containing its full
  rendered text, title, and dates.
- **FR-010a**: A story page MUST NOT display the characters, locations, or tags it references.
  That metadata drives the diagram and the feed filter; it is not shown to readers on the story
  itself.
- **FR-011**: The homepage MUST be a feed of every published story, ordered by publication date
  with the most recent first.
- **FR-011a**: The feed MUST support narrowing to a single character or location through a query
  string on its own address, applied in the browser. No per-name page is generated.
- **FR-011b**: With JavaScript unavailable the feed MUST display the complete unfiltered
  collection rather than an empty or broken page.
- **FR-011c**: The homepage MUST link to the network diagram and to the archive.
- **FR-012**: The generator MUST exclude every story marked as a draft from all generated output,
  including the feed, the archive, the filter data, and the network.
- **FR-013**: The generator MUST NOT produce character, location, or tag pages. Cast material —
  profiles, relationships, derived context, and notes — belongs to the portal (FR-053).
- **FR-014**: The archive MUST list every published story in in-world chronology, presenting the
  order of the fiction rather than the order of publication. There is no separate timeline page.
- **FR-014a**: The archive MUST remain fully usable without JavaScript.
- **FR-015**: The generator MUST produce a network page presenting characters and locations as
  connected nodes, together with the underlying connection data as a separate machine-readable
  file. This diagram is the centrepiece of the published site.
- **FR-015a**: Selecting a node in the diagram MUST take the reader to the feed narrowed to that
  character or location.
- **FR-016**: The generator MUST be deterministic: identical inputs produce byte-identical
  output.
- **FR-017**: The generator MUST fail loudly on *structurally* malformed input — unparseable
  frontmatter, missing required fields, colliding addresses — identifying the offending file and
  the specific problem, rather than skipping or guessing.
- **FR-017a**: The generator MUST NOT fail on naming inconsistencies. Probable duplicates,
  single-use names, and unfamiliar names are editorial judgments, not structural errors, and MUST
  NOT block publication.
- **FR-017b**: The generator MAY report naming inconsistencies as non-fatal warnings in its build
  output, and MUST publish the site regardless.
- **FR-018**: The generator MUST NOT retain output for stories that have been deleted or renamed
  since the previous build.
- **FR-019**: The generator MUST run unattended as an automated step triggered by pushing to the
  repository, with no interactive input.
- **FR-020**: The generator MUST signal failure in a way that fails the automated build rather
  than publishing a partial site.
- **FR-021**: Every published story MUST be reachable without JavaScript, through the feed and
  through the archive. No story may be reachable only by script.
- **FR-021a**: JavaScript is confined to two uses — the network diagram, and narrowing the feed.
  Both are navigational conveniences layered over content the HTML already contains. Neither may
  be the only route to a story.
- **FR-021b**: Filtering the feed by character is a JavaScript-only convenience, accepted
  deliberately. Readers without JavaScript get the complete feed and the full archive, so no
  writing becomes unreachable — only the shortcut does.
- **FR-022**: The network page MUST detect the absence of JavaScript and offer links to the feed
  and the archive, through which every published story remains reachable.
- **FR-023**: Published stories sharing an in-world date MUST be ordered deterministically by a
  documented tie-break, so that repeated builds agree.
- **FR-023a**: Published stories with no in-world date MUST be omitted from the archive's
  chronology and presented separately as undated, rather than being assigned a position by
  guesswork.
- **FR-023b**: In-world dates MUST tolerate imprecision — a year alone, or a year and month —
  without requiring a fabricated exact day.

#### Authoring portal

- **FR-024**: The portal MUST run locally on the author's machine and be used through a browser.
- **FR-025**: The portal MUST NOT be a component of the published site and MUST NOT be required
  for readers.
- **FR-026**: The portal MUST allow creating a story, writing its body and metadata, and saving
  it as a correctly formatted file in the stories directory.
- **FR-027**: The portal MUST allow opening an existing story for editing, preserving all
  metadata it does not itself manage.
- **FR-028**: The portal MUST refuse to save a story missing required metadata and MUST state
  what is missing.
- **FR-029**: The portal MUST offer the names already used elsewhere in the corpus for selection
  when assigning characters and locations, so that reuse is easier than retyping. Entering a new
  name MUST remain possible without any separate registration step.
- **FR-030**: The portal MUST allow renaming a character, location, or tag across the whole
  corpus. For a character or location, it MUST also allow editing the optional profile describing
  one — tags have no profile to edit.
- **FR-031**: Renaming a character, location, or tag MUST update every story referencing the old
  name, leaving no story still using it.
- **FR-032**: The portal MUST report probable naming mistakes for characters, locations, and tags
  alike: names differing from another only by case, punctuation, whitespace, or a small spelling
  variation.
- **FR-032a**: The portal MUST report profiles describing names that no story uses. Since tags
  have no profiles, this applies only to characters and locations.
- **FR-032b**: The portal MUST show how many stories use each name, across characters, locations,
  and tags, so that single-use names — the usual shape of a typo — are visible.
- **FR-032c**: Editorial review MUST live in the portal, ahead of the build. Every naming check
  the system performs MUST be surfaced while the author is writing, not deferred to publication.
- **FR-033a**: When a name new to the corpus appears in a story's metadata, the portal MUST offer
  a candidate profile for it — a pre-filled draft entry the author can accept, edit, or dismiss.
- **FR-033b**: A candidate profile MUST NOT be recorded until the author accepts
  it, and dismissing one MUST NOT remove the name from the stories using it.
- **FR-033c**: The portal MUST distinguish accepted profiles from names that have no profile, so
  that an unreviewed new name is visible as such.
- **FR-034**: The portal MUST allow triggering a full local build and MUST report build failures
  and their causes in the browser.
- **FR-035**: The portal MUST NOT perform version control operations; committing and pushing
  remain the author's responsibility.
- **FR-036**: The portal MUST operate only on the story collection it was started against, and
  MUST report clearly if started somewhere that is not one.

### Key Entities

- **Story**: A single work of short fiction. Carries a title, a publication date, an optional
  in-world date, a stable slug, a draft flag, the characters and locations it references, and a
  Markdown body. Lives as one file and is the canonical unit of the collection.
- **Character**: A named person recurring across stories. Brought into existence by being named
  in a story rather than by being declared. Appears on the published site only as a diagram node
  and a feed filter; everything known about them lives on their portal page.
- **Location**: A named place recurring across stories. Behaves the same as a character for
  existence and referencing, but is presented as a distinct kind of thing.
- **Tag**: Any other keyword attached to a story for grouping. Not published in the first
  version. Exists the same way a character or location does — by being named in a story — and
  gets the same naming-consistency treatment: duplicate detection, single-use flagging, rename
  across the corpus, and its own listing page in the portal. Unlike a character or location, a
  tag never has a profile, a relationship, or derived context.
- **Collection Settings**: Hand-owned settings governing the collection as a whole, principally
  its title. Never rewritten by the portal, and never the source of a name's existence.
- **Profile**: Optional enrichment for a character or location — description, display name,
  ordering. Owned by the authoring store. Only the display name is exported, for diagram labels;
  the description stays private. Cannot bring a name into existence.
- **Authoring Store**: The portal's local store. Authoritative for authoring: it arbitrates
  file conflicts and holds profiles, notes, relationships, and dismissal decisions. Excluded from
  version control, rebuildable from committed files, never read by the generator.
- **Note**: Private authoring text attached to a story, character, or location. Never published,
  never exported, survives renames.
- **Relationship**: A stated connection between two characters, with a description and an
  optional direction. Maintained independently of what stories say, distinguishable from
  co-appearance, survives renames.
- **Connection Graph**: The derived structure of characters and locations linked by the stories
  they share, underlying the network diagram. Fully rebuildable from the stories.
- **Generated Site**: The complete static output of a build. Disposable and reproducible.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From the network diagram, a reader reaches any character's or location's stories
  in one click.
- **SC-002**: A full build of the entire collection completes in under 60 seconds, so that
  publishing never feels like a wait.
- **SC-003**: Adding a story requires changing no file other than the new story itself, even when
  it introduces characters or locations the collection has never used before.
- **SC-004**: 100% of malformed story files cause a named, actionable build failure rather than
  silently missing or empty content on the published site.
- **SC-005**: Every published story is reachable with JavaScript disabled, through the feed and
  the archive. Only the diagram and the feed filter require it.
- **SC-006**: An author can create and save a complete, valid story through the portal in under
  five minutes without consulting documentation on the file format.
- **SC-007**: Every probable naming mistake in the corpus — near-duplicate spellings, single-use
  names, and profiles no story uses — is reported to the author in one place.
- **SC-010**: A character rename leaves zero occurrences of the old name anywhere in the corpus.
- **SC-011**: Deleting the authoring store loses no story text; the corpus on disk remains
  complete and the site builds unchanged from it.
- **SC-012**: The site builds correctly in an environment where the authoring store has never
  existed.
- **SC-013**: 100% of story files changed outside the portal are detected as divergent rather
  than silently overwritten in either direction.
- **SC-014**: No note text appears anywhere in the generated site or in any committed file.
<!-- SC-015 and SC-016 were retired 2026-08-11 with the character-media split; see
     002-character-media/spec.md. Numbering intentionally not closed up. -->
- **SC-017**: The published site consists of exactly four kinds of page — feed, diagram, archive,
  and story — and the build produces no others.
- **SC-018**: No profile description appears in any committed file or anywhere on the published
  site.
- **SC-008**: Two consecutive builds from unchanged sources produce identical output.
- **SC-009**: The published site remains fully readable if the authoring portal is never run.

## Assumptions

- **Technology is a given, not a finding**: the constitution fixes Python and Flask, and the
  automated build runs as a GitHub Action. These are recorded here as constraints rather than in
  the requirements above, which stay technology-agnostic.
- **Drafts are hidden**: the published site is fully public with no reader accounts, and a story
  marked as a draft is excluded entirely. Carried over from an earlier decision made before the
  architecture changed; it remains compatible with the current design.
- **Publishing is manual**: the author commits and pushes by hand. The build is triggered by the
  push; the portal never touches version control.
- **Single author, single machine**: the portal has no accounts, no concurrent editing, and no
  network exposure beyond the author's own browser.
- **Scale is modest**: the collection is a bounded set of short works, so pagination, search
  indexing, incremental rebuilds, and caching are assumed unnecessary until demonstrated
  otherwise.
- **Slugs are explicit and stable**: each story declares its own address, which does not change
  when its title does.
- **Editorial review belongs to the portal, not the build**: because stories are the source of
  truth for the cast, a misspelled name is valid input and creates a real character. Rather than
  hardening the build against this, all naming judgment lives in the portal, where the author is
  already working and can act on it. The build stays permissive by design: it publishes whatever
  parses, and at most warns. A publication step that refuses to publish over a spelling question
  is the wrong shape for this system.
- **New names produce candidate profiles, not obligations**: a name appearing for the first time
  becomes a suggested profile in the portal. Nothing is recorded until the author accepts it, and
  declining leaves the name working exactly as before. Dismissals persist, so a declined
  suggestion does not resurface.
- **The store is authoritative for authoring; the files are the export boundary**: the portal's
  store arbitrates conflicts and holds material no file represents, but every save writes the
  Markdown, so the corpus on disk is never behind. The generator reads only committed files and
  never the store — which is what lets the build run in CI where the store does not exist.
- **Git is the revision history**: because the files are always current and versioned, the portal
  deliberately holds no revision history and no autosaved drafts. A second history inside the
  tool would be a worse copy of one that already exists.
- **The store is disposable, its unique content is not precious**: losing it costs notes,
  relationships, and dismissals — never fiction. This is the accepted trade for keeping it out of
  version control and avoiding binary merge conflicts.
- **No file is half-owned**: settings are hand-owned and never rewritten; the profile export is
  generated and never hand-edited. Files that are partly both are how sync bugs start.
- **In-world dates are optional, publication dates are not**: every story appears in the feed;
  only those placed in the fiction's chronology appear in the archive's ordering.
- **Archive tie-break**: stories sharing an in-world date are ordered by publication date, then by
  slug, purely for determinism.
- **The published site is deliberately small for now**: a feed, a diagram, an archive, and the
  stories. Everything else the system knows — profiles, relationships, notes, derived context,
  per-character pages — is for the writer. This is a considered first version, not an oversight;
  the material exists and can be published later without restructuring anything, because it
  already lives in the store.
- **Cast pages are the payoff, in the portal**: a character's page gathers their stories, derived
  context, relationships, and notes in one place. It is an authoring surface and is never
  generated into the site.
- **Reachability, not feature parity, is the no-JavaScript promise**: every story stays reachable
  through the feed and the archive without scripting. The diagram and the feed filter are
  navigational conveniences that do require it — a deliberate trade for keeping the published site
  to three pages plus stories, rather than generating a page per name.
- **Portraits and moodboards are deferred, not dropped**: character media (portraits, moodboard
  images) was specified in an earlier draft of this document and was split out on 2026-08-11 into
  [002-character-media](../002-character-media/spec.md) so this first build could ship without an
  image-processing dependency at all. Nothing in this spec references media; `FR-057`'s "gather
  everything known about them" is scoped to what this spec actually defines — profile, derived
  context, relationships, notes — and will grow again when 002 is picked up.
- **One vendored diagram library**: the network page uses a single client-side library committed
  into the repository rather than loaded from a third party at page load. The portal's
  per-character diagram uses the same vendored library.
- **The export shrinks to what is read**: with cast pages unpublished, only stated relationships
  and display names cross the boundary. Descriptions staying private means the committed export
  contains nothing a reader cannot see.
- **Live preview is out of scope**: local building covers the need for now; rendering a single
  story without a full build was considered and deliberately excluded.
- **Writing utilities beyond editing are out of scope**: word counts, revision tracking, and
  similar aids belong to a later specification.
- **Hosting is out of scope**: where the generated site is served from is a deployment decision,
  not part of this feature.
