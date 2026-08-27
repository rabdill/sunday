"""Trigger a local build and browse the result."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flask import Blueprint, abort, current_app, redirect, render_template, send_from_directory, url_for

from ..build import BuildError, build_site
from ..corpus import CorpusError
from ..settings import SettingsError
from . import paths

bp = Blueprint("build", __name__)


@dataclass
class BuildOutcome:
    ok: bool
    pages: int = 0
    warnings: tuple[str, ...] = ()
    error: str | None = None


@bp.post("/build")
def run_build():
    p = paths()
    try:
        result = build_site(
            stories_dir=p.stories,
            settings_path=p.settings,
            cast_path=p.cast,
            output_dir=p.output,
        )
    except (CorpusError, SettingsError, BuildError) as exc:
        outcome = BuildOutcome(ok=False, error=str(exc))
    else:
        outcome = BuildOutcome(ok=True, pages=result.page_count, warnings=result.warnings)

    current_app.config["SUNDAY_LAST_BUILD"] = outcome
    return render_template("portal/build.html", outcome=outcome)


@bp.get("/build")
def build_status():
    outcome = current_app.config.get("SUNDAY_LAST_BUILD")
    if outcome is None:
        return redirect(url_for("dashboard.index"))
    return render_template("portal/build.html", outcome=outcome)


@bp.get("/build/output/")
@bp.get("/build/output/<path:subpath>")
def build_output(subpath: str = ""):
    """Serve the most recent local build for browsing."""
    root = paths().output.resolve()
    if not root.is_dir():
        abort(404, description="No local build yet — run one from the dashboard.")

    candidate = (root / subpath).resolve()
    if not candidate.is_relative_to(root):
        abort(404)

    if candidate.is_dir():
        candidate = candidate / "index.html"
    if not candidate.is_file():
        abort(404)

    return send_from_directory(candidate.parent, candidate.name)
