# Doctor: audit allow-list health and cross-toolkit symlink drift

**Issue:** [#10](https://github.com/ajanderson1/agent-toolkit-cli/issues/10)
**Date:** 2026-05-04

## Problem

Today the existing `symlinks` doctor group covers most symlink integrity (dangling targets, stale links pointing into the toolkit repo for assets that don't declare the harness). Two real-world drift modes are still uncovered:

1. **Allow-list rot.** An entry in `~/.agent-toolkit.yaml` (or `<project>/.agent-toolkit.yaml`) names an asset slug that no longer exists in the toolkit repo. The user's allowlist is stale; nothing flags it.
2. **Cross-toolkit symlink drift.** A symlink under `~/.{harness}/...` points into a *different* toolkit repo than the one the CLI is currently configured for. Common after `git mv`, repo relocation, or running CLI with `--toolkit-repo` against a clone that lives elsewhere.

The existing `symlinks` group catches "target missing" but treats "target points outside the configured toolkit repo" as an unrelated symlink and skips it. Issue #10 asks for explicit detection of both.

## Decision

Add a new doctor group: `allowlist-audit`. Wire into `commands/doctor.py` alongside the existing seven groups. The group does **two** checks:

1. **Allow-list slug existence.** For each entry in the user and project allow-lists, assert the slug names a real asset in the toolkit repo. Missing → WARN with kind, slug, source-yaml.
2. **Cross-toolkit symlink detection.** Walk all `~/.{harness}/...` symlink dirs across all four harnesses. Any symlink whose target is **inside a toolkit repo** (recognised by an `.agent-toolkit-source` marker in some ancestor) but **not the configured `toolkit_root`** → WARN with the path and the actual target.

The "broken symlink (target missing)" case is **not duplicated** — `symlinks.py` already covers it. This PR's group is strictly the part the existing groups don't cover.

## Affected files

| File | Change |
|---|---|
| `src/agent_toolkit_cli/doctor/allowlist_audit.py` | **Create.** Two-check group: allow-list rot + cross-toolkit symlinks. |
| `src/agent_toolkit_cli/commands/doctor.py` | Import the new group. Add to `_GROUPS` tuple. Add to `_run_global` runners list. |
| `tests/test_doctor_allowlist_audit.py` | **Create.** Test scenarios per the spec acceptance list. |

## Tests

Required scenarios (from issue body):

- **Clean repo (no findings):** allow-list entries all resolve to real assets, all symlinks point into the configured toolkit. → OK.
- **Drifted allow-list:** `~/.agent-toolkit.yaml` lists `skill: phantom` that doesn't exist in the toolkit repo. → WARN, finding mentions `phantom` and the yaml file.
- **Cross-toolkit symlink:** A symlink in `~/.claude/skills/foo` points into `/some/other/toolkit/skills/foo`. → WARN, finding mentions `foo`, the configured toolkit, and the actual target.

Plus one negative-control:
- **Broken symlink (target missing):** Already covered by `symlinks.py`; this group should NOT also report it. (Test: only `symlink-integrity` flags it; `allowlist-audit` returns OK.)

## Non-goals

- Auto-repair (separate `fix` command exists; this is detection only).
- Per-harness settings-schema validation (deliberately deferred per issue).
- Cross-scope conflict detection (e.g. linked in user AND project) — out of scope.
- Refactoring the existing `symlinks.py` group.
- A fancy data model for "what is a toolkit repo" — the heuristic `find an `.agent-toolkit-source` marker in an ancestor` is what the resolver already uses.

## Risk

Tiny. Pure addition. The new group adds one entry to `_GROUPS` and one runner. The two checks share no state with other groups. The cross-toolkit check uses the same `.agent-toolkit-source` marker that `_repo_resolution.py` already uses — no new heuristic.

## Edge cases

- **No `~/.agent-toolkit.yaml`:** allow-list audit silently skips it (parses empty), reports 0 user-allowlist findings.
- **No `<project>/.agent-toolkit.yaml`:** same.
- **Symlink with relative target:** resolve to absolute against parent dir before classifying.
- **Symlink target outside any toolkit repo (e.g. into a random user directory):** ignored — could be intentional (user manually managed). Not our concern.
- **Allow-list contains a slug that exists but doesn't declare the harness it's listed under:** out of scope here (would need section→harness coupling, which doesn't exist in the YAML schema).
