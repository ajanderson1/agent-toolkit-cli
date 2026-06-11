# agent install -p project lock entry (#362) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `agent install -p` (CLI and TUI) writes a project lock entry at `<project>/agents-lock.json`, derived from the global library entry, so project-scope list/TUI/doctor/uninstall/remove round-trip.

**Architecture:** Single fix point inside `agent_install.apply()` — both the CLI (`install_cmd.py`) and the TUI (`app.py::_apply_agent_pending`) call it with `InstallPlan(source=None)`. A pre-validation block (before any mutation) fail-louds when no global lock entry exists to derive from; a post-projection block writes the derived entry. The CLI additionally gains the same fail-loud check *before* it seeds the project canonical, so a doomed install leaves no residue. Spec: `docs/superpowers/specs/2026-06-11-agent-install-project-lock-design.md`.

**Tech Stack:** Python 3.12, Click, pytest. Run tests with `uv run pytest`.

**Critical invariants (do not violate):**
- The foreign-file guard must not weaken: on a FIRST project install, `overwrite` stays `False` (the derived entry is written only AFTER projection succeeds).
- #360 "unlisted" contract: a slug already in the **project** lock must install/uninstall fine with NO global lock entry — every new check is gated on `existing_entry is None`.
- Pure-remove plans (`add_agents` empty) are exempt from all new checks.
- Two pre-existing pytest failures on this machine are HOME-isolation environment leaks, green on CI: `test_pi_extension_inventory.py::test_empty_machine_is_empty` and `test_instruction_state.py::test_build_instruction_rows_empty_lock_no_canonical`. Do not chase them; they justify `--no-verify` ONLY if they are the only failures.

---

### Task 1: Failing facade tests — apply() with the real `source=None` plan shape

The existing round-trip tests pass `source=src` into `apply()`, which exercises the source-present lock path the CLI/TUI never use. These tests pin the real shape.

