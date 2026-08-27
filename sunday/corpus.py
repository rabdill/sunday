"""Corpus loading: frontmatter parsing, the Story model, and name extraction.

Both programs share this module. The generator reads a corpus and renders it; the
portal reads the same corpus and edits it. Neither may assume the other has run.

Two ideas here carry most of the weight:

*Structural errors fail loudly; editorial ones do not.* Unparseable frontmatter, a
missing title, a colliding slug — these raise, naming the file and the problem
(FR-017). A misspelled character name is valid input and creates a real character
(FR-008a); catching that is the portal's job, not this module's.

*Names are compared normalized but stored verbatim.* `Name.normalized` exists only
so two spellings can be recognized as probably-the-same. `Name.display` is exactly
what the author wrote and is never rewritten by the system.
"""

from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Iterable, Literal

import yaml

Kind = Literal["character", "location", "tag"]
KINDS: tuple[Kind, ...] = ("character", "location", "tag")

#: Frontmatter keys this module manages. Anything else is preserved in `Story.extra`
#: and round-trips untouched through the portal (FR-027).
MANAGED_KEYS = frozenset(
    {"slug", "title", "published", "occurs", "characters", "locations", "tags", "draft"}
)

SLUG_PATTERN = re.compile(r"^[a-z0-9-]+$")
_FENCE = re.compile(r"^---\s*$", re.MULTILINE)


# --------------------------------------------------------------------------- errors


class CorpusError(Exception):
    """Base for every structural failure in this module.

    Every subclass names the offending file and states the specific problem, so a
    build failure is actionable without opening the source (FR-017, SC-004).
    """


class StoryError(CorpusError):
    def __init__(self, path: Path | str, problem: str) -> None:
        self.path = Path(path)
        self.problem = problem
        super().__init__(f"{self.path}: {problem}")


class DuplicateSlugError(CorpusError):
    """Two stories claim one address. Names *both* files — either could be the mistake."""

    def __init__(self, slug: str, first: Path, second: Path) -> None:
        self.slug = slug
        self.first = Path(first)
        self.second = Path(second)
        super().__init__(
            f"duplicate slug {slug!r} claimed by both {self.first} and {self.second}"
        )


# ----------------------------------------------------------------------- partial date


class Precision(IntEnum):
    """How exact an in-world date is. Ordering matters: it is part of the sort key."""

    YEAR = 0
    MONTH = 1
    DAY = 2


@dataclass(frozen=True, order=False)
class PartialDate:
    """An in-world date that may be no more precise than the author knows.

    Fiction rarely carries an exact day, so `1921` and `March 1921` are first-class
    rather than padded into a fabricated `1921-01-01` (FR-023b). The padding exists
    only inside `sort_date`, for ordering — never for display.
    """

    year: int
    month: int | None = None
    day: int | None = None

    @property
    def precision(self) -> Precision:
        if self.day is not None:
            return Precision.DAY
        if self.month is not None:
            return Precision.MONTH
        return Precision.YEAR

    @property
    def sort_date(self) -> _dt.date:
        """Earliest instant the date could refer to. Ordering only, never displayed."""
        return _dt.date(self.year, self.month or 1, self.day or 1)

    def __str__(self) -> str:
        if self.day is not None:
            return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"
        if self.month is not None:
            return f"{self.year:04d}-{self.month:02d}"
        return f"{self.year:04d}"


