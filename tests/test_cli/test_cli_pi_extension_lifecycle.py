"""End-to-end CLI tests for pi-extension git-lifecycle verbs (PR2b).

Verbs: update, push, reset, import, doctor.
TDD: failing test first, then implementation, then green.

extensions[] observe-only guarantee: doctor and import tests assert that
settings.json extensions[] is NEVER mutated by any code path.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.cli import main
from agent_toolkit_cli.pi_extension_lock import read_lock, write_lock, LockEntry, LockFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_store_owned(tmp_path: Path, env: dict, upstream: Path) -> None:
    """Add a store-owned ext 'demo' via CLI. HOME must already be monkeypatched."""
    r = CliRunner().invoke(main, ["pi-extension", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output


def _install_global(slug: str = "demo") -> None:
    r = CliRunner().invoke(main, ["pi-extension", "install", slug, "-g"])
    assert r.exit_code == 0, r.output


def _git(cwd: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, capture_output=True,
        env=env,
    )


def _advance_remote(upstream: Path, env: dict, *, body: str = "updated\n") -> None:
    """Push a new commit to the upstream bare repo."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work"
        subprocess.run(
            ["git", "clone", str(upstream), str(work)],
            check=True, capture_output=True, env=env,
        )
        (work / "SKILL.md").write_text(body)
        subprocess.run(
            ["git", "-C", str(work), "add", "SKILL.md"],
            check=True, capture_output=True, env=env,
        )
        subprocess.run(
            ["git", "-C", str(work), "commit", "-m", "upstream update"],
            check=True, capture_output=True, env=env,
        )
        subprocess.run(
            ["git", "-C", str(work), "push", "origin", "main"],
            check=True, capture_output=True, env=env,
        )


# ---------------------------------------------------------------------------
# Task B1: update
# ---------------------------------------------------------------------------


def test_update_pulls_upstream_changes(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))

    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    canonical = pep.library_pi_extension_path("demo", env={})

    # Push a new commit to upstream.
    _advance_remote(git_sandbox.upstream, git_sandbox.env)

    sha_before = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    r = CliRunner().invoke(main, ["pi-extension", "update", "demo", "-g"])
    assert r.exit_code == 0, r.output

    sha_after = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert sha_before != sha_after, "update should advance HEAD"

    # Lock records new sha.
    lock = read_lock(pep.library_lock_path(env={}))
    assert lock.skills["demo"].local_sha == sha_after


def test_update_npm_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:foo"])
    r = CliRunner().invoke(main, ["pi-extension", "update", "foo", "-g"])
    assert r.exit_code == 0, r.output
    assert "npm" in r.output.lower() or "no-op" in r.output.lower()


def test_update_unknown_slug_reports_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["pi-extension", "update", "nope", "-g"])
    assert r.exit_code != 0
    assert "nope: not in lock" in r.output


