# Doctor backup-then-symlink fix for second unmanaged harness file — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When canonical `AGENTS.md` already has content, `instructions doctor`'s `unmanaged` finding offers a backup-then-symlink fix (rename the unmanaged file to `<name>.pre-adopt.bak`, merge the harness into the lock, reconcile the slot symlink) instead of degrading to report-only.

**Architecture:** One new finding-builder function `_backup_then_symlink_finding` in `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py`; the existing `_unmanaged_finding` becomes a two-way dispatcher (canonical missing/empty → existing adopt fix, unchanged; canonical populated → new fix). The new fix reuses `_adopt_harness_for` for slot attribution and mirrors the #337 adopt fix's exact rollback contract (rename before lock-write; on ANY `instructions_install.apply` failure undo symlink, restore file from `.bak`, restore prior lock).

**Tech Stack:** Python 3.11+, Click, pytest (`CliRunner`), uv. Tests live in `tests/test_cli/test_instructions_cli.py` (existing `_global_home` helper at line ~240).

**Spec:** `docs/superpowers/specs/2026-06-11-doctor-second-unmanaged-backup-symlink.md` · **Issue:** #375

**Context for a zero-context engineer:**
- `instructions doctor` scans harness "pointer slots" (e.g. `{PROJECT}/CLAUDE.md`, `~/.gemini/GEMINI.md` — table in `src/agent_toolkit_cli/instructions_adapters/symlink.py` `CELLS`). A real file at a slot that the lock doesn't record is an `unmanaged` finding.
- Findings with a `fix_action` get an interactive `y/N/q` prompt; `apply()` raising any exception prints `adopt failed: <exc>` and counts as skipped; any skipped finding → exit 1 (`doctor_cmd.py:239-278`). Do not change the loop.
- The lock is JSON at `{PROJECT}/instructions-lock.json` or `~/.agent-toolkit/instructions-lock.json`; helpers `read_lock/add_entry/write_lock` + `InstructionsLockEntry` are already imported in `doctor_cmd.py`.
- `Path.rename()` silently replaces an existing target on POSIX — the fail-loud `.bak` guard must be an explicit existence check before renaming.
- Run tests with `uv run pytest`, lint with `uv run ruff check`, types with `uv run mypy src` (pre-existing mypy/ruff noise on main exists; the bar is **no new errors**).

---

### Task 1: Happy path — backup-then-symlink fix at project scope

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py` (`_unmanaged_finding`, ~line 65)
- Test: `tests/test_cli/test_instructions_cli.py`

- [ ] **Step 1: Write the failing happy-path test + rewrite the obsolete report-only test**

Append after `test_doctor_adopts_augment_global_slot_as_augment_not_claude`:

```python
# --- #375 backup-then-symlink fix (canonical already populated) ----------------


def test_doctor_backup_fix_renames_to_bak_and_symlinks(tmp_path, monkeypatch):
    """Populated AGENTS.md + unmanaged CLAUDE.md: 'y' backs the file up to
    CLAUDE.md.pre-adopt.bak, symlinks the slot at canonical, merges the lock,
    and doctor is clean on re-run. Content is never merged or destroyed."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# different\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code == 0, result.output

    agents = project / "AGENTS.md"
    pointer = project / "CLAUDE.md"
    backup = project / "CLAUDE.md.pre-adopt.bak"
    assert agents.read_text() == "# real canon\n"  # canonical untouched
    assert backup.is_file() and backup.read_text() == "# different\n"
    assert pointer.is_symlink() and pointer.resolve() == agents.resolve()
    # Output points the user at the backup (manual content reconciliation).
    assert "pre-adopt.bak" in result.output

    lock = json.loads((project / "instructions-lock.json").read_text())
    assert "claude-code" in lock["instructions"]["AGENTS.md"]["harnesses"]

    again = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert again.exit_code == 0, again.output
    assert "clean" in again.output.lower()
```

Then REPLACE the body of `test_doctor_unmanaged_does_not_clobber_existing_agents`
(line ~420 — it asserts the report-only behaviour this issue removes; its
"y must not destroy content" intent is preserved by the new test above and by
this decline variant):

```python
def test_doctor_backup_fix_decline_keeps_finding(tmp_path, monkeypatch):
    """Real CLAUDE.md + populated AGENTS.md: 'N' leaves everything untouched,
    the finding stays reported, exit 1 (AC6)."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# different\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="N\n")
    assert result.exit_code != 0, result.output
    assert "unmanaged" in result.output.lower()
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink()
    assert claude.read_text() == "# different\n"
    assert not (project / "CLAUDE.md.pre-adopt.bak").exists()
