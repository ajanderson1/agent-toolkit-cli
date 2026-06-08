# Doctor Adopts Unmanaged Instruction Files — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `instructions doctor` detects a real, unmanaged instruction file at a known pointer slot (e.g. a bare `CLAUDE.md`) and offers to adopt it — rename → `AGENTS.md`, install the slot as a symlink, write the lock — honouring install's write-lock → apply → rollback contract.

**Architecture:** Migrate `commands/instructions/doctor_cmd.py` from a `list[str]` + `ctx.exit(1)` checker to the established `Finding` + `fix_action` interactive-doctor pattern already used by `skill/doctor_cmd.py` and `pi_extension/doctor_cmd.py`. The three existing findings (orphan/conflict/stray) become report-only `Finding`s; a new fourth **unmanaged** scan produces a `Finding` whose `fix_action` performs the adopt. The y/N/q prompt loop (with its non-TTY guard) is copied from `skill/doctor_cmd.py`, giving `--no-fix`, no-silent-mutation, and UX parity for free.

**Tech Stack:** Python 3, Click, pytest, `CliRunner`. Existing modules: `instructions_install.apply`, `instructions_lock`, `instructions_paths`, `instructions_adapters.symlink` (`_pointer_path`, `CELLS`, `PointerConflictError`, `SUPPORTED_HARNESSES`).

---

## File Structure

- **Modify:** `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py` — the whole feature lands here. Add a `--no-fix` flag, a local `Finding`/`FixAction` dataclass pair (or reuse a shared one if one exists — see Task 1), the unmanaged scan, the adopt closure, and the prompt loop.
- **Modify (tests):** `tests/test_cli/test_instructions_cli.py` — append the new test cases alongside the existing doctor tests; reuse the `_global_home` helper already defined there.

No new modules. The adopt logic is small and doctor-specific; keeping it in `doctor_cmd.py` matches how `skill`/`pi_extension` doctors carry their own loop. We do **not** add a standalone `adopt` command (explicitly out of scope per the spec).

---

## Task 1: Decide the Finding/FixAction carrier

**Files:**
- Read: `src/agent_toolkit_cli/commands/skill/doctor_cmd.py`, `src/agent_toolkit_cli/skill_doctor.py` (or wherever `Finding`/`FixAction` are defined for the skill doctor)
- Modify: `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py`

- [ ] **Step 1: Locate the existing Finding/FixAction types**

The skill doctor's `Finding` has `.slug`, `.kind`, `.scope`, `.path`, `.detail`, `.fix_action`; `FixAction` has `.shell_preview: str` and `.apply: Callable[[], None]`. Find their definitions:

```bash
grep -rn "class FixAction\|class Finding\|@dataclass" src/agent_toolkit_cli/skill_doctor.py src/agent_toolkit_cli/pi_extension_doctor.py 2>/dev/null
```

Decision rule: those `Finding` classes carry skill-specific fields (`slug`) the instructions doctor doesn't have. **Do not import them.** Define a small local pair in `doctor_cmd.py` tailored to instructions — keeps the instructions doctor self-contained and avoids coupling to skill internals. This is a deliberate, minimal duplication (two tiny dataclasses), consistent with each doctor owning its own loop.

- [ ] **Step 2: Add the local dataclasses to `doctor_cmd.py`**

At the top of `doctor_cmd.py` (after imports), add:

```python
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class FixAction:
    """A repair the user can opt into for a finding."""
    shell_preview: str
    apply: Callable[[], None]


@dataclass
class Finding:
    """One doctor finding. `fix_action=None` means report-only."""
    message: str
    fix_action: "FixAction | None" = None
```