def parse_partial_date(value: Any, *, path: Path | str, field_name: str) -> PartialDate:
    """Parse `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` into a `PartialDate`.

    YAML has already coerced some of these: a bare `1921` arrives as `int`, a full
    `1921-03-04` as `datetime.date`, and `1921-03` — not a valid YAML date — as `str`.
    All three are accepted; anything else is a structural error.
    """
    if isinstance(value, _dt.datetime):
        return PartialDate(value.year, value.month, value.day)
    if isinstance(value, _dt.date):
        return PartialDate(value.year, value.month, value.day)
    if isinstance(value, int):
        if not 1 <= value <= 9999:
            raise StoryError(path, f"{field_name} year out of range: {value}")
        return PartialDate(value)
    if isinstance(value, str):
        text = value.strip()
        for pattern, builder in (
            (r"^(\d{4})$", lambda m: PartialDate(int(m[1]))),
            (r"^(\d{4})-(\d{2})$", lambda m: PartialDate(int(m[1]), int(m[2]))),
            (
                r"^(\d{4})-(\d{2})-(\d{2})$",
                lambda m: PartialDate(int(m[1]), int(m[2]), int(m[3])),
            ),
        ):
            match = re.match(pattern, text)
            if match:
                partial = builder(match)
                try:  # reject 1921-13 and 1921-02-30 rather than silently accepting
                    partial.sort_date
                    if partial.day is not None:
                        _dt.date(partial.year, partial.month, partial.day)
                except ValueError as exc:
                    raise StoryError(path, f"{field_name} is not a real date: {text!r}") from exc
                return partial
        raise StoryError(
            path,
            f"{field_name} must be YYYY, YYYY-MM, or YYYY-MM-DD; got {text!r}",
        )
    raise StoryError(path, f"{field_name} must be a date, got {type(value).__name__}")


def parse_full_date(value: Any, *, path: Path | str, field_name: str) -> _dt.date:
    """Parse a publication date. Unlike `occurs`, this must be exact (FR-002a)."""
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, str):
        try:
            return _dt.date.fromisoformat(value.strip())
        except ValueError as exc:
            raise StoryError(
                path, f"{field_name} must be a full YYYY-MM-DD date; got {value!r}"
            ) from exc
    raise StoryError(
        path, f"{field_name} must be a full YYYY-MM-DD date, got {type(value).__name__}"
    )


# ------------------------------------------------------------------------ frontmatter


def split_frontmatter(text: str, *, path: Path | str) -> tuple[str, str]:
    """Split a story file into its frontmatter block and its body.

    Twelve lines instead of a dependency (see research.md). The file must open with a
    `---` fence; the block ends at the next one.
    """
    stripped = text.lstrip("﻿")
    if not stripped.startswith("---"):
        raise StoryError(path, "no frontmatter: file must begin with a '---' fence")
    after_open = stripped[3:]
    if after_open.startswith("\n"):
        after_open = after_open[1:]
    closing = _FENCE.search(after_open)
    if closing is None:
        raise StoryError(path, "unterminated frontmatter: no closing '---' fence")
    return after_open[: closing.start()], after_open[closing.end() :].lstrip("\n")


# ------------------------------------------------------------------------------ story


@dataclass
class Story:
    """One work of short fiction. The canonical unit of the collection."""

    slug: str
    title: str
    published: _dt.date
    body: str
    occurs: PartialDate | None = None
    characters: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    draft: bool = False
    #: Frontmatter keys this system does not manage, preserved verbatim (FR-027).
    extra: dict[str, Any] = field(default_factory=dict)
    #: For error messages only. Never rendered.
    source_path: Path | None = None

    def names_of_kind(self, kind: Kind) -> tuple[str, ...]:
        return {
            "character": self.characters,
            "location": self.locations,
            "tag": self.tags,
        }[kind]

    @property
    def archive_sort_key(self) -> tuple[_dt.date, int, _dt.date, str]:
        """Total order for the archive. Documented tie-break, so builds agree (FR-023).

        Only meaningful for stories that have an `occurs`; undated stories are
        partitioned out before sorting rather than given a fabricated position
        (FR-023a).
        """
        assert self.occurs is not None, "archive_sort_key requires an in-world date"
        return (self.occurs.sort_date, int(self.occurs.precision), self.published, self.slug)


def _string_list(value: Any, *, path: Path | str, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):  # a lone name written without a list dash
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for item in value:
            if not isinstance(item, (str, int, float)):
                raise StoryError(path, f"{field_name} entries must be text, got {item!r}")
            text = str(item).strip()
            if text:
                out.append(text)
        return tuple(out)
    raise StoryError(path, f"{field_name} must be a list of names, got {type(value).__name__}")


