"""Cast pages: the portal's richest surface, and where naming stays honest.

These pages are authoring surfaces and are never generated into the published site
(FR-053). A character's page gathers everything known about them in one place; a
tag's page is deliberately the thinnest thing this route serves — a story list and
nothing else, because a tag has no profile, no relationships, and no context
(FR-053b).
"""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..corpus import KINDS, Kind, load_corpus
from ..graph import derived_context
from ..review import findings as all_findings
from ..store import SUBJECT_KINDS
from ..writer import rename_across_corpus
from . import current_corpus, current_store, paths

bp = Blueprint("cast", __name__, url_prefix="/cast")


def _kind_or_404(kind: str) -> Kind:
    if kind not in KINDS:
        abort(404)
    return kind  # type: ignore[return-value]


@bp.get("/")
def index():
    corpus = current_corpus()
    store = current_store()
    store.sync_subjects(corpus)
    subjects = store.subjects()

    by_key = {(s.kind, s.name): s for s in subjects}
    findings = all_findings(corpus, subjects)

    flagged: dict[tuple[str, str], list] = {}
    for finding in findings:
        flagged.setdefault((finding.name.kind, finding.name.display), []).append(finding)

    rows = []
    for kind in KINDS:
        for name in corpus.names_of_kind(kind):
            subject = by_key.get((kind, name.display))
            rows.append(
                {
                    "name": name,
                    "uses": corpus.use_count(name),
                    "subject": subject,
                    "findings": flagged.get((kind, name.display), []),
                }
            )

    return render_template("portal/cast_index.html", rows=rows, kinds=KINDS)


@bp.get("/review/")
def review():
    """Every finding in one place (SC-007)."""
    corpus = current_corpus()
    store = current_store()
    store.sync_subjects(corpus)
    return render_template(
        "portal/review.html",
        findings=all_findings(corpus, store.subjects()),
    )


@bp.get("/<kind>/<slug>")
def show(kind: str, slug: str):
    kind = _kind_or_404(kind)
    corpus = current_corpus()
    name = corpus.name_by_slug(kind, slug)
    if name is None:
        abort(404)

    store = current_store()
    store.sync_subjects(corpus)

    # Drafts are included and marked: the portal shows the author their whole world.
    stories = corpus.stories_for(name, include_drafts=True)

    if kind == "tag":
        return render_template("portal/cast_page.html", name=name, stories=stories, is_tag=True)

    subject = store.subject(kind, name.display)
    context = derived_context(corpus, name)

    relationships = store.relationships_for(subject.id) if subject else ()
    notes = store.notes_for("subject", subject.id) if subject else ()

    return render_template(
        "portal/cast_page.html",
        name=name,
        stories=stories,
        subject=subject,
        context=context,
        relationships=relationships,
        notes=notes,
        is_tag=False,
        note_target_kind="subject",
        note_target_ref=f"{kind}/{slug}",
    )


@bp.post("/<kind>/<slug>/profile")
def save_profile(kind: str, slug: str):
    kind = _kind_or_404(kind)
    if kind not in SUBJECT_KINDS:
        abort(404, description="Tags have no profile to edit.")

    corpus = current_corpus()
    name = corpus.name_by_slug(kind, slug)
    if name is None:
        abort(404)

    current_store().set_profile(
        kind,
        name.display,
        description=request.form.get("description", "").strip(),
        display_name=request.form.get("display_name", "").strip(),
    )
    _reexport()
    flash(f"Saved the profile for “{name.display}”.", "success")
    return redirect(url_for("cast.show", kind=kind, slug=slug))


@bp.post("/<kind>/<slug>/dismiss")
def dismiss(kind: str, slug: str):
    """Decline a candidate profile — and remember it (FR-044)."""
    kind = _kind_or_404(kind)
    if kind not in SUBJECT_KINDS:
        abort(404)

    corpus = current_corpus()
    name = corpus.name_by_slug(kind, slug)
    if name is None:
        abort(404)

    current_store().dismiss(kind, name.display)
    flash(
        f"Dismissed the suggestion for “{name.display}”. It will not come back, and the "
        f"name keeps working exactly as before.",
        "success",
    )
    return redirect(url_for("cast.index"))


@bp.post("/<kind>/<slug>/rename")
def rename(kind: str, slug: str):
    """Rename across the whole corpus (FR-031), leaving zero occurrences (SC-010)."""
    kind = _kind_or_404(kind)
    corpus = current_corpus()
    name = corpus.name_by_slug(kind, slug)
    if name is None:
        abort(404)

    new_name = request.form.get("new_name", "").strip()
    if not new_name:
        flash("A new name is required.", "error")
        return redirect(url_for("cast.show", kind=kind, slug=slug))

    result = rename_across_corpus(paths().stories, kind, name.display, new_name)

    store = current_store()
    # Update each rewritten file's hash so the rename never manufactures its own
    # conflicts — the portal made these edits, and it knows it.
    reloaded = load_corpus(paths().stories)
    for path, written in result.written.items():
        story = next((s for s in reloaded.stories if s.source_path == path), None)
        if story is not None:
            store.record_write(story.slug, path, written)

    # Only characters and locations have a subject row to carry forward; a tag
    # rename has no store-side state at all.
    if kind in SUBJECT_KINDS:
        store.rename_subject(kind, name.display, new_name)
        _reexport()

    store.sync_subjects(reloaded)
    flash(
        f"Renamed “{name.display}” to “{new_name}” across {result.count} "
        f"file{'' if result.count == 1 else 's'}.",
        "success",
    )

    renamed = load_corpus(paths().stories).name(kind, new_name)
    if renamed is None:
        return redirect(url_for("cast.index"))
    return redirect(url_for("cast.show", kind=kind, slug=renamed.slug))


def _reexport() -> None:
    from . import reexport_cast

    reexport_cast()
