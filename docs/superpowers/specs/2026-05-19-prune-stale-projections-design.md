# Spec — Prune stale projections on reconcile after hand-edit (#120)

## Problem

After hand-removing an asset from `.agent-toolkit.yaml` and re-running
`agent-toolkit-cli link user <harness>` (no selector — reconcile mode),
the previously-projected artefact stays on disk.

Affected cells:

- `agent × claude`, `command × claude` — symlink-kinds.
- `mcp × claude`, `mcp × codex`, `mcp × opencode` — config-file kinds.

Source: `docs/audit/2026-05-19-toolkit-audit.md` rollup #2 and
`audit/demos/mcp-codex.sh` (robustness 2/3).

## Root cause

The CLI computes ownership as `previously_allowed ∪ desired_names`:

- For MCP/config-file kinds, the **reconcile path** (`_do_bare` in
  `commands/link.py`) calls `project_from_file()` **without** a
  `previous_allowed` snapshot. `project_from_file` then falls back to
  `previously_allowed = current_allowlist`. After a hand-edit that
  removed the asset, the current allowlist no longer contains it, so
  ownership is empty and the on-disk stanza is treated as
  hand-rolled → preserved.

- For symlink-kinds on claude (`agent`, `command`), the projection
  loop's "asset still in toolkit but not in allowlist" branch computes
  `slot_path_plain = target_dir / asset.slug` and tries to prune that
  path. But the actual slot filename includes a harness extension
  (`{slug}.md` for claude agent/command), so the call misses. The
  follow-up orphan sweep then `continue`s on this slot because
  `bare_name == expected_name` — its logic only prunes legacy-shaped
  slots, not orphans whose slug is unallowed.

(Symlink kinds on codex / opencode / pi are immune because their
mechanisms rebuild from `_USER_TARGETS` or have other guards that
recognise the orphan.)

## Goals

1. Reconcile mode (`link user <harness>` with no selector) prunes
   stale projections produced by a previous link, regardless of
   whether the user removed the slug from `.agent-toolkit.yaml` by
   hand or via `unlink`.
2. The fix is the same shape for both surfaces (symlink-kinds and
   config-file kinds): the projection step learns ownership from disk
   rather than relying solely on the pre-mutation allowlist snapshot.
3. No regression on existing tests.

## Non-goals

- Re-implementing the per-asset `unlink` path (issue #119).
- Fixing doctor's replaced-symlink blind spot (issue #121).
- Changing the wire shape of any adapter API.

## Approach

### Config-file kinds (MCP)

In `_link_lib.project_from_file()`, when `previous_allowed is None`
(the reconcile-from-disk case), compute the MCP `prev_mcps` as the
union of:

- `mcp_allowed_slugs` (current allowlist), **and**
- `adapter.list_installed(scope, project_root)` (on-disk state).

The on-disk state is the authoritative record of what we previously
projected. Taking the union with the current allowlist preserves the
existing behaviour for callers that pass `previous_allowed=None` and
have only added entries since the last run.

Apply the same fix to the hook branch (uses the same dispatch shape).

### Symlink-kinds (claude agent/command)

In the projection loop's "asset is in toolkit but not in allowlist"
branch (lines 607–617 of `_link_lib.py`):

- Replace the `slot_path_plain = target_dir / asset.slug` fallback
  with `slot_path = target_dir / _slot_filename(asset.slug, kind,
  harness)`. This is the canonical slot path; `_prune_if_into_repo`
  then sees the symlink, confirms it points into the toolkit, and
  prunes it.

This is also the right fix for any future harness whose slot filename
differs from the bare slug — the helper already exists.

### Order of operations

The orphan sweep that runs after the loop (lines 618–647) is
intentionally narrow (legacy-bare-slug cleanup). Leave it alone — the
per-asset prune branch is the correct place for the
slug-not-in-allowlist case because the loop already enumerates every
asset in the repo.

## Test plan

1. `tests/test_cli_link.py` — new test
   `test_link_bare_prunes_after_handedit_yaml`:
   - Seed an `agent` on claude.
   - Link it user-scope.
   - Hand-edit the allowlist file to remove the slug.
   - Re-run `link user claude` (no selector).
   - Assert the slot symlink is gone.
2. Same test shape for `command:demo-command` on claude.
3. `tests/test_cli_link.py` — new test for MCP:
   - Seed an `mcp` on codex.
   - Link user-scope.
   - Hand-edit allowlist to drop the slug.
   - Re-run reconcile.
   - Assert the `[mcp_servers.<slug>]` stanza is gone from
     `~/.codex/config.toml`.
4. Existing tests stay green.

## Acceptance

- All three new tests pass.
- `uv run ruff check .` clean.
- `uv run pytest -q` clean.
- The audit demo `mcp-codex.sh` rollup #2 case can be re-asserted
  manually (out of scope for CI gate).
