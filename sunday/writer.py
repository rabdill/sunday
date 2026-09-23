"""Writing story files, and renaming a name across the whole corpus."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from .corpus import Corpus, Kind, Story, load_corpus

#: Managed keys are written in this order, so diffs stay legible.
KEY_ORDER = ("slug", "title", "published", "occurs", "characters", "locations", "tags", "draft")


class _BlockDumper(yaml.SafeDumper):
    """Keeps lists as block sequences, which is how a person would write them."""


def _represent_str(dumper: yaml.SafeDumper, data: str):
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_BlockDumper.add_representer(str, _represent_str)


def serialize_story(story: Story) -> str:
    """Render a `Story` back to the exact text of its file."""
    meta: dict[str, object] = {
        "slug": story.slug,
        "title": story.title,
        "published": story.published,
    }
    if story.occurs is not None:
        meta["occurs"] = str(story.occurs)
    if story.characters:
        meta["characters"] = list(story.characters)
    if story.locations:
        meta["locations"] = list(story.locations)
    if story.tags:
        meta["tags"] = list(story.tags)
    if story.draft:
        meta["draft"] = True

    # Unmanaged keys keep their values and follow the managed block.
    for key in sorted(story.extra):
        meta[key] = story.extra[key]

    front = yaml.dump(
        meta,
        Dumper=_BlockDumper,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip("\n")

    body = story.body.strip("\n")
    return f"---\n{front}\n---\n\n{body}\n"


def atomic_write(path: Path | str, text: str) -> bytes:
    """Write `text` to `path` atomically, returning the exact bytes written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")

    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".sunday-", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    return data


def write_story(path: Path | str, story: Story) -> bytes:
    return atomic_write(path, serialize_story(story))


def story_path(stories_dir: Path | str, story: Story) -> Path:
    """Where a story's file belongs when the portal creates it."""
    return Path(stories_dir) / f"{story.slug}.md"


# ------------------------------------------------------------------------- rename


@dataclass
class RenameResult:
    """What a corpus-wide rename actually changed."""

    old: str
    new: str
    kind: Kind
    files_changed: tuple[Path, ...]
    written: dict[Path, bytes] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.written is None:
            self.written = {}

    @property
    def count(self) -> int:
        return len(self.files_changed)


def rename_across_corpus(
    stories_dir: Path | str, kind: Kind, old: str, new: str
) -> RenameResult:
    """Rewrite every story referencing `old` so it references `new` instead."""
    stories_dir = Path(stories_dir)
    corpus = load_corpus(stories_dir)
    new = new.strip()
    if not new:
        raise ValueError("the new name cannot be empty")

    changed: list[Path] = []
    written: dict[Path, bytes] = {}

    for story in corpus.stories:
        current = story.names_of_kind(kind)
        if old not in current:
            continue

        # Replace in place, preserving order, and drop a duplicate if the target
        # name is already present on this story.
        replaced: list[str] = []
        for value in current:
            candidate = new if value == old else value
            if candidate not in replaced:
                replaced.append(candidate)

        updated = Story(
            slug=story.slug,
            title=story.title,
            published=story.published,
            body=story.body,
            occurs=story.occurs,
            characters=tuple(replaced) if kind == "character" else story.characters,
            locations=tuple(replaced) if kind == "location" else story.locations,
            tags=tuple(replaced) if kind == "tag" else story.tags,
            draft=story.draft,
            extra=story.extra,
            source_path=story.source_path,
        )

        assert story.source_path is not None
        written[story.source_path] = write_story(story.source_path, updated)
        changed.append(story.source_path)

    return RenameResult(
        old=old, new=new, kind=kind, files_changed=tuple(changed), written=written
    )
