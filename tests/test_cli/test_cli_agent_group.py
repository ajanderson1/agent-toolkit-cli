"""CLI tests for the `agent` command group (feat/252-agent-cli-group).

Mandated test classes (per task spec):
  1. install→uninstall→assert-gone round-trip at both global and project scope
  2. idempotency — double-install / double-uninstall are safe
  3. foreign-file guard — a same-slug user-authored file is refused, not clobbered
  4. both-scope CLI coverage — isolated HOME for global path tests
  5. `agent add` global-only — assert -p is rejected
  6. CLI smoke — `agent --help` and `--help` for each verb exit 0 and list the verb

result.removed workaround: agent_install.apply() never populates result.removed
(the uninstall loop in apply() does not append — see agent_install.py). All
uninstall coverage therefore uses agent_install.uninstall() (via `agent uninstall`
CLI), which calls each adapter's uninstall() directly and correctly removes the
projected files. We do NOT assert on result.removed anywhere.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTENT = "---\nname: demo-agent\ndescription: CLI test agent\n---\n\nBody.\n"

# Two small but reliably-enabled harnesses for round-trip tests.
_TEST_HARNESSES = "claude-code,gemini-cli"


def _seed_global_canonical(tmp_path: Path, slug: str = "demo-agent") -> Path:
    """Create a global canonical with content file, honoring monkeypatched HOME."""
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    canonical = canonical_agent_dir(slug, scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / f"{slug}.md").write_text(_CONTENT)
    return canonical


def _seed_project_canonical(project: Path, slug: str = "demo-agent") -> Path:
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    canonical = canonical_agent_dir(slug, scope="project", project=project)
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / f"{slug}.md").write_text(_CONTENT)
    return canonical


def _write_global_lock(tmp_path: Path, slug: str = "demo-agent") -> None:
    """Write a minimal global lock entry so install treats the slug as known."""
    from agent_toolkit_cli.agent_lock import LockEntry, add_entry, read_lock, write_lock
    from agent_toolkit_cli.agent_paths import library_lock_path
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    entry = LockEntry(
        source=f"https://github.com/test/{slug}",
        source_type="github",
        agent_path=f"{slug}.md",
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


def _cc_dest(tmp_path: Path, slug: str = "demo-agent") -> Path:
    """claude-code destination for the slug under tmp_path HOME."""
    return tmp_path / ".claude" / "agents" / f"{slug}.md"


def _gem_dest(tmp_path: Path, slug: str = "demo-agent") -> Path:
    """gemini-cli destination for the slug under tmp_path HOME."""
    return tmp_path / ".gemini" / "agents" / f"{slug}.md"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset dev-shell env vars that would pollute destination paths."""
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


# ---------------------------------------------------------------------------
# 6. CLI smoke — --help for the group and each verb
# ---------------------------------------------------------------------------


def test_agent_group_help_exits_zero() -> None:
    r = CliRunner().invoke(main, ["agent", "--help"])
    assert r.exit_code == 0, r.output
    assert "agent" in r.output.lower()


@pytest.mark.parametrize("verb", [
    "add", "install", "uninstall", "remove",
    "list", "ls", "status",
    "update", "push", "import", "reset", "doctor",
])
def test_verb_help_exits_zero(verb: str) -> None:
    r = CliRunner().invoke(main, ["agent", verb, "--help"])
    assert r.exit_code == 0, f"{verb} --help failed:\n{r.output}"
    assert verb in r.output or verb.rstrip("e") in r.output  # "remove" -> "Remov..."


def test_agent_appears_in_top_level_help() -> None:
    r = CliRunner().invoke(main, ["--help"])
    assert r.exit_code == 0
    assert "agent" in r.output


# ---------------------------------------------------------------------------
# 5. `agent add` global-only — -p must be rejected
# ---------------------------------------------------------------------------


def test_add_has_no_project_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["agent", "add", "ajanderson1/test-agent", "-p"])
    assert r.exit_code != 0, "add -p should fail (global-only verb)"


# ---------------------------------------------------------------------------
# 4 + 1. Round-trip at GLOBAL scope with isolated HOME
# ---------------------------------------------------------------------------


