"""The authoring store: authoritative for authoring, disposable by design.

The store arbitrates conflicts and holds material no story file represents —
profiles, notes, relationships, dismissal decisions (FR-037). It is excluded from
version control and rebuildable from the committed files (FR-040), which is the
trade that keeps a binary out of git.

**Losing it must never lose a story** (FR-042). Story text is not kept here; only
the hash of what the portal last wrote, which is what conflict detection needs.
The file is read from disk on demand, so "no story exists only in the store" is
obvious rather than argued.

Hand-written SQL over stdlib `sqlite3`. Six tables do not justify an ORM, and a
migration framework exists to protect data you cannot reconstruct — this store is
explicitly reconstructible, so `delete and rebuild` is a legitimate upgrade path.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import sqlite3
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, Literal

from .corpus import Corpus, Kind, Name, load_corpus
from .export import CastExport, load_cast

SCHEMA_VERSION = 1

SubjectKind = Literal["character", "location"]
#: Tags deliberately get no `subjects` row. A subject row exists to give notes and
#: relationships something stable to follow across a rename; tags have neither, so a
#: row for one would be state with no consumer (see data-model.md).
SUBJECT_KINDS: tuple[SubjectKind, ...] = ("character", "location")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stories (
    id                INTEGER PRIMARY KEY,
    slug              TEXT NOT NULL UNIQUE,
    source_path       TEXT NOT NULL,
    last_written_hash TEXT,
    -- The exact text last written, so a conflict offers two real versions rather
    -- than a notification. FR-041 requires the author be able to *choose*, and
    -- without this there is nothing to choose between: the disk copy would be the
    -- only version that still exists. This does not make the store authoritative
    -- for story text — the file is written on every save and always holds it too,
    -- so losing the store still loses no fiction (FR-042).
    last_written_text TEXT,
    last_written_at   TEXT
);

CREATE TABLE IF NOT EXISTS subjects (
    id           INTEGER PRIMARY KEY,
    kind         TEXT NOT NULL CHECK (kind IN ('character', 'location')),
    name         TEXT NOT NULL,
    display_name TEXT,
    description  TEXT,
    dismissed    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (kind, name)
);

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('story', 'subject')),
    target_id   INTEGER NOT NULL,
    body        TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
    id              INTEGER PRIMARY KEY,
    from_subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    to_subject_id   INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    description     TEXT NOT NULL DEFAULT '',
    directed        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS conflicts (
    story_id    INTEGER PRIMARY KEY REFERENCES stories(id) ON DELETE CASCADE,
    detected_at TEXT NOT NULL,
    disk_hash   TEXT NOT NULL
);
"""


def content_hash(data: bytes | str) -> str:
    """SHA-256 of exactly the bytes on disk.

    Content, not modification time: a `git checkout` rewrites timestamps on every
    file, and an author trained to click through a false conflict prompt is worse
    off than one who never sees it.
    """
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------------ records


class ConflictState(str, Enum):
    CLEAN = "clean"
    DIVERGED = "diverged"
    UNTRACKED = "untracked"
    MISSING = "missing"


@dataclass(frozen=True)
class StoryState:
    slug: str
    state: ConflictState
    path: Path | None = None

    @property
    def blocked(self) -> bool:
        """Editing a diverged story is blocked until the author resolves it (FR-041)."""
        return self.state is ConflictState.DIVERGED


@dataclass(frozen=True)
class Subject:
    id: int
    kind: SubjectKind
    name: str
    display_name: str | None = None
    description: str | None = None
    dismissed: bool = False

    @property
    def has_profile(self) -> bool:
        """A row carrying only a dismissal is not a profile."""
        return bool(self.description or self.display_name)


@dataclass(frozen=True)
class Note:
    id: int
    target_kind: str
    target_id: int
    body: str
    updated_at: str


@dataclass(frozen=True)
class Relationship:
    id: int
    from_subject: Subject
    to_subject: Subject
    description: str
    directed: bool