```

(Delete the old `test_doctor_unmanaged_does_not_clobber_existing_agents` function entirely; the new name replaces it.)

- [ ] **Step 2: Run both tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py -k "backup_fix" -v`
Expected: `test_doctor_backup_fix_renames_to_bak_and_symlinks` FAILS (exit code 1, no fix offered — report-only today). `test_doctor_backup_fix_decline_keeps_finding` may already pass (declining a report-only finding also mutates nothing) — that is fine; it pins AC6 against regression.

- [ ] **Step 3: Implement the new finding builder + dispatch**

In `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py`, replace the
report-only early-return inside `_unmanaged_finding` (lines 76-81):

```python
    adoptable = not canonical.exists() or canonical.stat().st_size == 0
    if not adoptable:
        return _backup_then_symlink_finding(
            pointer=pointer, harness=harness, canonical=canonical,
            scope=scope, project_root=project_root, home=home,
            lock_path=lock_path,
        )
```

Add the new builder directly above `_unmanaged_finding`:

```python
def _backup_then_symlink_finding(
    *,
    pointer: Path,
    harness: str,
    canonical: Path,
    scope: str,
    project_root: Path | None,
    home: Path | None,
    lock_path: Path,
) -> Finding:
    """Canonical AGENTS.md already has content: offer to back the unmanaged
    file up beside itself and point its slot at canonical. Content is never
    merged — the .bak keeps the user's text for manual reconciliation (#375).
    """
    backup = pointer.with_name(pointer.name + ".pre-adopt.bak")
    adopt_harness = _adopt_harness_for(
        pointer, harness, scope=scope, project_root=project_root, home=home,
    )

    def _apply() -> None:
        # Re-assert guards at apply time — state may have changed since the
        # scan. is_symlink() catches a dangling symlink (exists() is False but
        # rename() onto it would still replace it).
        if backup.exists() or backup.is_symlink():
            raise click.ClickException(
                f"{backup} already exists — refusing to overwrite a previous backup"
            )
        if not canonical.exists() or canonical.stat().st_size == 0:
            raise click.ClickException(
                f"{canonical} no longer has content — re-run doctor"
            )
        prior = read_lock(lock_path)
        prior_existed = lock_path.exists()
        # Rename BEFORE writing the lock so a failure never leaves a lying
        # lock. The try opens HERE — not after write_lock — so a lock-write
        # failure also rolls the rename back; otherwise the user's file would
        # be stranded at the .bak with an empty slot, a state a doctor re-run
        # reports as clean (critical-review finding, #375).
        pointer.rename(backup)
        try:
            existing = prior.instructions.get("AGENTS.md")
            new_harnesses = sorted({*(existing.harnesses if existing else []), adopt_harness})
            new = add_entry(prior, "AGENTS.md", InstructionsLockEntry(
                scope=cast("Scope", scope),
                source="AGENTS.md",
                harnesses=new_harnesses,
            ))
            write_lock(lock_path, new)
            instructions_install.apply(scope=scope, project_root=project_root, home=home)
        except Exception as exc:
            # Stronger than the adopt fix's contract: roll back on ANY failure
            # after the rename (lock write or apply). Drop any symlink apply()
            # laid at our slot, restore the user's file from the backup, then
            # restore the prior lock.
            if pointer.is_symlink():
                pointer.unlink()
            if backup.exists() and not pointer.exists():
                backup.rename(pointer)
            if prior_existed:
                write_lock(lock_path, prior)
            else:
                lock_path.unlink(missing_ok=True)
            raise click.ClickException(str(exc)) from exc

    return Finding(
        message=(
            f"unmanaged: real file at {pointer} is not in the lock; "
            f"AGENTS.md already has content — fix backs the file up to "
            f"{backup.name} (content is never merged; reconcile manually)"
        ),
        fix_action=FixAction(
            shell_preview=(
                f"mv {pointer.name} {backup.name} && "
                f"instructions install --scope {scope} --harness {adopt_harness}"
            ),
            apply=_apply,
        ),
    )
```

No other changes: the prompt loop, exit codes, `--no-fix`, and the
missing/empty-canonical adopt branch stay exactly as they are.

