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
