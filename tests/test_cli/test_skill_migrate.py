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


def _fail_forward_swap_for(mig, monkeypatch, slug):
    """Patch os.replace so the FORWARD swap into <slug>'s clone fails once.

    The crash-safe swap does `os.replace(clone, trash)` then
    `os.replace(tmp_link, clone)` then, on failure, `os.replace(trash, clone)`
    to restore. We must fail only the forward swap (tmp_link -> clone) and let
    the restore through, so the test exercises the real interrupted-swap path
    rather than also breaking recovery. The forward swap's `src` is the
    `.{slug}.migrating` temp link; key on that to distinguish it from restore.
    """
    real_replace = mig.os.replace

    def boom(src, dst, *a, **k):
        if str(src).endswith(f".{slug}.migrating") and str(dst).endswith(
            f"/{slug}"
        ):
            raise OSError("swap interrupted")
        return real_replace(src, dst, *a, **k)

    monkeypatch.setattr(mig.os, "replace", boom)


def test_migrate_isolates_per_skill_failure(tmp_path, monkeypatch):
    """A skill failing mid-swap is reported as an error and does NOT abort
    migration of the other eligible skills (spec: per-skill independence)."""
    parent_url, _, _, _ = _setup(
        tmp_path, monkeypatch, slugs=("journal", "mkdocs"),
    )
    _fail_forward_swap_for(_migcmd(), monkeypatch, "journal")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    # mkdocs still migrated despite journal's failure.
    assert "parentUrl" in _lock()["skills"]["mkdocs"]
    assert library_skill_path("mkdocs").is_symlink()
    # journal reported as an error, not silently dropped, and recovered.
    assert "swap interrupted" in r.output
    assert "Migrated 1" in r.output
    assert "Skipped 1" in r.output
    # Crash-safety: journal's original clone survives (restored), no half-state.
    assert not library_skill_path("journal").is_symlink()
    assert (library_skill_path("journal") / "SKILL.md").exists()
    assert "parentUrl" not in _lock()["skills"]["journal"]


# --- crash-safety regression tests (adversarial review of PR #266) ----------


def _migcmd():
    """The migrate command *module* (for monkeypatching its internals).

    `from ... import migrate_cmd` binds the click Command, not the module, so
    import the module object explicitly.
    """
    import importlib
    return importlib.import_module(
        "agent_toolkit_cli.commands.skill.migrate_cmd"
    )


def test_migrate_swap_is_crash_safe_when_finalise_fails(tmp_path, monkeypatch):
    """If the directory swap fails AFTER the clone is moved aside, the skill
    must remain recoverable — the original clone is not lost and the lock is
    not left claiming a migration that did not complete.

    This is the highest-severity adversarial finding: the old code did
    `rmtree(clone)` then `rename(tmp_link, clone)`; a failure between them
    destroyed the clone (and its git history) while the lock already said
    migrated, with no repair path on re-run.
    """
    parent_url, _, _, env = _setup(tmp_path, monkeypatch, slugs=("journal",))
    journal_clone = library_skill_path("journal")
    original_text = (journal_clone / "SKILL.md").read_text()

    # Interrupt the forward swap (tmp_link -> clone) but let the restore run.
    _fail_forward_swap_for(_migcmd(), monkeypatch, "journal")
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output

    # Recoverable: the clone content survives, either still at the clone path
    # or restorable, and the lock does NOT falsely claim a completed migration.
    assert "parentUrl" not in _lock()["skills"]["journal"], (
        "lock must not claim migration when the swap failed"
    )
    assert journal_clone.exists(), "the original clone must not be destroyed"
    assert (journal_clone / "SKILL.md").read_text() == original_text
    assert not journal_clone.is_symlink(), (
        "failed swap must leave the real clone, not a dangling symlink"
    )
    # The independent git history must survive — the core data-loss concern.
    assert (journal_clone / ".git").exists(), (
        "the clone's git history must not be lost on a failed swap"
    )
    # No orphaned sidecar/temp paths left behind for a future run to trip on.
    assert not (journal_clone.parent / ".journal.migrating").exists()
    assert not (journal_clone.parent / ".journal.trash").exists()
    assert "journal" in r.output  # reported as failed/skipped, not silent


def test_migrate_reproject_failure_is_surfaced_not_buried(tmp_path, monkeypatch):
    """A reproject (engine_apply) failure AFTER the irreversible swap must be
    surfaced loudly — the migration completed, but the user must be told the
    harness symlinks need repair. It must NOT be a silent stderr warning under
    a clean 'Migrated' banner, and the skill must NOT be mislabeled 'Skipped'.
    """
    from agent_toolkit_cli.skill_install import InstallError

    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    mig = _migcmd()

    def boom_apply(*a, **k):
        raise InstallError("conflicting symlink at projection path")

    monkeypatch.setattr(mig, "engine_apply", boom_apply)
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    # The swap DID complete — lock + symlink reflect a migration.
    assert "parentUrl" in _lock()["skills"]["journal"]
    assert library_skill_path("journal").is_symlink()
    # And the reproject failure is surfaced (loud, names a repair path), not
    # buried as a success.
    out = r.output.lower()
    assert "reproject" in out or "doctor" in out
    assert "conflicting symlink" in r.output