- [ ] **Step 4: Run the new tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py -k "backup_fix" -v`
Expected: both PASS.

- [ ] **Step 5: Run the whole instructions CLI test file (regressions)**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py -v`
Expected: all PASS — in particular every pre-existing adopt/rollback test (the adopt branch is untouched).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/doctor_cmd.py tests/test_cli/test_instructions_cli.py
git commit -m "feat(instructions): doctor backup-then-symlink fix when canonical is populated (#375)

Device: $(hostname -s)"
```

---

### Task 2: Fail loudly on a pre-existing `.pre-adopt.bak`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py` (only if Step 2 fails)
- Test: `tests/test_cli/test_instructions_cli.py`

- [ ] **Step 1: Write the test**

```python
def test_doctor_backup_fix_fails_loudly_on_existing_bak(tmp_path, monkeypatch):
    """A pre-existing CLAUDE.md.pre-adopt.bak: the fix refuses, nothing changes
    (never clobber, never silently discard — AC3)."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# mine\n")
    (project / "CLAUDE.md.pre-adopt.bak").write_text("# old backup\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "already exists" in result.output.lower()

    # Nothing changed.
    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink()
    assert claude.read_text() == "# mine\n"
    assert (project / "CLAUDE.md.pre-adopt.bak").read_text() == "# old backup\n"
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    lock_file = project / "instructions-lock.json"
    if lock_file.exists():
        lock = json.loads(lock_file.read_text())
        assert lock.get("instructions", {}) == {}
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py::test_doctor_backup_fix_fails_loudly_on_existing_bak -v`
Expected: PASS (the guard shipped in Task 1 Step 3). If it FAILS, the guard in `_apply` is wrong — fix the guard, not the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_instructions_cli.py
git commit -m "test(instructions): pre-existing .pre-adopt.bak refuses loudly (#375)

Device: $(hostname -s)"
```

---

### Task 3: Rollback on mid-apply failure (mirror the #337 adopt rollback tests)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py` (only if tests fail)
- Test: `tests/test_cli/test_instructions_cli.py`

- [ ] **Step 1: Write the three rollback tests**

```python
def test_doctor_backup_fix_rolls_back_on_apply_failure(tmp_path, monkeypatch):
    """If install.apply() raises ANY error mid-fix, the user's file comes back
    from the .bak, the .bak is gone, canonical untouched, no lock entry (AC4)."""
    import agent_toolkit_cli.instructions_install as install_mod

    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# mine\n")
    monkeypatch.chdir(project)

    def boom(*a, **k):
        raise OSError("disk gone")

    # doctor_cmd calls instructions_install.apply via the module attribute —
    # patch the source module (Click re-exports would not be reached).
    monkeypatch.setattr(install_mod, "apply", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "adopt failed" in result.output.lower()

    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink()
    assert claude.read_text() == "# mine\n"
    assert not (project / "CLAUDE.md.pre-adopt.bak").exists()
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    lock_file = project / "instructions-lock.json"
    if lock_file.exists():
        lock = json.loads(lock_file.read_text())
        assert lock.get("instructions", {}) == {}, "lock claims a fix that was rolled back"


def test_doctor_backup_fix_rolls_back_partial_apply_with_prior_lock(tmp_path, monkeypatch):
    """apply() that lays our slot's symlink then raises on a different slot must
    restore the user's file AND the prior lock verbatim — no half-applied state."""
    import agent_toolkit_cli.instructions_install as install_mod

    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# mine\n")
    (project / "instructions-lock.json").write_text(json.dumps({
        "version": 1,
        "instructions": {"AGENTS.md": {
            "scope": "project", "source": "AGENTS.md", "harnesses": ["gemini-cli"],
        }},
    }))
    monkeypatch.chdir(project)

    def apply_then_fail(*a, **k):
        # Simulate apply() creating our symlink (slot is free: the real file
        # was renamed to .bak), then failing on another slot.
        (project / "CLAUDE.md").symlink_to(project / "AGENTS.md")
        raise install_mod.CanonicalMissingError("boom on other slot")

    monkeypatch.setattr(install_mod, "apply", apply_then_fail)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output

    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink(), "symlink not cleaned up on rollback"
    assert claude.read_text() == "# mine\n"
    assert not (project / "CLAUDE.md.pre-adopt.bak").exists()
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    lock = json.loads((project / "instructions-lock.json").read_text())
    assert lock["instructions"]["AGENTS.md"]["harnesses"] == ["gemini-cli"]
```

