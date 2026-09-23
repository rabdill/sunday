"""Private authoring notes. Never published or exported."""

from __future__ import annotations

from flask import Blueprint, abort, flash, redirect, request, url_for

from . import current_corpus, current_store

bp = Blueprint("notes", __name__, url_prefix="/notes")


def _back_to(target_kind: str, target_ref: str) -> str:
    if target_kind == "story":
        return url_for("stories.edit", slug=target_ref)
    kind, _, slug = target_ref.partition("/")
    return url_for("cast.show", kind=kind, slug=slug)


@bp.post("/")
def create():
    """Attach a note to a story, character, or location."""
    target_kind = request.form.get("target_kind", "")
    target_ref = request.form.get("target_ref", "")
    body = request.form.get("body", "").strip()

    if target_kind not in ("story", "subject") or not target_ref:
        abort(400)
    if not body:
        flash("An empty note was not saved.", "error")
        return redirect(_back_to(target_kind, target_ref))

    store = current_store()
    corpus = current_corpus()

    if target_kind == "story":
        story = corpus.by_slug(target_ref)
        if story is None:
            abort(404)
        target_id = store.story_id(story.slug)
        if target_id is None:
            store.record_write(story.slug, story.source_path, story.source_path.read_bytes())
            target_id = store.story_id(story.slug)
    else:
        kind, _, slug = target_ref.partition("/")
        name = corpus.name_by_slug(kind, slug)  # type: ignore[arg-type]
        if name is None:
            abort(404)
        target_id = store.ensure_subject(kind, name.display).id

    store.add_note(target_kind, int(target_id), body)
    flash("Note saved. It stays here — nothing published ever sees it.", "success")
    return redirect(_back_to(target_kind, target_ref))


@bp.post("/<int:note_id>")
def update(note_id: int):
    store = current_store()
    note = store.note(note_id)
    if note is None:
        abort(404)

    target_ref = request.form.get("target_ref", "")
    if request.form.get("delete"):
        store.delete_note(note_id)
        flash("Note deleted.", "success")
    else:
        body = request.form.get("body", "").strip()
        if not body:
            flash("An empty note was not saved.", "error")
        else:
            store.update_note(note_id, body)
            flash("Note updated.", "success")

    return redirect(_back_to(note.target_kind, target_ref))
