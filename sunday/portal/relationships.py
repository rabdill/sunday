"""Stated relationships between characters.

Maintained independently of what any story says (FR-049), so the author can record
what is true of the world before it has been written down. Every change re-exports
`cast.yml` (FR-038), which is how a relationship reaches the published diagram.

The published diagram draws these as a distinct edge kind and never merges them
with co-appearance (FR-051): "they appear in a story together" and "the author says
they are siblings" are different claims.
"""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..store import SUBJECT_KINDS
from . import current_corpus, current_store, reexport_cast

bp = Blueprint("relationships", __name__, url_prefix="/relationships")


@bp.get("/")
def index():
    corpus = current_corpus()
    store = current_store()
    store.sync_subjects(corpus)

    return render_template(
        "portal/relationships.html",
        relationships=store.relationships(),
        characters=store.subjects("character"),
    )


@bp.post("/")
def create():
    store = current_store()
    store.sync_subjects(current_corpus())

    try:
        from_id = int(request.form["from_subject"])
        to_id = int(request.form["to_subject"])
    except (KeyError, ValueError):
        abort(400)

    if from_id == to_id:
        flash("A character cannot be in a relationship with themselves.", "error")
        return redirect(url_for("relationships.index"))

    store.add_relationship(
        from_id,
        to_id,
        request.form.get("description", "").strip(),
        bool(request.form.get("directed")),
    )
    reexport_cast()
    flash("Relationship recorded. It will appear on the published diagram.", "success")
    return redirect(url_for("relationships.index"))


@bp.post("/<int:relationship_id>")
def update(relationship_id: int):
    store = current_store()
    if store.relationship(relationship_id) is None:
        abort(404)

    if request.form.get("delete"):
        store.delete_relationship(relationship_id)
        flash("Relationship deleted.", "success")
    else:
        store.update_relationship(
            relationship_id,
            request.form.get("description", "").strip(),
            bool(request.form.get("directed")),
        )
        flash("Relationship updated.", "success")

    reexport_cast()
    return redirect(url_for("relationships.index"))
