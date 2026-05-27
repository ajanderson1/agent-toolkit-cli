"""skill migrate-to-monorepo: re-home owned per-skill entries into a monorepo."""
import json
import subprocess

from click.testing import CliRunner

from agent_toolkit_cli.cli import main as cli
from agent_toolkit_cli.skill_lock import LockEntry, LockFile, write_lock
from agent_toolkit_cli.skill_migrate import (
    RefusalReason,
    check_refusal,
    is_migratable,
    migrated_entry,
    monorepo_subpath_for,
)
from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path
from tests.conftest import scrub_git_env


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


def _git(args, cwd, env):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, env=env,
                   capture_output=True)


def _commit_all(cwd, env, msg="init"):
    _git(["add", "."], cwd, env)
    _git(["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
          "-m", msg], cwd, env)


def _setup(tmp_path, monkeypatch, slugs=("journal",)):
    """Build a monorepo parent + per-skill clones + own-repo lock entries.

    Returns (parent_url, parent_path, library_root, env).
    """
    env = scrub_git_env()
    parent = tmp_path / "parent"
    for slug in slugs:
        d = parent / "skills" / slug
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"# {slug}\n")
    _git(["init", "-q", "-b", "main"], parent, env)
    _commit_all(parent, env)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))
    skills = {}
    for slug in slugs:
        clone = library_skill_path(slug)
        clone.mkdir(parents=True)
        (clone / "SKILL.md").write_text(f"# {slug}\n")
        _git(["init", "-q", "-b", "main"], clone, env)
        _commit_all(clone, env)
        sha = subprocess.run(
            ["git", "-C", str(clone), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True, env=env,
        ).stdout.strip()
        skills[slug] = LockEntry(
            source=f"ajanderson1/{slug}-skill", source_type="github",
            skill_path="SKILL.md", upstream_sha=sha, local_sha=sha,
        )
    write_lock(library_lock_path(), LockFile(version=1, skills=skills))
    return parent_url, parent, library, env


def _lock():
    return json.loads(library_lock_path().read_text())


def test_migrate_happy_path_rewrites_entry_and_symlinks(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    entry = _lock()["skills"]["journal"]
    assert entry["source"] == parent_url or entry["source"].endswith("agent-toolkit")
    assert entry["skillPath"] == "skills/journal"
    assert "parentUrl" in entry
    assert "readOnly" not in entry
    assert "localSha" not in entry
    clone = library_skill_path("journal")
    assert clone.is_symlink()
    assert (clone / "SKILL.md").read_text() == "# journal\n"
    assert "Migrated 1" in r.output


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
