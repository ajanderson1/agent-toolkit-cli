# Default `skill install --agents` to `standard` (and `uninstall` to `all`)

**Issue:** #393
**Tier:** standard (changes the default behaviour of a published CLI interface; single-file, backward-compatible, no new schema/asset-type/convention)
**Unblocks:** #369 (bundle manifest — its uniform per-kind dispatch needs `skill install` to have a default agent target)
**Date:** 2026-06-12

## Problem statement

`skill install <slug>` requires an explicit `--agents` target with **no default** —
declared `@click.option("--agents", "agents_str", required=True, ...)`
(`src/agent_toolkit_cli/commands/skill/__init__.py:507`). `skill uninstall` is the
same (`:611`). Every sibling asset kind **defaults** its projection target:

| Kind | Install flags | Target default |
|---|---|---|
| `agent install` | `-g/-p [--harnesses …]` | harnesses default (covered-aware) |
| `pi-extension install` | `-g/-p` | scope only |
| `instructions install` | `--scope --harness …` | all symlink-verdict harnesses |
| **`skill install`** | `--agents <REQUIRED> --scope/-p` | **none — required** |

Skill is the lone kind whose install demands an explicit target. The `'standard'`
token already exists and is fully handled by `_resolve_agents` (`:200`), projecting
to the standard-bundle symlink `~/.agents/skills/<slug>`.

**Why it matters:** the asymmetry blocks any *programmatic* "install this skill"
caller — there is no sane default `--agents` to supply. Surfaced building the
bundle manifest (#369), whose uniform per-kind dispatch cannot install a skill
member; three independent critical reviewers flagged it as a v1 blocker. A future
`bundle init`, a config-file installer, or TUI bulk actions would hit the same wall.

## Acceptance criteria

1. `skill install <slug>` with **no** `--agents` flag succeeds and projects to the
   **standard** bundle (the `standard` token path: `~/.agents/skills/<slug>` at
   global scope, `<project>/.agents/skills/<slug>` at project scope).
2. `skill uninstall <slug>` with **no** `--agents` flag succeeds and removes the
   **maximal** set (the `all` token: every agent detected as installed at that
   scope, plus the standard-bundle symlink).
3. An explicit `--agents <value>` is honoured **unchanged** on both `install` and
   `uninstall` — the value still flows through `_resolve_agents` exactly as today.
   Only the *omitted* case changes behaviour (from a `UsageError` to the default).
4. `skill install --help` and `skill uninstall --help` show the `--agents` option
   as optional with its default, no longer as `[required]`.
5. The change is confined to the two `@click.option("--agents", ...)` declarations
   in `commands/skill/__init__.py`: drop `required=True`, add `default="standard"`
   (install) / `default="all"` (uninstall). No change to `_resolve_agents`, the
   `InstallPlan` / `engine_apply` path, the lock format, or any other module.
6. Both behaviours hold at **global** and **project** scope.

## The deliberate install/uninstall asymmetry

`install` defaults **minimal** (`standard`) and `uninstall` defaults **maximal**
(`all`). This mirrors the existing `agent uninstall` precedent
(`commands/agent/uninstall_cmd.py:_resolve_harnesses_for_uninstall`), whose own
code comment states the rationale: a default uninstall must clean up *everything*
— including projections an earlier or narrower install wrote — so a bare "undo"
never leaves orphaned symlinks behind. Mechanically, for skill: `--agents standard`
removes only the standard-bundle symlink, while `--agents all` removes every
per-agent symlink; defaulting uninstall to `all` ensures `skill uninstall <slug>`
with no flag removes a skill *everywhere* it was projected, not just from the
standard bundle.

A short comment will be added on the skill `uninstall_cmd` `--agents` default
pointing at the agent-uninstall rationale, so the asymmetry reads as deliberate
rather than as an inconsistency.

## Architecture

A two-line behavioural change in one file. No new units, no data-flow change.

- **Touched:** `src/agent_toolkit_cli/commands/skill/__init__.py` — the `--agents`
  option declaration on `install_cmd` (~:507) and `uninstall_cmd` (~:611).
- **Untouched (load-bearing):** `_resolve_agents` already accepts `"standard"` and
  `"all"`; `install_cmd`/`uninstall_cmd` already guard `if not target_agents:
  nothing to do`; the `InstallPlan` → `engine_apply` projection path is unchanged.

### Error handling

No new error paths. `_resolve_agents` already raises `UsageError` for unknown
tokens; that behaviour is unchanged for explicit values. The previously-required
flag's `UsageError("Missing option '--agents'")` simply no longer fires — the
default value is supplied instead.

## Backward compatibility

Fully backward-compatible. The only behavioural change is the *omitted-`--agents`*
case: previously a hard `UsageError`, now the documented default. No existing
invocation that passed `--agents` changes behaviour. No deprecation, no migration.

## Test surface

- `skill install <slug>` (no `--agents`, global) → standard-bundle symlink created.
- `skill install <slug>` (no `--agents`, `-p`) → project standard symlink created.
- `skill uninstall <slug>` (no `--agents`, global) → all symlinks for the slug
  removed (seed an install to >1 agent, then bare-uninstall, assert all gone).
- `skill uninstall <slug>` (no `--agents`, `-p`) → project symlinks removed.
- Regression: explicit `--agents claude-code` on install still projects only to
  claude-code; explicit `--agents all` on uninstall unchanged.
- `skill install --help` / `skill uninstall --help` no longer mark `--agents`
  required and show the default.

## Skills / tools required

- `superpowers:test-driven-development` (red-green per AC).
- Existing skill-install test fixtures (`git_sandbox`, monkeypatched HOME,
  `CliRunner`) — same pattern as `tests/test_cli/` skill tests.

## Trust-level recommendation (advisory)

**L3 (conditional).** Tiny, well-scoped, backward-compatible default change with a
clear codebase precedent (agent uninstall). Any divergence — e.g. touching
`_resolve_agents` or the engine, or a different uninstall default — should raise.

## Out of scope

- The `-g` / `--scope global` flag alias for skill install/uninstall (cross-kind
  flag parity) — **split to a separate follow-up issue**. Orthogonal nicety, not
  a blocker for #369.
- Any change to `_resolve_agents`, the install engine, the lock format, or the
  sibling kinds' install/uninstall verbs.
- The bundle manifest itself (#369) — this issue only removes its skill-member
  blocker.

## Links

- Issue #393.
- Unblocks #369 (bundle manifest).
- Precedent: `commands/agent/uninstall_cmd.py` maximal-uninstall default.
- `_resolve_agents` token handling: `commands/skill/__init__.py:200`.
