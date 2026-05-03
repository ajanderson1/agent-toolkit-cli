# Retire the bash CLI

**Issue:** [#6](https://github.com/ajanderson1/agent-toolkit-cli/issues/6) — *Retire bash CLI: delete bin/, bats suite, parity test (PR-2 of unify-CLI)*
**Predecessor:** PR #5 (port link/unlink/list/diff to Python). PR #15 (validate harness) shipped subsequently.
**Date:** 2026-05-04

## Problem

After PR #5, the bash dispatcher (`bin/agent-toolkit`) and its subcommand modules (`bin/lib/*.sh`) are dead weight:

- The Python CLI implements `link`, `unlink`, `list`, `diff` natively.
- The TUI (`src/agent_toolkit_tui/runner.py`) calls `shutil.which("agent-toolkit")` — the Python entry point on PATH — not the bash binary. Verified at `runner.py:18-42`.
- The bats suite (`tests/bats/`) and the cross-language parity test (`tests/test_target_dir_parity.py`) exist solely to police drift between the two implementations. With one implementation, they cease to have any subject.

The bash side still carries one feature the Python side does not: `agent-toolkit conventions` (handled by `bin/lib/conventions.sh`). PR #5 deliberately left this out of scope. Issue #9 / PR #15 confirmed the policy: unknown harnesses (including the string `conventions`) now exit 2. Conventions handling, if ever resurrected, will live in a separate package — not this CLI.

## Goals

1. Delete the bash dispatcher and all `.sh` modules under `bin/`.
2. Delete the entire bats test suite (`tests/bats/`) and its helpers.
3. Delete the cross-language parity test (`tests/test_target_dir_parity.py`) — the second implementation it polices is gone.
4. Strip the `bats` job from CI (`.github/workflows/test.yml`) and the `bats` and `schema-vendor-check` (no — keep schema-vendor-check) commands from `lefthook.yml`. Keep `pytest` and `schema-vendor-check`.
5. Update fix-hint strings in `src/agent_toolkit/inventory.py`, `src/agent_toolkit/doctor/symlinks.py`, `src/agent_toolkit/doctor/conventions.py` from `bin/agent-toolkit link …` to `agent-toolkit link …` (the entry-point name).
6. Update `tests/test_inventory.py` assertion to match the new fix-hint string.
7. Update `AGENTS.md` to drop the bash/zero-dep framing and present the project as a single Python CLI.
8. Update `docs/agent-toolkit/cli.md` similarly — the flag tables themselves are unchanged (the grammar was identical), so the surgical edit is wording, not contracts.

## Non-goals

- Behavioural changes to any Python subcommand.
- Renaming subcommands.
- Re-introducing `conventions` to this CLI.
- Tagging `v0.2.0` manually — release-please now owns versioning (PR #14/#16 already shipped 0.2.0).
- Touching docstring references in TUI files (`runner.py:24`, `app.py:30`, `__init__.py:3`) — they are accurate prose ("sister to bin/agent-toolkit" is historical context, not a code path) and rewriting them is bikeshed. Defer to a future docs sweep if anyone cares.

## Approach

Single commit (or two if the AGENTS.md/docs rewrite feels logically separate from the deletion). Conventional commit message: `chore(cli): retire bash CLI — delete bin/, bats suite, and parity test`.

### Files deleted

```
bin/agent-toolkit
bin/lib/_ui.sh
bin/lib/common.sh
bin/lib/conventions.sh
bin/lib/diff.sh
bin/lib/link.sh
bin/lib/list.sh
bin/lib/unlink.sh
tests/bats/                      (entire directory: 16 .bats files + helpers.bash)
tests/test_target_dir_parity.py
```

After deletion, `bin/` and `bin/lib/` are empty — `git rm -r bin/` clears them.

### Files edited

| File | Edit |
|---|---|
| `lefthook.yml` | Remove the `bats:` command block. Keep `pytest`, keep `schema-vendor-check`. |
| `.github/workflows/test.yml` | Remove the `bats:` job. Keep the `pytest:` job. |
| `AGENTS.md` | Strike "bash+Python CLI", rewrite "bash CLI is for filesystem operations (symlinks). Stays zero-dep." in layered contract section, update Code map (drop `bin/agent-toolkit` and `bin/lib/` entries), update Development workflow (drop `bats tests/bats`). |
| `docs/agent-toolkit/cli.md` | Replace mentions of "bash CLI" or `bin/agent-toolkit` with `agent-toolkit` (the entry point). Flag tables unchanged. |
| `src/agent_toolkit/inventory.py` (lines 164-165) | `bin/agent-toolkit link` → `agent-toolkit link`. |
| `src/agent_toolkit/doctor/symlinks.py` (line 101) | `bin/agent-toolkit link user` → `agent-toolkit link user`. |
| `src/agent_toolkit/doctor/conventions.py` (line 60) | Same. |
| `tests/test_inventory.py` (line 66) | Update assertion string to match. |

## Tests

No new tests. The existing `pytest -q` suite (300 passed, 2 skipped on PR #15's branch — same on main now) must remain green. The parity test is being deleted on purpose; coverage of the target-dir tables now lives entirely in the Python tests (`tests/test_link_lib.py` + the link/unlink integration tests).

`bats` will not exist post-PR — pre-commit and CI will not run it because their config no longer mentions it.

## Acceptance checklist

- [ ] `bin/`, `tests/bats/`, `tests/test_target_dir_parity.py` no longer exist on disk.
- [ ] `pytest -q` is green and the count is `300 - 2 (parity) = 298 passed, 2 skipped`. (Approximate; parity file has 2 tests.)
- [ ] `lefthook.yml` and `.github/workflows/test.yml` no longer reference `bats`.
- [ ] `agent-toolkit link/unlink/list/diff` continue to work (smoke: `uv run agent-toolkit list`).
- [ ] `agent-toolkit-tui` still launches (smoke: `uv run agent-toolkit-tui --headless --help`).
- [ ] `grep -rn "bin/agent-toolkit" --include="*.py"` returns only docstring matches in TUI files (per non-goal #4) — no production code paths.

## Risk

- **TUI e2e regression.** The bats `test_tui_e2e.bats` was the only direct end-to-end test of the TUI. Deleting it leaves a coverage hole. Mitigation: a smoke run (`uv run agent-toolkit-tui --headless --help`) is part of the acceptance check. A real e2e port to pytest is a separate concern, out of scope here.
- **Conventions silently disappearing.** Anyone still calling `agent-toolkit conventions` from a script will now get exit 2 with `unknown harness 'conventions'`. That message is the right footgun guard — the scriptable bash side that *did* this is also gone, so the user already had to migrate.
- **Schema-drift gate stays.** `lefthook.yml`'s `schema-vendor-check` is unchanged — it tests bundled vs vendored schema, not bash vs python.

## Out-of-scope follow-ups

- Pytest port of `test_tui_e2e.bats` if the TUI needs it.
- A docs sweep through TUI module docstrings (`runner.py`, `app.py`, `__init__.py`) to update the "sister to bin/agent-toolkit" framing.
- README review (if a README exists in the repo root — check during build).