def test_migrate_completed_migration_not_mislabeled_skipped(tmp_path,
                                                            monkeypatch):
    """If engine_apply raises a NON-InstallError after the swap, the skill is
    still fully migrated — it must not be re-routed into 'Skipped' by the outer
    boundary catch (which would lie about a completed, irreversible change).
    """
    parent_url, _, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    mig = _migcmd()

    def boom_apply(*a, **k):
        raise OSError("unexpected fs error during reproject")

    monkeypatch.setattr(mig, "engine_apply", boom_apply)
    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    assert "parentUrl" in _lock()["skills"]["journal"]
    assert library_skill_path("journal").is_symlink()
    # Must be counted as migrated, never skipped — the destructive half is done.
    assert "Migrated 1" in r.output
    assert "Skipped 1" not in r.output


def test_migrate_recovers_leftover_migrating_symlink(tmp_path, monkeypatch):
    """A `.{slug}.migrating` leftover from a crashed prior run, where the lock
    already records the migration, must be reconciled on re-run rather than
    skipped forever. After re-run the clone path resolves into the monorepo.
    """
    parent_url, parent, _, _ = _setup(tmp_path, monkeypatch, slugs=("journal",))
    # Simulate a crash mid-swap: lock already migrated, clone dir gone, only a
    # leftover `.journal.migrating` symlink points into the monorepo subpath.
    import shutil as _sh
    clone = library_skill_path("journal")
    mono_skill = parent / "skills" / "journal"
    cur = _lock()
    cur["skills"]["journal"] = {
        "source": parent_url, "sourceType": "git",
        "skillPath": "skills/journal",
        "upstreamSha": cur["skills"]["journal"]["upstreamSha"],
        "parentUrl": parent_url,
    }
    library_lock_path().write_text(json.dumps(cur, indent=2) + "\n")
    _sh.rmtree(clone)
    leftover = clone.parent / ".journal.migrating"
    leftover.symlink_to(mono_skill, target_is_directory=True)

    r = CliRunner().invoke(cli, ["skill", "migrate-to-monorepo", parent_url])
    assert r.exit_code == 0, r.output
    # Recovered: clone path now resolves a real SKILL.md, leftover is gone.
    assert clone.is_symlink()
    assert (clone / "SKILL.md").exists()
    assert not leftover.exists()


# --- _trees_equal direct unit tests (gates the destructive swap) ------------


def test_trees_equal_true_for_identical_nested(tmp_path):
    mig = _migcmd()
    a = tmp_path / "a"
    b = tmp_path / "b"
    for root in (a, b):
        (root / "sub").mkdir(parents=True)
        (root / "SKILL.md").write_text("# s\n")
        (root / "sub" / "ref.md").write_text("ref\n")
    assert mig._trees_equal(a, b) is True


def test_trees_equal_false_for_nested_content_diff(tmp_path):
    mig = _migcmd()
    a = tmp_path / "a"
    b = tmp_path / "b"
    for root in (a, b):
        (root / "sub").mkdir(parents=True)
        (root / "SKILL.md").write_text("# s\n")
    (a / "sub" / "ref.md").write_text("one\n")
    (b / "sub" / "ref.md").write_text("two\n")
    assert mig._trees_equal(a, b) is False


def test_trees_equal_false_for_extra_file(tmp_path):
    mig = _migcmd()
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "SKILL.md").write_text("# s\n")
    (b / "SKILL.md").write_text("# s\n")
    (a / "extra.md").write_text("x\n")
    assert mig._trees_equal(a, b) is False


def test_trees_equal_ignores_git_at_any_depth(tmp_path):
    mig = _migcmd()
    a = tmp_path / "a"
    b = tmp_path / "b"
    for root in (a, b):
        root.mkdir()
        (root / "SKILL.md").write_text("# s\n")
    # A nested .git dir present only in `a` must not cause drift.
    (a / "sub" / ".git").mkdir(parents=True)
    (a / "sub" / ".git" / "HEAD").write_text("ref\n")
    (a / "sub").mkdir(exist_ok=True)
    (a / "sub" / "keep.md").write_text("k\n")
    (b / "sub").mkdir()
    (b / "sub" / "keep.md").write_text("k\n")
    assert mig._trees_equal(a, b) is True