NOTE: in the second test the prior lock wants `gemini-cli`, whose project slot
(`{PROJECT}/GEMINI.md`) has no pointer on disk. A missing pointer is not a
conflict/orphan finding (canonical exists), so the only finding is our
unmanaged CLAUDE.md — same shape as the existing
`test_doctor_adopt_rolls_back_partial_apply_with_prior_lock`.

Add a third rollback test — the critical-review finding this plan's `_apply`
structure exists to close (try opens at the rename, not after the lock write):

```python
def test_doctor_backup_fix_rolls_back_when_lock_write_fails(tmp_path, monkeypatch):
    """write_lock failing right after the rename must restore the user's file
    from the .bak — otherwise the file is stranded at the .bak with an empty
    slot and a doctor re-run reports clean (critical-review finding, #375)."""
    import importlib

    # The instructions package re-exports the Click command `doctor_cmd` over
    # the submodule name, so attribute access yields a Command, not the
    # module — fetch the module explicitly to patch its namespace.
    doctor_mod = importlib.import_module(
        "agent_toolkit_cli.commands.instructions.doctor_cmd"
    )

    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# mine\n")
    monkeypatch.chdir(project)

    def boom(*a, **k):
        raise OSError("lock dir read-only")

    # doctor_cmd does `from ...instructions_lock import write_lock` — patch
    # the name in doctor_cmd's namespace. (No prior lock file exists, so the
    # rollback's lock-restore path takes the unlink branch and never calls
    # the patched write_lock itself.)
    monkeypatch.setattr(doctor_mod, "write_lock", boom)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code != 0, result.output
    assert "adopt failed" in result.output.lower()

    claude = project / "CLAUDE.md"
    assert claude.is_file() and not claude.is_symlink()
    assert claude.read_text() == "# mine\n"
    assert not (project / "CLAUDE.md.pre-adopt.bak").exists()
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    assert not (project / "instructions-lock.json").exists()
```

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py -k "backup_fix_rolls_back" -v`
Expected: all three PASS (rollback + try-at-rename placement shipped in Task 1 Step 3). If any FAILS, fix `_apply` to match the assertions — the contract is: try opens immediately after `pointer.rename(backup)`; on exception drop our-slot symlink → restore file from `.bak` → restore prior lock (or unlink if it didn't exist).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_instructions_cli.py
git commit -m "test(instructions): backup-fix rollback mirrors #337 adopt contract (#375)

Device: $(hostname -s)"
```

---

### Task 4: Global scope — live-repro shape + augment slot attribution

**Files:**
- Test: `tests/test_cli/test_instructions_cli.py`

- [ ] **Step 1: Write both global-scope tests**

```python
def test_doctor_backup_fix_global_second_harness(tmp_path, monkeypatch):
    """The #375 live repro: claude-code already managed at global scope; a real
    ~/.gemini/GEMINI.md gets the backup fix and joins the existing lock entry."""
    home = _global_home(tmp_path, monkeypatch)
    runner = CliRunner()
    runner.invoke(main, [
        "instructions", "install", "--scope", "global", "--harness", "claude-code",
    ])
    gemini = home / ".gemini" / "GEMINI.md"
    gemini.parent.mkdir(parents=True, exist_ok=True)
    gemini.write_text("# gemini instructions\n")

    result = runner.invoke(main, ["instructions", "doctor", "--scope", "global"], input="y\n")
    assert result.exit_code == 0, result.output

    canonical = home / ".agent-toolkit" / "AGENTS.md"
    backup = home / ".gemini" / "GEMINI.md.pre-adopt.bak"
    assert backup.is_file() and backup.read_text() == "# gemini instructions\n"
    assert gemini.is_symlink() and gemini.resolve() == canonical.resolve()
    lock = json.loads((home / ".agent-toolkit" / "instructions-lock.json").read_text())
    assert lock["instructions"]["AGENTS.md"]["harnesses"] == ["claude-code", "gemini-cli"]

    again = runner.invoke(main, ["instructions", "doctor", "--scope", "global"])
    assert again.exit_code == 0, again.output
    assert "clean" in again.output.lower()


def test_doctor_backup_fix_augment_global_slot_records_augment(tmp_path, monkeypatch):
    """~/.augment/CLAUDE.md at global scope is augment's OWN slot: the backup
    fix must record augment in the lock and must NOT fabricate a claude-code
    pointer (AC5 — _adopt_harness_for path-match rule)."""
    home = _global_home(tmp_path, monkeypatch)  # seeds populated canonical
    augment_slot = home / ".augment" / "CLAUDE.md"
    augment_slot.parent.mkdir(parents=True, exist_ok=True)
    augment_slot.write_text("# augment instructions\n")

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "global"], input="y\n")
    assert result.exit_code == 0, result.output

    canonical = home / ".agent-toolkit" / "AGENTS.md"
    backup = home / ".augment" / "CLAUDE.md.pre-adopt.bak"
    assert canonical.read_text() == "# global canon\n"  # canonical untouched
    assert backup.read_text() == "# augment instructions\n"
    assert augment_slot.is_symlink() and augment_slot.resolve() == canonical.resolve()
    assert not (home / ".claude" / "CLAUDE.md").exists(), "fabricated an unrelated claude-code pointer"
    lock = json.loads((home / ".agent-toolkit" / "instructions-lock.json").read_text())
    assert lock["instructions"]["AGENTS.md"]["harnesses"] == ["augment"]
```

