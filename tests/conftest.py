"""Shared fixtures.

The demonstration corpus is deliberately small but exercises every awkward case:
a draft, an undated story, bare-year and year-month in-world dates, a
near-duplicate character pair, a near-duplicate tag pair, a character who appears
only in a draft, a character sharing no story with anyone, an unmanaged
frontmatter key, and a non-ASCII location.
"""

from __future__ import annotations

import ast
import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CORPUS_DIR = FIXTURES / "corpus"
STORIES_DIR = CORPUS_DIR / "stories"
SETTINGS_PATH = CORPUS_DIR / "sunday.yml"
BROKEN_DIR = FIXTURES / "broken"

#: The published (non-draft) stories in the fixture corpus.
PUBLISHED_SLUGS = (
    "letters-home",
    "the-fog",
    "the-keeper",
    "the-lighthouse",
    "the-second-letter",
    "winter-crossing",
)


def build_into(target: Path, corpus_dir: Path):
    """Build the site from a corpus directory laid out like the fixture."""
    from sunday.build import build_site

    return build_site(
        stories_dir=corpus_dir / "stories",
        settings_path=corpus_dir / "sunday.yml",
        cast_path=corpus_dir / "cast.yml",
        output_dir=target,
    )


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


@dataclass
class ModuleIdentifiers:
    """A module's AST, bucketed for structural-guard tests.

    Split by bucket so each guard can compose exactly the vocabulary it needs — e.g.
    excluding `constants` avoids matching a docstring's prose about the very rule
    being enforced.
    """

    imports: set[str]
    names_attrs_defs: set[str]
    constants: set[str]


def module_identifiers(path: Path) -> ModuleIdentifiers:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    names_attrs_defs: set[str] = set()
    constants: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            imports.add(base)
            imports.update(
                f"{base}.{alias.name}" if base else alias.name for alias in node.names
            )
        elif isinstance(node, ast.Name):
            names_attrs_defs.add(node.id)
        elif isinstance(node, ast.Attribute):
            names_attrs_defs.add(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names_attrs_defs.add(node.name)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            constants.add(node.value)

    return ModuleIdentifiers(
        imports=imports, names_attrs_defs=names_attrs_defs, constants=constants
    )
