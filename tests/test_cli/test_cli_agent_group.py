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
    """Global-scope install→uninstall: projected files created then truly removed."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_global_canonical(tmp_path)
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

    # Lock entry also cleared.
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import library_lock_path
    assert "demo-agent" not in read_lock(library_lock_path()).skills


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
    assert "claude-code" in r.output


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

    # `agent add` needs a content file — create it in the upstream and seed
    # the canonical manually (since the upstream is a bare git repo used for
    # cloning, we manipulate the canonical directly post-add by seeding it).
    r_add = runner.invoke(
        main, ["agent", "add", str(git_sandbox.upstream), "--slug", "sandbox-agent"],  # type: ignore[union-attr]
    )
    assert r_add.exit_code == 0, r_add.output

    # Seed the <slug>.md content file the adapter needs.
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    canonical = canonical_agent_dir("sandbox-agent", scope="global")
    (canonical / "sandbox-agent.md").write_text(_CONTENT)

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

    # remove → projections + canonical gone.
    # --force is used because we wrote sandbox-agent.md directly to the canonical
    # (uncommitted) — the dirty-guard would otherwise refuse.
    r_remove = runner.invoke(main, ["agent", "remove", "sandbox-agent", "--force"])
    assert r_remove.exit_code == 0, r_remove.output
    assert not cc.exists(), "projection still present after remove"
    assert not canonical.exists(), "canonical still present after remove"
