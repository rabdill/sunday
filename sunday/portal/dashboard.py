"""The portal's front page: what needs the author's attention right now."""

from __future__ import annotations

from flask import Blueprint, current_app, render_template

from . import current_corpus

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    corpus = current_corpus()
    recent = corpus.feed_order(include_drafts=True)[:8]

    return render_template(
        "portal/dashboard.html",
        recent=recent,
        story_count=len(corpus.stories),
        draft_count=sum(1 for s in corpus.stories if s.draft),
        last_build=current_app.config.get("SUNDAY_LAST_BUILD"),
    )
