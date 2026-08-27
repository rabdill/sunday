"""Markdown rendering and date display.

Two rules govern this module. Markdown output must be *defined by a spec* rather
than by accumulated quirks, because FR-016 demands byte-identical rebuilds — so
CommonMark, with nothing enabled beyond it. And a partial in-world date must be
displayed at its true precision (FR-023b): "1921" stays "1921" and never becomes
"1 January 1921", which would be a fabrication.
"""

from __future__ import annotations

import datetime as _dt

from markdown_it import MarkdownIt

from .corpus import PartialDate, Precision

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

#: CommonMark defaults, no plugins. Extensions get added when a story needs one,
#: not in advance (Constitution II).
_md = MarkdownIt("commonmark")


def render_markdown(text: str) -> str:
    """Render a story body to HTML."""
    return _md.render(text)


def format_date(value: _dt.date) -> str:
    """Display a publication date. Always exact, so always a full date."""
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


def format_partial(value: PartialDate) -> str:
    """Display an in-world date at exactly the precision the author gave it."""
    if value.precision is Precision.DAY:
        return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"
    if value.precision is Precision.MONTH:
        return f"{_MONTHS[value.month - 1]} {value.year}"
    return str(value.year)