- [ ] **Step 3: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/doctor_cmd.py
git commit -m "refactor(instructions): add Finding/FixAction carriers to doctor"
```

(No test yet — Task 2 migrates behaviour onto these and is covered by the *existing* doctor tests, which must keep passing.)

---

## Task 2: Migrate existing findings onto Finding objects (no behaviour change)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py`
- Test (existing, must stay green): `tests/test_cli/test_instructions_cli.py::test_doctor_reports_orphan_pointer_when_canonical_gone`, `::test_doctor_clean_exit_zero`, `::test_doctor_reports_conflict`, `::test_doctor_global_clean`

- [ ] **Step 1: Run the existing doctor tests to confirm green baseline**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py -q -k doctor`
Expected: PASS (4 doctor tests).

- [ ] **Step 2: Replace `findings: list[str]` with `findings: list[Finding]`**

In `doctor_cmd`, change the accumulator and every `findings.append(f"...")` to `findings.append(Finding(message=f"..."))`. Keep the exact message strings (existing tests assert on substrings `orphan`, `conflict`, `stray`). Concretely:

```python
findings: list[Finding] = []
# orphan
findings.append(Finding(message=f"orphan: canonical AGENTS.md missing at {canonical}"))
# conflict (both branches)
findings.append(Finding(message=f"conflict: {harness} pointer at {pointer} is a real file (not ours)"))
findings.append(Finding(message=f"conflict: {harness} pointer at {pointer} → {pointer.resolve()} (not canonical)"))
# stray
findings.append(Finding(message=f"stray: {harness} pointer at {pointer} points at canonical but isn't recorded in the lock"))
```

Also, **while building conflicts, record the conflict paths** for Task 3's exclusion:

```python
conflict_paths: set[Path] = set()
...
if pointer.exists() and not pointer.is_symlink():
    conflict_paths.add(pointer)
    findings.append(Finding(message=f"conflict: {harness} pointer at {pointer} is a real file (not ours)"))
```

- [ ] **Step 3: Replace the print/exit tail with the report-only loop (interim)**

Replace the final block:

```python
    if not findings:
        click.echo("clean — no findings at this scope")
        return
    for f in findings:
        click.echo(f.message)
    ctx.exit(1)
```

(Keep `clean — no findings at this scope` verbatim — `test_doctor_clean_exit_zero` asserts `"clean"` is in output. Keep exit 1 when findings exist.)

- [ ] **Step 4: Run the doctor tests again**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py -q -k doctor`
Expected: PASS (unchanged behaviour — strings and exit codes identical).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/doctor_cmd.py
git commit -m "refactor(instructions): doctor findings carried as objects (no behaviour change)"
```

---

## Task 3: Detect the unmanaged file (RED → GREEN, report-only)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py`
- Test: `tests/test_cli/test_instructions_cli.py`

- [ ] **Step 1: Write the failing test (project scope)**

Append to `tests/test_cli/test_instructions_cli.py`:

```python
def test_doctor_detects_unmanaged_claude_md(tmp_path, monkeypatch):
    """A real, lock-unrecorded CLAUDE.md is an 'unmanaged' finding (not 'clean')."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# my instructions\n")  # real file, no lock, no AGENTS.md
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project", "--no-fix"])
    assert result.exit_code != 0, result.output
    assert "unmanaged" in result.output.lower()
    assert "clean" not in result.output.lower()
    # --no-fix must not mutate.
    assert (project / "CLAUDE.md").is_file() and not (project / "CLAUDE.md").is_symlink()
    assert not (project / "AGENTS.md").exists()
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py::test_doctor_detects_unmanaged_claude_md -v`
Expected: FAIL — either `--no-fix` is an unknown option, or output says `clean` and exit 0.

- [ ] **Step 3: Add the `--no-fix` flag and the unmanaged scan block**

Add the option to the command:

```python
@click.option("--no-fix", is_flag=True, help="Report only; do not prompt or mutate.")
```

and the parameter `no_fix: bool` to `doctor_cmd`'s signature.

After the stray block, add the unmanaged scan. It dedupes by pointer path and excludes conflict slots:

```python
    # Unmanaged: a real file (not a symlink) at a known pointer slot that the
    # lock doesn't record. A real file at a *wanted* slot is already a conflict
    # (above), so exclude conflict_paths. Several harnesses share a slot
    # (augment+claude-code → CLAUDE.md); dedupe by path so we emit one finding.
    seen_unmanaged: set[Path] = set()
    for harness in sorted(SUPPORTED_HARNESSES):
        try:
            pointer = _pointer_path(harness, scope, project_root, home)
        except ValueError:
            continue
        if pointer in conflict_paths or pointer in seen_unmanaged:
            continue
        if pointer.exists() and not pointer.is_symlink():
            seen_unmanaged.add(pointer)
            findings.append(_unmanaged_finding(
                pointer=pointer, harness=harness, canonical=canonical,
                scope=scope, project_root=project_root, home=home,
                lock_path=lock_path,
            ))
```

Add a helper `_unmanaged_finding(...)` (filled in Task 4) that, for now, returns a report-only finding:

```python
def _unmanaged_finding(*, pointer, harness, canonical, scope, project_root, home, lock_path) -> Finding:
    adoptable = not canonical.exists() or canonical.stat().st_size == 0
    if not adoptable:
        return Finding(message=(
            f"unmanaged: real file at {pointer} is not in the lock; "
            f"AGENTS.md already exists — adopt skipped (content merge is out of scope)"
        ))
    return Finding(message=(
        f"unmanaged: real file at {pointer} is not in the lock "
        f"(adopt → rename to AGENTS.md + symlink {pointer.name})"
    ))
```

- [ ] **Step 4: Run the test — expect PASS**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py::test_doctor_detects_unmanaged_claude_md -v`
Expected: PASS.

- [ ] **Step 5: Add the shared-slot dedupe test**

```python
def test_doctor_unmanaged_dedupes_shared_slot(tmp_path, monkeypatch):
    """augment + claude-code share the CLAUDE.md slot → exactly one unmanaged finding."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# x\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project", "--no-fix"])
    assert result.output.lower().count("unmanaged") == 1, result.output
```

- [ ] **Step 6: Run the full doctor suite — confirm no regression**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py -q -k doctor`
Expected: PASS (all prior doctor tests + 2 new).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/doctor_cmd.py tests/test_cli/test_instructions_cli.py
git commit -m "feat(instructions): doctor detects unmanaged instruction files (#337)"
```

---

## Task 4: The adopt fix_action (RED → GREEN)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py`
- Test: `tests/test_cli/test_instructions_cli.py`

- [ ] **Step 1: Write the failing adopt test (project scope)**

```python
def test_doctor_adopt_renames_and_symlinks(tmp_path, monkeypatch):
    """`y` at the prompt: CLAUDE.md → AGENTS.md (content kept), CLAUDE.md becomes a symlink, lock written, re-run clean."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# my instructions\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    assert result.exit_code == 0, result.output  # adopted → nothing skipped

    agents = project / "AGENTS.md"
    pointer = project / "CLAUDE.md"
    assert agents.is_file() and agents.read_text() == "# my instructions\n"
    assert pointer.is_symlink() and pointer.resolve() == agents.resolve()

    lock = json.loads((project / "instructions-lock.json").read_text())
    assert "claude-code" in lock["instructions"]["AGENTS.md"]["harnesses"]

    # Round-trip: doctor is now clean.
    again = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert again.exit_code == 0, again.output
    assert "clean" in again.output.lower()
```

- [ ] **Step 2: Run it — expect FAIL**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py::test_doctor_adopt_renames_and_symlinks -v`
Expected: FAIL — there's no prompt yet (loop added in Task 5) and `_unmanaged_finding` has no `fix_action`, so nothing adopts; exit code ≠ 0 or AGENTS.md absent.

- [ ] **Step 3: Add the adopt closure to `_unmanaged_finding`**

Replace the adoptable branch's return so it attaches a `fix_action`. Derive the adopting harness from the slot — for the shared `CLAUDE.md` slot prefer `claude-code`:

```python
def _adopt_harness_for(pointer: Path, harness: str) -> str:
    # The CLAUDE.md slot is shared by augment + claude-code; claude-code is the
    # canonical adopter. Otherwise the scanning harness owns its slot.
    if pointer.name == "CLAUDE.md":
        return "claude-code"
    return harness
```

```python
    adopt_harness = _adopt_harness_for(pointer, harness)

    def _apply() -> None:
        # Re-assert the guard (a non-empty AGENTS.md may have appeared).
        if canonical.exists() and canonical.stat().st_size > 0:
            raise click.ClickException(
                f"{canonical} already exists with content — refusing to clobber"
            )
        prior = read_lock(lock_path)
        prior_existed = lock_path.exists()
        # Rename BEFORE writing the lock so a failure never leaves a lying lock.
        pointer.rename(canonical)
        existing = prior.instructions.get("AGENTS.md")
        new_harnesses = sorted({*(existing.harnesses if existing else []), adopt_harness})
        new = add_entry(prior, "AGENTS.md", InstructionsLockEntry(
            scope=scope, source="AGENTS.md", harnesses=new_harnesses,
        ))
        write_lock(lock_path, new)
        try:
            instructions_install.apply(scope=scope, project_root=project_root, home=home)
        except (instructions_install.CanonicalMissingError, PointerConflictError) as exc:
            # Roll back: restore the real file and the prior lock.
            if canonical.exists() and not pointer.exists():
                canonical.rename(pointer)
            if prior_existed:
                write_lock(lock_path, prior)
            else:
                lock_path.unlink(missing_ok=True)
            raise click.ClickException(str(exc)) from exc

    return Finding(
        message=(f"unmanaged: real file at {pointer} is not in the lock"),
        fix_action=FixAction(
            shell_preview=f"mv {pointer.name} AGENTS.md && instructions install --harness {adopt_harness}",
            apply=_apply,
        ),
    )
```

Add the required imports at the top of the file:

```python
from agent_toolkit_cli import instructions_install
from agent_toolkit_cli.instructions_adapters.symlink import PointerConflictError
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry, add_entry, read_lock, write_lock,
)
```