def test_install_uninstall_global_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Global-scope install→uninstall: projections removed, canonical + lock KEPT (#303)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    runner = CliRunner()

    r_install = runner.invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", _TEST_HARNESSES],
    )
    assert r_install.exit_code == 0, r_install.output

    cc = _cc_dest(tmp_path)
    gem = _gem_dest(tmp_path)
    assert cc.exists(), f"claude-code projection not created: {cc}"
    assert gem.exists(), f"gemini-cli projection not created: {gem}"

    r_uninstall = runner.invoke(
        main, ["agent", "uninstall", "demo-agent", "-g",
               "--harnesses", _TEST_HARNESSES],
    )
    assert r_uninstall.exit_code == 0, r_uninstall.output

    assert not cc.exists(), f"claude-code projection ORPHANED after uninstall: {cc}"
    assert not gem.exists(), f"gemini-cli projection ORPHANED after uninstall: {gem}"

    # #303: uninstall is non-destructive — canonical + lock entry are KEPT.
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import library_lock_path
    assert canonical.exists(), "uninstall must KEEP the library canonical (#303)"
    assert "demo-agent" in read_lock(library_lock_path()).skills, (
        "uninstall must KEEP the lock entry (#303)"
    )


def test_install_uninstall_project_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Project-scope install→uninstall: projected files created then truly removed."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    # Seed the project canonical so install can find the content file.
    _seed_project_canonical(project)

    runner = CliRunner()

    # Pass --project flag so main() sets ctx.obj["project_root"] correctly.
    # Using obj={} would be overwritten by main()'s ctx.obj["project_root"] = None.
    r_install = runner.invoke(
        main, ["--project", str(project),
               "agent", "install", "demo-agent", "-p",
               "--harnesses", _TEST_HARNESSES],
    )
    assert r_install.exit_code == 0, r_install.output

    cc = project / ".claude" / "agents" / "demo-agent.md"
    gem = project / ".gemini" / "agents" / "demo-agent.md"
    assert cc.exists(), f"claude-code projection not created: {cc}"
    assert gem.exists(), f"gemini-cli projection not created: {gem}"

    r_uninstall = runner.invoke(
        main, ["--project", str(project),
               "agent", "uninstall", "demo-agent", "-p",
               "--harnesses", _TEST_HARNESSES],
    )
    assert r_uninstall.exit_code == 0, r_uninstall.output

    assert not cc.exists(), "claude-code projection ORPHANED after uninstall (project)"
    assert not gem.exists(), "gemini-cli projection ORPHANED after uninstall (project)"


# ---------------------------------------------------------------------------
# 2. Idempotency — double-install / double-uninstall
# ---------------------------------------------------------------------------


def test_double_install_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Installing twice must not raise and file must still exist."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    runner = CliRunner()
    r1 = runner.invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    r2 = runner.invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    assert _cc_dest(tmp_path).exists()


