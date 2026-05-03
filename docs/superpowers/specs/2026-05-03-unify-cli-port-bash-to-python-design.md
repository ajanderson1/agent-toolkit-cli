---
title: Unify CLI — port bash subcommands to Python
issue: 1
created: 2026-05-03
status: draft
effort: L
---

# Unify CLI — port bash subcommands to Python

## Problem

After the assets/CLI split (`v0.1`), the CLI is bilingual:

- **Python** (`src/agent_toolkit/`) — `check`, `fix`, `doctor`, `new`, `inventory`, `ingest`, `tui` and the hidden helpers `_list-json` / `_yaml-edit`.
- **Bash** (`bin/agent-toolkit` + `bin/lib/*.sh`) — `link`, `unlink`, `list`, `diff`.

This split causes three concrete failures, all surfaced during the post-split walkthrough (assets-repo PR #5):

1. **`uv tool install` doesn't expose the bash entry point.** Only scripts in `[project.scripts]` are installed; `bin/agent-toolkit` is not. After install, `agent-toolkit link …` returns `Error: No such command 'link'`.
2. **The TUI is read-only after install.** `runner.py:_plan` shells out to `agent-toolkit link --plan -`; the shell-out fails post-install with `RunnerError: link --plan grammar error (rc=2)`.
3. **The published fresh-machine flow is broken.** `agent-toolkit`'s README tells users to run `uv tool install … && agent-toolkit link user claude --all` — step 2 fails for the same reason.

The original justification for bash ("zero-dep on a Unix box") no longer applies: `uv tool install` already requires Python.

## Goals

- One CLI binary, one language. The four bash subcommands (`link`, `unlink`, `list`, `diff`) become first-class Click subcommands of the existing `agent-toolkit` Python entry point.
- **Pure port.** No flag changes, no output regressions, no schema changes. Same human-visible behaviour, single language behind it.
- **Tests-first parity** with the bats suite. The bats files are the behavioural spec; pytest must cover the same surface before bats is deleted.
- **TUI write-side works after `uv tool install`.** The single failing user-visible regression from the split is resolved.

## Non-goals

- Behavioural changes to `link`/`unlink`/`list`/`diff`. Same flags, same output (modulo trivial wording fidelity to the bats expectations).
- Renaming subcommands or restructuring the CLI surface.
- Schema changes.
- Cross-platform support beyond what the existing Python primitives already provide. Windows is a fall-out improvement, not a target.

## Design

### Code shape

Four new modules under `src/agent_toolkit/commands/`:

| New module | Replaces | Notes |
|---|---|---|
| `link.py` | `bin/lib/link.sh` + the symlink/projection logic in `bin/lib/common.sh` | Modes: bare (project compatibles), per-asset, `--all`, `--plan -`, `--dry-run`. |
| `unlink.py` | `bin/lib/unlink.sh` | Modes: bare (error hint), per-asset, `--all`, `--plan -`. |
| `list.py` | `bin/lib/list.sh` | Text by default; `--format=json` already exists as the hidden `_list-json` and is reused as a backend. |
| `diff.py` | `bin/lib/diff.sh` | Thin alias: invokes `link` with `dry_run=True` and the `Previewing` header swap. |

Each module exposes a Click command, registered in `src/agent_toolkit/cli.py`. They participate in the existing four-step `--toolkit-repo` resolver (flag → env → walk-up `.agent-toolkit-source` → default), via `_repo_resolution.resolve_toolkit_root()` — same as `check`, `doctor`, `inventory`.

### Reused primitives (no rewrite)

The Python side already contains everything bash duplicated. The port is essentially "wire the existing primitives into Click commands":

| Bash function (in `bin/lib/*.sh`) | Python equivalent (already exists) |
|---|---|
| `harness_target_dir()` / `project_target_dir()` | `commands/_list_json.py:_USER_TARGETS` / `_PROJECT_TARGETS` |
| `discover_assets_for_kind()` | `walker.py:discover_assets()` |
| `read_allowlist_section()` | `_allowlist.py:read_allowlist()` |
| `kind_to_section()` | `_allowlist.py:kind_to_section()` |
| `resolve_toolkit_root()` | `_repo_resolution.py:resolve_toolkit_root()` |
| `_yaml_add` / `_yaml_remove` / `_yaml_snapshot` (shell helpers calling Python) | `commands/_yaml_edit.py` (called as a function, no subprocess) |
| Cell status / symlink projection | `commands/_list_json.py:_cell_status()` |

The only real new code is **the Click command shells, the action loops** (`_LINK_CREATED` / `_UPDATED` / `_REMOVED` counters), and **the human-readable output formatters**. The latter is what we have to be careful about — bats tests pin the exact strings.

### Output contract (must preserve)

From `docs/agent-toolkit/cli.md` and the bats expectations:

- **Headers and summaries → stderr.** Data (created/removed paths) → stdout.
- `AGENT_TOOLKIT_QUIET=1` (env) and `--quiet`/`-q` (flag) suppress headers/summaries; data still goes to stdout.
- Diff is `link --dry-run` with the header word `Previewing` instead of `Linking`. Output otherwise identical.
- Counters in the summary line use the same wording: `created`, `updated`, `removed`, `unchanged`, `would-link`, `would-unlink`.

These are pinned by bats. The pytest port must assert on the same strings to keep the contract documented.

### TUI runner rewire

`src/agent_toolkit_tui/runner.py` currently shells out via `subprocess.run([cli_path, "list", "--format=json", …])` and `subprocess.run([cli_path, "link"|"unlink", scope, harness, "--plan", "-", …])`. After the port:

- The Python entry point handles `link`/`unlink`/`list` directly. The runner can either continue to shell out (`agent-toolkit list --format=json`, `agent-toolkit link --plan -`) — now resolving to the Python CLI installed by `uv tool install` — or import the handlers and call them in-process.
- **Decision: keep the subprocess boundary.** It preserves a clean process isolation between the TUI and the CLI, lets the TUI exit without leaking CLI state, and matches the way bats tests already drive the surface. The `cli_path` discovery in `runner.py` changes from "find `bin/agent-toolkit`" to "find the installed `agent-toolkit` script" (likely just `shutil.which("agent-toolkit")`, with a worktree fallback for development). The functional change is a few lines.

### Repo deletions

In the same PR, once pytest covers the surface:

- `bin/agent-toolkit`, `bin/lib/*.sh`
- `tests/bats/` (the entire directory)
- `tests/test_target_dir_parity.py` (no more cross-language drift to enforce)
- `lefthook.yml` — drop the `bats` command
- `.github/workflows/test.yml` — drop the `bats` job
- `AGENTS.md` — strike the "bash side / zero-dep" language; describe a single Python CLI
- `docs/agent-toolkit/cli.md` — refresh wording where it implies bash-vs-Python; keep the user-facing flag table unchanged
- `pyproject.toml` — confirm `[project.scripts]` exposes `agent-toolkit` correctly (it already does for the Python commands, and that's now the only entry point)

### Tests-first contract

The bats suite (`tests/bats/`, ~1500 lines) is the behavioural spec. Migration shape:

1. For each `tests/bats/test_<cmd>.bats`, write a corresponding `tests/test_cli_<cmd>.py` that asserts the same behaviour against the new Python implementation. Use `click.testing.CliRunner` for in-process invocation, or `subprocess.run` against the installed entry point where the test depends on stderr/stdout split fidelity.
2. **Keep bats and pytest running side-by-side until pytest reaches parity coverage.** This means: while porting, the bash CLI keeps working too — the Python commands sit alongside until parity is proven, then bash deletes.
3. Once each bash subcommand has a green pytest equivalent, delete its `.bats` file. The final commit of this PR deletes `bin/`, the bats directory, and the parity test together.

The non-link/unlink/list/diff bats files (commons, conventions, help, toolkit-resolution, TUI e2e, UI chrome) — **inventory them during the port**: most are testing `bin/agent-toolkit` behaviour that goes away with the dispatcher, so they can be deleted. Anything that tests cross-cutting behaviour (e.g. toolkit-root resolution) gets its semantic ported into the existing pytest equivalent (`test_repo_resolution.py` etc.) if not already covered.

## Risks

- **Output-string drift.** The bats tests pin specific human-readable lines. Highest-risk regression — a misplaced apostrophe or a `Linking` vs `Linked` mismatch breaks user shell scripts. Mitigation: pytest tests assert on the same strings; we treat the bats file's literal `assert_output --partial '…'` calls as the canonical spec.
- **TUI breakage.** Worktree-mode TUI development relies on `runner.py`'s ability to find the CLI. Mitigation: keep a `shutil.which("agent-toolkit")` resolution with a clear fallback path (and matching error message) in `runner.py`; cover with a `tests/test_tui/test_runner.py` regression test.
- **Pre-existing bats coverage gaps.** If bats is missing a case (e.g. unusual flag combo), the port will inherit the gap. Mitigation: out-of-scope for this PR; document anything noticed during the port as a follow-up.
- **PR size.** This is a large but cohesive change (one PR was the explicit ask). Mitigation: structure commits as `port-link → port-unlink → port-list → port-diff → tui-rewire → bats-retire → docs` so a reviewer can read it sequentially.

## Done when

- `agent-toolkit link user claude --all` works after `uv tool install --from git+… agent-toolkit-cli` from a clean Python environment.
- The TUI's apply-button (write-side) works post-install — toggling a row writes a symlink.
- `bin/`, `tests/bats/`, `tests/test_target_dir_parity.py` deleted.
- `pytest -q` is green and covers everything bats covered.
- `lefthook.yml` and `.github/workflows/test.yml` no longer reference bats.
- `docs/agent-toolkit/cli.md` and `AGENTS.md` reflect the single-language CLI.
- Tag `v0.2.0` (minor — user-visible behaviour preserved, implementation now mono-language).

## Out of scope

- Behavioural deltas in `link`/`unlink`/`list`/`diff`. Anything noticed during the port that isn't a regression goes into a follow-up issue.
- Schema or spec changes.
- Cross-platform fixes beyond what falls out for free.
- Renaming subcommands.

## Related

- Issue: https://github.com/ajanderson1/agent-toolkit-cli/issues/1
- Assets-repo PR #5 (cut-over): https://github.com/ajanderson1/agent-toolkit/pull/5
- Cut-over spec §11: https://github.com/ajanderson1/agent-toolkit/blob/main/docs/superpowers/specs/2026-05-03-agent-toolkit-cli-tui-split-design.md