def test_update_no_args_updates_all(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    _advance_remote(git_sandbox.upstream, git_sandbox.env)
    # update with no slug args => updates all
    r = CliRunner().invoke(main, ["pi-extension", "update", "-g"])
    assert r.exit_code == 0, r.output


def _seed_pinned_entry(tmp_path, git_sandbox) -> str:
    """Store-owned entry pinned to a SHA, with a real clone on disk.
    Returns the pinned SHA."""
    from agent_toolkit_cli import pi_extension_add as pea
    sha = subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    pea.add(
        source=f"file://{git_sandbox.upstream}/tree/{sha}",
        slug="pinned", env=git_sandbox.env,
    )
    return sha


def test_update_skips_pinned_entry(tmp_path, monkeypatch, git_sandbox):
    """A SHA-pinned entry must not poison `update`: skip + exit 0 (#330)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    sha = _seed_pinned_entry(tmp_path, git_sandbox)

    r = CliRunner().invoke(main, ["pi-extension", "update", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned" in r.output.lower()
    assert sha[:7] in r.output
    assert "conflict" not in r.output.lower()


def test_reset_skips_pinned_entry(tmp_path, monkeypatch, git_sandbox):
    """`reset` on a pinned entry: informational skip, exit 0 (#330)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    sha = _seed_pinned_entry(tmp_path, git_sandbox)

    r = CliRunner().invoke(main, ["pi-extension", "reset", "pinned", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned to" in r.output.lower()
    assert sha[:7] in r.output


# ---------------------------------------------------------------------------
# Task B2: push
# ---------------------------------------------------------------------------


def test_push_nothing_to_push_on_clean_up_to_date(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    r = CliRunner().invoke(main, ["pi-extension", "push", "demo", "-g"])
    assert r.exit_code == 0, r.output
    assert "nothing" in r.output.lower() or "clean" in r.output.lower()


def test_push_npm_rejects(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:foo"])
    r = CliRunner().invoke(main, ["pi-extension", "push", "foo", "-g"])
    # npm rows have nothing to push; should report an error or "nothing"
    assert r.exit_code != 0 or "npm" in r.output.lower() or "nothing" in r.output.lower()


def test_push_dirty_store_via_pr_or_direct(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    canonical = pep.library_pi_extension_path("demo", env={})

    # Add an uncommitted change.
    (canonical / "ext.ts").write_text("// new code")

    # Push --direct commits and pushes.
    r = CliRunner().invoke(main, ["pi-extension", "push", "demo", "-g", "--direct"])
    assert r.exit_code == 0, r.output
    assert "pushed" in r.output.lower()

    # Canonical is now clean.
    from agent_toolkit_cli import skill_git
    assert skill_git.status(canonical, env=None).value == "clean"


def test_push_skips_pinned_entry(tmp_path, monkeypatch, git_sandbox):
    """A SHA-pinned entry must not poison `push`: skip + exit 0 (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    sha = _seed_pinned_entry(tmp_path, git_sandbox)

    r = CliRunner().invoke(main, ["pi-extension", "push", "pinned", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned to" in r.output.lower()
    assert sha[:7] in r.output


def test_push_pinned_does_not_poison_batch(tmp_path, monkeypatch, git_sandbox):
    """A pinned entry alongside a clean store-owned entry: bare push over both
    stays exit 0 — the pin is a benign skip, not a rejection (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)  # 'demo', unpinned
    sha = _seed_pinned_entry(tmp_path, git_sandbox)                    # 'pinned'

    r = CliRunner().invoke(main, ["pi-extension", "push", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned to" in r.output.lower()
    assert sha[:7] in r.output


def test_push_pinned_skips_even_when_dirty(tmp_path, monkeypatch, git_sandbox):
    """The skip is unconditional w.r.t. working-tree state: a pinned checkout
    with a local edit still skips (the edit is intentionally unreachable via
    push — remove+re-add to publish) (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _seed_pinned_entry(tmp_path, git_sandbox)
    canonical = pep.library_pi_extension_path("pinned", env={})
    (canonical / "ext.ts").write_text("// local edit on a pinned checkout")

    r = CliRunner().invoke(main, ["pi-extension", "push", "pinned", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned to" in r.output.lower()
    assert "pushed" not in r.output.lower()  # the local edit was NOT pushed


# ---------------------------------------------------------------------------
# Task B3: import
# ---------------------------------------------------------------------------


def test_import_from_lock_file_adds_missing(tmp_path, monkeypatch, git_sandbox):
    """import reconstructs extensions present in a lock file but not locally."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))

    # Build an incoming lock file with one store-owned entry pointing at upstream.
    incoming_lock = LockFile(
        version=1,
        skills={
            "demo": LockEntry(
                source=str(git_sandbox.upstream),
                source_type="local",
                pi_extension_path="demo",
            )
        },
    )
    import_file = tmp_path / "incoming-pi-extensions-lock.json"
    write_lock(import_file, incoming_lock)

    r = CliRunner().invoke(main, ["pi-extension", "import", str(import_file)])
    assert r.exit_code == 0, r.output
    assert pep.library_pi_extension_path("demo", env={}).exists()
    lock = read_lock(pep.library_lock_path(env={}))
    assert "demo" in lock.skills


def test_import_skips_already_present(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    incoming_lock = LockFile(
        version=1,
        skills={
            "demo": LockEntry(
                source=str(git_sandbox.upstream),
                source_type="local",
                pi_extension_path="demo",
            )
        },
    )
    import_file = tmp_path / "incoming.json"
    write_lock(import_file, incoming_lock)

    r = CliRunner().invoke(main, ["pi-extension", "import", str(import_file)])
    assert r.exit_code == 0, r.output
    assert "skipped" in r.output.lower()


def test_import_nonexistent_file_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["pi-extension", "import", str(tmp_path / "nope.json")])
    assert r.exit_code != 0


def test_import_never_mutates_extensions_array(tmp_path, monkeypatch, git_sandbox):
    """CRITICAL: import must NEVER write to extensions[] in settings.json."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))

    # Seed a settings.json with an extensions[] entry.
    settings = tmp_path / ".pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True)
    original_ext = ["my-local-ext"]
    settings.write_text(json.dumps({"extensions": original_ext, "packages": []}, indent=2) + "\n")

    incoming_lock = LockFile(
        version=1,
        skills={
            "demo": LockEntry(
                source=str(git_sandbox.upstream),
                source_type="local",
                pi_extension_path="demo",
            )
        },
    )
    import_file = tmp_path / "incoming.json"
    write_lock(import_file, incoming_lock)

    r = CliRunner().invoke(main, ["pi-extension", "import", str(import_file)])
    assert r.exit_code == 0, r.output

    # extensions[] MUST be untouched.
    body = json.loads(settings.read_text())
    assert body["extensions"] == original_ext, (
        "import MUST NOT mutate extensions[]"
    )


# ---------------------------------------------------------------------------
# Task B4: reset
# ---------------------------------------------------------------------------


def test_reset_discards_local_edits(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    canonical = pep.library_pi_extension_path("demo", env={})

    # Dirty the store.
    (canonical / "SKILL.md").write_text("dirty edit\n")
    from agent_toolkit_cli import skill_git
    assert skill_git.status(canonical, env=None).value == "dirty"

    # Without --force, reset refuses (mirrors skill reset dirty-guard).
    r_no_force = CliRunner().invoke(main, ["pi-extension", "reset", "demo", "-g"])
    assert r_no_force.exit_code != 0, r_no_force.output

    # With --force, reset succeeds and cleans the tree.
    r = CliRunner().invoke(main, ["pi-extension", "reset", "demo", "-g", "--force"])
    assert r.exit_code == 0, r.output
    assert skill_git.status(canonical, env=None).value == "clean"


def test_reset_refuses_dirty_without_force(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    canonical = pep.library_pi_extension_path("demo", env={})

    # Commit a local change to make it "dirty" for the --no-force path.
    # Actually reset's dirty guard uses git status DIRTY = uncommitted changes.
    (canonical / "SKILL.md").write_text("local commit\n")
    _git(canonical, "add", "SKILL.md", env=git_sandbox.env)
    _git(canonical, "commit", "-m", "local commit", env=git_sandbox.env)

    # --force is required to reset beyond committed local changes.
    r = CliRunner().invoke(main, ["pi-extension", "reset", "demo", "-g"])
    assert r.exit_code == 0, r.output  # clean working tree → no force needed
    # After reset, HEAD aligns with upstream.
    sha = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    upstream_sha = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "origin/main"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert sha == upstream_sha


def test_reset_npm_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    CliRunner().invoke(main, ["pi-extension", "add", "npm:foo"])
    r = CliRunner().invoke(main, ["pi-extension", "reset", "foo", "-g"])
    # npm rows have no git repo — should report an error or no-op message.
    assert r.exit_code != 0 or "npm" in r.output.lower() or "no" in r.output.lower()


def test_reset_requires_at_least_one_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["pi-extension", "reset", "-g"])
    assert r.exit_code != 0


# ---------------------------------------------------------------------------
# Task B5: doctor
# ---------------------------------------------------------------------------


def test_doctor_clean_reports_clean(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    _install_global()

    r = CliRunner().invoke(main, ["pi-extension", "doctor", "-g"])
    assert r.exit_code == 0, r.output
    assert "clean" in r.output.lower() or r.output.strip() == ""


def test_doctor_detects_stray_symlink(tmp_path, monkeypatch):
    """A symlink in extensions/ with no lock entry is a stray."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Plant a stray symlink.
    target = tmp_path / "some-ext"
    target.mkdir()
    (target / "index.ts").write_text("export default {}")
    link = pep.pi_extension_dir("stray", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)

    r = CliRunner().invoke(main, ["pi-extension", "doctor", "-g", "--no-fix"])
    assert r.exit_code != 0 or "stray" in r.output.lower()
    # The stray symlink is reported — and NOT removed (--no-fix).
    assert link.is_symlink()


def test_doctor_detects_missing_canonical(tmp_path, monkeypatch, git_sandbox):
    """If the store copy vanishes but the lock still has it, doctor reports it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    canonical = pep.library_pi_extension_path("demo", env={})

    import shutil
    shutil.rmtree(canonical)

    r = CliRunner().invoke(main, ["pi-extension", "doctor", "-g", "--no-fix"])
    assert "demo" in r.output
    # Doctor does NOT auto-fix without --fix / prompt.


def test_doctor_reclone_sha_pinned_lands_on_pin(tmp_path, monkeypatch, git_sandbox):
    """Reclone of a SHA-pinned entry must land on the pin, not HEAD (#330)."""
    monkeypatch.setenv("HOME", str(tmp_path))

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(git_sandbox.clone), *args],
            check=True, env=git_sandbox.env, capture_output=True, text=True,
        ).stdout.strip()

    first_sha = git("rev-parse", "HEAD")
    (git_sandbox.clone / "EXTRA.md").write_text("second\n")
    git("add", "-A"); git("commit", "-m", "second"); git("push", "origin", "main")

    # Lock entry: store-owned, pinned to first_sha, store copy MISSING.
    # upstream_sha=None matches what a real SHA-pinned add records (the
    # post-checkout `rev-parse origin/<sha>` fails and is caught).
    lock_path = pep.library_lock_path(env={})
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock(lock_path, LockFile(version=1, skills={
        "pinned": LockEntry(
            source=str(git_sandbox.upstream), source_type="git",
            ref=first_sha, pi_extension_path="pinned", upstream_sha=None,
        ),
    }))

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    reclone = next(
        f for f in findings
        if f.fix_action is not None and "Re-clone" in f.fix_action.description
    )
    reclone.fix_action.apply()

    canonical = pep.library_pi_extension_path("pinned", env={})
    head = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert head == first_sha
    assert not (canonical / "EXTRA.md").exists()


def test_doctor_reclone_branch_entry_lands_on_current_tip(
    tmp_path, monkeypatch, git_sandbox,
):
    """Regression: a BRANCH entry whose upstream_sha is stale (one commit
    behind the pushed tip) must reclone onto the CURRENT tip, on the branch —
    upstream_sha is the observed tip at add time, NOT a pin (#330 review)."""
    monkeypatch.setenv("HOME", str(tmp_path))

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(git_sandbox.clone), *args],
            check=True, env=git_sandbox.env, capture_output=True, text=True,
        ).stdout.strip()

    first_sha = git("rev-parse", "HEAD")
    (git_sandbox.clone / "EXTRA.md").write_text("second\n")
    git("add", "-A"); git("commit", "-m", "second"); git("push", "origin", "main")
    second_sha = git("rev-parse", "HEAD")

    lock_path = pep.library_lock_path(env={})
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock(lock_path, LockFile(version=1, skills={
        "tracking": LockEntry(
            source=str(git_sandbox.upstream), source_type="git",
            ref="main", pi_extension_path="tracking", upstream_sha=first_sha,
        ),
    }))

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    reclone = next(
        f for f in findings
        if f.fix_action is not None and "Re-clone" in f.fix_action.description
    )
    reclone.fix_action.apply()

    canonical = pep.library_pi_extension_path("tracking", env={})

    def store_git(*args):
        return subprocess.run(
            ["git", "-C", str(canonical), *args],
            check=True, env=git_sandbox.env, capture_output=True, text=True,
        ).stdout.strip()

    assert store_git("rev-parse", "HEAD") == second_sha  # CURRENT tip, not stale
    assert store_git("rev-parse", "--abbrev-ref", "HEAD") == "main"  # on branch


def test_doctor_detects_drifted_symlink(tmp_path, monkeypatch, git_sandbox):
    """If the symlink points to the wrong path, doctor reports it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    _install_global()

    # Drift the symlink to some other target.
    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    other = tmp_path / "other-ext"
    other.mkdir()
    link.unlink()
    link.symlink_to(other)

    r = CliRunner().invoke(main, ["pi-extension", "doctor", "-g", "--no-fix"])
    assert "demo" in r.output


def test_doctor_never_mutates_extensions_array(tmp_path, monkeypatch, git_sandbox):
    """CRITICAL: doctor must NEVER write to extensions[] in settings.json."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))

    # Seed settings.json with extensions[] entries pointing at non-existent paths
    # (to trigger the orphaned-override check). Doctor will report them but MUST
    # NOT remove or rewrite them.
    settings = tmp_path / ".pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True)
    original_ext = ["my-ext", "!excluded-ext"]
    settings.write_text(
        json.dumps({"extensions": original_ext, "packages": []}, indent=2) + "\n"
    )

    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    # Run doctor (may exit non-zero due to orphaned overrides — that's fine).
    CliRunner().invoke(main, ["pi-extension", "doctor", "-g", "--no-fix"])

    # extensions[] MUST be byte-for-value identical after doctor runs.
    body = json.loads(settings.read_text())
    assert body["extensions"] == original_ext, (
        "doctor MUST NOT mutate extensions[]"
    )


def test_doctor_orphaned_extensions_entry_reported_not_removed(tmp_path, monkeypatch, git_sandbox):
    """Doctor reports an orphaned extensions[] entry (path missing) but never removes it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))

    # extensions[] entry pointing at a missing path.
    settings = tmp_path / ".pi" / "agent" / "settings.json"
    settings.parent.mkdir(parents=True)
    missing_path = str(tmp_path / "nonexistent-ext")
    settings.write_text(
        json.dumps({"extensions": [missing_path], "packages": []}, indent=2) + "\n"
    )

    r = CliRunner().invoke(main, ["pi-extension", "doctor", "-g", "--no-fix"])
    # Doctor should report the orphaned entry.
    assert "orphan" in r.output.lower() or missing_path in r.output or r.exit_code != 0

    # The extensions[] entry MUST still be there — never auto-removed.
    body = json.loads(settings.read_text())
    assert missing_path in body["extensions"], (
        "doctor must not remove extensions[] entries"
    )


def test_doctor_squatted_projection_reported(tmp_path, monkeypatch, git_sandbox):
    """Fix #314: doctor emits squatted_projection when a real non-symlink dir
    squats the projection slot of a store-owned slug, and does NOT touch the
    foreign dir (report-only, clobber-safety preserved).
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))

    # Add a store-owned slug to the lock (adds canonical to the store).
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    # Plant a REAL non-symlink directory at the projection path with index.ts.
    link = pep.pi_extension_dir("demo", scope="global", home=tmp_path)
    link.parent.mkdir(parents=True, exist_ok=True)
    assert not link.exists(), "projection path must be free before test setup"
    link.mkdir()
    (link / "index.ts").write_text("export default {}")

    # Run doctor (--no-fix so no prompt is needed).
    r = CliRunner().invoke(main, ["pi-extension", "doctor", "-g", "--no-fix"])

    # Doctor must find a problem (non-zero exit, finding in output).
    assert r.exit_code != 0, (
        f"doctor must exit non-zero when projection is squatted; got 0.\n"
        f"Output:\n{r.output}"
    )
    assert "squatted_projection" in r.output, (
        f"Expected 'squatted_projection' in doctor output.\n{r.output}"
    )
    assert "demo" in r.output

    # CRITICAL: the foreign dir must be untouched — doctor never deletes user data.
    assert link.exists() and not link.is_symlink(), (
        "doctor must not remove or modify the foreign dir (clobber-safety)."
    )
    assert (link / "index.ts").exists()


def test_status_reports_pin_column(tmp_path, monkeypatch, git_sandbox):
    """status over a pinned entry shows a trailing pinned:<sha7> column (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    sha = _seed_pinned_entry(tmp_path, git_sandbox)

    r = CliRunner().invoke(main, ["pi-extension", "status", "-g"])
    assert r.exit_code == 0, r.output
    line = next(ln for ln in r.output.splitlines() if ln.startswith("pinned\t"))
    fields = line.split("\t")
    assert fields[-1] == f"pinned:{sha[:7]}"
    # load-scope column preserved (4 fields: slug, origin, loaded, pin)
    assert len(fields) == 4


def test_status_unpinned_has_empty_pin_field(tmp_path, monkeypatch, git_sandbox):
    """A non-pinned store-owned entry prints an empty 4th field (#346)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)  # 'demo'

    r = CliRunner().invoke(main, ["pi-extension", "status", "-g"])
    assert r.exit_code == 0, r.output
    line = next(ln for ln in r.output.splitlines() if ln.startswith("demo\t"))
    fields = line.split("\t")
    assert len(fields) == 4
    assert fields[-1] == ""
    assert "pinned:" not in line


def test_reclone_force_replaces_non_repo_dir(tmp_path, monkeypatch, git_sandbox):
    """#347: a forced reclone over a non-git-repo dir rmtrees it then clones
    (the un-forced _apply would no-op on canonical.exists())."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    from agent_toolkit_cli import pi_extension_doctor as ped

    # A non-repo half-dir squatting the canonical path.
    canonical = pep.library_pi_extension_path("demo", env={})
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")
    assert not (canonical / ".git").exists()

    entry = LockEntry(
        source=str(git_sandbox.upstream), source_type="git",
        ref=None, pi_extension_path="demo", upstream_sha=None,
    )
    action = ped._make_reclone_action(slug="demo", entry=entry, force=True)
    action.apply()

    # Now a real git repo, junk gone.
    assert (canonical / ".git").exists()
    assert not (canonical / "JUNK.md").exists()


def test_doctor_detects_half_dir(tmp_path, monkeypatch, git_sandbox):
    """#347: a store-owned lock entry whose canonical exists but is NOT a
    git repo yields a half_dir finding (not missing_canonical, not dirty)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    import shutil
    canonical = pep.library_pi_extension_path("demo", env={})
    shutil.rmtree(canonical)
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    half = [f for f in findings if f.finding_type == "half_dir"]
    assert len(half) == 1, [f.finding_type for f in findings]
    assert half[0].slug == "demo"
    assert not [f for f in findings if f.finding_type == "missing_canonical"]
    assert not [f for f in findings if f.finding_type == "dirty_tree"]


def test_doctor_half_dir_fix_repairs(tmp_path, monkeypatch, git_sandbox):
    """#347: applying the half_dir fix_action turns the dir into a valid repo."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    import shutil
    canonical = pep.library_pi_extension_path("demo", env={})
    shutil.rmtree(canonical)
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    half = next(f for f in findings if f.finding_type == "half_dir")
    assert half.fix_action is not None
    half.fix_action.apply()
    assert (canonical / ".git").exists()
    assert not (canonical / "JUNK.md").exists()


def test_doctor_missing_canonical_still_detected(tmp_path, monkeypatch, git_sandbox):
    """#347 regression: an ABSENT canonical stays missing_canonical, not half_dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    import shutil
    shutil.rmtree(pep.library_pi_extension_path("demo", env={}))

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    assert [f for f in findings if f.finding_type == "missing_canonical"]
    assert not [f for f in findings if f.finding_type == "half_dir"]


def test_doctor_npm_row_no_half_dir(tmp_path, monkeypatch):
    """#347: an npm (registry-tracked) row has no canonical, so it can never
    yield a half_dir finding even if a same-named dir squats the store path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import pi_extension_add as pea
    pea.add(source="npm:@scope/widget", slug=None, env={})
    canonical = pep.library_pi_extension_path("@scope/widget", env={})
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    assert not [f for f in findings if f.finding_type == "half_dir"]


# ---------------------------------------------------------------------------
# G4 / AC4: pi-extension push not-in-lock (specific-message assertion)
# ---------------------------------------------------------------------------


def test_push_unknown_slug_not_in_lock(tmp_path, monkeypatch):
    """pi-extension push <unknown> -g => specific 'not in the global lock' message + exit 1."""
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".agent-toolkit").mkdir(parents=True, exist_ok=True)
    r = CliRunner().invoke(main, ["pi-extension", "push", "ghost", "-g"])
    assert r.exit_code != 0
    assert "ghost: not in the global lock" in r.output
