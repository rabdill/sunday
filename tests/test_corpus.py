"""Parsing, validation, and name normalization.

Frontmatter parsing, tag normalization, and the character/location graph are where
a bad file quietly produces a wrong page instead of an error.
"""

from __future__ import annotations

import datetime as _dt

import pytest

from sunday.corpus import (
    DuplicateSlugError,
    Precision,
    StoryError,
    load_corpus,
    normalize_name,
    parse_story,
    slugify,
)

# ------------------------------------------------------------------ a valid parse


def test_parses_a_complete_story(stories_dir):
    story = parse_story(stories_dir / "the-lighthouse.md")

    assert story.slug == "the-lighthouse"
    assert story.title == "The Lighthouse"
    assert story.published == _dt.date(2026, 8, 4)
    assert story.occurs is not None and str(story.occurs) == "1921-03"
    assert story.characters == ("Mara Vance", "Elias Doyle")
    assert story.locations == ("Portsmouth",)
    assert story.tags == ("epistolary",)
    assert story.draft is False
    assert "The fog came in early" in story.body


def test_unmanaged_frontmatter_keys_are_preserved(stories_dir):
    """Keys the system does not manage must survive untouched."""
    story = parse_story(stories_dir / "the-lighthouse.md")
    assert story.extra == {"mood": "bleak"}


def test_draft_flag_is_read(stories_dir):
    assert parse_story(stories_dir / "unfinished.md").draft is True


def test_absent_optional_fields_default_cleanly(stories_dir):
    story = parse_story(stories_dir / "the-keeper.md")
    assert story.occurs is None
    assert story.tags == ("Epistolary",)
    assert story.extra == {}


# ------------------------------------------------------------- structural failures
#
# Each of these must name the file and the specific problem — a build failure the
# author can act on without opening the source.


@pytest.mark.parametrize(
    ("filename", "expected_phrase"),
    [
        ("unparseable.md", "not valid YAML"),
        ("missing-title.md", "missing required frontmatter field: title"),
        ("empty-body.md", "body is empty"),
        ("no-frontmatter.md", "no frontmatter"),
        ("bad-date.md", "full YYYY-MM-DD date"),
        ("bad-slug.md", "slug must match"),
        ("bad-draft.md", "draft must be true or false"),
        ("bad-occurs.md", "not a real date"),
    ],
)
def test_structural_errors_name_file_and_problem(broken_dir, filename, expected_phrase):
    with pytest.raises(StoryError) as caught:
        parse_story(broken_dir / filename)

    message = str(caught.value)
    assert filename in message, "the error must name the offending file"
    assert expected_phrase in message, f"the error must state the problem; got: {message}"


def test_duplicate_slug_names_both_files(broken_dir, tmp_path):
    """Either file could be the mistake, so blaming one would be a guess."""
    colliding = tmp_path / "stories"
    colliding.mkdir()
    for name in ("collide-a.md", "collide-b.md"):
        (colliding / name).write_text(
            (broken_dir / name).read_text(encoding="utf-8"), encoding="utf-8"
        )

    with pytest.raises(DuplicateSlugError) as caught:
        load_corpus(colliding)

    message = str(caught.value)
    assert "collide-a.md" in message
    assert "collide-b.md" in message
    assert "duplicated-slug" in message


# ----------------------------------------------------------------- partial dates
#
# All three forms, and the sort key that orders the archive.


def test_all_three_date_precisions_parse(corpus):
    by_slug = {s.slug: s for s in corpus.stories}

    year_only = by_slug["the-fog"].occurs
    assert (year_only.year, year_only.month, year_only.day) == (1921, None, None)
    assert year_only.precision is Precision.YEAR

    year_month = by_slug["the-lighthouse"].occurs
    assert (year_month.year, year_month.month, year_month.day) == (1921, 3, None)
    assert year_month.precision is Precision.MONTH

    full = by_slug["letters-home"].occurs
    assert (full.year, full.month, full.day) == (1922, 6, 14)
    assert full.precision is Precision.DAY


def test_partial_dates_are_never_padded_into_a_fabricated_day(corpus):
    """`1921` must stay `1921`. Padding lives only in the sort key."""
    fog = next(s for s in corpus.stories if s.slug == "the-fog")
    assert str(fog.occurs) == "1921"
    assert fog.occurs.day is None
    assert fog.occurs.sort_date == _dt.date(1921, 1, 1)  # ordering only


def test_sort_key_orders_by_date_then_precision(corpus):
    by_slug = {s.slug: s for s in corpus.stories}
    # Same year: the bare year sorts before the more precise March.
    assert by_slug["the-fog"].archive_sort_key < by_slug["the-lighthouse"].archive_sort_key


