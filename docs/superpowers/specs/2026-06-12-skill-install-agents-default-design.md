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
   **maximal** set — the `standard` bundle symlink **plus** every per-agent
   projection detected as installed at that scope, so a bare uninstall leaves no
   orphans. (See "The maximal-uninstall mechanism" below — this is **not** simply
   `--agents all`, which provably excludes the `standard` token.)
3. An explicit `--agents <value>` is honoured **unchanged** on both `install` and
   `uninstall` — the value still flows through `_resolve_agents` exactly as today.
   Only the *omitted* case changes behaviour (from a `UsageError` to a default).
4. `skill install --help` and `skill uninstall --help` show the `--agents` option
   as optional, no longer as `[required]`.
5. **Install** is a one-line option change: drop `required=True`, add
   `default="standard"` on `install_cmd`'s `--agents` (`commands/skill/__init__.py`
   ~:507). **Uninstall** drops `required=True` and uses a sentinel default
   (`default=None`); when `--agents` is omitted, `uninstall_cmd` computes the
   maximal target itself as `("standard", *detect_installed_agents())` before
   calling `_resolve_agents`/`engine_apply`. **`_resolve_agents`, the `InstallPlan`
   / `engine_apply` path, the lock format, and the other skill verbs are
   untouched** — the union is local to `uninstall_cmd`.
6. Both behaviours hold at **global** and **project** scope (project-scope uninstall
   removes `<project>/.agents/skills/<slug>` via the `standard` token plus the
   project per-agent symlinks).

## The maximal-uninstall mechanism (corrected after critical review)

The naïve "default uninstall to `all`" does **not** work, and critical review
caught it against the code:

- `_resolve_agents("all")` returns `tuple(detect_installed_agents())`, and
  `detect_installed_agents()` enumerates only real catalog agents
  (`[n for n,c in AGENTS.items() if c.detect_installed()]`). The synthetic
  `standard` token has `detect_installed=lambda: False`, so **`all` can never
  include `standard`** — and only the `standard` token removes the
  `~/.agents/skills/<slug>` bundle symlink. A `default="all"` would orphan it.
- `_resolve_agents("standard,all")` would **raise** `UsageError("unknown agent(s):
  all")`: the resolver only treats `"all"` specially when it is the *entire* string
  (`if agents_str == "all"`), not inside a comma list.

This is exactly why the cited precedent, `agent uninstall`
(`commands/agent/uninstall_cmd.py:_resolve_harnesses_for_uninstall`), builds its
maximal set as `("standard", *sorted(detected))` rather than relying on a token.
**Skill mirrors that:** when `--agents` is omitted, `uninstall_cmd` computes
`target_agents = ("standard", *detect_installed_agents())` directly and passes it
to the existing `engine_apply` path. `_resolve_agents` is not changed and not
called for the default path (it is still used for explicit `--agents` values).

`install` stays **minimal** (`standard` — the single safest target, created
directly by the add path, no detection needed) and `uninstall` is **maximal**
(`standard` + all detected). The asymmetry is deliberate: a bare uninstall must
clean up everywhere a skill was ever projected. A code comment on the uninstall
default points at the agent-uninstall precedent so it reads as intentional.

**User-facing consequence (documented, not a bug):** because bare uninstall is
maximal, `skill install foo --agents claude-code` (narrow) followed by a bare
`skill uninstall foo` removes `foo` from **every** detected agent, not only
claude-code. This matches `agent uninstall`'s behaviour and is the correct
"remove it everywhere" default, but it is broader than the typical install — a
user wanting a narrow uninstall passes an explicit `--agents`.

## Why the default belongs in the CLI (not only the #369 caller)

Critical review noted #369 could instead pass an explicit `--agents standard` from
its dispatch, needing no CLI change. The CLI default is chosen deliberately on its
own merits, independent of #369:

- **Human ergonomics.** `skill` is the lone asset kind that forces the user to
  name a target on every install; the sibling kinds all default. `skill install
  <slug>` Just Working removes a real, recurring friction for the primary user.
- **One default, not N hard-codes.** Putting the default in the CLI means every
  programmatic caller (the bundle, a future `bundle init`, config-file installers,
  TUI bulk actions) inherits a sane target without each re-deciding and hard-coding
  `standard`. The convention lives in one place.

#369 is the *trigger* that surfaced the asymmetry, not the sole justification.

## Architecture

- **Install** — a one-line option change on `install_cmd`'s `--agents`
  (`commands/skill/__init__.py` ~:507): `required=True` → `default="standard"`.
- **Uninstall** — `uninstall_cmd`'s `--agents` becomes `default=None`; a small
  block at the top of the command computes `agents_str` / `target_agents` as the
  maximal union when the flag is omitted (`("standard", *detect_installed_agents())`),
  then proceeds through the unchanged `_resolve_agents`(for explicit values) →
  `InstallPlan` → `engine_apply` path. `detect_installed_agents` is already
  imported/available in this module (used by the `all` branch of `_resolve_agents`).
- **Untouched (load-bearing):** `_resolve_agents`, the `InstallPlan` →
  `engine_apply` projection path, the lock format, and the sibling kinds.

### Error handling

No new error paths. `_resolve_agents` still raises `UsageError` for unknown
*explicit* tokens (unchanged). The previously-required flag's `UsageError("Missing
option '--agents'")` no longer fires — the default (install) or computed union
(uninstall) is supplied instead.

## Backward compatibility

Backward-compatible for every invocation that passed `--agents` — those are
unaffected. The one behavioural change is the *omitted-`--agents`* case: previously
a hard `UsageError`, now a default projection (install) / maximal uninstall. This
inverts a **deliberately-tested** contract — `test_install_agents_required` and
`test_uninstall_agents_required` currently assert the bare invocation errors; those
tests are intentionally rewritten to assert the new default behaviour (the proof
the error was deliberate, not incidental). No deprecation or migration; the risk a
caller depended on the error-as-signal is negligible for this single-power-user
tool, but the change is named here rather than claimed as a pure no-op.

## Test surface

- `skill install <slug>` (no `--agents`, global) → standard-bundle symlink created.
- `skill install <slug>` (no `--agents`, `-p`) → project standard symlink created.
- `skill uninstall <slug>` (no `--agents`, global) → install to the standard bundle
  **and** a real per-agent (e.g. claude-code), bare-uninstall, assert **both** gone
  (proves the union default removes the standard bundle, which `all` alone does not).
- `skill uninstall <slug>` (no `--agents`, `-p`) → install to project standard +
  a project per-agent symlink, bare-uninstall, assert both project projections
  removed and the external canonical preserved (project-scope coverage — a distinct
  code path from global).
- Regression: explicit `--agents claude-code` on install still projects only to
  claude-code; explicit `--agents standard` / `--agents all` unchanged on both verbs.
- `skill install --help` / `skill uninstall --help` no longer mark `--agents`
  `[required]`.

## Skills / tools required

- `superpowers:test-driven-development` (red-green per AC).
- Existing skill-install test fixtures (`git_sandbox`, monkeypatched HOME,
  `CliRunner`) — same pattern as `tests/test_cli/` skill tests.

## Trust-level recommendation (advisory)

**L3 (conditional).** Well-scoped, backward-compatible default change with a clear
codebase precedent (`agent uninstall`'s maximal union). Install is a one-line
option flip; uninstall adds a small maximal-union block in `uninstall_cmd`. Any
divergence — touching `_resolve_agents` or the engine, defaulting uninstall to bare
`all` (which orphans the standard bundle — see the maximal-uninstall mechanism), or
changing the lock format — should raise.

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
