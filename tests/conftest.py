"""Shared fixtures.

The demonstration corpus is deliberately small but exercises every awkward case:
a draft, an undated story, bare-year and year-month in-world dates, a
near-duplicate character pair, a near-duplicate tag pair, a character who appears
only in a draft, a character sharing no story with anyone, an unmanaged
frontmatter key, and a non-ASCII location.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CORPUS_DIR = FIXTURES / "corpus"
STORIES_DIR = CORPUS_DIR / "stories"
SETTINGS_PATH = CORPUS_DIR / "sunday.yml"
BROKEN_DIR = FIXTURES / "broken"


@pytest.fixture
def stories_dir() -> Path:
    return STORIES_DIR


@pytest.fixture
def settings_path() -> Path:
    return SETTINGS_PATH


@pytest.fixture
def broken_dir() -> Path:
    return BROKEN_DIR


@pytest.fixture
def corpus():
    from sunday.corpus import load_corpus

    return load_corpus(STORIES_DIR)


@pytest.fixture
def scratch_corpus(tmp_path: Path) -> Path:
    """A writable copy of the fixture corpus, for tests that mutate files."""
    target = tmp_path / "corpus"
    shutil.copytree(CORPUS_DIR, target)
    return target
