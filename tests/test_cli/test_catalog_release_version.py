"""Version labels describe the fetched catalogue, never its schema or another commit."""

import pytest

from agent_toolkit_cli.skill_catalog import fetch_catalog
from tests.test_cli.test_reground import git
from tests.test_cli.test_skill_catalog import catalog_repo


@pytest.mark.parametrize("annotated", [False, True])
def test_version_comes_from_release_tag_at_fetched_commit(tmp_path, annotated):
    cat = catalog_repo(tmp_path, {"version": 2, "entries": []})
    args = ("-a", "v1.1.0", "-m", "release") if annotated else ("v1.1.0",)
    git(cat, "-c", "user.name=Test", "-c", "user.email=test@example.test", "tag", *args)
    snapshot = fetch_catalog(cat.as_uri())
    assert not snapshot.error
    assert snapshot.version == "v1.1.0"
    assert snapshot.revision == git(cat, "rev-parse", "HEAD")


def test_multiple_matching_tags_choose_numeric_not_lexical_version(tmp_path):
    cat = catalog_repo(tmp_path, {"version": 2, "entries": []})
    for tag in ("v1.9.0", "v1.10.0", "other-label"):
        git(cat, "tag", tag)
    assert fetch_catalog(cat.as_uri()).version == "v1.10.0"


def test_untagged_updates_do_not_claim_previous_release_or_schema_version(tmp_path):
    cat = catalog_repo(tmp_path, {"version": 2, "entries": []})
    git(cat, "tag", "v1.1.0")
    git(cat, "-c", "user.name=Test", "-c", "user.email=test@example.test",
        "commit", "--allow-empty", "-m", "unreleased update")
    snapshot = fetch_catalog(cat.as_uri(), "main")
    assert not snapshot.error
    assert snapshot.version is None
    assert snapshot.revision == git(cat, "rev-parse", "HEAD")
    assert fetch_catalog(cat.as_uri(), "v1.1.0").version == "v1.1.0"


def test_optional_tag_lookup_failure_does_not_hide_catalogue(tmp_path, monkeypatch):
    import agent_toolkit_cli.skill_catalog as transport

    cat = catalog_repo(tmp_path, {"version": 2, "entries": []})
    real_git = transport.run_git

    def unavailable_tags(args, **kwargs):
        if args[0] == "ls-remote":
            raise ValueError("tag lookup unavailable")
        return real_git(args, **kwargs)

    monkeypatch.setattr(transport, "run_git", unavailable_tags)
    snapshot = fetch_catalog(cat.as_uri())
    assert not snapshot.error
    assert snapshot.revision == git(cat, "rev-parse", "HEAD")
    assert snapshot.version is None
