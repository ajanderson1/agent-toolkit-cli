# Plan: retire the bash CLI

**Spec:** `docs/superpowers/specs/2026-05-04-retire-bash-cli-design.md`
**Issue:** #6
**Branch:** `chore/6-retire-bash-cli`
**Mode:** mechanical refactor — no TDD because no behaviour changes; verify by running the existing suite after each step.

## Task list

### T1 — Update fix-hint strings in production code

Three files, mechanical replace `bin/agent-toolkit` → `agent-toolkit`:

- `src/agent_toolkit_cli/inventory.py` lines 164-165
- `src/agent_toolkit_cli/doctor/symlinks.py` line 101
- `src/agent_toolkit_cli/doctor/conventions.py` line 60

**Run:** `pytest tests/test_inventory.py tests/doctor -q` → expect `test_inventory.py` line 66 to fail (asserts the old string). Good.

### T2 — Update the assertion in `tests/test_inventory.py`

Line 66: `"bin/agent-toolkit link user claude"` → `"agent-toolkit link user claude"`.

**Run:** `pytest tests/test_inventory.py -q` → green.

### T3 — Delete bin/

```
git rm -r bin/
```

### T4 — Delete tests/bats/

```
git rm -r tests/bats/
```

### T5 — Delete tests/test_target_dir_parity.py

```
git rm tests/test_target_dir_parity.py
```

### T6 — Edit lefthook.yml

Remove the `bats:` block (lines 7-9). Keep `pytest` and `schema-vendor-check`.

### T7 — Edit .github/workflows/test.yml

Remove the `bats:` job (lines 17-24). Keep the `pytest:` job.

### T8 — Edit AGENTS.md

Three substantive changes:

1. **Opening paragraph** (line 3): `"The bash+Python CLI (\`bin/agent-toolkit\`, \`src/agent_toolkit_cli\`) and the Textual TUI ..."` → `"The Python CLI (\`src/agent_toolkit_cli\`) and the Textual TUI ..."`.
2. **Code map** (lines 31-50): drop the `bin/agent-toolkit` and `bin/lib/` entries. Keep everything else.
3. **Layered contract** rule 6 (line 59): delete the `"6. **Bash CLI** is for filesystem operations (symlinks). Stays zero-dep."` line entirely.
4. **Development workflow** (lines 64-67): drop the `bats tests/bats` line.

### T9 — Edit docs/agent-toolkit/cli.md

Read first (it's 19K), then surgical edits: replace any prose that says "bash CLI" or `bin/agent-toolkit` with `agent-toolkit` (the entry-point name). Flag tables stay untouched — the grammar was identical.

If the file does not exist post-PR-5 or has already been updated, skip silently. If the file is gone entirely (e.g. moved to the toolkit repo), skip and note in `flow.log`.

### T10 — Smoke tests

```bash
uv sync --all-extras                                          # fresh install
uv run agent-toolkit --help                                   # CLI still loads
uv run agent-toolkit list --format=json                       # core read path
uv run agent-toolkit-tui --headless --help                    # TUI still loads
uv run pytest -q                                              # full suite
grep -rn "bin/agent-toolkit" --include="*.py" src tests       # only docstrings
```

Expected:
- All commands exit 0 (or list shows whatever the local repo state is).
- `pytest -q` reports `~298 passed, 2 skipped` (was 300; parity was 2 tests).
- `grep` returns only docstring lines in `src/agent_toolkit_tui/`.

### T11 — Single commit

```
chore(cli): retire bash CLI — delete bin/, bats suite, parity test

Closes #6.

After PR #5, the bash dispatcher and bats suite are dead weight: the
Python CLI implements link/unlink/list/diff natively, the TUI calls
the Python entry point via PATH (not bin/agent-toolkit), and the
parity test exists only to police drift between two implementations
of which one is now unused.

- Delete bin/agent-toolkit, bin/lib/*.sh
- Delete tests/bats/ (16 files + helpers.bash)
- Delete tests/test_target_dir_parity.py
- Strip bats from lefthook.yml and .github/workflows/test.yml
- Update fix-hint strings in inventory.py, doctor/symlinks.py,
  doctor/conventions.py from `bin/agent-toolkit link` to
  `agent-toolkit link` (the entry-point name)
- Rewrite AGENTS.md and docs/agent-toolkit/cli.md to drop bash framing

Conventions handling stays unimplemented (per #1, #9). Anyone calling
`agent-toolkit conventions` from a script now gets exit 2 from the
unknown-harness validator.
```

## Acceptance checklist (Verify will run this)

- [ ] `bin/` does not exist on disk
- [ ] `tests/bats/` does not exist on disk
- [ ] `tests/test_target_dir_parity.py` does not exist
- [ ] `pytest -q` ≈ 298 passed, 2 skipped
- [ ] `agent-toolkit list` works
- [ ] `agent-toolkit-tui --headless --help` works
- [ ] No production-code `bin/agent-toolkit` references (docstrings ok)
- [ ] `lefthook.yml` has no `bats:` block
- [ ] `.github/workflows/test.yml` has no `bats:` job

## Estimated diff size

~−3000 lines (deletions dwarf edits): bin/lib/*.sh ≈ 1500 LOC, bats ≈ 1500 LOC, parity ≈ 65 LOC. Edits ~30 LOC across 6 files.

## Subagent escalation triggers

- TUI smoke test fails → halt; the assumption that runner.py is fully Python is wrong. Surface the failure.
- pytest count drops by more than the 2 parity tests → halt; something else broke. Surface the failure list.
- AGENTS.md edits change the meaning of the layered contract beyond rule 6 → halt; surface the diff for human review.
