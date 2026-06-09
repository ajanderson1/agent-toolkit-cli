# Split `ajanderson1/skills` into category repos — design

- **Issue:** [#341](https://github.com/ajanderson1/agent-toolkit-cli/issues/341)
- **Date:** 2026-06-10
- **Tier:** deep (new top-level repos ×8; breaking change to every first-party skill's published `source`; release machinery ×8; branch-protection/secrets domain)
- **Status:** design approved 2026-06-10

## Problem

`ajanderson1/skills` is a flat monorepo holding **32 first-party skills** at its root
(`<repo>/<slug>/SKILL.md`). It has grown unwieldy: one PR stream, one release line,
and one branch-protection surface span everything from `journal` to `apk-deep-audit`.

AJ wants **better-defined repos** and **granular per-category PR / release control**.
The fix is to split the single monorepo into **8 independent GitHub repos**, one per
skill category, each a small flat monorepo of its own.

**This must not strand or break any installed skill.** Every registered skill must keep
resolving, applying, pushing, and doctoring after the migration — from its new repo.

### Blast radius (confirmed)

Consumers = **this machine, AJ only**. No other machines, no external consumers. So no
deprecation/redirect strategy and no multi-machine portability requirement: the migration
is "re-register locally + archive the old repo".

**Scope is wider than global, though.** First-party skills are registered in the **global
lock plus ~12 project locks** (scanned `~/GitHub/**/skills-lock.json`, 2026-06-10):

| lock | first-party entries |
|---|---|
| `~/.agent-toolkit/skills-lock.json` (global) | (library + global installs) |
| `~/GitHub/projects/whatsapp_sync` | 8 |
| `~/GitHub/projects/agent-toolkit-cli` | 6 |
| `~/GitHub/contexts/servers` | 3 |
| `~/GitHub/projects/ryanair_fares` | 3 |
| `~/GitHub/projects/Scottish_Property_Analysis` | 3 |
| `~/GitHub/POC/claude-dispatches-pi-chatterboxes`, `~/GitHub/APK/third_party_apks` (+ `BankID`, `Swish`), `~/GitHub/projects/whatsapp_chat_autoexport`, `~/GitHub/projects/cornelius_explore`, `~/GitHub/agent-toolkit/conventions` | 1 each |

The migration script MUST re-discover this set at run time (`find ~/GitHub -name
skills-lock.json` + filter `source == ajanderson1/skills`) rather than hard-code it — the
list drifts. Re-register each affected slug at **each** lock where it appears.

## Architecture

Eight new **private** repos under `ajanderson1/`, each a flat monorepo
(`<repo>/<slug>/SKILL.md`):

| repo | skills (count) |
|---|---|
| `skills-workflow` | aj-flow, aj-issue, aj-run, aj-bootstrap, autonomous-run, project-manager, repo-recon (7) |
| `skills-orchestration` | cmux-pm, claude-orchestrated-pi-agents (2) |
| `skills-authoring` | agent-builder, skill-builder, conventions (3) |
| `skills-journal` | journal, journal-maintenance, learn-for-me, obsidian (4) |
| `skills-finance` | outgoings-admin, pocketsmith, bank-statement-download (3) |
| `skills-infra` | contexts, dev-server, kuma-uptime, domain-manager, mkdocs, pypi, bitwarden (7) |
| `skills-comms` | telegram, whatsapp-backup (2) |
| `skills-android` | android-driver, apk-deep-audit, apk-workbench (3) |

**Totals:** 31 skills migrated · 1 deleted (`telegram-botfather`) · 32 physical dirs accounted for · 0 unplaced.

Placement reasoning for the ambiguous calls:
- `cmux-pm` + `claude-orchestrated-pi-agents` get their own `skills-orchestration` (running *other* agents, distinct from the issue→run pipeline).
- `conventions` → `skills-authoring` (authoring standards, not personal config).
- `bitwarden` → `skills-infra` (secrets/infra tool), **not** comms.
- `bank-statement-download` → `skills-finance` (financial, despite being browser-driven).
- `pypi` → `skills-infra` (release/publishing infrastructure).
- `telegram-botfather` (unregistered stray, real folder with references+scripts) → **deleted**; carried only in the archive.

Each new repo is self-contained, carrying its own copy of the monorepo's repo-level
scaffolding: `LICENSE`, `README.md`, `AGENTS.md`, `lefthook.yml`, `scripts/`,
`version.txt`, and a `release-please-config.json` + `.release-please-manifest.json` +
`.github/workflows/release-please.yml`.

**Git history:** fresh start per repo (initial commit = current skill state). The original
`ajanderson1/skills` (166 commits) is **archived** read-only after verification — history
preserved, nothing resolves from it.

## Key feasibility findings (verified in code)

1. **Ownership is owner-keyed, not repo-keyed.** `skill_ownership.py:12`
   `OWNED_OWNERS = frozenset({"ajanderson1"})`; `is_owned_owner(owner)` lowercases and
   matches the **owner** only. Therefore **every new `ajanderson1/skills-<category>` repo
   is automatically "owned"** — `--owned` is implied, `skill push` targets the new repo,
   and **no CLI code change is required** for the split.

2. **`skillPath` stays single-segment.** Because each new repo is *flat-at-root*
   (`<repo>/<slug>`), the migrated lock entry keeps `skillPath: <slug>` (e.g. `journal`).
   What changes is **`source`** (`ajanderson1/skills` → `ajanderson1/skills-journal`) plus
   the derived `upstreamSha` and `parentUrl`. Nested layout (multi-segment `skillPath`) is
   NOT used here — that was the subfolder design (now superseded).

3. **Lock-entry shape** (per live `journal` entry): `source`, `sourceType`, `ref`,
   `skillPath`, `upstreamSha`, `parentUrl`. There is **no per-entry `owned` field** — owned-ness
   is computed from the owner at command time. So re-registration only needs the new source.

4. **release-please is whole-repo.** The monorepo config is `release-type: simple`, single
   `"."` package, `include-component-in-tag: false`. Each new repo gets a **verbatim copy**
   of this same config (no multi-package refactor). Per-repo = independent version line per
   category — this delivers the "granular release control" goal directly.

## Migration mechanism (per skill)

Move-only is forbidden (it leaves the lock pointing at the dead `source`). Each registered
skill is **re-registered**:

1. **Stand up target repo** — `gh repo create ajanderson1/skills-<category> --private`;
   populate with the skill dir(s) + repo-level scaffolding (§Architecture); push `main`.
2. **Enumerate scopes** — find every lock the skill is registered in (global + any project
   lock) *before* removing. A skill may be library-registered and/or installed at
   global+project independently.
3. **Remove** — `agent-toolkit-cli skill remove <slug> --force` at each scope
   (`--force` required in non-TTY).
4. **Add** — `agent-toolkit-cli skill add ajanderson1/skills-<category>/<slug>` at each
   scope (`--owned` implied via OWNED_OWNERS, but pass it explicitly for clarity/robustness).
5. **Re-project** — re-run install so agent projections are recreated (skills project as
   **symlinks**); `skill doctor` must come back clean for the slug at every scope.

A single **idempotent, dry-runnable** migration script driven by the slug→repo map is the
deterministic path (31 re-registrations in one pass). The old repo stays as a live archive
throughout, so every step is recoverable.

## Error handling / safety

- **Recoverable by construction** — old repo archived (not deleted) until DoD is met.
- **Untouched:** `aj-workflow` lives in its own separate repo and does not move; the ~22
  third-party skills (`mattpocock`, `anthropics`, etc.) are not ours to reorganise.
- **Fail loud** — script aborts (does not silently skip) if a target repo already exists
  with content, if a scope enumeration is ambiguous, or if `skill doctor` is non-clean
  after a re-register.
- **No CLI consumption gap** — flat-at-root resolution is the default, already-tested path;
  no reliance on `migrate-to-monorepo` (which emits flat `skills/<slug>` only).

## Testing strategy

- **Per-repo resolution:** at least one moved skill from a representative repo loads + applies
  in a fresh agent session, resolving from its new `source`.
- **`skill push` round-trip:** `skill push <slug>` for ≥1 moved skill opens a PR against the
  **new** repo (proves owner-keyed ownership + new source resolve correctly).
- **`skill doctor` clean:** zero findings for every moved slug, at global scope and each
  affected project scope.
- **Lock assertions:** each migrated entry shows `source: ajanderson1/skills-<category>`,
  `skillPath: <slug>`, refreshed `upstreamSha`/`parentUrl`.
- **CLI suite green:** existing `tests/test_cli/` (incl. monorepo/nested-monorepo source-parse
  tests) still pass — no regression from any incidental tooling change.
- **release-please:** each new repo's workflow cuts a release as the monorepo did.

## Definition of done

- [ ] 8 repos created (private) + populated + pushed `main`.
- [ ] 31 skills re-registered at **every** scope they were installed; `source` updated.
- [ ] `telegram-botfather` deleted (archive-only).
- [ ] `skill doctor` clean — global + each affected project — zero findings for moved slugs.
- [ ] Lock entries show new `source` + single-segment `skillPath` for all moved skills.
- [ ] ≥1 moved skill loads + applies in a fresh session.
- [ ] `skill push <slug>` round-trips to the new repo for ≥1 moved skill.
- [ ] `aj-workflow` + all third-party skills untouched and still resolving.
- [ ] Each new repo's release-please valid and cuts a release.
- [ ] `ajanderson1/skills` archived (read-only) after the above pass.
- [ ] CLI test suite green; monorepo/nested source-parse tests still pass.

## Non-goals

- **No CLI code change for consumption.** Owner-keyed ownership + flat-at-root resolution
  already cover separate-repos. Fix tooling only if a real gap surfaces mid-migration.
- **Not reorganising third-party skills**, and not moving `aj-workflow`.
- **Not preserving per-skill commit history** in the new repos (fresh start; history lives
  in the archived monorepo).
- **Not building a redirect/deprecation layer** (single-consumer blast radius).

## Superseded design

The original #341 write-up proposed **category subfolders inside the one `ajanderson1/skills`
repo** (`<repo>/<category>/<slug>/SKILL.md`, multi-segment `skillPath`, no new repos). AJ
chose separate-repos-per-category instead (2026-06-10), so that runbook is superseded. It is
preserved in the issue body under a collapsed "Superseded design" note for the record.
