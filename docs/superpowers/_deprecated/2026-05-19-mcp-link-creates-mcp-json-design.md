# 2026-05-19 — Fix: project-scope MCP link silently no-ops when target config absent

Closes #125.

## Symptom

`agent-toolkit-cli --project . link project claude mcp:<slug>` exits 0 without
creating `.mcp.json` or emitting any output when `.mcp.json` doesn't already
exist in the project directory. Same symptom for codex with `.codex/config.toml`.

## Root cause

`ClaudeAdapter.config_target(scope="project", project_root)` returns `None`
when `<project_root>/.mcp.json` is absent (claude.py:36-39). Downstream:

- `ClaudeAdapter.diff()` checks `if target is None: return []` (claude.py:88-90)
  → no `WriteAction` produced → silent no-op.
- Same pattern in `CodexAdapter.config_target` (codex.py:40-43) — returns `None`
  when `.codex/` directory is absent. `CodexAdapter.diff()` short-circuits the
  same way (codex.py:114-116).

The `None` was a misuse of the `Path | None` return type: the type was meant to
indicate "adapter does not support this scope" (genuine impossibility), but is
also being returned for "this scope's target doesn't exist on disk yet" — a
state the create-branch inside `diff()` already knows how to handle
(claude.py:94-106, codex.py:120-148).

## Fix

Make `config_target` return the **intended path** even when the file/dir
doesn't exist. The existing create-branch in each adapter's `diff()` already
handles file creation (it writes the file from scratch when
`not target.is_file()`). For codex, also ensure the parent `.codex/` directory
is created when writing (it's currently created lazily — verify).

This restores symmetry with user-scope behaviour, which has always returned a
path regardless of whether the file existed.

## Scope

In scope:

- `ClaudeAdapter.config_target` (project scope): return `project_root / ".mcp.json"` unconditionally.
- `CodexAdapter.config_target` (project scope): return `project_root / ".codex" / "config.toml"` unconditionally.
- Ensure write paths create parent directories where missing (codex `.codex/`).
- Update tests covering the silent-no-op case for both adapters.

Out of scope:

- Other adapters (gemini, opencode, codex_hook) — separate audit; this fix
  targets the two flagged in #125 and the symmetric codex variant.
- Restructuring the `Path | None` Protocol return type (no genuine "scope
  unsupported" callers exist today). Tracked as future cleanup if it surfaces.

## Verification

- New unit test: `link project claude` against a fresh project dir (no
  `.mcp.json`) creates `.mcp.json` with the expected entry.
- New unit test: same for codex (no `.codex/`).
- Existing tests continue to pass.

## Risk

Low. Behaviour was a silent no-op; any path that depended on "config_target
returns None when file absent in project scope" was already broken from the
user's perspective. The `list_installed` / `entry_drift` methods that check
`target is None or not target.is_file()` continue to short-circuit on the
`not target.is_file()` branch.
