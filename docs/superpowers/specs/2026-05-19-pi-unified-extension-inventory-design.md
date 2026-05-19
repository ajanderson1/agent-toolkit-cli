# Spec — Pi: unified extension inventory + load/unload across both channels

**Issue:** [#103](https://github.com/ajanderson1/agent-toolkit-cli/issues/103)
**Author:** agent (flow `--auto`, full-scope by user choice)
**Date:** 2026-05-19
**Status:** Draft for approval

> **Scope override.** Issue #103 was sliced into five PRs (PR 1 inventory read → PR 5 doctor advisories). The operator chose **full scope in one PR** for this flow run. This spec therefore covers all five slices; the plan will keep them as internal commit boundaries so the diff remains navigable.

## 1. Problem

Pi (`@earendil-works/pi-coding-agent`) has **two parallel extension distribution channels**, both feeding the same runtime `resolve()` pipeline:

| Channel | Install verb | Settings | Lands at |
|---|---|---|---|
| Auto-discovery dirs (toolkit's current model) | (symlink in place) | none — directory IS the registry | `~/.pi/agent/extensions/<slug>/` |
| Pi packages | `pi install npm:<spec>` etc. | `~/.pi/agent/settings.json` `packages[]` | `~/.pi/agent/npm/node_modules/<pkg>/` |

The toolkit allowlist (`_allowlist.SECTIONS`) only tracks the first channel via `pi_extensions:`. An operator who wants to audit what Pi will actually load must inspect:

1. `~/.pi/agent/extensions/` and `~/.pi/project/extensions/` (auto-discovery dirs)
2. `~/.pi/agent/settings.json` `packages[]` (declared package installs)
3. `~/.pi/agent/npm/node_modules/` (actually-resolved package installs)
4. The toolkit allowlist (intent, separate from runtime)

No single command answers "what will Pi load right now?" The TUI cannot offer toggle-to-load because it has no unified row model to render.

## 2. Goal

One command, `agent-toolkit-cli pi inventory`, returns **one record per extension Pi could load**, regardless of channel of origin. Four sibling verbs (`load`, `unload`, `sync`) let the operator change loaded state without leaving the toolkit. The TUI gains a Pi tab that consumes the same inventory and routes its toggles through the verbs.

**Non-goal:** re-implementing `pi install`. Pi owns npm/git resolution, lockfiles, and scope merging. The toolkit owns *intent* (allowlist) and *view* (inventory).

## 3. Acceptance criteria

From the issue, verbatim:

1. After `pi install npm:pi-subagents` in a fresh shell, `agent-toolkit-cli pi inventory` shows it as `origin=third-party` / `user_loaded=true` / `toolkit_intent=none`.
2. After `agent-toolkit-cli pi load pi-subagents` from the same state, the allowlist gains `pi_packages: [npm:pi-subagents]`, `toolkit_intent` flips to `user`. **No second `pi install` runs** (idempotent).
3. After `agent-toolkit-cli pi unload pi-subagents`, `pi remove npm:pi-subagents` runs, `settings.json` no longer contains the entry, `~/.pi/agent/npm/node_modules/pi-subagents/` is gone, allowlist entry removed.
4. `agent-toolkit-cli pi sync` is a no-op (exit 0, no writes) immediately after any successful `load`/`unload`.
5. TUI Pi tab renders exactly what `pi inventory --format json` describes; toggles route through the verbs.

## 4. Design

### 4.1 Allowlist schema delta (additive — no version bump)

Add one new section. No `_KIND_TO_SECTION` entry (packages aren't schema-validated assets).

```yaml
pi_extensions: [status-bar]      # first-party — toolkit-vendored, today's model
pi_packages:                      # NEW — third-party install bookkeeping
  - npm:pi-subagents
  - npm:pi-mcp-adapter
  - git:github.com/user/repo@v1
```

Touched module: `_allowlist.py` — extend `SECTIONS` tuple by one element.

### 4.2 Inventory record shape

```json
{
  "slug": "pi-subagents",
  "origin": "first-party" | "third-party",
  "source": "npm:pi-subagents" | "git:..." | "extension:<slug>" | "local:<path>",
  "user_loaded": true,
  "project_loaded": false,
  "user_installed_at": "/Users/.../.pi/agent/npm/node_modules/pi-subagents",
  "project_installed_at": null,
  "toolkit_intent": "user" | "project" | "both" | "none"
}
```

`origin`:
- `first-party` — slug present in `pi_extensions:` (toolkit-vendored asset, lives as a symlink under `~/.pi/agent/extensions/<slug>/`).
- `third-party` — slug arrived via Pi's package manager. Determined by presence in `settings.json` `packages[]` or in `node_modules/`.

If a slug appears in both channels (collision), `first-party` wins for the `origin` field and the doctor advisory (PR 5 / commit) surfaces a warning.

### 4.3 "Loaded?" computation

A slug is `user_loaded=true` iff **any** of:

- An auto-discovery directory exists at `~/.pi/agent/extensions/<slug>/`.
- A package matching the slug is listed in `~/.pi/agent/settings.json` `packages[]` **and** resolves to a real directory under `~/.pi/agent/npm/node_modules/`.

Symmetric rule for `project_loaded` using `~/.pi/project/...` paths (resolved per `--project`).

The slug is derived per channel:
- Auto-discovery: directory name.
- npm: package name with optional `pi-` prefix stripped for display (kept verbatim for `source`).
- git: last path segment of the URL, suffix trimmed, ref stripped.

### 4.4 CLI surface

| Command | Purpose | Read/Write |
|---|---|---|
| `agent-toolkit-cli pi inventory [--scope user\|project\|both] [--format json\|text]` | Emit one record per extension Pi could load. | Read |
| `agent-toolkit-cli pi load <slug> [--scope user\|project]` | Make loaded. Dispatches to symlink (first-party) or `pi install` (third-party). | Write |
| `agent-toolkit-cli pi unload <slug> [--scope user\|project]` | Make not-loaded. Dispatches to symlink-remove or `pi remove`. | Write |
| `agent-toolkit-cli pi sync [--scope user\|project\|both]` | Reconcile allowlist intent → Pi's actual state. Idempotent. | Write |

All four obey the standard two-flag contract (`--toolkit-repo`, `--project`).

`--scope both` is the default for `inventory` and `sync`; `load`/`unload` require explicit `--scope` to avoid ambiguity.

### 4.5 TUI Pi tab

A new tab/screen consuming `pi inventory --format json`:

| Column | Source |
|---|---|
| Slug | record.slug |
| Origin | record.origin (badge: 1P / 3P) |
| Source | record.source (truncated) |
| Loaded (user) | record.user_loaded ✓ / ✗ |
| Loaded (project) | record.project_loaded ✓ / ✗ |
| Intent | record.toolkit_intent |

Toggle key bindings:
- `u` → `pi load --scope user <slug>` (or `unload` if already loaded under user)
- `p` → `pi load --scope project <slug>` (or `unload` if already loaded under project)

Refresh after each toggle by re-invoking `pi inventory`.

### 4.6 Doctor advisories

`agent-toolkit-cli doctor` learns three new advisories (read-only):

1. **Hand-authored extension** — auto-discovery dir present at `~/.pi/agent/extensions/<slug>/` that is **not** a symlink (likely operator-authored content the toolkit didn't put there).
2. **Drift** — allowlist `pi_packages:` lists an entry that has no matching settings.json entry **or** no resolved `node_modules/` dir.
3. **Slug collision** — same slug visible in both `pi_extensions:` and `pi_packages:`.

Each advisory states the slug, the channel(s) involved, and a one-line remediation.

## 5. Non-goals

- Querying registries (`npm view`, `pi.dev/packages`, GitHub). Inventory only describes installed-or-claimed state.
- Re-implementing `pi install` / `pi remove`. The toolkit shells out.
- Schema-validating third-party packages. They're declared, not validated.
- v1alpha2 → v1alpha3 schema bump. The change is purely additive.

## 6. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Pi pins move (`@earendil-works/pi-coding-agent@x.y.z` paths shift) | CI snapshot test against a known-good Pi version; path-resolution mirror is a single module that's easy to update. |
| Race: operator runs `pi install` in another terminal while inventory is reading | Each read is one snapshot; sync runs idempotently. No global lock. |
| Slug collisions across channels | First-party wins; doctor advisory surfaces conflict. |
| `pi` CLI not on PATH | `load`/`unload` for third-party fail loudly with an actionable message. `inventory` continues to work (it doesn't invoke `pi`). |
| Folding `extensions[]` settings-array entries into `pi_packages` | Defer — current spec treats `extensions[]` as out of scope. If Pi changes shape, add a `local:` source entry later. |

## 7. Internal commit slicing (single PR, five logical commits)

Even though all five slices ship in one PR per operator choice, the plan will keep them as separate commits for review navigability:

| Commit | Scope |
|---|---|
| 1 — inventory read | `pi inventory` subcommand + path-resolution module + record shape. No schema change. |
| 2 — schema + sync | `pi_packages:` added to `SECTIONS`; `pi sync` subcommand. |
| 3 — load/unload | `pi load` / `pi unload` verbs (shell to `pi install` / `pi remove`). |
| 4 — TUI Pi tab | New tab consuming `pi inventory --format json`. |
| 5 — doctor advisories | Three new advisory checks. |

## 8. Open questions (resolved on draft)

1. `pi.dev/packages` is npm with styling — confirmed, no registry-query work.
2. `extensions[]` array in settings.json — **deferred** (see Risks).
3. First-party / third-party slug collision — **first-party wins, doctor warns** (see §4.2).
4. Pi version pinning — CI snapshot test against `@earendil-works/pi-coding-agent@0.75.3`.
5. Race with manual `pi install` — handled by re-reading inventory on demand.

## 9. References

- Issue: [#103](https://github.com/ajanderson1/agent-toolkit-cli/issues/103)
- Brainstorm doc (content repo): `docs/brainstorms/2026-05-19-pi-unified-extension-inventory-requirements.md`
- Pi package manager source: `@earendil-works/pi-coding-agent@0.75.3` `dist/core/package-manager.js:654-687`
- Existing allowlist: `src/agent_toolkit_cli/_allowlist.py`
- Two-flag contract: `AGENTS.md` § Two-flag contract
