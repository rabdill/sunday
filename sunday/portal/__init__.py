"""The local authoring portal: a Flask app the author runs on their own machine.

Never a component of the published site, never required for readers (FR-025). It
binds `127.0.0.1` only — it writes files and has no authentication, and binding
anywhere else would be indefensible.

The corpus is reloaded from disk on every request rather than cached. That is what
makes hand-editing a story in a text editor a supported workflow (FR-005) instead
of something the portal fights.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flask import Flask, current_app, g

from ..corpus import Corpus, load_corpus
from ..export import CastExport, load_cast
from ..settings import Settings, SettingsError, load_settings


class CollectionNotFound(Exception):
    """Raised when the portal is pointed at something that is not a collection."""


@dataclass(frozen=True)
class Paths:
    stories: Path
    settings: Path
    cast: Path
    store: Path
    output: Path


def paths() -> Paths:
    return current_app.config["SUNDAY_PATHS"]


def current_corpus() -> Corpus:
    """The corpus as it is on disk *right now*, reloaded once per request."""
    if "corpus" not in g:
        g.corpus = load_corpus(paths().stories)
    return g.corpus


def current_cast() -> CastExport:
    if "cast" not in g:
        g.cast = load_cast(paths().cast)
    return g.cast


def current_settings() -> Settings:
    if "settings" not in g:
        g.settings = load_settings(paths().settings)
    return g.settings


def current_store():
    """The authoring store, opened once per request.

    Imported lazily and only here: nothing in the generator may reach the store,
    and keeping the import local to the portal keeps that boundary obvious.
    """
    from ..store import Store

    if "store" not in g:
        g.store = Store.open(paths().store)
    return g.store


def reexport_cast() -> None:
    """Rewrite `cast.yml` from current store state (FR-038).

    Called after any save that changes a display name or a relationship, so the
    committed export never lags the store.
    """
    from ..export import export_from_store, write_cast

    write_cast(paths().cast, export_from_store(current_store()))


def _verify_collection(stories: Path, settings: Path) -> None:
    """Refuse to start anywhere that is not a story collection (FR-036).

    Starting in the wrong directory and silently creating an empty collection would
    be a confusing way to lose an afternoon.
    """
    if not stories.is_dir():
        raise CollectionNotFound(
            f"no stories directory at {stories} — this does not look like a Sunday "
            f"collection. Start the portal from your collection's root, or pass --stories."
        )
    try:
        load_settings(settings)
    except SettingsError as exc:
        raise CollectionNotFound(
            f"{exc}. This does not look like a Sunday collection."
        ) from exc


def create_app(
    *,
    stories_dir: Path | str,
    settings_path: Path | str,
    cast_path: Path | str,
    store_path: Path | str,
    output_dir: Path | str = "site",
) -> Flask:
    resolved = Paths(
        stories=Path(stories_dir),
        settings=Path(settings_path),
        cast=Path(cast_path),
        store=Path(store_path),
        output=Path(output_dir),
    )
    _verify_collection(resolved.stories, resolved.settings)

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).parent.parent / "templates"),
        static_folder=str(Path(__file__).parent.parent / "static"),
        static_url_path="/assets",
    )
    app.config["SUNDAY_PATHS"] = resolved
    app.config["SUNDAY_LAST_BUILD"] = None
    app.secret_key = "sunday-local-portal"  # local single-user tool; flashes only

    # The store is created or rebuilt once at startup, not per request, so the author
    # is told immediately if anything could not be recovered (FR-040).
    from ..store import Store

    app.config["SUNDAY_STORE_REPORT"] = Store.ensure(
        resolved.store, resolved.stories, resolved.cast
    )

    @app.teardown_appcontext
    def _close_store(_exception=None):  # pragma: no cover - trivial
        store = g.pop("store", None)
        if store is not None:
            store.close()

    @app.context_processor
    def _inject():
        # Surfaces arrive phase by phase; the chrome shows only what is wired up.
        registered = app.blueprints
        return {
            "site_title": current_settings().title,
            "has_stories": "stories" in registered,
            "has_cast": "cast" in registered,
            "has_relationships": "relationships" in registered,
            "has_notes": "notes" in registered,
        }

    from . import build_routes, cast, dashboard, notes, relationships, stories

    app.register_blueprint(dashboard.bp)
    app.register_blueprint(stories.bp)
    app.register_blueprint(cast.bp)
    app.register_blueprint(notes.bp)
    app.register_blueprint(relationships.bp)
    app.register_blueprint(build_routes.bp)

    return app