def test_sort_key_tie_break_is_total_and_deterministic(corpus):
    """Two stories share 1922-06-14; publication date then slug must separate them."""
    by_slug = {s.slug: s for s in corpus.stories}
    a, b = by_slug["letters-home"], by_slug["the-second-letter"]
    assert a.occurs.sort_date == b.occurs.sort_date
    assert a.archive_sort_key != b.archive_sort_key
    # the-second-letter was published earlier, so it sorts first
    assert b.archive_sort_key < a.archive_sort_key


# ------------------------------------------------------------------ normalization
#
# The display/normalized split is the crux: compare loosely, store exactly.


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Mara Vance", "mara vance"),
        ("MARA VANCE", "mara vance"),
        ("mara  vance", "mara vance"),
        ("  Mara Vance  ", "mara vance"),
        ("Mara Vance.", "mara vance"),
        ("O'Brien", "obrien"),
        ("Café Verlaine", "cafe verlaine"),
        ("Saint-Élie", "saintelie"),
    ],
)
def test_normalization_folds_case_punctuation_whitespace_and_accents(raw, expected):
    assert normalize_name(raw) == expected


def test_normalization_never_rewrites_the_display_form(corpus):
    """The system compares loosely but must store exactly what the author typed."""
    names = {n.display for n in corpus.names_of_kind("location")}
    assert "Café Verlaine" in names, "the accent must survive verbatim"

    tags = {n.display for n in corpus.names_of_kind("tag")}
    assert {"epistolary", "Epistolary"} <= tags, "both spellings are kept as written"


def test_near_duplicate_names_stay_distinct_until_the_author_decides(corpus):
    """A typo creates a real second character. Detecting it is review's job, not this module's."""
    characters = {n.display for n in corpus.names_of_kind("character")}
    assert "Mara Vance" in characters
    assert "Mara Vanse" in characters


def test_same_string_under_two_kinds_is_two_names(tmp_path):
    path = tmp_path / "s.md"
    path.write_text(
        "---\nslug: s\ntitle: S\npublished: 2026-01-01\n"
        "characters:\n  - Avon\nlocations:\n  - Avon\n---\n\nBody.\n",
        encoding="utf-8",
    )
    loaded = load_corpus(tmp_path)
    assert loaded.name("character", "Avon") is not None
    assert loaded.name("location", "Avon") is not None
    assert loaded.name("character", "Avon") != loaded.name("location", "Avon")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Mara Vance", "mara-vance"),
        ("Café Verlaine", "cafe-verlaine"),
        ("O'Brien", "obrien"),
        ("Lighthouse  Point", "lighthouse-point"),
    ],
)
def test_slugify_produces_url_safe_segments(raw, expected):
    assert slugify(raw) == expected


def test_distinct_names_never_share_a_slug(tmp_path):
    """Silently merging two characters would be exactly the quiet wrongness we test against."""
    path = tmp_path / "s.md"
    path.write_text(
        "---\nslug: s\ntitle: S\npublished: 2026-01-01\n"
        "locations:\n  - Café Verlaine\n  - Cafe Verlaine\n---\n\nBody.\n",
        encoding="utf-8",
    )
    loaded = load_corpus(tmp_path)
    locations = loaded.names_of_kind("location")
    assert len(locations) == 2, "the two spellings are distinct names"
    assert len({n.slug for n in locations}) == 2, "and must not collide on one slug"


# ------------------------------------------------------------------ corpus loading


def test_corpus_loads_every_story_including_drafts(corpus):
    assert len(corpus.stories) == 7
    assert len(corpus.published()) == 6, "one story is a draft"


def test_feed_order_is_newest_published_first(corpus):
    order = [s.slug for s in corpus.feed_order()]
    assert order == [
        "the-lighthouse",
        "the-fog",
        "letters-home",
        "the-keeper",
        "winter-crossing",
        "the-second-letter",
    ]
    assert "unfinished" not in order, "drafts never appear in the feed"


def test_stories_for_a_name_excludes_drafts_by_default(corpus):
    mara = corpus.name("character", "Mara Vance")
    published = [s.slug for s in corpus.stories_for(mara)]
    with_drafts = [s.slug for s in corpus.stories_for(mara, include_drafts=True)]

    assert "unfinished" not in published
    assert "unfinished" in with_drafts


def test_a_character_appearing_only_in_a_draft_has_no_published_stories(corpus):
    ghost = corpus.name("character", "Ghost Character")
    assert ghost is not None, "the name exists in the corpus"
    assert corpus.stories_for(ghost) == (), "but nothing published references it"


def test_missing_stories_directory_is_an_error(tmp_path):
    from sunday.corpus import CorpusError

    with pytest.raises(CorpusError, match="stories directory not found"):
        load_corpus(tmp_path / "nope")