(`read_lock` is already imported; add only what's missing. `_pointer_path` and `SUPPORTED_HARNESSES` are already imported.)

- [ ] **Step 4: Run it — still FAIL (no prompt loop yet)**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py::test_doctor_adopt_renames_and_symlinks -v`
Expected: FAIL — `fix_action` exists but the command still prints+exits without prompting. Proceed to Task 5 (the loop) to turn this green.

- [ ] **Step 5: Commit (test stays red until Task 5 — commit the impl + test together at end of Task 5)**

Do not commit a red test alone. Carry this test into Task 5 and commit once green. (Skip commit here.)

---

## Task 5: The interactive prompt loop (turns Task 4 green)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/instructions/doctor_cmd.py`
- Test: `tests/test_cli/test_instructions_cli.py` (the Task 4 adopt test + a non-TTY test)

- [ ] **Step 1: Replace the report-only tail with the y/N/q loop**

Copy the loop from `skill/doctor_cmd.py` (lines 36-86), adapted to the instructions `Finding` (which has `.message` not `.slug/.kind/...`):

```python
    if not findings:
        click.echo("clean — no findings at this scope")
        return

    fixed = skipped = 0
    quit_loop = False
    for f in findings:
        click.echo("")
        click.echo(f.message)
        if f.fix_action is None or no_fix or quit_loop:
            skipped += 1
            if f.fix_action is None:
                click.echo("  (report-only — no automatic fix)")
            continue
        click.echo(f"  fix:    {f.fix_action.shell_preview}")
        try:
            ans = click.prompt(
                "  apply?", default="N", show_default=False,
                type=click.Choice(["y", "N", "q"], case_sensitive=False),
            )
        except (click.Abort, EOFError, OSError):
            click.echo("\n  (no input available — stopping; nothing applied)")
            quit_loop = True
            skipped += 1
            continue
        ans = ans.lower()
        if ans == "y":
            try:
                f.fix_action.apply()
                click.echo("  adopted.")
                fixed += 1
            except Exception as exc:
                click.echo(f"  adopt failed: {exc}")
                skipped += 1
        elif ans == "q":
            quit_loop = True
            skipped += 1
        else:
            skipped += 1

    click.echo("")
    click.echo(f"summary: {len(findings)} findings, {fixed} fixed, {skipped} skipped")
    if skipped > 0:
        ctx.exit(1)
```

Note: a fully-adopted run has `skipped == 0` → exit 0 (the adopt test asserts exit 0). A `--no-fix` run skips everything → exit 1.

- [ ] **Step 2: Run the adopt test — expect PASS**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py::test_doctor_adopt_renames_and_symlinks -v`
Expected: PASS.

- [ ] **Step 3: Add the non-TTY no-mutation test**

```python
def test_doctor_unmanaged_non_tty_does_not_mutate(tmp_path, monkeypatch):
    """No --no-fix, but no input available (non-TTY): finding reported, nothing adopted, exit 1."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "CLAUDE.md").write_text("# x\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    # No `input=` → click.prompt hits EOF → the except guard fires.
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"])
    assert result.exit_code != 0, result.output
    assert (project / "CLAUDE.md").is_file() and not (project / "CLAUDE.md").is_symlink()
    assert not (project / "AGENTS.md").exists()
    assert "no input available" in result.output.lower()
```

- [ ] **Step 4: Run it — expect PASS**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py::test_doctor_unmanaged_non_tty_does_not_mutate -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/instructions/doctor_cmd.py tests/test_cli/test_instructions_cli.py
git commit -m "feat(instructions): doctor adopts unmanaged file as AGENTS.md (#337)"
```

---

## Task 6: Guard non-empty AGENTS.md (no clobber)

**Files:**
- Test: `tests/test_cli/test_instructions_cli.py`

- [ ] **Step 1: Write the no-clobber test**

```python
def test_doctor_unmanaged_does_not_clobber_existing_agents(tmp_path, monkeypatch):
    """Real CLAUDE.md + non-empty AGENTS.md: reported but report-only; 'y' must not destroy either."""
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# real canon\n")
    (project / "CLAUDE.md").write_text("# different\n")
    monkeypatch.chdir(project)

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "project"], input="y\n")
    # Reported as unmanaged (real file, not in lock) but adopt is skipped → exit 1.
    assert result.exit_code != 0, result.output
    assert "unmanaged" in result.output.lower()
    # Neither file destroyed.
    assert (project / "AGENTS.md").read_text() == "# real canon\n"
    assert (project / "CLAUDE.md").read_text() == "# different\n"
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py::test_doctor_unmanaged_does_not_clobber_existing_agents -v`
Expected: PASS already — `_unmanaged_finding` returns a report-only `Finding` (no `fix_action`) when `canonical` is non-empty, so the loop skips it and exits 1. If it FAILS, fix `_unmanaged_finding`'s `adoptable` guard.

- [ ] **Step 3: Commit (if any fix was needed)**

```bash
git add tests/test_cli/test_instructions_cli.py src/agent_toolkit_cli/commands/instructions/doctor_cmd.py
git commit -m "test(instructions): doctor never clobbers an existing AGENTS.md"
```

---

## Task 7: Global-scope adopt

**Files:**
- Test: `tests/test_cli/test_instructions_cli.py` (reuse `_global_home`)

- [ ] **Step 1: Write the global adopt test**

The global `claude-code` slot is `~/.claude/CLAUDE.md`. Seed a real file there (and DELETE the seeded canonical so it's adoptable), then adopt:

```python
def test_doctor_adopt_global(tmp_path, monkeypatch):
    home = _global_home(tmp_path, monkeypatch)
    # _global_home seeds ~/.agent-toolkit/AGENTS.md — remove it so adoption is unambiguous.
    (home / ".agent-toolkit" / "AGENTS.md").unlink()
    # Real, unmanaged file at the global claude-code slot.
    (home / ".claude").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "CLAUDE.md").write_text("# global instructions\n")

    runner = CliRunner()
    result = runner.invoke(main, ["instructions", "doctor", "--scope", "global"], input="y\n")
    assert result.exit_code == 0, result.output

    agents = home / ".agent-toolkit" / "AGENTS.md"
    pointer = home / ".claude" / "CLAUDE.md"
    assert agents.is_file() and agents.read_text() == "# global instructions\n"
    assert pointer.is_symlink() and pointer.resolve() == agents.resolve()

    again = runner.invoke(main, ["instructions", "doctor", "--scope", "global"])
    assert again.exit_code == 0, again.output
    assert "clean" in again.output.lower()
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py::test_doctor_adopt_global -v`
Expected: PASS. The global pointer path resolution for `claude-code` is `{HOME}/.claude/CLAUDE.md`; the canonical rename target is `{HOME}/.agent-toolkit/AGENTS.md`. The adopt's `pointer.rename(canonical)` works across these because `apply()` re-creates the pointer at the right slot. If the rename crosses devices (rare in tmp), it still works within a single tmpdir filesystem.

If it FAILS because the global pointer scan didn't fire: confirm the unmanaged loop passes `home` through to `_pointer_path` for global scope (it must — `home = Path.home()` is set for global at the top of `doctor_cmd`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_instructions_cli.py
git commit -m "test(instructions): doctor adopts an unmanaged file at global scope"
```

---

## Task 8: Full suite + lint

**Files:** none (verification)

- [ ] **Step 1: Run the whole instructions CLI suite**

Run: `uv run pytest tests/test_cli/test_instructions_cli.py -q`
Expected: PASS (all original + ~6 new tests).

- [ ] **Step 2: Run the entire test suite**

Run: `uv run pytest -q`
Expected: PASS — confirm the doctor refactor didn't break anything elsewhere (e.g. anything importing the old behaviour).

- [ ] **Step 3: Lint**

Run: `uv run ruff check src/agent_toolkit_cli/commands/instructions/doctor_cmd.py tests/test_cli/test_instructions_cli.py`
Expected: clean. Fix any unused-import / line-length issues (the new imports must all be used).

- [ ] **Step 4: Commit any lint fixes**

```bash
git add -A
git commit -m "style(instructions): lint doctor adopt changes" || echo "nothing to commit"
```

---

## Self-Review notes (plan vs spec)

- **Spec: new unmanaged finding, project + global** → Tasks 3 (project), 7 (global). ✓
- **Spec: adopt = rename → install → lock, with rollback** → Task 4's `_apply` (rename-before-lock, rollback on `CanonicalMissingError`/`PointerConflictError`). ✓
- **Spec: non-TTY / `--no-fix` must not mutate** → Task 3 (`--no-fix` test), Task 5 (non-TTY EOF test). ✓
- **Spec: don't clobber non-empty AGENTS.md** → `_unmanaged_finding` adoptable guard + Task 6 test + re-assert inside `_apply`. ✓
- **Spec: shared-slot dedupe (augment+claude-code)** → Task 3 `seen_unmanaged` set + dedupe test. ✓
- **Spec: conflict vs unmanaged mutually exclusive** → Task 2 records `conflict_paths`, Task 3 excludes them. ✓
- **Spec: round-trip doctor clean after adopt** → Tasks 4 & 7 re-run doctor and assert `clean`. ✓
- **Type consistency:** `Finding.message`, `Finding.fix_action`, `FixAction.shell_preview`, `FixAction.apply` used identically across Tasks 1–5. `_unmanaged_finding(...)` keyword args match its call site in Task 3. `_adopt_harness_for` defined once, used once. ✓
- **No placeholders:** every code step shows complete code. ✓
