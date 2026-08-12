"""Writing and editing stories, and reconciling files edited outside the portal.

A save is not complete until three things land: the file, the store row with the
hash of exactly those bytes, and — when relationships or display names changed —
the `cast.yml` export.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..corpus import Story, StoryError, parse_partial_date, parse_story
from ..store import ConflictState
from ..writer import atomic_write, story_path, write_story
from . import current_corpus, current_store, paths

bp = Blueprint("stories", __name__, url_prefix="/stories")


@dataclass
class FormValues:
    """Whatever the author typed, valid or not, so a rejected save is not lost."""

    slug: str = ""
    title: str = ""
    published: str = ""
    occurs: str = ""
    characters: str = ""
    locations: str = ""
    tags: str = ""
    draft: bool = False
    body: str = ""

    @classmethod
    def from_request(cls) -> "FormValues":
        form = request.form
        return cls(
            slug=form.get("slug", "").strip(),
            title=form.get("title", "").strip(),
            published=form.get("published", "").strip(),
            occurs=form.get("occurs", "").strip(),
            characters=form.get("characters", ""),
            locations=form.get("locations", ""),
            tags=form.get("tags", ""),
            draft=bool(form.get("draft")),
            body=form.get("body", ""),
        )

    @classmethod
    def from_story(cls, story: Story) -> "FormValues":
        return cls(
            slug=story.slug,
            title=story.title,
            published=story.published.isoformat(),
            occurs=str(story.occurs) if story.occurs else "",
            characters="\n".join(story.characters),
            locations="\n".join(story.locations),
            tags="\n".join(story.tags),
            draft=story.draft,
            body=story.body,
        )


def _lines(value: str) -> tuple[str, ...]:
    seen: list[str] = []
    for line in value.replace(",", "\n").splitlines():
        cleaned = line.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return tuple(seen)


def _suggestions():
    """Names already in the corpus, offered so reuse is easier than retyping (FR-029)."""
    corpus = current_corpus()
    return {
        kind: [name.display for name in corpus.names_of_kind(kind)]
        for kind in ("character", "location", "tag")
    }


def _to_story(values: FormValues, existing: Story | None) -> tuple[Story | None, list[str]]:
    """Build a `Story` from form input, collecting every problem rather than the first."""
    problems: list[str] = []

    if not values.title:
        problems.append("A title is required.")
    if not values.slug:
        problems.append("A slug is required — it is the story's permanent address.")
    if not values.body.strip():
        problems.append("The body is empty; a story needs text.")

    published = None
    if not values.published:
        problems.append("A publication date is required.")
    else:
        try:
            published = _dt.date.fromisoformat(values.published)
        except ValueError:
            problems.append("The publication date must be YYYY-MM-DD.")

    occurs = None
    if values.occurs:
        try:
            occurs = parse_partial_date(values.occurs, path="(form)", field_name="occurs")
        except StoryError:
            problems.append(
                "The in-world date must be YYYY, YYYY-MM, or YYYY-MM-DD — "
                "imprecision is fine, invention is not."
            )

    if problems or published is None:
        return None, problems

    return (
        Story(
            slug=values.slug,
            title=values.title,
            published=published,
            body=values.body,
            occurs=occurs,
            characters=_lines(values.characters),
            locations=_lines(values.locations),
            tags=_lines(values.tags),
            draft=values.draft,
            extra=dict(existing.extra) if existing else {},
            source_path=existing.source_path if existing else None,
        ),
        [],
    )


# ------------------------------------------------------------------------ listing


@bp.get("/")
def index():
    corpus = current_corpus()
    states = current_store().scan(corpus)

    # A store row whose file has vanished — deleted or renamed outside the portal.
    # Reported rather than quietly forgotten, since the store is not the authority
    # on what exists; the files are.
    known = {story.slug for story in corpus.stories}
    vanished = tuple(
        state for slug, state in sorted(states.items())
        if slug not in known and state.state is ConflictState.MISSING
    )

    return render_template(
        "portal/stories.html",
        stories=corpus.feed_order(include_drafts=True),
        states=states,
        vanished=vanished,
    )


@bp.post("/<slug>/forget")
def forget(slug: str):
    """Drop a store row for a story whose file is gone."""
    current_store().forget_story(slug)
    flash(f"Forgot “{slug}”. Its file was already gone.", "success")
    return redirect(url_for("stories.index"))


# ------------------------------------------------------------------------- forms


@bp.get("/new")
def new():
    return render_template(
        "portal/story_form.html",
        values=FormValues(published=_dt.date.today().isoformat()),
        suggestions=_suggestions(),
        problems=[],
        is_new=True,
    )


@bp.get("/<slug>/edit")
def edit(slug: str):
    corpus = current_corpus()
    story = corpus.by_slug(slug)
    if story is None:
        abort(404)

    # A diverged file is not editable until the author has chosen a side (FR-041):
    # saving over it would silently discard whichever version they meant to keep.
    state = current_store().state_of(slug, story.source_path)
    if state.blocked:
        return redirect(url_for("stories.conflict", slug=slug))

    store = current_store()
    story_id = store.story_id(slug)
    return render_template(
        "portal/story_form.html",
        values=FormValues.from_story(story),
        suggestions=_suggestions(),
        problems=[],
        is_new=False,
        story=story,
        notes=store.notes_for("story", story_id) if story_id else (),
        note_target_kind="story",
        note_target_ref=slug,
    )


@bp.post("/<slug>")
def save(slug: str):
    corpus = current_corpus()
    store = current_store()
    existing = corpus.by_slug(slug)
    is_new = existing is None

    if existing is not None:
        state = store.state_of(slug, existing.source_path)
        if state.blocked:
            return redirect(url_for("stories.conflict", slug=slug))

    values = FormValues.from_request()
    story, problems = _to_story(values, existing)

    if story is None:
        # Nothing is written, and the form comes back with what was typed (FR-028).
        return (
            render_template(
                "portal/story_form.html",
                values=values,
                suggestions=_suggestions(),
                problems=problems,
                is_new=is_new,
                story=existing,
            ),
            400,
        )

    target = existing.source_path if existing else story_path(paths().stories, story)
    if is_new and target.exists():
        return (
            render_template(
                "portal/story_form.html",
                values=values,
                suggestions=_suggestions(),
                problems=[f"A file already exists at {target.name}. Choose a different slug."],
                is_new=True,
            ),
            400,
        )

    written = write_story(target, story)
    store.record_write(story.slug, target, written)

    if existing is not None and story.slug != existing.slug:
        store.forget_story(existing.slug)

    # Re-read from disk so a newly typed name gains its subject row immediately.
    store.sync_subjects(_reloaded_corpus())
    flash(f"Saved “{story.title}”.", "success")
    return redirect(url_for("stories.edit", slug=story.slug))


def _reloaded_corpus():
    """Re-read from disk after a write, so subject sync sees the new names."""
    from ..corpus import load_corpus

    return load_corpus(paths().stories)


# --------------------------------------------------------------------- conflicts


@bp.get("/<slug>/conflict")
def conflict(slug: str):
    corpus = current_corpus()
    story = corpus.by_slug(slug)
    if story is None or story.source_path is None:
        abort(404)

    state = current_store().state_of(slug, story.source_path)
    if not state.blocked:
        return redirect(url_for("stories.edit", slug=slug))

    row = current_store().story_row(slug)
    return render_template(
        "portal/conflict.html",
        slug=slug,
        story=story,
        disk_text=story.source_path.read_text(encoding="utf-8"),
        store_text=row["last_written_text"] if row else None,
    )


@bp.post("/<slug>/conflict")
def resolve_conflict(slug: str):
    """Resolve a divergence — but only ever the way the author chose.

    Neither side is overwritten until this point. "Keep disk" adopts the file as it
    stands; "keep store" rewrites it from the parsed story. There is deliberately no
    default and no automatic merge.
    """
    corpus = current_corpus()
    story = corpus.by_slug(slug)
    if story is None or story.source_path is None:
        abort(404)

    choice = request.form.get("choice")
    store = current_store()

    if choice == "disk":
        store.record_write(slug, story.source_path, story.source_path.read_bytes())
        flash("Kept the version on disk.", "success")
    elif choice == "store":
        row = store.story_row(slug)
        previous = row["last_written_text"] if row else None
        if not previous:
            abort(400, description="No earlier version was recorded for this story.")
        written = atomic_write(story.source_path, previous)
        store.record_write(slug, story.source_path, written)
        flash("Restored the version the portal last wrote.", "success")
    else:
        abort(400)

    return redirect(url_for("stories.edit", slug=slug))
