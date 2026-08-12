"""The portal as an application: startup checks, routes, and its structural guards.

The guard tests at the bottom protect two MUSTs that are otherwise enforced only
by nobody having written the offending line yet — the portal must never touch git
(FR-035) and must never write the hand-owned settings file (FR-006).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from sunday.portal import CollectionNotFound, create_app

PORTAL_PACKAGE = Path(__file__).parent.parent / "sunday" / "portal"


@pytest.fixture
def app(scratch_corpus, tmp_path):
    application = create_app(
        stories_dir=scratch_corpus / "stories",
        settings_path=scratch_corpus / "sunday.yml",
        cast_path=scratch_corpus / "cast.yml",
        store_path=tmp_path / ".sunday" / "store.db",
        output_dir=tmp_path / "site",
    )
    application.config.update(TESTING=True, SECRET_KEY="test")
    return application


@pytest.fixture
def client(app):
    return app.test_client()


# --------------------------------------------------------------------- startup


def test_refuses_to_start_outside_a_collection(tmp_path):
    """FR-036: starting in the wrong directory should say so, not invent a collection."""
    with pytest.raises(CollectionNotFound, match="does not look like a Sunday collection"):
        create_app(
            stories_dir=tmp_path / "nope",
            settings_path=tmp_path / "sunday.yml",
            cast_path=tmp_path / "cast.yml",
            store_path=tmp_path / "store.db",
        )


def test_refuses_to_start_without_settings(tmp_path):
    (tmp_path / "stories").mkdir()
    with pytest.raises(CollectionNotFound):
        create_app(
            stories_dir=tmp_path / "stories",
            settings_path=tmp_path / "sunday.yml",
            cast_path=tmp_path / "cast.yml",
            store_path=tmp_path / "store.db",
        )


def test_dashboard_lists_the_collection(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "The Lighthouse" in body
    assert "draft" in body.lower()


# ----------------------------------------------------------------- local build


def test_build_route_generates_the_site(client, tmp_path):
    response = client.post("/build")
    assert response.status_code == 200
    assert "Build succeeded" in response.get_data(as_text=True)
    assert (tmp_path / "site" / "index.html").exists()


def test_build_failure_is_reported_in_the_browser(client, scratch_corpus):
    """FR-034: the author is in the browser; that is where the cause belongs."""
    (scratch_corpus / "stories" / "broken.md").write_text(
        "---\nnot: [valid\n---\n\nbody\n", encoding="utf-8"
    )
    response = client.post("/build")
    body = response.get_data(as_text=True)

    assert "Build failed" in body
    assert "broken.md" in body, "the offending file must be named"


def test_portal_build_matches_a_cli_build(client, scratch_corpus, tmp_path):
    """A local build is the same code path as CI, so the result must match."""
    from sunday.build import build_site

    client.post("/build")

    reference = tmp_path / "reference"
    build_site(
        stories_dir=scratch_corpus / "stories",
        settings_path=scratch_corpus / "sunday.yml",
        cast_path=scratch_corpus / "cast.yml",
        output_dir=reference,
    )

    portal_built = tmp_path / "site"
    for page in ("index.html", "archive/index.html", "graph.json"):
        assert (portal_built / page).read_text(encoding="utf-8") == (
            reference / page
        ).read_text(encoding="utf-8")


def test_build_output_is_browsable(client, tmp_path):
    client.post("/build")
    response = client.get("/build/output/")
    assert response.status_code == 200
    assert "The Lighthouse" in response.get_data(as_text=True)


def test_build_output_refuses_to_escape_the_output_directory(client, tmp_path):
    client.post("/build")
    response = client.get("/build/output/../../etc/passwd")
    assert response.status_code == 404


# --------------------------------------------------------- writing and editing


def test_saving_a_new_story_writes_a_file_the_generator_accepts(client, scratch_corpus):
    from sunday.corpus import parse_story

    response = client.post(
        "/stories/new",
        data={
            "slug": "a-new-tide",
            "title": "A New Tide",
            "published": "2026-08-11",
            "occurs": "1925",
            "characters": "Mara Vance\nSilas Thorne",
            "locations": "Portsmouth",
            "tags": "",
            "body": "The tide came in, and did not go out again.",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    written = scratch_corpus / "stories" / "a-new-tide.md"
    assert written.exists()

    story = parse_story(written)
    assert story.title == "A New Tide"
    assert story.characters == ("Mara Vance", "Silas Thorne")
    assert str(story.occurs) == "1925"


def test_a_no_op_save_preserves_meaning_and_unmanaged_keys(client, scratch_corpus):
    """US3 scenario 2 / FR-027 — a round trip must lose nothing."""
    from sunday.corpus import parse_story

    path = scratch_corpus / "stories" / "the-lighthouse.md"
    before = parse_story(path)

    client.get("/stories/the-lighthouse/edit")
    client.post(
        "/stories/the-lighthouse",
        data={
            "slug": before.slug,
            "title": before.title,
            "published": before.published.isoformat(),
            "occurs": str(before.occurs),
            "characters": "\n".join(before.characters),
            "locations": "\n".join(before.locations),
            "tags": "\n".join(before.tags),
            "body": before.body,
        },
        follow_redirects=True,
    )

    after = parse_story(path)
    assert after.title == before.title
    assert after.characters == before.characters
    assert after.occurs.year == before.occurs.year
    assert after.extra == {"mood": "bleak"}, "an unmanaged key must survive the round trip"
    assert after.body.strip() == before.body.strip()


def test_a_missing_required_field_refuses_and_explains(client, scratch_corpus):
    """FR-028: nothing is written, and the reason is specific."""
    before = (scratch_corpus / "stories" / "the-fog.md").read_bytes()

    response = client.post(
        "/stories/the-fog",
        data={
            "slug": "the-fog",
            "title": "",
            "published": "2026-07-28",
            "occurs": "1921",
            "characters": "Mara Vance",
            "locations": "Portsmouth",
            "tags": "",
            "body": "Still here.",
        },
    )

    assert response.status_code == 400
    assert "A title is required" in response.get_data(as_text=True)
    assert (scratch_corpus / "stories" / "the-fog.md").read_bytes() == before


def test_an_invalid_in_world_date_is_rejected_without_writing(client, scratch_corpus):
    before = (scratch_corpus / "stories" / "the-fog.md").read_bytes()

    response = client.post(
        "/stories/the-fog",
        data={
            "slug": "the-fog",
            "title": "The Fog",
            "published": "2026-07-28",
            "occurs": "sometime in the twenties",
            "characters": "Mara Vance",
            "locations": "Portsmouth",
            "tags": "",
            "body": "Still here.",
        },
    )

    assert response.status_code == 400
    assert "imprecision is fine, invention is not" in response.get_data(as_text=True)
    assert (scratch_corpus / "stories" / "the-fog.md").read_bytes() == before


def test_new_names_need_no_registration(client, scratch_corpus):
    """FR-008a: typing a brand new name is always allowed."""
    from sunday.corpus import parse_story

    client.post(
        "/stories/new",
        data={
            "slug": "first-sighting",
            "title": "First Sighting",
            "published": "2026-08-11",
            "occurs": "",
            "characters": "Someone Entirely New",
            "locations": "",
            "tags": "",
            "body": "Nobody had seen her before.",
        },
        follow_redirects=True,
    )

    story = parse_story(scratch_corpus / "stories" / "first-sighting.md")
    assert story.characters == ("Someone Entirely New",)


# ------------------------------------------------------------------- conflicts


def diverge(scratch_corpus, slug="the-fog"):
    path = scratch_corpus / "stories" / f"{slug}.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nEdited in a text editor.\n", encoding="utf-8")
    return path


def test_editing_a_diverged_story_redirects_to_the_conflict(client, scratch_corpus):
    client.get("/stories/")  # adopt the corpus
    diverge(scratch_corpus)

    response = client.get("/stories/the-fog/edit")
    assert response.status_code == 302
    assert "/conflict" in response.headers["Location"]


def test_the_conflict_page_shows_both_versions(client, scratch_corpus):
    client.get("/stories/")
    diverge(scratch_corpus)

    body = client.get("/stories/the-fog/conflict").get_data(as_text=True)
    assert "Edited in a text editor." in body, "the version on disk must be shown"
    assert "On disk" in body and "What the portal last wrote" in body
    assert body.count("diff-body") >= 2, "both versions must be presented, not just one"


def test_neither_side_is_overwritten_until_the_author_chooses(client, scratch_corpus):
    client.get("/stories/")
    path = diverge(scratch_corpus)
    on_disk = path.read_bytes()

    client.get("/stories/the-fog/conflict")

    assert path.read_bytes() == on_disk, "merely viewing a conflict must change nothing"


def test_keeping_the_disk_version_preserves_the_outside_edit(client, scratch_corpus):
    client.get("/stories/")
    path = diverge(scratch_corpus)

    client.post("/stories/the-fog/conflict", data={"choice": "disk"}, follow_redirects=True)

    assert "Edited in a text editor." in path.read_text(encoding="utf-8")
    assert client.get("/stories/the-fog/edit").status_code == 200, "no longer blocked"


def test_keeping_the_portal_version_rewrites_the_file(client, scratch_corpus):
    client.get("/stories/")
    path = diverge(scratch_corpus)

    client.post("/stories/the-fog/conflict", data={"choice": "store"}, follow_redirects=True)

    assert "Edited in a text editor." not in path.read_text(encoding="utf-8")
    assert client.get("/stories/the-fog/edit").status_code == 200


def test_a_save_is_refused_while_a_story_is_conflicted(client, scratch_corpus):
    client.get("/stories/")
    path = diverge(scratch_corpus)
    on_disk = path.read_bytes()

    response = client.post(
        "/stories/the-fog",
        data={
            "slug": "the-fog",
            "title": "Overwritten",
            "published": "2026-07-28",
            "occurs": "1921",
            "characters": "Mara Vance",
            "locations": "Portsmouth",
            "tags": "",
            "body": "This must not land.",
        },
    )

    assert response.status_code == 302 and "/conflict" in response.headers["Location"]
    assert path.read_bytes() == on_disk


# ------------------------------------------------------------------ cast pages


def test_cast_index_lists_all_three_kinds(client):
    body = client.get("/cast/").get_data(as_text=True)
    assert "Mara Vance" in body      # character
    assert "Portsmouth" in body      # location
    assert "epistolary" in body      # tag


def test_cast_index_flags_a_probable_duplicate(client):
    body = client.get("/cast/").get_data(as_text=True)
    assert "Mara Vanse" in body
    assert "looks like" in body


def test_review_page_gathers_every_finding_in_one_place(client):
    """SC-007."""
    body = client.get("/cast/review/").get_data(as_text=True)
    assert "Probable duplicates" in body
    assert "Mara Vanse" in body
    assert "Used once" in body


def test_a_character_page_gathers_everything_known(client):
    """FR-057 — stories, derived context, relationships, and a diagram in one place."""
    body = client.get("/cast/character/mara-vance").get_data(as_text=True)

    assert "The Lighthouse" in body                  # stories
    assert "Portsmouth" in body                      # derived locations
    assert "Elias Doyle" in body                     # co-appearing
    assert "First appearance" in body
    assert "Relationships" in body
    assert "Diagram" in body


def test_a_character_page_marks_drafts(client):
    """The portal shows the whole world, not only the published part."""
    body = client.get("/cast/character/mara-vance").get_data(as_text=True)
    assert "Unfinished" in body and "draft" in body


def test_a_tag_page_is_only_a_story_list(client):
    """FR-053b: none of the character-specific concepts apply to a tag."""
    page = client.get("/cast/tag/correspondence").get_data(as_text=True)
    # Scope to the page's own content — the nav chrome links to other surfaces.
    body = page.split("<main>", 1)[1].split("</main>", 1)[0]

    assert "Letters Home" in body, "its stories are listed"
    for absent in ("From the stories", "Relationships", "Diagram", "Save profile", "Notes"):
        assert absent not in body, f"a tag page must not offer {absent!r}"


def test_renaming_leaves_no_occurrence_of_the_old_name(client, scratch_corpus):
    """SC-010 / FR-031."""
    client.get("/cast/")  # adopt the corpus first
    client.post(
        "/cast/character/mara-vanse/rename",
        data={"new_name": "Mara Vance"},
        follow_redirects=True,
    )

    remaining = [
        path.name
        for path in (scratch_corpus / "stories").glob("*.md")
        if "Mara Vanse" in path.read_text(encoding="utf-8")
    ]
    assert remaining == []


def test_renaming_a_tag_works_the_same_way(client, scratch_corpus):
    """A tag rename is the same operation, with no store-side state to carry."""
    client.get("/cast/")
    # `epistolary-2` is the stray capitalised spelling; the dominant one holds the
    # clean slug. Folding it in is exactly what review suggests.
    client.post(
        "/cast/tag/epistolary-2/rename",
        data={"new_name": "epistolary"},
        follow_redirects=True,
    )

    remaining = [
        path.name
        for path in (scratch_corpus / "stories").glob("*.md")
        if "Epistolary" in path.read_text(encoding="utf-8")
    ]
    assert remaining == []


def test_a_rename_does_not_manufacture_its_own_conflicts(client, scratch_corpus):
    """The portal made these edits and knows it, so no story should look diverged."""
    client.get("/stories/")
    client.post(
        "/cast/character/mara-vanse/rename",
        data={"new_name": "Mara Vance"},
        follow_redirects=True,
    )

    body = client.get("/stories/").get_data(as_text=True)
    assert "conflict" not in body


def test_dismissing_a_candidate_is_remembered(client):
    """FR-044: it does not come back, and the name keeps working."""
    client.post("/cast/character/silas-thorne/dismiss", follow_redirects=True)

    review = client.get("/cast/review/").get_data(as_text=True)
    unprofiled = review.split("Not yet profiled", 1)[1]
    assert "Silas Thorne" not in unprofiled

    assert client.get("/cast/character/silas-thorne").status_code == 200


def test_saving_a_profile_exports_the_display_name_but_not_the_description(
    client, scratch_corpus
):
    """FR-038a/b — the export carries only what the published site consumes."""
    client.post(
        "/cast/character/elias-doyle/profile",
        data={"display_name": "Doyle", "description": "A private note about him."},
        follow_redirects=True,
    )

    exported = (scratch_corpus / "cast.yml").read_text(encoding="utf-8")
    assert "Doyle" in exported
    assert "A private note about him." not in exported
    assert "description" not in exported


# ---------------------------------------------------------- notes and relationships


def test_a_note_can_be_attached_to_a_character_and_is_shown_again(client):
    client.post(
        "/notes/",
        data={
            "target_kind": "subject",
            "target_ref": "character/mara-vance",
            "body": "She never answers the second letter.",
        },
        follow_redirects=True,
    )

    body = client.get("/cast/character/mara-vance").get_data(as_text=True)
    assert "She never answers the second letter." in body


def test_a_note_can_be_attached_to_a_story(client):
    client.get("/stories/")
    client.post(
        "/notes/",
        data={"target_kind": "story", "target_ref": "the-fog", "body": "Ends too abruptly."},
        follow_redirects=True,
    )

    body = client.get("/stories/the-fog/edit").get_data(as_text=True)
    assert "Ends too abruptly." in body


def test_an_empty_note_is_not_saved(client):
    response = client.post(
        "/notes/",
        data={"target_kind": "subject", "target_ref": "character/mara-vance", "body": "   "},
        follow_redirects=True,
    )
    assert "empty note was not saved" in response.get_data(as_text=True)


def test_recording_a_relationship_exports_it(client, scratch_corpus):
    client.get("/relationships/")
    from sunday.store import Store

    with Store.open(client.application.config["SUNDAY_PATHS"].store) as store:
        mara = store.subject("character", "Mara Vance")
        elias = store.subject("character", "Elias Doyle")

    client.post(
        "/relationships/",
        data={
            "from_subject": mara.id,
            "to_subject": elias.id,
            "description": "sister",
            "directed": "",
        },
        follow_redirects=True,
    )

    exported = (scratch_corpus / "cast.yml").read_text(encoding="utf-8")
    assert "Mara Vance" in exported and "Elias Doyle" in exported and "sister" in exported


def test_a_relationship_reaches_the_published_diagram(client, scratch_corpus, tmp_path):
    """US9 end to end: recorded in the portal, drawn on the site."""
    import json

    from sunday.store import Store

    with Store.open(client.application.config["SUNDAY_PATHS"].store) as store:
        from sunday.corpus import load_corpus

        store.sync_subjects(load_corpus(scratch_corpus / "stories"))
        silas = store.subject("character", "Silas Thorne")
        elias = store.subject("character", "Elias Doyle")

    client.post(
        "/relationships/",
        data={
            "from_subject": silas.id,
            "to_subject": elias.id,
            "description": "rival",
            "directed": "on",
        },
        follow_redirects=True,
    )
    client.post("/build")

    graph = json.loads((tmp_path / "site" / "graph.json").read_text(encoding="utf-8"))
    stated = [e for e in graph["edges"] if e["kind"] == "stated"]

    assert len(stated) == 1
    assert stated[0]["description"] == "rival"
    assert stated[0]["directed"] is True


def test_a_character_cannot_relate_to_themselves(client):
    client.get("/relationships/")
    from sunday.store import Store

    with Store.open(client.application.config["SUNDAY_PATHS"].store) as store:
        mara = store.subject("character", "Mara Vance")

    response = client.post(
        "/relationships/",
        data={"from_subject": mara.id, "to_subject": mara.id, "description": "self"},
        follow_redirects=True,
    )
    assert "cannot be in a relationship with themselves" in response.get_data(as_text=True)


# ------------------------------------------------------------ structural guards


def _identifiers(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(node.module or "")
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(node.value)
    return found


def _portal_modules() -> list[Path]:
    return sorted(PORTAL_PACKAGE.glob("*.py"))


def test_portal_performs_no_version_control_operations():
    """T116 / FR-035: committing and pushing stay the author's responsibility."""
    forbidden = {"subprocess", "git", "pygit2", "dulwich", "os.system", "popen"}
    offenders: dict[str, set[str]] = {}

    for module in _portal_modules():
        hits = {
            token
            for token in _identifiers(module)
            if token.lower() in forbidden or token.lower().startswith("git ")
        }
        if hits:
            offenders[module.name] = hits

    assert offenders == {}, f"the portal must not touch version control: {offenders}"


def test_portal_never_writes_the_settings_file():
    """T117 / FR-006: `sunday.yml` is hand-owned and the portal never rewrites it."""
    offenders: dict[str, set[str]] = {}

    for module in _portal_modules():
        source = module.read_text(encoding="utf-8")
        tree = ast.parse(source)
        hits: set[str] = set()

        for node in ast.walk(tree):
            # Any write through a `settings` path would have to name it.
            if isinstance(node, ast.Attribute) and node.attr in {"write_text", "write_bytes", "open"}:
                target = ast.unparse(node)
                if "settings" in target:
                    hits.add(target)
            if isinstance(node, ast.Call):
                rendered = ast.unparse(node)
                if "write_cast" in rendered and "settings" in rendered:
                    hits.add(rendered)

        if hits:
            offenders[module.name] = hits

    assert offenders == {}, f"the portal must never write sunday.yml: {offenders}"
