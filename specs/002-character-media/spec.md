# Feature Specification: Character Portraits and Moodboards

**Feature Branch**: `002-character-media`

**Created**: 2026-08-11

**Status**: Draft — deferred, not yet scheduled

**Input**: User description: "Private reference images for characters — a portrait and a
moodboard — that help the author write but never reach the published site."

**Depends on**: [001-story-site-and-authoring](../001-story-site-and-authoring/spec.md). This
feature attaches to characters and locations as they exist there (the authoring store, the cast
pages, the portal). It has no meaning on its own.

**Why this is a separate spec**: 001 originally included this material directly. It was split
out on 2026-08-11 to keep 001's first build simple — image handling was, by a wide margin, the
most volatile part of that spec: five back-and-forth answers just to settle on formats, privacy,
storage location, and a resize option, and it was the one piece of work that reversed an already-
made architectural decision (adding an image-processing dependency the plan had explicitly
rejected). None of that instability reflects on the feature's value — it reflects that it's a
second, genuinely separate concern from getting stories published. This document exists so the
decisions already made are not lost, and so this can be picked up as its own well-scoped unit of
work whenever it's actually needed.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Give a character a portrait (Priority: P1)

The author is writing about a character and wants a single reference image — a face, a sketch, a
photo that captures how they picture this person — attached to that character, visible only to
the author.

**Why this priority**: The simplest, most self-contained piece of this feature. A moodboard is
naturally an extension of "one image," not a prerequisite for it.

**Independent Test**: Attach a portrait to a character in the portal, rebuild the published site,
and confirm no trace of the image exists anywhere in the output or in any committed file.

**Acceptance Scenarios**:

1. **Given** a character with no portrait, **When** the author uploads one, **Then** it is shown
   whenever that character is viewed in the portal.
2. **Given** a character with a portrait, **When** the author uploads a new one, **Then** it
   replaces the old one — a character has at most one portrait at a time.
3. **Given** any portrait, **When** the published site is built, **Then** no image, filename, or
   reference to it appears anywhere in the output or in any file committed to the repository.
4. **Given** a portrait attached to a character, **When** that character is renamed, **Then** the
   portrait remains attached to them under the new name.
5. **Given** the author's local authoring database is deleted and rebuilt from the repository,
   **When** the rebuild completes, **Then** the portrait is still there.

---

### User Story 2 - Build a moodboard for a character (Priority: P2)

The author gathers a handful of images that evoke a character — not a single defining portrait,
but a scattered set of references — and keeps them together, each with an optional note about
why it's there.

**Why this priority**: A real convenience for character development, but strictly additive to
User Story 1; nothing else depends on it.

**Independent Test**: Attach three moodboard images with captions to a character, reorder them,
delete one, and confirm the remaining two and their captions and order persist correctly and
never appear in the published output.

**Acceptance Scenarios**:

1. **Given** a character, **When** the author adds an image to their moodboard, **Then** it
   appears alongside any others already there.
2. **Given** a moodboard image, **When** the author adds a caption, **Then** the caption is shown
   with the image.
3. **Given** several moodboard images, **When** the author reorders them, **Then** the new order
   is retained the next time the character is viewed.
4. **Given** a moodboard image, **When** the author removes it, **Then** it no longer appears, and
   the remaining images keep their relative order.
5. **Given** any moodboard content, **When** the published site is built, **Then** none of it —
   images, captions, or the fact that a moodboard exists — appears anywhere in the output or in
   any committed file.

---

### Edge Cases

- An image file referenced by a portrait or moodboard entry is deleted from where it's stored,
  outside the application, while the reference to it still exists.
- An uploaded file is not actually a supported image format, or is corrupted.
- An uploaded photo is very large, either in dimensions or in file size.
- A photo comes directly from an iPhone in its native format, which most browsers cannot display
  without conversion.
- A character with a portrait or moodboard is renamed, or later stops appearing in any story.
- A character's profile is deleted while they still have a portrait or moodboard attached.
- The author's local authoring database is lost and rebuilt from the repository, which — per
  001 — does not preserve everything. Whether media survives that rebuild is a decision this spec
  must make explicitly (see Assumptions).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow attaching exactly one portrait image to a character. Uploading
  a new portrait MUST replace any existing one.