**Files:**
- Modify: `tests/test_cli/test_agent_install_roundtrip.py` (append; reuse the module's `_seed_global_canonical`, `_seed_project_canonical`, `_CONTENT` helpers and the autouse `_clean_env` fixture)

- [ ] **Step 1: Add a global-lock-entry helper + the seven tests**

Append to `tests/test_cli/test_agent_install_roundtrip.py`:

```python
# ── #362: project installs (source=None, the real CLI/TUI shape) must write
#    a derived project lock entry ─────────────────────────────────────────────

def _write_global_lock_entry(slug="rt-agent", ref=None):
    """Write a global library lock entry (honours monkeypatched HOME)."""
    from agent_toolkit_cli.agent_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.agent_paths import library_lock_path

    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    entry = LockEntry(
        source=f"x/{slug}", source_type="github", ref=ref,
        agent_path=f"{slug}.md",
    )
    write_lock(lock_path, add_entry(lock, slug, entry))


def _source_none_plan(slug="rt-agent", add=("claude-code", "gemini-cli")):
    from agent_toolkit_cli._install_core import InstallPlan

    return InstallPlan(
        slug=slug, scope="project", source=None, ref=None,
        add_agents=tuple(add), remove_agents=(),
    )


def test_project_install_source_none_writes_derived_lock_entry(
    tmp_path, monkeypatch,
):
    """#362 core: apply(source=None, project scope) derives the project lock
    entry from the global entry; full lifecycle: install → entry present →
    uninstall keeps it (#303) → remove drops it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli.agent_install import apply, remove, uninstall
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()
    _write_global_lock_entry(ref="main")
    _seed_project_canonical(project)

    result = apply(_source_none_plan(), project=project)

    lock_path = lock_file_path(scope="project", project=project)
    entry = read_lock(lock_path).skills.get("rt-agent")
    assert entry is not None, "#362: project install wrote NO project lock entry"
    assert entry.source == "x/rt-agent"
    assert entry.source_type == "github"
    assert entry.ref == "main"
    assert entry.agent_path == "rt-agent.md"
    assert entry.upstream_sha is None and entry.local_sha is None, (
        "project entries don't pin SHAs (skills precedent)"
    )
    assert result.lock_action == "added"

    uninstall(
        slug="rt-agent", scope="project", home=None, project=project,
        harnesses=("claude-code", "gemini-cli"),
    )
    assert "rt-agent" in read_lock(lock_path).skills, (
        "uninstall must KEEP the lock entry (#303)"
    )

    remove(
        slug="rt-agent", scope="project", home=None, project=project,
        harnesses=("claude-code", "gemini-cli"),
    )
    assert "rt-agent" not in read_lock(lock_path).skills, (
        "remove must DROP the lock entry"
    )


def test_project_install_no_global_entry_fails_before_projection(
    tmp_path, monkeypatch,
):
    """No global lock entry → InstallError BEFORE any file is projected."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    import pytest as _pytest

    from agent_toolkit_cli.agent_install import InstallError, apply
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()  # canonical only — NO global lock entry
    _seed_project_canonical(project)

    with _pytest.raises(InstallError, match="no global lock entry"):
        apply(_source_none_plan(), project=project)

    assert not (project / ".claude" / "agents" / "rt-agent.md").exists(), (
        "fail-loud must come BEFORE projection (no orphaned files)"
    )
    assert not (project / ".gemini" / "agents" / "rt-agent.md").exists()
    lock_path = lock_file_path(scope="project", project=project)
    assert "rt-agent" not in read_lock(lock_path).skills


def test_project_reinstall_source_none_is_idempotent(tmp_path, monkeypatch):
    """Second apply() succeeds: the entry written by the first run makes the
    slug tool-owned (overwrite=True), fixing the F3 re-install conflict."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli.agent_install import apply

    _seed_global_canonical()
    _write_global_lock_entry()
    _seed_project_canonical(project)

    r1 = apply(_source_none_plan(), project=project)
    assert r1.lock_action == "added"
    r2 = apply(_source_none_plan(), project=project)  # must not raise
    assert r2.lock_action == "unchanged"
    assert (project / ".gemini" / "agents" / "rt-agent.md").exists()


def test_project_first_install_still_refuses_foreign_file(
    tmp_path, monkeypatch,
):
    """Foreign pre-existing destination still refused on FIRST install
    (overwrite must stay False until the entry exists) — and the failed
    install writes NO lock entry."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    import pytest as _pytest

    from agent_toolkit_cli.agent_adapters import AgentProjectionConflictError
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()
    _write_global_lock_entry()
    _seed_project_canonical(project)
    foreign = project / ".gemini" / "agents" / "rt-agent.md"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("# user's own file\n")

    with _pytest.raises(AgentProjectionConflictError):
        apply(_source_none_plan(add=("gemini-cli",)), project=project)

    assert foreign.read_text() == "# user's own file\n", "foreign file clobbered"
    lock_path = lock_file_path(scope="project", project=project)
    assert "rt-agent" not in read_lock(lock_path).skills, (
        "a FAILED install must not write a lock entry"
    )


def test_project_unlisted_entry_operable_without_global_entry(
    tmp_path, monkeypatch,
):
    """#360 'unlisted' contract: slug already in the PROJECT lock installs
    fine with NO global lock entry (the new fail-loud must be exempt), and a
    pure-remove plan never consults the global lock."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli.agent_lock import (
        LockEntry, add_entry, read_lock, write_lock,
    )
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()  # NO global lock entry
    _seed_project_canonical(project)
    # Pre-existing project lock entry (the #360 unlisted shape).
    lock_path = lock_file_path(scope="project", project=project)
    write_lock(lock_path, add_entry(
        read_lock(lock_path), "rt-agent",
        LockEntry(source="x/rt-agent", source_type="github",
                  agent_path="rt-agent.md"),
    ))

    apply(_source_none_plan(add=("gemini-cli",)), project=project)  # no raise
    assert (project / ".gemini" / "agents" / "rt-agent.md").exists()

    # Pure-remove plan with NO lock entries anywhere: must not raise either.
    pure_remove = InstallPlan(
        slug="other-agent", scope="project", source=None, ref=None,
        add_agents=(), remove_agents=("gemini-cli",),
    )
    apply(pure_remove, project=project)


def test_project_install_all_skipped_writes_no_lock_entry(tmp_path, monkeypatch):
    """Critical-review G4: an install whose requested harnesses are ALL
    skipped as unsupported projects nothing — it must NOT write a project
    lock entry, or the zero-projection install claims tool ownership and
    flips overwrite=True for a later first REAL projection (guard bypass)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import lock_file_path

    _seed_global_canonical()
    _write_global_lock_entry()
    _seed_project_canonical(project)

    # codex is a real catalog entry with subagent_mechanism='none' → skipped.
    result = apply(_source_none_plan(add=("codex",)), project=project)

    assert result.skipped == ("codex",)
    assert result.lock_action == "unchanged"
    lock_path = lock_file_path(scope="project", project=project)
    assert "rt-agent" not in read_lock(lock_path).skills, (
        "G4: zero-projection install must not claim ownership"
    )


def test_global_install_source_none_writes_no_global_entry(
    tmp_path, monkeypatch,
):
    """AC9: global installs never write lock entries (that is `agent add`'s
    job) — behaviour unchanged for canonical-only global slugs."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli.agent_lock import read_lock
    from agent_toolkit_cli.agent_paths import library_lock_path

    _seed_global_canonical()  # canonical only — NO lock entry

    result = apply(
        InstallPlan(
            slug="rt-agent", scope="global", source=None, ref=None,
            add_agents=("gemini-cli",), remove_agents=(),
        ),
        home=tmp_path,
    )
    assert result.lock_action == "unchanged"
    assert "rt-agent" not in read_lock(library_lock_path()).skills
```

- [ ] **Step 2: Run the new tests, verify the right RED/GREEN split**

Run: `uv run pytest tests/test_cli/test_agent_install_roundtrip.py -v -k "source_none or unlisted or foreign or reinstall or global_entry or all_skipped"`

Expected failures (RED — the bug):
- `test_project_install_source_none_writes_derived_lock_entry` — entry is None
- `test_project_install_no_global_entry_fails_before_projection` — no InstallError raised
- `test_project_reinstall_source_none_is_idempotent` — second apply raises `AgentProjectionConflictError` (the F3 conflict) or lock_action wrong

Expected passes already (regression pins, must STAY green):
- `test_project_first_install_still_refuses_foreign_file`
- `test_project_unlisted_entry_operable_without_global_entry`
- `test_project_install_all_skipped_writes_no_lock_entry` (pre-fix nothing is ever written; post-fix the `created` gate keeps it green)
- `test_global_install_source_none_writes_no_global_entry`

If a "must stay green" test fails BEFORE the implementation, stop — the test or the understanding is wrong.

- [ ] **Step 3: Commit the red tests**

```bash
git add tests/test_cli/test_agent_install_roundtrip.py
git commit -m "test(agent): pin project-install lock round-trip for #362 (red)

Device: $(hostname -s)" -- tests/test_cli/test_agent_install_roundtrip.py
```

(Pre-commit runs the full suite; the new red tests will fail it. Commit with `--no-verify` for this red-state commit ONLY, or fold this commit into Task 2's commit if the executor prefers a single green commit. The two known HOME-isolation failures listed in the header are also acceptable `--no-verify` justification.)

---

### Task 2: Implement the derived project lock entry in `agent_install.apply()`

**Files:**
- Modify: `src/agent_toolkit_cli/agent_install.py` (apply(), currently lines ~197–352)

- [ ] **Step 1: Add pre-validation after `existing_entry` is read**

In `apply()`, directly after `existing_entry = lock.skills.get(plan.slug)` (line ~236), insert:

```python
    # #362: a project-scope install driven by the CLI/TUI plan shape
    # (source=None) must leave a project lock entry behind, derived from
    # the global library entry — otherwise every project read surface
    # (list / TUI / doctor / remove) is blind to the install and doctor's
    # orphan sweep (#366) misclassifies our own files. Validate BEFORE any
    # mutation so a failed install projects nothing. Exempt: pure-remove
    # plans (a slug whose library entry was dropped must stay removable)
    # and slugs already in the project lock (#360 "unlisted" entries stay
    # operable without a library entry).
    derive_project_entry = (
        plan.scope == "project"
        and plan.source is None
        and bool(plan.add_agents)
        and existing_entry is None
    )
    global_entry = None
    if derive_project_entry:
        from agent_toolkit_cli.agent_paths import library_lock_path

        global_entry = read_lock(library_lock_path()).skills.get(plan.slug)
        if global_entry is None:
            raise InstallError(
                f"{plan.slug}: no global lock entry; "
                f"run `agent add {plan.slug}` first"
            )
```

`InstallError` is already imported at module level (re-exported from `_install_core`); `read_lock` is already imported inside `apply()`.

- [ ] **Step 2: Write the derived entry after the projection loops**

Change the lock-update block at the end of `apply()` (currently `if plan.source is not None:` …, lines ~322–343) by adding an `elif`:

```python
    # Update lock — agent_path identifies which file was written.
    lock_action: Literal["added", "updated", "unchanged"] = "unchanged"
    if plan.source is not None:
        # …existing body unchanged…
    elif derive_project_entry and created:
        # #362: derived project entry, written only AFTER the projection
        # loops succeeded so `overwrite` stays False on a first install
        # (foreign-file guard) and a failed install leaves no entry. The
        # `created` gate keeps an all-skipped install (every harness
        # unsupported) from claiming ownership of files it never wrote.
        # Mirrors skill_install.ensure_project_canonical's derivation:
        # project entries copy source/ref identity but never pin SHAs.
        assert global_entry is not None  # guaranteed by pre-validation
        entry = LockEntry(
            source=global_entry.source,
            source_type=global_entry.source_type,
            ref=global_entry.ref,
            agent_path=global_entry.agent_path or f"{plan.slug}.md",
            upstream_sha=None,
            local_sha=None,
            parent_url=global_entry.parent_url,
            read_only=global_entry.read_only,
        )
        write_lock(lock_path, add_entry(lock, plan.slug, entry))
        lock_action = "added"
```

- [ ] **Step 3: Run the Task 1 tests — all seven pass**

Run: `uv run pytest tests/test_cli/test_agent_install_roundtrip.py -v`
Expected: PASS (all, including the pre-existing round-trip tests).

- [ ] **Step 4: Run the neighbouring suites for collateral damage**

Run: `uv run pytest tests/test_cli/test_agent_install.py tests/test_cli/test_cli_agent_group.py tests/test_cli/test_agent_doctor.py tests/test_cli/test_agent_doctor_unlisted.py tests/test_tui/test_agent_grid.py tests/test_tui/test_agent_state.py -v`
Expected: PASS. If a TUI apply test now fails because it asserted NO project lock was written, that test was pinning the bug — update it to assert the entry IS written, citing #362.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/agent_install.py tests/test_cli/test_agent_install_roundtrip.py
git commit -m "fix(agent): agent install -p writes a derived project lock entry (#362)

Device: $(hostname -s)" -- src/agent_toolkit_cli/agent_install.py tests/test_cli/test_agent_install_roundtrip.py
```

---

### Task 3: CLI fail-loud before seeding + CLI-level round-trip

`apply()` already fail-louds, but the CLI seeds the project canonical (copytree) BEFORE calling it — a doomed install would leave canonical residue. Move the check ahead of the seeding. The TUI is left as-is: its seeding residue lands in the external store (outside the project tree, harmless, reused by a later successful install); note no doctor sweep reclaims project-scope agent canonicals today — that gap belongs to the existing doctor follow-ups, not this issue. Placement note: the new check sits BEFORE the `no enabled harnesses; nothing to do` early return, so a canonical-only slug with an empty harness set now fails loud instead of no-op'ing — consistent with the fail-loud contract.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/install_cmd.py` (install_cmd body, lines ~99–133)
- Test: `tests/test_cli/test_cli_agent_group.py`

- [ ] **Step 1: Add the two failing CLI tests**

Append to `tests/test_cli/test_cli_agent_group.py` (reuses the module's `_seed_global_canonical`, `_seed_project_canonical`, `_write_global_lock`, `_TEST_HARNESSES` helpers):

```python
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
```

- [ ] **Step 2: Run them, verify expected RED**

Run: `uv run pytest tests/test_cli/test_cli_agent_group.py -v -k "writes_lock or before_seeding"`
Expected: `…writes_lock…` FAILS only if Task 2 is not yet merged into the working tree (with Task 2 done it PASSES already — the lock comes from apply()); `…before_seeding` FAILS on the canonical-residue assertion (apply() raises, but the copytree already happened).

- [ ] **Step 3: Add the pre-seeding check to install_cmd**

In `src/agent_toolkit_cli/commands/agent/install_cmd.py`, directly after the global-library existence check (the block ending `raise click.ClickException(f"{slug}: not in the global library; run \`agent add\` first")`, line ~109), insert:

```python
    # #362: a project install derives its project lock entry from the
    # GLOBAL lock entry — require it before seeding the project canonical
    # so a doomed install leaves no residue. Exempt slugs already in the
    # project lock (#360 "unlisted" entries reinstall without a library
    # entry). apply() re-checks this; the duplicate here is purely to
    # fail before the copytree.
    if scope == "project" and project is not None:
        from agent_toolkit_cli.agent_paths import lock_file_path
        project_lock = read_lock(
            lock_file_path(scope="project", project=project)
        )
        if (
            slug not in project_lock.skills
            and slug not in global_lock.skills
        ):
            raise click.ClickException(
                f"{slug}: no global lock entry; run `agent add {slug}` first"
            )
```

Also update the command docstring's note about the slug-existence check (the "a manually-seeded canonical also counts" comment, lines ~99–102) to add: manually-seeded canonicals still install at GLOBAL scope; PROJECT scope additionally requires a global lock entry (#362).

- [ ] **Step 4: Run the CLI suite**

Run: `uv run pytest tests/test_cli/test_cli_agent_group.py -v`
Expected: PASS (both new tests + all pre-existing, notably `test_install_uninstall_project_round_trip` and `test_double_install_is_safe`).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/install_cmd.py tests/test_cli/test_cli_agent_group.py
git commit -m "fix(agent): project install fail-louds before seeding when no global lock entry (#362)

Device: $(hostname -s)" -- src/agent_toolkit_cli/commands/agent/install_cmd.py tests/test_cli/test_cli_agent_group.py
```

---

### Task 4: Doctor regression — a fresh project install is NOT an orphan

Since #366, project-scope doctor's orphan sweep flags a sentineled slot file with no lock entry. Pre-fix, that meant doctor offered `rm` for the tool's own successful install. Pin the post-fix behaviour.

**Files:**
- Test: `tests/test_cli/test_agent_doctor.py` (reuse the module's `_diagnose`, `_by_type`, `_seed_global_canonical`, `_write_global_lock` helpers — read their exact signatures in the file before writing; `_diagnose` requires all four kwargs)

- [ ] **Step 1: Add the test**

Append to `tests/test_cli/test_agent_doctor.py` (adapt helper names/signatures to the file if they differ — the assertions are the contract):

```python
def test_project_install_is_not_flagged_as_orphan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#362 × #366: a successful `agent install -p` must NOT be flagged by
    project-scope doctor's orphan sweep (pre-fix, the sentineled slot file
    had no lock entry → standard-slot-orphan with an rm fix offered)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    project = tmp_path / "proj"
    project.mkdir()
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    _seed_global_canonical()
    _write_global_lock()
    proj_canonical = canonical_agent_dir(
        "demo-agent", scope="project", project=project,
    )
    proj_canonical.mkdir(parents=True)
    (proj_canonical / "demo-agent.md").write_text(_CONTENT)

    apply(
        InstallPlan(
            slug="demo-agent", scope="project", source=None, ref=None,
            add_agents=("claude-code",), remove_agents=(),
        ),
        project=project,
    )
    assert (project / ".claude" / "agents" / "demo-agent.md").exists()

    findings = _diagnose(
        slugs=None, scope="project", home=tmp_path, project=project,
    )
    orphans = _by_type(findings, "standard-slot-orphan")
    assert orphans == [], (
        f"#362: doctor misclassifies its own install as orphan: "
        f"{[f.finding_type for f in findings]}"
    )
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_cli/test_agent_doctor.py -v`
Expected: the new test PASSES with Task 2 in place (it is a regression pin, red only on pre-fix main). All pre-existing doctor tests still PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_agent_doctor.py
git commit -m "test(agent): doctor must not orphan-flag a fresh project install (#362)

Device: $(hostname -s)" -- tests/test_cli/test_agent_doctor.py
```

---

### Task 5: Full suite + wrap-up

- [ ] **Step 1: Full test run**

Run: `uv run pytest`
Expected: everything green EXCEPT (possibly) the two known HOME-isolation environment failures listed in the header — those fail on pristine main too on this machine and are green on CI. Any OTHER failure is yours: fix before proceeding.

- [ ] **Step 2: Lint + types**

Run: `uv run ruff check src tests && uv run mypy src`
Expected: no NEW errors versus main (main has pre-existing mypy/ruff counts; compare, don't zero).

- [ ] **Step 3: Verify the demo repro from the issue is fixed**

In a sandbox HOME + scratch project. CAUTION: a bare `uv run agent-toolkit-cli` from a scratch cwd finds no project and resolves the PATH-installed tool (v3.8.x, pre-fix) — pin every invocation to the working tree with `--project`:

```bash
REPO=<absolute path to the worktree under test>
SANDBOX=$(mktemp -d) && cd $(mktemp -d) && git init -q .
HOME=$SANDBOX uv run --project "$REPO" agent-toolkit-cli agent add /path/to/any/local/agent/repo --slug demo-agent
HOME=$SANDBOX uv run --project "$REPO" agent-toolkit-cli agent install demo-agent -p --harnesses claude-code
HOME=$SANDBOX uv run --project "$REPO" agent-toolkit-cli agent list -p     # MUST show demo-agent ✔
HOME=$SANDBOX uv run --project "$REPO" agent-toolkit-cli agent doctor -p   # MUST be clean (no orphan)
HOME=$SANDBOX uv run --project "$REPO" agent-toolkit-cli agent install demo-agent -p --harnesses claude-code  # re-install MUST succeed
```

- [ ] **Step 4: Push and open the PR**

PR title: `fix(agent): agent install -p writes no project lock entry — project list/TUI/doctor blind to installed agents (#362)` — keep the conventional `fix:` prefix so release-please picks it up. Body links the spec + plan and cites the issue with `Closes #362`.
