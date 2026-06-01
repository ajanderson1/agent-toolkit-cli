# Plan — agent kind (minor) fixes · issue #304

Spec: `docs/superpowers/specs/2026-05-31-agent-kind-minor-fixes-design.md`
Discipline: TDD — write the failing test, watch it fail, make it pass. Three
independent tasks; commit each separately so a bisect points at one bug.

## Task 1 — `agent status` honesty (Bug 1)

**Files**
- impl: `src/agent_toolkit_cli/commands/agent/status_cmd.py`
- test: `tests/test_cli/test_cli_agent_status.py` (new or extend if present)

**Behaviour**
- Resolve scope as today (`scope_and_roots(..., read_only=True)`) — no policy change.
- Compute `targets` (sorted lock entries, filtered by `slugs` if given).
- Empty handling, scope-named:
  - On `FileNotFoundError` → `no agents in the {scope} library`.
  - Lock exists but `targets` empty **and no `slugs` filter** → same
    `no agents in the {scope} library` (this is the currently-silent branch).
  - `slugs` given but none match → per-slug `not found` line(s) (don't claim the
    library is empty). Match existing unknown-slug convention if one exists in a
    sibling verb; otherwise `{slug}\tnot found`.
- Otherwise render rows as today.

**Tests (write first)**
1. `status -g` on empty global lock → output contains `global` and is non-empty.
2. add an agent globally, then `status -g` → row for that slug present (parity
   with `list -g`).
3. `status -p` (or bare `status` in a project tmp dir with empty/no project lock)
   → message names `project`.
4. `status -g foo` where `foo` absent but library non-empty → `foo` flagged
   `not found`, no false "empty library" claim.

## Task 2 — `agent add` validates `<slug>.md` (Bug 2)

**Files**
- impl: `src/agent_toolkit_cli/commands/agent/add_cmd.py`
- test: `tests/test_cli/test_cli_agent_add.py` (extend if present)

**Behaviour**
- After the clone block + idempotent short-circuit, before constructing
  `LockEntry` (currently line ~108):
  ```python
  content_file = canonical / f"{final_slug}.md"
  if not content_file.exists():
      raise click.ClickException(
          f"{final_slug}: content file {final_slug}.md absent in source "
          f"{parsed.url!r}; expected <slug>.md at the repo root. "
          f"Pass --slug to match the file, or add a conforming source."
      )
  ```
  (Wording mirrors doctor's `missing-content-file` detail so the two read alike.)
- Lock entry is built/written ONLY after this check passes — the clone stays on
  disk as the canonical (matches existing add behaviour; re-run with correct
  `--slug` is idempotent via the `canonical.exists()` guard).

**Tests (write first)**
1. local source dir whose only `.md` is `AGENT.md` (no `<slug>.md`) →
   `agent add <dir> --slug whatever` exits non-zero, message names the expected
   `<slug>.md`, and lock has **no** entry for the slug afterward.
2. local source dir containing `<slug>.md` → `add` succeeds, lock entry written
   (happy-path guard — confirms the new check doesn't break the good path).
   Use a local-path source so the test needs no network (mirror existing
   add-test fixtures).

## Task 3 — TUI display label (Bug 3)

**Files**
- impl: `src/agent_toolkit_tui/widgets/skill_grid.py` (line ~552),
  `src/agent_toolkit_tui/column_info.py` (line ~48)
- test: `tests/test_tui/` (extend the grid/header render test; add label assert)

**Behaviour**
- `skill_grid.py:552`: `"Universal"` → `"General"`. Token comparison
  `agent == "universal"` unchanged.
- `column_info.py:48`: `ColumnInfo(title="Universal bundle", ...)` →
  `title="General bundle"`. Dict key `"universal"` on line 72 unchanged.

**Tests (write first)**
1. Headless grid render → header row contains `General`, not `Universal`.
2. (If a column-info modal test exists) modal title is `General bundle`.
3. Confirm existing bundle-detection tests (token `"universal"`) still pass —
   no new test needed, just don't break them.

## Sequencing

1. Task 1 (status) — commit `fix: agent status scope-named empty state (#304)`.
2. Task 2 (add) — commit `fix: agent add validates <slug>.md exists (#304)`.
3. Task 3 (TUI) — commit `fix: TUI grid label universal→General (#304)`.

Each task: red → green → refactor, then commit. Conventional-commit subjects so
release-please cuts a patch.

## Verification (flow Step 8-9)

- Pre-flight CI: `uv run ruff check .` + `uv run pytest -q` (from CI/lefthook).
- Verify (Step 9, no `.claude/testing.md`/`verify.sh`): terminal recipe —
  `uv run agent-toolkit-cli agent --help` + a live `agent status -g` /
  `agent add` malformed-source demo captured to artifacts.

## Done when

- All three tasks' tests pass; `ruff` clean; `pytest -q` green.
- Self-review (Step 10) PASS.
- PR opened ready-for-review, `Closes #304`.