def parse_story(path: Path | str, text: str | None = None) -> Story:
    """Parse one story file, raising `StoryError` on any structural problem."""
    path = Path(path)
    if text is None:
        text = path.read_text(encoding="utf-8")

    meta_text, body = split_frontmatter(text, path=path)

    try:
        meta = yaml.safe_load(meta_text)
    except yaml.YAMLError as exc:
        detail = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
        raise StoryError(path, f"frontmatter is not valid YAML: {detail}") from exc

    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise StoryError(path, "frontmatter must be a mapping of keys to values")

    for required in ("slug", "title", "published"):
        if meta.get(required) in (None, ""):
            raise StoryError(path, f"missing required frontmatter field: {required}")

    slug = str(meta["slug"]).strip()
    if not SLUG_PATTERN.match(slug):
        raise StoryError(
            path, f"slug must match [a-z0-9-]+ (lowercase, digits, hyphens); got {slug!r}"
        )

    if not body.strip():
        raise StoryError(path, "body is empty: a story needs text")

    draft = meta.get("draft", False)
    if not isinstance(draft, bool):
        raise StoryError(path, f"draft must be true or false, got {draft!r}")

    occurs = None
    if meta.get("occurs") not in (None, ""):
        occurs = parse_partial_date(meta["occurs"], path=path, field_name="occurs")

    return Story(
        slug=slug,
        title=str(meta["title"]).strip(),
        published=parse_full_date(meta["published"], path=path, field_name="published"),
        body=body,
        occurs=occurs,
        characters=_string_list(meta.get("characters"), path=path, field_name="characters"),
        locations=_string_list(meta.get("locations"), path=path, field_name="locations"),
        tags=_string_list(meta.get("tags"), path=path, field_name="tags"),
        draft=draft,
        extra={k: v for k, v in meta.items() if k not in MANAGED_KEYS},
        source_path=path,
    )


# ------------------------------------------------------------------------------ names


_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def normalize_name(text: str) -> str:
    """Fold a name for *comparison only*. The display form is never rewritten.

    Casefold, strip accents, drop punctuation and apostrophes, collapse whitespace.
    This is what lets "Mara Vance" and "mara vance." be recognized as probably the
    same person without the system ever changing what the author typed.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    folded = without_marks.casefold()
    return _SPACE.sub(" ", _PUNCT.sub("", folded)).strip()


def slugify(text: str) -> str:
    """Derive a URL-safe segment from a name, for filter query strings and node ids.

    Apostrophes are dropped rather than hyphenated, so "O'Brien" reads as `obrien`
    and not `o-brien` — matching how `normalize_name` treats them.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(c for c in decomposed if not unicodedata.combining(c))
    ascii_only = without_marks.encode("ascii", "ignore").decode("ascii")
    without_quotes = re.sub(r"['‘’\"]", "", ascii_only)
    slug = re.sub(r"[^a-z0-9]+", "-", without_quotes.casefold()).strip("-")
    return slug or "unnamed"


@dataclass(frozen=True)
class Name:
    """A character, location, or tag, as the corpus uses it.

    Exists because a story names it (FR-008) — never because it was declared.

    **One distinct spelling is one Name.** "epistolary" and "Epistolary" are two
    Names, not one, because the spec is explicit that a typo silently produces a
    second character rather than an error — and detecting that pair is the entire
    point of User Story 4. `normalized` exists so review can recognize the two as
    probably-the-same (FR-032); it is never the identity of a name.
    """

    display: str
    normalized: str
    kind: Kind
    slug: str

    @property
    def key(self) -> tuple[Kind, str]:
        return (self.kind, self.display)


# ----------------------------------------------------------------------------- corpus


