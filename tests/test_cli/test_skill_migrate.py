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


def test_migrate_skips_sha_diverged(tmp_path, monkeypatch):
    parent_url, _, _, env = _setup(tmp_path, monkeypatch, slugs=("journal",))
    # Local commit in the clone so head != recorded upstream_sha.
    clone = library_skill_path("journal")
    (clone / "SKILL.md").write_text("# journal\nlocal edit\n")
    _commit_all(clone, env, msg="local improvement")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    entry = _lock()["skills"]["journal"]
    assert entry["source"] == "ajanderson1/journal-skill"  # untouched
    assert "parentUrl" not in entry
    assert not library_skill_path("journal").is_symlink()  # clone preserved
    assert "Skipped 1" in r.output
    assert "journal" in r.output


def test_migrate_skips_dirty_tree(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    # Uncommitted edit: head == upstream_sha but tree dirty.
    (library_skill_path("journal") / "SKILL.md").write_text("# journal\nWIP\n")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    assert "parentUrl" not in _lock()["skills"]["journal"]
    assert not library_skill_path("journal").is_symlink()
    assert "Skipped 1" in r.output


def test_migrate_skips_content_drift(tmp_path, monkeypatch):
    parent_url, parent, _, env = _setup(tmp_path, monkeypatch, slugs=("journal",))
    # Diverge the MONOREPO copy so it differs from the clean, in-sync clone.
    (parent / "skills" / "journal" / "SKILL.md").write_text("# journal\nDRIFT\n")
    _commit_all(parent, env, msg="monorepo drift")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    assert "parentUrl" not in _lock()["skills"]["journal"]   # untouched
    assert not library_skill_path("journal").is_symlink()    # clone preserved
    assert "Skipped 1" in r.output


def test_migrate_skips_owned_not_in_monorepo(tmp_path, monkeypatch):
    # Monorepo has only journal; repo-recon owned entry exists but isn't folded.
    parent_url, parent, _, env = _setup(tmp_path, monkeypatch, slugs=("journal",))
    clone = library_skill_path("repo-recon")
    clone.mkdir(parents=True)
    (clone / "SKILL.md").write_text("# repo-recon\n")
    _git(["init", "-q", "-b", "main"], clone, env)
    _commit_all(clone, env)
    sha = subprocess.run(["git", "-C", str(clone), "rev-parse", "HEAD"],
                         check=True, capture_output=True, text=True,
                         env=env).stdout.strip()
    cur = _lock()
    cur["skills"]["repo-recon"] = {
        "source": "ajanderson1/repo-recon-skill", "sourceType": "github",
        "skillPath": "SKILL.md", "upstreamSha": sha, "localSha": sha,
    }
    library_lock_path().write_text(json.dumps(cur, indent=2) + "\n")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    assert "parentUrl" in _lock()["skills"]["journal"]        # migrated
    assert "parentUrl" not in _lock()["skills"]["repo-recon"] # skipped
    assert not library_skill_path("repo-recon").is_symlink()
    assert "Migrated 1" in r.output
    assert "Skipped 1" in r.output


def test_migrate_never_touches_third_party_readonly(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    cur = _lock()
    cur["skills"]["pdf"] = {
        "source": "anthropics/skills", "sourceType": "github",
        "skillPath": "skills/pdf", "upstreamSha": "x",
        "parentUrl": "https://github.com/anthropics/skills", "readOnly": True,
    }
    library_lock_path().write_text(json.dumps(cur, indent=2) + "\n")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    pdf = _lock()["skills"]["pdf"]
    assert pdf["source"] == "anthropics/skills"   # untouched
    assert pdf["readOnly"] is True


def test_migrate_is_idempotent(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    r1 = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r1.exit_code == 0, r1.output
    assert "Migrated 1" in r1.output
    # Second run: journal now has parentUrl -> ineligible -> no-op.
    r2 = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r2.exit_code == 0, r2.output
    assert "Migrated 1" not in r2.output
    assert library_skill_path("journal").is_symlink()  # still a symlink
    assert "parentUrl" in _lock()["skills"]["journal"]


def test_migrate_dry_run_writes_nothing(tmp_path, monkeypatch):
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    r = CliRunner().invoke(
        cli, ["skill", "migrate-to-monorepo", parent_url, "--dry-run"])
    assert r.exit_code == 0, r.output
    assert "Would migrate 1" in r.output
    entry = _lock()["skills"]["journal"]
    assert "parentUrl" not in entry                       # nothing written
    assert not library_skill_path("journal").is_symlink()  # clone intact