(Note `_global_home` seeds `~/.agent-toolkit/AGENTS.md` with `# global canon\n` — canonical is populated, so these exercise the NEW branch, unlike the existing adopt-global tests which `unlink()` it first.)

- [ ] **Step 2: Run them**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py -k "backup_fix_global or backup_fix_augment" -v`
Expected: both PASS. If the augment test fails on lock contents, the bug is in how `_backup_then_symlink_finding` derives `adopt_harness` — it must call `_adopt_harness_for` (path match), never the bare scanning-harness name or a filename match.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_instructions_cli.py
git commit -m "test(instructions): backup-fix global-scope repro + augment slot attribution (#375)

Device: $(hostname -s)"
```

---

### Task 5: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `uv run pytest`
Expected: all green. Known environment quirk: `test_empty_machine_is_empty` can fail LOCALLY only (global pi inventory ignores `home=`); if it is the sole failure it is pre-existing, not yours.

- [ ] **Step 2: Lint + types — no NEW errors**

Run: `uv run ruff check src/agent_toolkit_cli/commands/instructions/doctor_cmd.py tests/test_cli/test_instructions_cli.py && uv run mypy src/agent_toolkit_cli/commands/instructions/doctor_cmd.py`
Expected: no errors attributable to the new code (main has pre-existing repo-wide noise; the bar is no-new-errors on touched files).

- [ ] **Step 3: Manual smoke in a sandbox HOME (optional but cheap)**

```bash
SANDBOX=$(mktemp -d)
mkdir -p "$SANDBOX/.agent-toolkit" "$SANDBOX/.gemini"
printf '# canon\n' > "$SANDBOX/.agent-toolkit/AGENTS.md"
printf '# gemini stuff\n' > "$SANDBOX/.gemini/GEMINI.md"
HOME="$SANDBOX" uv run agent-toolkit-cli instructions doctor --scope global <<< "y"
ls -la "$SANDBOX/.gemini/"   # expect: GEMINI.md -> canonical symlink + GEMINI.md.pre-adopt.bak
HOME="$SANDBOX" uv run agent-toolkit-cli instructions doctor --scope global   # expect: clean
rm -rf "$SANDBOX"
```

- [ ] **Step 4: Final commit (if any stragglers) + push branch + PR per repo flow**

```bash
git status --short   # expect empty or only intended files
```

PR title must be conventional (`feat(instructions): ...`) so release-please picks it up on squash-merge.

---

## Self-review notes

- Spec coverage: AC1 (Task 1), AC2 (Tasks 1+4), AC3 (Task 2), AC4 (Task 3), AC5 (Task 4 + untouched `_adopt_harness_for`), AC6 (Task 1 decline test; `--no-fix`/non-TTY paths are finding-agnostic loop code, already pinned by existing tests).
- Critical-review resolutions baked in: try-block opens at the rename (Task 1 Step 3 + third rollback test in Task 3); coexisting-`conflict` interaction documented in the spec behaviour matrix as accepted rollback behaviour (no pre-flight guard — deliberate).
- The adopt branch (canonical missing/empty) is behaviourally untouched; all #337 tests stay as-is.
- `test_doctor_unmanaged_does_not_clobber_existing_agents` is deliberately replaced (its report-only assertion is the removed behaviour); its no-destruction intent survives in the Task 1 tests.
- Types/names consistent: `_backup_then_symlink_finding`, `backup = pointer.with_name(pointer.name + ".pre-adopt.bak")`, message prefix `unmanaged:` retained (the dedupe-count test greps `unmanaged:`).