def test_double_uninstall_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uninstalling twice must not raise even if files are already gone."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    runner = CliRunner()
    runner.invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    r1 = runner.invoke(
        main, ["agent", "uninstall", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    r2 = runner.invoke(
        main, ["agent", "uninstall", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output


# ---------------------------------------------------------------------------
# 3. Foreign-file guard — same-slug user-authored file is refused
# ---------------------------------------------------------------------------


def test_install_refuses_foreign_file_at_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user-authored file at the adapter destination must be refused, not clobbered.

    Intentionally does NOT write a lock entry so apply() sees overwrite=False
    (fresh install). The global canonical IS seeded so install_cmd's library
    check passes. This simulates a user who has a manual agent file already
    at the destination before ever running `agent install`.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    # Seed canonical but NO lock entry → overwrite=False in apply().
    _seed_global_canonical(tmp_path)

    # Plant a foreign file at the claude-code destination.
    foreign = _cc_dest(tmp_path)
    foreign.parent.mkdir(parents=True, exist_ok=True)
    foreign.write_text("USER AUTHORED — DO NOT CLOBBER\n")

    r = CliRunner().invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    assert r.exit_code != 0, "install should fail when a foreign file is present"
    assert foreign.read_text() == "USER AUTHORED — DO NOT CLOBBER\n", (
        "user-authored file was clobbered"
    )


def test_install_allows_refresh_of_tool_owned_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-installing a file the toolkit previously wrote (lock entry present) succeeds."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    runner = CliRunner()
    # First install — tool-owned file is created.
    r1 = runner.invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    assert r1.exit_code == 0, r1.output
    assert _cc_dest(tmp_path).exists()

    # Update the canonical content.
    (canonical / "demo-agent.md").write_text("---\nname: demo-agent\ndescription: updated\n---\n\nNew.\n")

    # Second install — refreshing our own file must succeed.
    r2 = runner.invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    assert r2.exit_code == 0, r2.output
    # Content should be updated.
    assert "New." in _cc_dest(tmp_path).read_text()


# ---------------------------------------------------------------------------
# add / remove verbs
# ---------------------------------------------------------------------------


def test_add_unknown_source_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passing a completely invalid source string must fail clearly."""
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["agent", "add", "not-a-valid-source-!!!"])
    # Should fail (exit != 0) OR at least not crash with a traceback.
    # A ClickException is expected.
    assert r.exit_code != 0 or "error" in r.output.lower()


# ---------------------------------------------------------------------------
# add content-file validation (#304 bug 2) — fail loud when <slug>.md is absent
#
# add hardcodes agent_path=f"{slug}.md"; before #304 it never verified the file
# existed in the clone, so it would write a lock entry pointing at a missing
# file and a later `install` would silently no-op while printing success
# (the #283 lock-honesty class). add must now refuse at add time.
# ---------------------------------------------------------------------------


def _local_agent_repo(parent: Path, *, content_filename: str | None) -> Path:
    """Build a local git repo to use as an `agent add` source.

    If `content_filename` is given, the repo contains that one markdown file;
    if None, the repo has only a README (no <slug>.md) — the malformed case.
    Returns an absolute path (so parse_source classifies it as `local`).
    """
    import subprocess

    from tests.conftest import scrub_git_env

    repo = parent / "agent-src"
    repo.mkdir()
    env = scrub_git_env()
    env.update({
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
    })
    subprocess.run(["git", "init", "--initial-branch=main", str(repo)],
                   check=True, env=env, capture_output=True)
    if content_filename is not None:
        (repo / content_filename).write_text(_CONTENT)
    else:
        (repo / "README.md").write_text("# no agent content here\n")
    subprocess.run(["git", "-C", str(repo), "add", "-A"],
                   check=True, env=env, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "seed"],
                   check=True, env=env, capture_output=True)
    return repo.resolve()


def test_add_refuses_when_content_file_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """add of a source whose <slug>.md is absent fails loud and writes no lock entry."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Source repo has only README.md — no `my-agent.md`.
    src = _local_agent_repo(tmp_path, content_filename=None)

    r = CliRunner().invoke(main, ["agent", "add", str(src), "--slug", "my-agent"])

    assert r.exit_code != 0, f"add should fail when <slug>.md is absent:\n{r.output}"
    assert "my-agent.md" in r.output, f"error must name the expected file: {r.output!r}"

    # The honesty contract: no lock entry pointing at a missing file.
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import library_lock_path
    lock = read_lock(library_lock_path())
    assert "my-agent" not in lock.skills, "add wrote a lock entry despite missing content file"


def test_add_succeeds_when_content_file_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy-path guard: add of a source containing <slug>.md still writes the lock entry."""
    monkeypatch.setenv("HOME", str(tmp_path))
    src = _local_agent_repo(tmp_path, content_filename="my-agent.md")

    r = CliRunner().invoke(main, ["agent", "add", str(src), "--slug", "my-agent"])

    assert r.exit_code == 0, f"add should succeed when <slug>.md is present:\n{r.output}"
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import library_lock_path
    lock = read_lock(library_lock_path())
    assert "my-agent" in lock.skills, "happy-path add did not write a lock entry"
    assert lock.skills["my-agent"].agent_path == "my-agent.md"


# ---------------------------------------------------------------------------
# #313 — clone-before-validate orphan cleanup
#
# Regression guard: `agent add <src>` (no --slug) that fails the content-file
# check because the derived slug (from repo name "agent-src") doesn't match
# the actual content file ("actual-name.md") must leave NO stray canonical.
# Before #313 the clone sat at agents/agent-src/ with no lock entry,
# invisible to `remove` and `doctor`.
# ---------------------------------------------------------------------------


def test_add_no_slug_leaves_no_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """add without --slug that fails slug-mismatch check leaves no orphan canonical (#313)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Source repo has "actual-name.md", but the repo dir is named "agent-src",
    # so the derived slug would be "agent-src", not "actual-name".
    src = _local_agent_repo(tmp_path, content_filename="actual-name.md")

    r = CliRunner().invoke(main, ["agent", "add", str(src)])  # no --slug

    assert r.exit_code != 0, (
        f"add should fail when derived slug doesn't match content file:\n{r.output}"
    )

    # #313 fix: the clone at agents/agent-src/ must be removed on failure.
    from agent_toolkit_cli.agent_paths import library_agent_path
    orphan_path = library_agent_path("agent-src")
    assert not orphan_path.exists(), (
        f"add left an orphan canonical at {orphan_path} — #313 regression"
    )

    # No lock entry for the derived slug either.
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import library_lock_path
    lock = read_lock(library_lock_path())
    assert "agent-src" not in lock.skills, "add wrote a lock entry for the orphaned slug"


def test_add_no_slug_idempotent_reuse_not_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Idempotent re-run with correct --slug reuses pre-existing clone (#313/#283).

    If a canonical already exists (perhaps from a previous partial run),
    `add` with the correct --slug must succeed and not remove the pre-existing
    directory. This guards the intentional idempotent-reuse path.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    src = _local_agent_repo(tmp_path, content_filename="actual-name.md")

    # First run: add with the correct --slug → success and canonical on disk.
    r1 = CliRunner().invoke(main, ["agent", "add", str(src), "--slug", "actual-name"])
    assert r1.exit_code == 0, f"first add should succeed:\n{r1.output}"

    from agent_toolkit_cli.agent_paths import library_agent_path
    canonical = library_agent_path("actual-name")
    assert canonical.exists(), "first add must leave canonical on disk"

    # Second run (idempotent): same slug — must not remove the canonical.
    r2 = CliRunner().invoke(main, ["agent", "add", str(src), "--slug", "actual-name"])
    assert r2.exit_code == 0, f"idempotent re-add should succeed:\n{r2.output}"
    assert canonical.exists(), "idempotent re-add must not remove the canonical"


# ---------------------------------------------------------------------------
# #313 — doctor orphan-canonical detection
# ---------------------------------------------------------------------------


def test_doctor_detects_orphan_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """doctor --no-fix reports orphan-canonical when a canonical dir has no lock entry (#313)."""
    monkeypatch.setenv("HOME", str(tmp_path))

    # Plant a stray canonical (no lock entry) simulating a failed add.
    from agent_toolkit_cli.agent_paths import library_agent_path
    stray = library_agent_path("stray-orphan")
    stray.mkdir(parents=True, exist_ok=True)
    (stray / "stray-orphan.md").write_text(_CONTENT)

    r = CliRunner().invoke(main, ["agent", "doctor", "-g", "--no-fix"])
    assert r.exit_code != 0, f"doctor should report findings:\n{r.output}"
    assert "orphan-canonical" in r.output, (
        f"doctor must report orphan-canonical finding: {r.output!r}"
    )
    assert "stray-orphan" in r.output, (
        f"doctor must name the stray slug: {r.output!r}"
    )


def test_doctor_fixes_orphan_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """doctor with fix=y removes an orphan canonical directory (#313)."""
    monkeypatch.setenv("HOME", str(tmp_path))

    from agent_toolkit_cli.agent_paths import library_agent_path
    stray = library_agent_path("stray-orphan")
    stray.mkdir(parents=True, exist_ok=True)
    (stray / "stray-orphan.md").write_text(_CONTENT)

    # Apply the fix by answering "y" to the prompt.
    r = CliRunner().invoke(main, ["agent", "doctor", "-g"], input="y\n")
    assert r.exit_code == 0, f"doctor should exit 0 after fixing all findings:\n{r.output}"
    assert not stray.exists(), (
        f"doctor should have removed the stray canonical at {stray}"
    )


def test_doctor_clean_not_affected_by_orphan_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """doctor on a fully clean library (no orphans) still reports all clean (#313 non-regression)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    r = CliRunner().invoke(main, ["agent", "doctor", "-g"])
    assert r.exit_code == 0, r.output
    assert "clean" in r.output.lower(), f"expected 'all clean', got: {r.output!r}"


def test_remove_not_in_library_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["agent", "remove", "nonexistent-agent"])
    assert r.exit_code != 0


def test_remove_drops_projections_and_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """remove: all harness projections + canonical + lock entry are gone after remove."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    runner = CliRunner()
    runner.invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    cc = _cc_dest(tmp_path)
    assert cc.exists()

    r = runner.invoke(main, ["agent", "remove", "demo-agent"])
    assert r.exit_code == 0, r.output
    assert not cc.exists(), "projection not removed by `agent remove`"
    assert not canonical.exists(), "canonical not removed by `agent remove`"

    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import library_lock_path
    assert "demo-agent" not in read_lock(library_lock_path()).skills


def test_uninstall_vs_remove_distinct_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#303: `uninstall` and `remove` must have DISTINCT effects.

    uninstall detaches one harness but KEEPS the library (canonical + lock), so
    a re-install re-projects from the intact canonical. remove deletes the whole
    library copy. Same fixture, two commands, opposite library outcomes.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import library_lock_path

    runner = CliRunner()
    cc = _cc_dest(tmp_path)

    # install → projection present
    assert runner.invoke(
        main, ["agent", "install", "demo-agent", "-g", "--harnesses", "claude-code"],
    ).exit_code == 0
    assert cc.exists()

    # uninstall → projection GONE, but library (canonical + lock) KEPT
    r_uninstall = runner.invoke(
        main, ["agent", "uninstall", "demo-agent", "-g", "--harnesses", "claude-code"],
    )
    assert r_uninstall.exit_code == 0, r_uninstall.output
    assert not cc.exists(), "uninstall must remove the projection"
    assert canonical.exists(), "uninstall must KEEP the canonical (distinct from remove)"
    assert "demo-agent" in read_lock(library_lock_path()).skills, (
        "uninstall must KEEP the lock entry (distinct from remove)"
    )
    # The agent is still in the library → `list -g` shows it.
    r_list = runner.invoke(main, ["agent", "list", "-g"])
    assert "demo-agent" in r_list.output, "uninstalled agent must still be listed"

    # re-install from the intact canonical → projection back, no re-clone needed
    assert runner.invoke(
        main, ["agent", "install", "demo-agent", "-g", "--harnesses", "claude-code"],
    ).exit_code == 0
    assert cc.exists(), "re-install after uninstall must re-project from the canonical"

    # remove → projection GONE, canonical GONE, lock GONE
    r_remove = runner.invoke(main, ["agent", "remove", "demo-agent"])
    assert r_remove.exit_code == 0, r_remove.output
    assert not cc.exists(), "remove must remove the projection"
    assert not canonical.exists(), "remove must delete the canonical (distinct from uninstall)"
    assert "demo-agent" not in read_lock(library_lock_path()).skills, (
        "remove must drop the lock entry (distinct from uninstall)"
    )


# ---------------------------------------------------------------------------
# list / status verbs
# ---------------------------------------------------------------------------


def test_list_empty_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["agent", "list", "-g"])
    assert r.exit_code == 0, r.output
    assert "no agents found" in r.output or r.output.strip() == ""


def test_list_json_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["agent", "list", "-g", "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert isinstance(data, list)


def test_list_shows_installed_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    r = CliRunner().invoke(main, ["agent", "list", "-g"])
    assert r.exit_code == 0, r.output
    assert "demo-agent" in r.output


def test_list_json_shows_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    r = CliRunner().invoke(main, ["agent", "list", "-g", "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    slugs = [d["slug"] for d in data]
    assert "demo-agent" in slugs


def test_list_projected_state_reflects_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After install the list output should show the agent as projected."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    runner = CliRunner()
    runner.invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )

    r = runner.invoke(main, ["agent", "list", "-g", "--json"])
    assert r.exit_code == 0, r.output
    data = {d["slug"]: d for d in json.loads(r.output)}
    assert data["demo-agent"]["projected"] is True


def test_status_shows_agent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    r = CliRunner().invoke(main, ["agent", "status", "demo-agent", "-g"])
    assert r.exit_code == 0, r.output
    assert "demo-agent" in r.output


def test_status_shows_projected_harnesses_after_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Contract update (#361): claude-code's destination IS the standard
    slot, so status dedupes by destination and reports it as `standard`."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    runner = CliRunner()
    runner.invoke(
        main, ["agent", "install", "demo-agent", "-g",
               "--harnesses", "claude-code"],
    )
    r = runner.invoke(main, ["agent", "status", "demo-agent", "-g"])
    assert r.exit_code == 0, r.output
    assert "standard" in r.output
    assert "claude-code" not in r.output


# ---------------------------------------------------------------------------
# status empty-state honesty (#304 bug 1)
#
# Regression guard for the scope-default mismatch + silent-blank trap: an empty
# library must produce a *scope-named*, non-blank message — never a blank screen
# (the prior behaviour when the lock existed but had no entries) and never a
# scope-blind message that hides which lock was searched.
# ---------------------------------------------------------------------------


def test_status_empty_global_names_scope_not_blank(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`status -g` on an empty global library prints a non-blank, scope-named line."""
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["agent", "status", "-g"])
    assert r.exit_code == 0, r.output
    assert r.output.strip() != "", "status must not print a blank screen for an empty library"
    assert "global" in r.output.lower(), f"empty message should name the scope: {r.output!r}"


def test_status_empty_present_lock_is_not_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lock file that exists but has no entries must not render as a blank screen.

    Mirrors `agent list`, which prints a message in this case. The prior
    `status` render loop simply didn't iterate, leaving stdout empty.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    # Force an empty-but-present global lock on disk.
    from agent_toolkit_cli.agent_lock import LockFile, write_lock
    from agent_toolkit_cli.agent_paths import library_lock_path
    write_lock(library_lock_path(), LockFile(version=1, skills={}))

    r = CliRunner().invoke(main, ["agent", "status", "-g"])
    assert r.exit_code == 0, r.output
    assert r.output.strip() != "", "empty-but-present lock must not render blank"
    assert "global" in r.output.lower()


def test_status_default_scope_in_project_names_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bare `status` from a project dir with a project lock names the *project* scope.

    This is the wrong-scope confusion the reporter hit: `list -g` (explicit
    global) showed the agent while bare `status` defaulted to project scope and
    found that project's (empty) lock. The empty message must name `project` so
    the mismatch is legible.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    # Empty project lock so read_only default-scope resolves to project.
    from agent_toolkit_cli.agent_lock import LockFile, write_lock
    from agent_toolkit_cli.agent_paths import lock_file_path
    write_lock(lock_file_path(scope="project", project=project),
               LockFile(version=1, skills={}))

    r = CliRunner().invoke(main, ["--project", str(project), "agent", "status"])
    assert r.exit_code == 0, r.output
    assert "project" in r.output.lower(), f"empty message should name project scope: {r.output!r}"


def test_status_unknown_slug_is_not_empty_library_claim(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Filtering to an absent slug must not claim the whole library is empty."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    r = CliRunner().invoke(main, ["agent", "status", "ghost-agent", "-g"])
    assert r.exit_code == 0, r.output
    # The library is NOT empty (demo-agent is present) — so don't say it is.
    assert "ghost-agent" in r.output, f"unknown slug should be named: {r.output!r}"
    assert "not found" in r.output.lower()


# ---------------------------------------------------------------------------
# install refused without global lock entry
# ---------------------------------------------------------------------------


def test_install_without_library_entry_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """install must error if the slug isn't in the global library (no lock AND no canonical)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Deliberately do NOT seed canonical or lock entry.

    r = CliRunner().invoke(
        main, ["agent", "install", "nonexistent-agent", "-g",
               "--harnesses", "claude-code"],
    )
    assert r.exit_code != 0
    assert "agent add" in r.output or "library" in r.output.lower()


# ---------------------------------------------------------------------------
# reset requires at least one slug
# ---------------------------------------------------------------------------


def test_reset_requires_at_least_one_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(main, ["agent", "reset", "-g"])
    assert r.exit_code != 0


# ---------------------------------------------------------------------------
# doctor clean reports clean
# ---------------------------------------------------------------------------


def test_doctor_clean_reports_clean(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    r = CliRunner().invoke(main, ["agent", "doctor", "-g"])
    assert r.exit_code == 0, r.output
    assert "clean" in r.output.lower()


def test_doctor_detects_missing_canonical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the canonical vanishes but the lock still has it, doctor reports it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    import shutil
    shutil.rmtree(canonical)

    r = CliRunner().invoke(main, ["agent", "doctor", "-g", "--no-fix"])
    assert "demo-agent" in r.output
    assert "missing" in r.output.lower() or r.exit_code != 0


# ---------------------------------------------------------------------------
# import: nonexistent file errors
# ---------------------------------------------------------------------------


def test_import_nonexistent_file_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    r = CliRunner().invoke(
        main, ["agent", "import", str(tmp_path / "nope-agents-lock.json")],
    )
    assert r.exit_code != 0


def test_import_skips_already_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """import skips slugs that are already in the library."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)

    from agent_toolkit_cli.agent_lock import LockEntry, LockFile, write_lock
    incoming = LockFile(
        version=1,
        skills={
            "demo-agent": LockEntry(
                source="https://github.com/test/demo-agent",
                source_type="github",
                agent_path="demo-agent.md",
            ),
        },
    )
    import_file = tmp_path / "incoming-agents-lock.json"
    write_lock(import_file, incoming)

    r = CliRunner().invoke(main, ["agent", "import", str(import_file)])
    assert r.exit_code == 0, r.output
    assert "skipped" in r.output.lower()


# ---------------------------------------------------------------------------
# Full round-trip loop: add (from local path) → install → list → remove
# ---------------------------------------------------------------------------


def test_full_loop_with_git_sandbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_sandbox: object,
) -> None:
    """Full CLI loop using a real git repo as the agent source.

    add (clone) → install (project) → list (projected=True) →
    remove (projections + canonical gone)
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():  # type: ignore[union-attr]
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))  # re-assert after env loop

    runner = CliRunner()

    # Seed the upstream with the <slug>.md content file BEFORE add. Since #304,
    # `agent add` validates that `<slug>.md` exists in the cloned source and
    # refuses otherwise, so the loop must use an honest source: push
    # `sandbox-agent.md` into the upstream via a throwaway clone, then add.
    import subprocess
    seed2 = tmp_path / "loop-seed"
    subprocess.run(
        ["git", "clone", str(git_sandbox.upstream), str(seed2)],  # type: ignore[union-attr]
        check=True, env=git_sandbox.env, capture_output=True,  # type: ignore[union-attr]
    )
    (seed2 / "sandbox-agent.md").write_text(_CONTENT)
    subprocess.run(["git", "-C", str(seed2), "add", "sandbox-agent.md"],
                   check=True, env=git_sandbox.env, capture_output=True)  # type: ignore[union-attr]
    subprocess.run(["git", "-C", str(seed2), "commit", "-m", "add agent content"],
                   check=True, env=git_sandbox.env, capture_output=True)  # type: ignore[union-attr]
    subprocess.run(["git", "-C", str(seed2), "push", "origin", "main"],
                   check=True, env=git_sandbox.env, capture_output=True)  # type: ignore[union-attr]

    r_add = runner.invoke(
        main, ["agent", "add", str(git_sandbox.upstream), "--slug", "sandbox-agent"],  # type: ignore[union-attr]
    )
    assert r_add.exit_code == 0, r_add.output

    # The content file came down with the clone — no manual canonical seeding.
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    canonical = canonical_agent_dir("sandbox-agent", scope="global")
    assert (canonical / "sandbox-agent.md").exists(), "content file not cloned"

    # install → projected.
    r_install = runner.invoke(
        main, ["agent", "install", "sandbox-agent", "-g",
               "--harnesses", "claude-code"],
    )
    assert r_install.exit_code == 0, r_install.output
    cc = tmp_path / ".claude" / "agents" / "sandbox-agent.md"
    assert cc.exists(), "claude-code projection not created"

    # list --json shows projected=True.
    r_list = runner.invoke(main, ["agent", "list", "-g", "--json"])
    assert r_list.exit_code == 0, r_list.output
    data = {d["slug"]: d for d in json.loads(r_list.output)}
    assert data["sandbox-agent"]["projected"] is True

    # remove → projections + canonical gone. The canonical is a clean clone
    # (content file committed upstream), so no --force is needed.
    r_remove = runner.invoke(main, ["agent", "remove", "sandbox-agent"])
    assert r_remove.exit_code == 0, r_remove.output
    assert not cc.exists(), "projection still present after remove"
    assert not canonical.exists(), "canonical still present after remove"


# ---------------------------------------------------------------------------
# #370: default fan-out over frontmatter-less agent → clean error, no traceback
# ---------------------------------------------------------------------------


def test_default_fanout_missing_description_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path, slug="no-fm")
    (canonical / "no-fm.md").write_text("Body only, no frontmatter.\n")
    _write_global_lock(tmp_path, slug="no-fm")

    r = CliRunner().invoke(main, ["agent", "install", "no-fm", "-g"])

    assert r.exit_code != 0
    # The failure must be a handled ClickException, not an escaped ValueError.
    assert not isinstance(r.exception, ValueError), (
        f"raw ValueError escaped the CLI layer:\n{r.output}"
    )
    # Clean message names the harness and the missing key, with no traceback.
    assert "github-copilot" in r.output
    assert "description" in r.output
    assert "Traceback" not in r.output, (
        f"raw Traceback leaked into output:\n{r.output}"
    )


# ---------------------------------------------------------------------------
# #362 — project install writes the project lock; list -p sees it
# ---------------------------------------------------------------------------


def test_project_install_writes_lock_and_list_shows_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#362 round-trip mandate: install -p → agents-lock.json entry →
    `agent list -p` lists the slug as projected."""
    import json as _json

    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_global_canonical(tmp_path)
    _write_global_lock(tmp_path)
    _seed_project_canonical(project)

    runner = CliRunner()
    r_install = runner.invoke(
        main, ["--project", str(project),
               "agent", "install", "demo-agent", "-p",
               "--harnesses", _TEST_HARNESSES],
    )
    assert r_install.exit_code == 0, r_install.output

    lock_file = project / "agents-lock.json"
    assert lock_file.exists(), "#362: install -p wrote no project lock"
    data = _json.loads(lock_file.read_text())
    assert "demo-agent" in data["skills"], data

    r_list = runner.invoke(
        main, ["--project", str(project), "agent", "list", "-p"],
    )
    assert r_list.exit_code == 0, r_list.output
    assert "demo-agent" in r_list.output, (
        f"#362: list -p blind to installed agent:\n{r_list.output}"
    )
    assert "✔" in r_list.output, "expected projected marker"


def test_project_install_without_global_entry_fails_before_seeding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Canonical-only slug (no global lock entry): project install fails
    loud BEFORE seeding the project canonical — no residue anywhere."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_global_canonical(tmp_path)  # NO _write_global_lock

    runner = CliRunner()
    r = runner.invoke(
        main, ["--project", str(project),
               "agent", "install", "demo-agent", "-p",
               "--harnesses", _TEST_HARNESSES],
    )
    assert r.exit_code != 0
    assert "no global lock entry" in r.output, r.output

    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    assert not canonical_agent_dir(
        "demo-agent", scope="project", project=project,
    ).exists(), "doomed install must not seed the project canonical"
    assert not (project / ".claude" / "agents" / "demo-agent.md").exists()
    assert not (project / "agents-lock.json").exists()


def _seed_agent_lock(path, slugs):
    """Minimal v1 agents lock with bare github entries for `slugs`."""
    import json as _json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json.dumps({
        "version": 1,
        "skills": {
            s: {"source": "acme/agents", "sourceType": "github"} for s in slugs
        },
    }))


def test_agent_push_project_scope_hints_global_lock(tmp_path, monkeypatch):
    """Slug only in the GLOBAL agents lock, resolved scope project → hint + exit 1 (#371)."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_agent_lock(home / ".agent-toolkit" / "agents-lock.json", ["my-agent"])
    _seed_agent_lock(project / "agents-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "agent", "push", "my-agent"],
    )
    assert result.exit_code == 1, result.output
    assert "my-agent: not in the project lock" in result.output
    assert "found in the global lock — re-run with -g" in result.output


def test_agent_push_global_scope_hints_project_lock(tmp_path, monkeypatch):
    """Slug only in the PROJECT agents lock, -g forces global → inverse hint + exit 1."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_agent_lock(home / ".agent-toolkit" / "agents-lock.json", [])
    _seed_agent_lock(project / "agents-lock.json", ["my-agent"])
    result = CliRunner().invoke(
        main, ["--project", str(project), "agent", "push", "-g", "my-agent"],
    )
    assert result.exit_code == 1, result.output
    assert "my-agent: not in the global lock" in result.output
    assert "found in the project lock — re-run with -p" in result.output


def test_agent_push_slug_in_neither_lock_exits_nonzero(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_agent_lock(home / ".agent-toolkit" / "agents-lock.json", [])
    _seed_agent_lock(project / "agents-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "agent", "push", "ghost"],
    )
    assert result.exit_code == 1, result.output
    assert "ghost: not in the project lock" in result.output
    assert "found in" not in result.output


def test_agent_bare_push_empty_lock_unchanged(tmp_path, monkeypatch):
    """Bare push takes targets from the lock — never hits the branch; exit 0."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "proj"
    project.mkdir()
    _seed_agent_lock(project / "agents-lock.json", [])
    result = CliRunner().invoke(
        main, ["--project", str(project), "agent", "push"],
    )
    assert result.exit_code == 0, result.output
    assert "not in the" not in result.output


def test_install_error_output_names_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#373 (gap 2): the clean CLI error names WHICH agent failed."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path, slug="no-fm")
    (canonical / "no-fm.md").write_text("Body only, no frontmatter.\n")
    _write_global_lock(tmp_path, slug="no-fm")

    r = CliRunner().invoke(main, ["agent", "install", "no-fm", "-g"])

    assert r.exit_code != 0
    assert "no-fm" in r.output, f"slug missing from error:\n{r.output}"
    assert "Traceback" not in r.output


def test_failed_fanout_retry_succeeds_after_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#373 (gap 3, dissolved by #368): a fan-out that fails on one harness
    leaves sentineled projections behind; fixing the canonical and re-running
    must succeed — no AgentProjectionConflictError on our own leftovers."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path, slug="retry-agent")
    # gemini-cli succeeds without a description; github-copilot requires one
    # and fails AFTER gemini-cli's file is already on disk.
    (canonical / "retry-agent.md").write_text(
        "---\nname: retry-agent\n---\nbody\n"
    )
    _write_global_lock(tmp_path, slug="retry-agent")

    r1 = CliRunner().invoke(
        main,
        ["agent", "install", "retry-agent", "-g",
         "--harnesses", "gemini-cli,github-copilot"],
    )
    assert r1.exit_code != 0
    assert "description" in r1.output

    # Fix the canonical, retry the same fan-out.
    (canonical / "retry-agent.md").write_text(
        "---\nname: retry-agent\ndescription: now valid\n---\nbody\n"
    )
    r2 = CliRunner().invoke(
        main,
        ["agent", "install", "retry-agent", "-g",
         "--harnesses", "gemini-cli,github-copilot"],
    )
    assert r2.exit_code == 0, f"retry wedged:\n{r2.output}"


def test_uninstall_install_error_clean_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#373 (AC6): uninstall converts InstallError to a clean ClickException
    (the data-dependent path is only reachable via catalog-disabled
    harnesses today, so simulate it at the facade seam)."""
    from agent_toolkit_cli import agent_install
    from agent_toolkit_cli._install_core import InstallError

    monkeypatch.setenv("HOME", str(tmp_path))

    def _boom(**kwargs):
        raise InstallError("retry-agent: firebender: /x/firebender.json: bad")

    monkeypatch.setattr(agent_install, "uninstall", _boom)
    r = CliRunner().invoke(main, ["agent", "uninstall", "retry-agent", "-g"])

    assert r.exit_code != 0
    assert not isinstance(r.exception, InstallError), "raw InstallError escaped"
    assert "firebender.json" in r.output
    assert "Traceback" not in r.output
