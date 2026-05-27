"""skill migrate-to-monorepo: re-home owned per-skill entries into a monorepo."""
import json  # noqa: F401
import subprocess  # noqa: F401
from pathlib import Path  # noqa: F401

from click.testing import CliRunner  # noqa: F401

from agent_toolkit_cli.cli import main as cli  # noqa: F401
from agent_toolkit_cli.skill_lock import LockEntry, LockFile, write_lock  # noqa: F401
from agent_toolkit_cli.skill_migrate import is_migratable, monorepo_subpath_for
from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path  # noqa: F401
from tests.conftest import scrub_git_env  # noqa: F401


def test_monorepo_subpath_for_uses_bare_slug():
    assert monorepo_subpath_for("journal") == "skills/journal"


def test_is_migratable_true_for_own_repo_shape():
    e = LockEntry(source="ajanderson1/journal-skill", source_type="github",
                  skill_path="SKILL.md", upstream_sha="a", local_sha="a")
    assert is_migratable(e) is True


def test_is_migratable_true_for_renamed_source():
    e = LockEntry(source="ajanderson1/journal", source_type="github",
                  skill_path="SKILL.md", upstream_sha="a", local_sha="a")
    assert is_migratable(e) is True


def test_is_migratable_false_when_already_monorepo():
    e = LockEntry(source="ajanderson1/agent-toolkit", source_type="github",
                  skill_path="skills/journal", upstream_sha="a",
                  parent_url="https://github.com/ajanderson1/agent-toolkit")
    assert is_migratable(e) is False


def test_is_migratable_false_for_third_party_readonly():
    e = LockEntry(source="anthropics/skills", source_type="github",
                  skill_path="skills/pdf", upstream_sha="a",
                  parent_url="https://github.com/anthropics/skills",
                  read_only=True)
    assert is_migratable(e) is False


from agent_toolkit_cli.skill_migrate import RefusalReason, check_refusal  # noqa: E402


def test_check_refusal_none_when_all_clean():
    assert check_refusal(sha_match=True, tree_clean=True,
                          content_matches=True, in_monorepo=True) is None


def test_check_refusal_not_in_monorepo():
    assert check_refusal(sha_match=True, tree_clean=True,
                         content_matches=True,
                         in_monorepo=False) is RefusalReason.NOT_IN_MONOREPO


def test_check_refusal_sha_divergence():
    assert check_refusal(sha_match=False, tree_clean=True,
                         content_matches=True,
                         in_monorepo=True) is RefusalReason.SHA_DIVERGED


def test_check_refusal_dirty_tree():
    assert check_refusal(sha_match=True, tree_clean=False,
                         content_matches=True,
                         in_monorepo=True) is RefusalReason.DIRTY_TREE


def test_check_refusal_content_drift():
    assert check_refusal(sha_match=True, tree_clean=True,
                         content_matches=False,
                         in_monorepo=True) is RefusalReason.CONTENT_DRIFT


def test_refusal_reason_has_hint():
    for r in RefusalReason:
        assert r.hint  # non-empty string


from agent_toolkit_cli.skill_migrate import migrated_entry  # noqa: E402


def test_migrated_entry_has_owned_monorepo_shape():
    old = LockEntry(source="ajanderson1/journal-skill", source_type="github",
                    skill_path="SKILL.md", upstream_sha="old", local_sha="old")
    new = migrated_entry(
        old, slug="journal",
        parent_source="ajanderson1/agent-toolkit",
        parent_url="https://github.com/ajanderson1/agent-toolkit",
        parent_sha="PARENTHEAD",
    )
    assert new.source == "ajanderson1/agent-toolkit"
    assert new.skill_path == "skills/journal"
    assert new.parent_url == "https://github.com/ajanderson1/agent-toolkit"
    assert new.upstream_sha == "PARENTHEAD"
    assert new.local_sha is None
    assert new.read_only is False
    assert new.source_type == "github"
