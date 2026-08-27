"""Hand-owned collection settings.

`sunday.yml` belongs to the author: read here, never written. See docs/DESIGN.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class SettingsError(Exception):
    """Raised when the settings file is missing or malformed."""


@dataclass(frozen=True)
class Settings:
    title: str
    source_path: Path | None = None


def load_settings(path: Path | str) -> Settings:
    """Read `sunday.yml`. A missing file is an error — the site needs a title."""
    path = Path(path)
    if not path.exists():
        raise SettingsError(
            f"settings file not found: {path} (a collection needs a 'title:')"
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SettingsError(f"{path}: not valid YAML: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise SettingsError(f"{path}: must be a mapping of settings")

    title = data.get("title")
    if not title or not str(title).strip():
        raise SettingsError(f"{path}: missing required setting: title")

    return Settings(title=str(title).strip(), source_path=path)