- **FR-002**: The system MUST allow attaching an ordered collection of moodboard images to a
  character, each with an optional caption.
- **FR-003**: The author MUST be able to reorder moodboard images and remove any of them
  individually.
- **FR-004**: The system MUST accept common photo formats, including the format iPhone cameras
  produce natively (HEIC), without requiring the author to convert a file before uploading it.
- **FR-005**: Every uploaded image MUST be viewable within the portal regardless of its original
  format. A format not displayable by ordinary web browsers MUST be converted to one that is,
  automatically, at upload time.
- **FR-006**: The system MUST offer an option, enabled by default, to reduce an oversized image's
  dimensions on upload, and MUST let the author turn this off for a given upload.
- **FR-007**: No portrait, moodboard image, or caption MUST ever appear in the published site or
  in any file committed to version control, under any circumstance. This material is exclusively
  for the author's own use.
- **FR-008**: Portrait and moodboard images MUST be stored outside of version control.
- **FR-009**: Removing a character's profile MUST NOT silently delete their portrait or moodboard.
  The author MUST be told what will happen and MUST choose before anything is removed.
- **FR-010**: A portrait or moodboard entry whose underlying image file has gone missing MUST be
  reported to the author as missing, not displayed as a broken or blank image.
- **FR-011**: A portrait or moodboard image MUST remain attached to its character across a rename
  of that character.
- **FR-012**: Portrait and moodboard images, their captions, and their positions MUST survive a
  rebuild of the author's local authoring database from the repository — this is the one part of
  that rebuild explicitly required not to lose anything, since a gathered set of reference images
  is far harder to reassemble from scratch than a note or a decision can be.

### Key Entities

- **Portrait**: A single reference image attached to a character. At most one per character;
  replacing it discards the previous one.
- **Moodboard Image**: One entry in an ordered collection of reference images attached to a
  character, with an optional caption. A character may have any number of these.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero portrait images, moodboard images, captions, or references to any of them
  appear in the published site or in any committed file, under any test corpus.
- **SC-002**: An author can attach a portrait taken directly from an iPhone, with no manual
  conversion step, and see it displayed correctly.
- **SC-003**: Rebuilding the local authoring database from the repository preserves 100% of
  portraits and moodboard entries, including captions and ordering.
- **SC-004**: A character's portrait and moodboard remain correctly attached after that character
  is renamed.

## Assumptions

- **This is additive to 001, not a modification of it**: nothing here changes how stories, the
  cast, notes, or relationships work. It attaches new material to characters that already exist
  under 001's model.
- **Privacy is absolute, not a default**: unlike other authoring material in 001 (which is simply
  never exported today, but conceivably could be later), FR-007 treats "never reaches the
  published site" as a permanent property of this feature, not a current setting.
- **Formats and resize threshold carry over known answers from 001's exploratory work**: accepted
  formats (common web formats plus HEIC) and a default-on resize option were both already decided
  during 001's fourth clarification session before this material was split out. A specific resize
  threshold (a 2000-pixel longer edge, in that earlier discussion) is a planning-level default,
  not fixed here, and can be revisited without consequence to this spec.
- **Image processing requires a real dependency**: converting HEIC to a displayable format and
  resizing on upload cannot be done without image-processing capability the rest of 001
  deliberately avoided taking on. That tradeoff is inherent to this feature and is why it was
  worth separating: 001 without it needs no such dependency at all.
- **Storage location is a planning decision**: where images physically live (alongside the
  authoring database, inside it, or elsewhere) is deferred to the planning phase for this feature.
  FR-008 and FR-012 constrain the answer — outside version control, survives a database rebuild —
  without dictating the mechanism.
- **No image editing**: cropping, filters, and manual thumbnail management are out of scope. The
  one automatic resize in FR-006 is the entire extent of image manipulation this feature performs.
- **Scale is small**: a handful of images per character, for a bounded personal collection. No
  requirement here anticipates galleries at any larger scale.