@dataclass
class RebuildReport:
    """What a rebuild recovered, and what it could not."""

    rebuilt: bool
    stories: int = 0
    subjects: int = 0
    profiles: int = 0
    relationships: int = 0
    lost: tuple[str, ...] = ()

    def describe(self) -> str:
        if not self.rebuilt:
            return "Store is current; nothing rebuilt."
        lines = [
            "Rebuilt the authoring store from committed files.",
            f"  recovered: {self.stories} stories, {self.subjects} subjects, "
            f"{self.profiles} profiles, {self.relationships} relationships",
        ]
        if self.lost:
            lines.append(f"  NOT recoverable: {', '.join(self.lost)}")
        return "\n".join(lines)


#: Never exported, so never recoverable by a rebuild. Named explicitly rather than
#: discovered by the author later (FR-042).
UNRECOVERABLE = ("notes", "dismissed candidates", "profile descriptions")


# -------------------------------------------------------------------------- store


class Store:
    """A connection to the authoring store. One per request; closed on teardown."""

    def __init__(self, connection: sqlite3.Connection, path: Path) -> None:
        self.connection = connection
        self.path = path
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

    # -- lifecycle

    @classmethod
    def open(cls, path: Path | str) -> "Store":
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        store = cls(sqlite3.connect(path), path)
        store._create_schema()
        return store

    @classmethod
    def ensure(
        cls, path: Path | str, stories_dir: Path | str, cast_path: Path | str
    ) -> RebuildReport:
        """Open the store, rebuilding it if missing, empty, or version-mismatched."""
        path = Path(path)
        needs_rebuild = not path.exists() or path.stat().st_size == 0

        if not needs_rebuild:
            with cls.open(path) as store:
                needs_rebuild = store.schema_version() != SCHEMA_VERSION

        if needs_rebuild:
            return rebuild_store(store_path=path, stories_dir=stories_dir, cast_path=cast_path)

        with cls.open(path) as store:
            store.sync_subjects(load_corpus(stories_dir))
        return RebuildReport(rebuilt=False)

    def _create_schema(self) -> None:
        self.connection.executescript(SCHEMA)
        self.connection.execute(
            "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.connection.commit()

    def schema_version(self) -> int:
        row = self.connection.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        return int(row["value"]) if row else 0

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- stories and conflict tracking

    def story_row(self, slug: str) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM stories WHERE slug = ?", (slug,)
        ).fetchone()

    def story_id(self, slug: str) -> int | None:
        row = self.story_row(slug)
        return int(row["id"]) if row else None

    def record_write(self, slug: str, path: Path | str, data: bytes | str) -> None:
        """Record the exact bytes the portal just wrote.

        Called on every save, so the portal's own writes never look like someone
        else's edit.
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        digest = content_hash(data)
        self.connection.execute(
            """
            INSERT INTO stories
                (slug, source_path, last_written_hash, last_written_text, last_written_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET
                source_path = excluded.source_path,
                last_written_hash = excluded.last_written_hash,
                last_written_text = excluded.last_written_text,
                last_written_at = excluded.last_written_at
            """,
            (slug, str(path), digest, data.decode("utf-8", errors="replace"), _now()),
        )
        self.connection.execute(
            "DELETE FROM conflicts WHERE story_id = (SELECT id FROM stories WHERE slug = ?)",
            (slug,),
        )
        self.connection.commit()

    def forget_story(self, slug: str) -> None:
        self.connection.execute("DELETE FROM stories WHERE slug = ?", (slug,))
        self.connection.commit()

    def state_of(self, slug: str, path: Path | str | None) -> StoryState:
        """Classify one story against what the portal last wrote."""
        row = self.story_row(slug)
        path = Path(path) if path else None

        if row is None:
            return StoryState(slug, ConflictState.UNTRACKED, path)
        if path is None or not path.exists():
            return StoryState(slug, ConflictState.MISSING, path)

        current = content_hash(path.read_bytes())
        if row["last_written_hash"] == current:
            return StoryState(slug, ConflictState.CLEAN, path)
        return StoryState(slug, ConflictState.DIVERGED, path)

    def scan(self, corpus: Corpus) -> dict[str, StoryState]:
        """Classify every story, and adopt any the store has never seen.

        A file the portal did not write is *untracked*, not conflicted — adopting it
        silently is right, because there is no earlier version to disagree with.
        """
        states: dict[str, StoryState] = {}
        for story in corpus.stories:
            state = self.state_of(story.slug, story.source_path)
            if state.state is ConflictState.UNTRACKED and story.source_path:
                self.record_write(
                    story.slug, story.source_path, story.source_path.read_bytes()
                )
                state = StoryState(story.slug, ConflictState.CLEAN, story.source_path)
            if state.state is ConflictState.DIVERGED and story.source_path:
                self.connection.execute(
                    """
                    INSERT INTO conflicts (story_id, detected_at, disk_hash)
                    VALUES ((SELECT id FROM stories WHERE slug = ?), ?, ?)
                    ON CONFLICT(story_id) DO UPDATE SET
                        detected_at = excluded.detected_at,
                        disk_hash = excluded.disk_hash
                    """,
                    (story.slug, _now(), content_hash(story.source_path.read_bytes())),
                )
                self.connection.commit()
            states[story.slug] = state

        known = {row["slug"] for row in self.connection.execute("SELECT slug FROM stories")}
        for orphan in sorted(known - {s.slug for s in corpus.stories}):
            states[orphan] = StoryState(orphan, ConflictState.MISSING, None)

        return states

    def conflicts(self, corpus: Corpus) -> tuple[StoryState, ...]:
        return tuple(
            state for state in self.scan(corpus).values() if state.state is ConflictState.DIVERGED
        )

    # -- subjects

    def sync_subjects(self, corpus: Corpus) -> int:
        """Ensure a `subjects` row exists for every character and location in use.

        Preserves existing ids, so notes and relationships keep pointing at the same
        subject across reloads.
        """
        added = 0
        for kind in SUBJECT_KINDS:
            for name in corpus.names_of_kind(kind):
                cursor = self.connection.execute(
                    "INSERT OR IGNORE INTO subjects (kind, name) VALUES (?, ?)",
                    (kind, name.display),
                )
                added += cursor.rowcount or 0
        self.connection.commit()
        return added

    def subject(self, kind: str, name: str) -> Subject | None:
        row = self.connection.execute(
            "SELECT * FROM subjects WHERE kind = ? AND name = ?", (kind, name)
        ).fetchone()
        return self._subject_from(row) if row else None

    def subject_by_id(self, subject_id: int) -> Subject | None:
        row = self.connection.execute(
            "SELECT * FROM subjects WHERE id = ?", (subject_id,)
        ).fetchone()
        return self._subject_from(row) if row else None

    def ensure_subject(self, kind: str, name: str) -> Subject:
        self.connection.execute(
            "INSERT OR IGNORE INTO subjects (kind, name) VALUES (?, ?)", (kind, name)
        )
        self.connection.commit()
        found = self.subject(kind, name)
        assert found is not None
        return found

    def subjects(self, kind: str | None = None) -> tuple[Subject, ...]:
        if kind:
            rows = self.connection.execute(
                "SELECT * FROM subjects WHERE kind = ? ORDER BY name", (kind,)
            )
        else:
            rows = self.connection.execute("SELECT * FROM subjects ORDER BY kind, name")
        return tuple(self._subject_from(row) for row in rows)

    def set_profile(
        self, kind: str, name: str, *, description: str | None, display_name: str | None
    ) -> Subject:
        subject = self.ensure_subject(kind, name)
        self.connection.execute(
            "UPDATE subjects SET description = ?, display_name = ?, dismissed = 0 WHERE id = ?",
            (description or None, display_name or None, subject.id),
        )
        self.connection.commit()
        return self.subject_by_id(subject.id)  # type: ignore[return-value]

    def clear_profile(self, subject_id: int) -> None:
        self.connection.execute(
            "UPDATE subjects SET description = NULL, display_name = NULL WHERE id = ?",
            (subject_id,),
        )
        self.connection.commit()

    def dismiss(self, kind: str, name: str) -> None:
        """Remember that the author declined a candidate profile (FR-044)."""
        subject = self.ensure_subject(kind, name)
        self.connection.execute(
            "UPDATE subjects SET dismissed = 1 WHERE id = ?", (subject.id,)
        )
        self.connection.commit()

    def rename_subject(self, kind: str, old: str, new: str) -> None:
        """Rename in place, so notes and relationships follow the id (FR-047, FR-050)."""
        existing = self.subject(kind, new)
        subject = self.subject(kind, old)
        if subject is None:
            self.ensure_subject(kind, new)
            return

        if existing is not None and existing.id != subject.id:
            # Merging into a name that already exists: move dependents, drop the old row.
            self.connection.execute(
                "UPDATE notes SET target_id = ? WHERE target_kind = 'subject' AND target_id = ?",
                (existing.id, subject.id),
            )
            self.connection.execute(
                "UPDATE relationships SET from_subject_id = ? WHERE from_subject_id = ?",
                (existing.id, subject.id),
            )
            self.connection.execute(
                "UPDATE relationships SET to_subject_id = ? WHERE to_subject_id = ?",
                (existing.id, subject.id),
            )
            self.connection.execute("DELETE FROM subjects WHERE id = ?", (subject.id,))
        else:
            self.connection.execute(
                "UPDATE subjects SET name = ? WHERE id = ?", (new, subject.id)
            )
        self.connection.commit()

    # -- notes
    #
    # Never exported, never published (FR-046). Attached to an id, so they survive a
    # rename (FR-047). Lost with the store, and the UI says so.

    def notes_for(self, target_kind: str, target_id: int) -> tuple[Note, ...]:
        rows = self.connection.execute(
            "SELECT * FROM notes WHERE target_kind = ? AND target_id = ? ORDER BY id",
            (target_kind, target_id),
        )
        return tuple(
            Note(
                id=int(r["id"]),
                target_kind=r["target_kind"],
                target_id=int(r["target_id"]),
                body=r["body"],
                updated_at=r["updated_at"],
            )
            for r in rows
        )

    def note(self, note_id: int) -> Note | None:
        row = self.connection.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        if row is None:
            return None
        return Note(
            id=int(row["id"]),
            target_kind=row["target_kind"],
            target_id=int(row["target_id"]),
            body=row["body"],
            updated_at=row["updated_at"],
        )

    def add_note(self, target_kind: str, target_id: int, body: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO notes (target_kind, target_id, body, updated_at) VALUES (?, ?, ?, ?)",
            (target_kind, target_id, body, _now()),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def update_note(self, note_id: int, body: str) -> None:
        self.connection.execute(
            "UPDATE notes SET body = ?, updated_at = ? WHERE id = ?", (body, _now(), note_id)
        )
        self.connection.commit()

    def delete_note(self, note_id: int) -> None:
        self.connection.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.connection.commit()

    # -- relationships
    #
    # Maintained independently of what stories say (FR-049), referenced by subject id
    # so a rename cannot break them (FR-050).

    def _relationship_from(self, row: sqlite3.Row) -> Relationship:
        return Relationship(
            id=int(row["id"]),
            from_subject=self.subject_by_id(int(row["from_subject_id"])),  # type: ignore[arg-type]
            to_subject=self.subject_by_id(int(row["to_subject_id"])),  # type: ignore[arg-type]
            description=row["description"],
            directed=bool(row["directed"]),
        )

    def relationships(self) -> tuple[Relationship, ...]:
        rows = self.connection.execute("SELECT * FROM relationships ORDER BY id")
        return tuple(self._relationship_from(r) for r in rows)

    def relationships_for(self, subject_id: int) -> tuple[Relationship, ...]:
        rows = self.connection.execute(
            "SELECT * FROM relationships WHERE from_subject_id = ? OR to_subject_id = ? ORDER BY id",
            (subject_id, subject_id),
        )
        return tuple(self._relationship_from(r) for r in rows)

    def relationship(self, relationship_id: int) -> Relationship | None:
        row = self.connection.execute(
            "SELECT * FROM relationships WHERE id = ?", (relationship_id,)
        ).fetchone()
        return self._relationship_from(row) if row else None

    def add_relationship(
        self, from_subject_id: int, to_subject_id: int, description: str, directed: bool
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO relationships (from_subject_id, to_subject_id, description, directed)
            VALUES (?, ?, ?, ?)
            """,
            (from_subject_id, to_subject_id, description, int(directed)),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def update_relationship(self, relationship_id: int, description: str, directed: bool) -> None:
        self.connection.execute(
            "UPDATE relationships SET description = ?, directed = ? WHERE id = ?",
            (description, int(directed), relationship_id),
        )
        self.connection.commit()

    def delete_relationship(self, relationship_id: int) -> None:
        self.connection.execute("DELETE FROM relationships WHERE id = ?", (relationship_id,))
        self.connection.commit()

    @staticmethod
    def _subject_from(row: sqlite3.Row) -> Subject:
        return Subject(
            id=int(row["id"]),
            kind=row["kind"],
            name=row["name"],
            display_name=row["display_name"],
            description=row["description"],
            dismissed=bool(row["dismissed"]),
        )


# ------------------------------------------------------------------------ rebuild


def rebuild_store(
    *, store_path: Path | str, stories_dir: Path | str, cast_path: Path | str
) -> RebuildReport:
    """Discard the store and rebuild it from the committed files.

    Recovers stories and their hashes from the corpus, subjects from the names in
    use, and profiles and relationships from `cast.yml`. Cannot recover notes,
    dismissals, or profile descriptions — none of the three is exported, and the
    report says so rather than letting the author find out later.
    """
    store_path = Path(store_path)
    if store_path.exists():
        store_path.unlink()

    corpus = load_corpus(stories_dir)
    cast = load_cast(cast_path)

    with Store.open(store_path) as store:
        for story in corpus.stories:
            if story.source_path is not None:
                store.record_write(story.slug, story.source_path, story.source_path.read_bytes())

        subjects = store.sync_subjects(corpus)

        profiles = 0
        for name, override in sorted(cast.display_names.items()):
            for kind in SUBJECT_KINDS:
                if corpus.name(kind, name) is not None:
                    store.set_profile(kind, name, description=None, display_name=override)
                    profiles += 1
                    break
            else:
                store.set_profile("character", name, description=None, display_name=override)
                profiles += 1

        relationships = 0
        for rel in cast.relationships:
            endpoints = []
            for display in (rel.from_name, rel.to_name):
                kind = next(
                    (k for k in SUBJECT_KINDS if corpus.name(k, display) is not None),
                    "character",
                )
                endpoints.append(store.ensure_subject(kind, display))
            store.connection.execute(
                """
                INSERT INTO relationships (from_subject_id, to_subject_id, description, directed)
                VALUES (?, ?, ?, ?)
                """,
                (endpoints[0].id, endpoints[1].id, rel.description, int(rel.directed)),
            )
            relationships += 1
        store.connection.commit()

        return RebuildReport(
            rebuilt=True,
            stories=len(corpus.stories),
            subjects=len(store.subjects()),
            profiles=profiles,
            relationships=relationships,
            lost=UNRECOVERABLE,
        )
