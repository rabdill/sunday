"""Command line entry point: `build`, `portal`, and `store rebuild`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

EXIT_OK = 0
EXIT_STRUCTURAL_ERROR = 1
EXIT_BAD_INVOCATION = 2

DEFAULT_STORIES = "stories"
DEFAULT_SETTINGS = "sunday.yml"
DEFAULT_CAST = "cast.yml"
DEFAULT_OUTPUT = "site"
DEFAULT_STORE = ".sunday/store.db"


def _add_source_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--stories", default=DEFAULT_STORIES, type=Path, help="corpus directory")
    parser.add_argument(
        "--settings", default=DEFAULT_SETTINGS, type=Path, help="hand-owned settings file"
    )
    parser.add_argument(
        "--cast", default=DEFAULT_CAST, type=Path, help="generated relationship/display-name export"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sunday",
        description="Publish short fiction as a static site, and author it locally.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="generate the static site")
    _add_source_options(build)
    build.add_argument("--output", default=DEFAULT_OUTPUT, type=Path, help="output directory")
    build.add_argument(
        "--strict",
        action="store_true",
        help="promote naming warnings to errors (off by default; CI does not use it)",
    )
    build.add_argument("--quiet", action="store_true", help="suppress warnings; errors still print")

    portal = sub.add_parser("portal", help="run the local authoring portal")
    _add_source_options(portal)
    portal.add_argument("--store", default=DEFAULT_STORE, type=Path, help="local authoring store")
    portal.add_argument("--port", default=5000, type=int, help="local port")
    portal.add_argument(
        "--no-browser", action="store_true", help="do not open a browser automatically"
    )

    store = sub.add_parser("store", help="manage the local authoring store")
    store_sub = store.add_subparsers(dest="store_command", required=True)
    rebuild = store_sub.add_parser("rebuild", help="discard and rebuild the store from files")
    _add_source_options(rebuild)
    rebuild.add_argument("--store", default=DEFAULT_STORE, type=Path, help="store to rebuild")
    rebuild.add_argument("--yes", action="store_true", help="skip the confirmation prompt")

    return parser


def _run_build(args: argparse.Namespace) -> int:
    from .build import build_site
    from .corpus import CorpusError
    from .settings import SettingsError

    try:
        result = build_site(
            stories_dir=args.stories,
            settings_path=args.settings,
            cast_path=args.cast,
            output_dir=args.output,
        )
    except (CorpusError, SettingsError) as exc:
        # Structural failure: name the file and the problem, publish nothing.
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_STRUCTURAL_ERROR

    # Naming findings are editorial, not structural. They never block publication
    # unless the author explicitly opts in with --strict.
    if result.warnings and not args.quiet:
        for warning in result.warnings:
            print(f"warning: {warning}", file=sys.stderr)

    if result.warnings and args.strict:
        print(
            f"error: --strict: {len(result.warnings)} naming warning(s) treated as errors",
            file=sys.stderr,
        )
        return EXIT_STRUCTURAL_ERROR

    if not args.quiet:
        print(f"built {result.page_count} pages into {args.output}")
    return EXIT_OK


def _run_portal(args: argparse.Namespace) -> int:
    from .portal import create_app
    from .portal import CollectionNotFound

    try:
        app = create_app(
            stories_dir=args.stories,
            settings_path=args.settings,
            cast_path=args.cast,
            store_path=args.store,
        )
    except CollectionNotFound as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INVOCATION

    if not args.no_browser:
        import threading
        import webbrowser

        threading.Timer(
            0.7, lambda: webbrowser.open(f"http://127.0.0.1:{args.port}/")
        ).start()

    # 127.0.0.1 only. The portal writes files and has no authentication; binding
    # anywhere else would be indefensible.
    app.run(host="127.0.0.1", port=args.port, debug=False)
    return EXIT_OK


def _run_store_rebuild(args: argparse.Namespace) -> int:
    from .corpus import CorpusError
    from .store import rebuild_store

    if not args.yes:
        print(
            "Rebuilding the store recovers stories, subjects, relationships, and display\n"
            "names from the committed files. It CANNOT recover notes, dismissed candidates,\n"
            "or profile descriptions — none of those are exported.",
            file=sys.stderr,
        )
        reply = input("Rebuild anyway? [y/N] ").strip().lower()
        if reply not in ("y", "yes"):
            print("aborted", file=sys.stderr)
            return EXIT_OK

    try:
        report = rebuild_store(
            store_path=args.store,
            stories_dir=args.stories,
            cast_path=args.cast,
        )
    except CorpusError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_STRUCTURAL_ERROR

    print(report.describe())
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build":
        return _run_build(args)
    if args.command == "portal":
        return _run_portal(args)
    if args.command == "store" and args.store_command == "rebuild":
        return _run_store_rebuild(args)

    parser.print_usage(sys.stderr)
    return EXIT_BAD_INVOCATION


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