@dataclass
class Corpus:
    """Every story, plus the names they use. Read-only once loaded.

    The portal mutates *files and store*, then reloads — an in-memory copy is never
    allowed to become authoritative.
    """

    stories: tuple[Story, ...]
    names: dict[tuple[Kind, str], Name]
    _by_name: dict[tuple[Kind, str], tuple[Story, ...]]
    stories_dir: Path | None = None

    # -- stories

    def published(self) -> tuple[Story, ...]:
        """Non-draft stories only. Everything the generator emits starts here (FR-012)."""
        return tuple(s for s in self.stories if not s.draft)

    def by_slug(self, slug: str) -> Story | None:
        return next((s for s in self.stories if s.slug == slug), None)

    def feed_order(self, *, include_drafts: bool = False) -> tuple[Story, ...]:
        """Publication order, newest first (FR-011). Ties break by slug for determinism."""
        pool = self.stories if include_drafts else self.published()
        return tuple(sorted(pool, key=lambda s: (s.published, s.slug), reverse=True))

    # -- names

    def name(self, kind: Kind, display: str) -> Name | None:
        """Look up a name by its exact spelling."""
        return self.names.get((kind, display.strip()))

    def name_by_slug(self, kind: Kind, slug: str) -> Name | None:
        """Look up a name by its URL segment — how portal routes address one."""
        return next(
            (n for n in self.names.values() if n.kind == kind and n.slug == slug), None
        )

    def names_of_kind(self, kind: Kind) -> tuple[Name, ...]:
        return tuple(
            sorted(
                (n for n in self.names.values() if n.kind == kind),
                key=lambda n: (n.normalized, n.display),
            )
        )

    def all_names(self) -> tuple[Name, ...]:
        return tuple(
            sorted(self.names.values(), key=lambda n: (n.kind, n.normalized, n.display))
        )

    def stories_for(self, name: Name, *, include_drafts: bool = False) -> tuple[Story, ...]:
        """Every story referencing a name, newest published first (FR-053a)."""
        found = self._by_name.get(name.key, ())
        if not include_drafts:
            found = tuple(s for s in found if not s.draft)
        return tuple(sorted(found, key=lambda s: (s.published, s.slug), reverse=True))

    def use_count(self, name: Name, *, include_drafts: bool = True) -> int:
        """How many stories use this name — single use is the usual shape of a typo."""
        return len(self.stories_for(name, include_drafts=include_drafts))


def _index_names(stories: Iterable[Story]) -> tuple[
    dict[tuple[Kind, str], Name], dict[tuple[Kind, str], tuple[Story, ...]]
]:
    """Gather every name the corpus uses, keyed by exact spelling.

    Two spellings are two names. Collapsing them on the normalized form would make a
    case-only typo invisible — and finding that typo is exactly what User Story 4 is
    for. Review compares the normalized forms and offers a rename; this index just
    reports, faithfully, what the corpus says.

    Distinct names that would slugify identically ("Café Verlaine" and "Cafe
    Verlaine", or "epistolary" and "Epistolary") get a deterministic suffix rather
    than colliding on one URL, which would silently merge two names' stories.
    """
    members: dict[tuple[Kind, str], list[Story]] = {}

    for story in sorted(stories, key=lambda s: s.slug):
        for kind in KINDS:
            for display in story.names_of_kind(kind):
                display = display.strip()
                if not display or not normalize_name(display):
                    continue
                members.setdefault((kind, display), []).append(story)

    by_base: dict[tuple[Kind, str], list[tuple[Kind, str]]] = {}
    for key in sorted(members):
        by_base.setdefault((key[0], slugify(key[1])), []).append(key)

    names: dict[tuple[Kind, str], Name] = {}
    for (kind, base), keys in by_base.items():
        # When spellings collide on one slug, the most-used one keeps the clean URL.
        # Sorting by name alone would hand it to whichever sorts first in ASCII,
        # which is arbitrary from the author's point of view — a single stray
        # "Epistolary" would outrank the "epistolary" on most of the corpus.
        ordered = sorted(keys, key=lambda k: (-len(members[k]), k[1]))
        for position, key in enumerate(ordered):
            slug = base if position == 0 else f"{base}-{position + 1}"
            names[key] = Name(
                display=key[1],
                normalized=normalize_name(key[1]),
                kind=kind,
                slug=slug,
            )

    return names, {k: tuple(v) for k, v in members.items()}


def load_corpus(stories_dir: Path | str) -> Corpus:
    """Read every `.md` under `stories_dir` into a `Corpus`.

    Raises `DuplicateSlugError` naming *both* files when two stories claim one
    address — either could be the mistake, so blaming one would be a guess.
    """
    stories_dir = Path(stories_dir)
    if not stories_dir.is_dir():
        raise CorpusError(f"stories directory not found: {stories_dir}")

    stories: list[Story] = []
    seen: dict[str, Path] = {}
    for path in sorted(stories_dir.rglob("*.md")):
        story = parse_story(path)
        if story.slug in seen:
            raise DuplicateSlugError(story.slug, seen[story.slug], path)
        seen[story.slug] = path
        stories.append(story)

    names, by_name = _index_names(stories)
    return Corpus(
        stories=tuple(stories),
        names=names,
        _by_name=by_name,
        stories_dir=stories_dir,
    )
