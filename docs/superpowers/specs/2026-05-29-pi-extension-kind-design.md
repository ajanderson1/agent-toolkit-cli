# Design: `pi-extension` asset kind (v3.2.0)

- **Date:** 2026-05-29
- **Status:** Approved (design); pending implementation plan
- **Milestone:** v3.2.0
- **Depends on:** v3.1.0 (the `agent` kind, issue #252) — specifically the
  generalization of `skill_install.py` / `skill_lock.py` / `skill_paths.py`
  onto a `kind` dimension, and whatever lock structure that lands.
- **Supersedes:** the prior-generation Pi extension work (closed issues
  #103 / #106 / #107 / #109) that lived in the older `agent-toolkit` content
  repo and is **not** present in this CLI repo. Lessons carried forward are
  called out inline.

---

## 1. Motivation

Pi extensions are installed today by hand (`pi install npm:@juicesharp/rpiv-i18n`)
or by dropping dirs / symlinks into `~/.pi/agent/extensions/`. There is no
single curated, owned, granularly-toggleable library — and once an extension is
installed, there is no durable local-edit story with an upstream connection.

This is exactly the problem `agent-toolkit` already solved for skills (and is
solving for subagents): treat each installed asset as a first-class **owned git
repo** in a canonical store, drive projection from a **lockfile**, and toggle
install/uninstall per scope through a **TUI grid**.

v3.2.0 folds Pi extensions into that same machinery as a third asset `kind`,
so the operator gets:

- a **curated library** of extensions, owned and version-controlled, that are
  not necessarily installed;
- a **durable upstream connection** for git/local extensions (clone, edit
  locally, commit, `push` back, merge-aware `update`) — identical to skills;
- **granular per-scope install/uninstall** (Pi global + Pi project) from one grid.

`pi-extension` is the only Pi-specific kind. All non-Pi harnesses are ignored
for this kind; the grid collapses to Pi-only columns.

---

## 2. Verified Pi discovery contract (load-bearing)

Read from Pi source at `pi-mono/packages/coding-agent/src/core/` (verify against
the installed `@earendil-works/pi-coding-agent` version at implementation time):

- **Discovery roots** (`resource-loader.ts:787,793`): Pi scans
  - `~/.pi/agent/extensions/` — **global / "user" scope**
  - `<cwd>/.pi/extensions/` — **project scope**
  (`CONFIG_DIR_NAME` = `.pi`). Project-scope dirs confirmed in the wild across
  multiple repos.
- **Symlinks are first-class** (`loader.ts:447,453`): `discoverExtensionsInDir`
  explicitly branches on `entry.isSymbolicLink()` for both files and
  directories. A symlinked directory is resolved exactly like a real directory.
- **Entry-point contract** (`loader.ts:resolveExtensionEntries`): a directory
  loads if it contains
  1. a `package.json` with a `pi.extensions` field (declared paths), **or**
  2. an `index.ts` / `index.js`.
  Loose `*.ts` / `*.js` files directly under `extensions/` also load.
  No recursion beyond one level.
- **`settings.json` has two distinct arrays** (`settings-manager.ts:80`):
  - `packages[]` — registry refs (`npm:<spec>`, `git:<url>`) Pi resolves into
    `~/.pi/agent/npm/node_modules/`.
  - `extensions[]` — explicit list of local extension file/dir paths.
  Both feed the same load pipeline. `setGlobalExtensions` /
  `setProjectExtensions` write the project vs global copies
  (`settings-manager.ts:710,717`).

**Conclusion:** a symlink projected into `extensions/` is loaded identically to a
hand-placed extension. The existing skill projection engine therefore works for
git/local extensions **unchanged**.

---

## 3. The two row behaviours (one coherent rule)

> **The store owns what it can genuinely own.**

| Behaviour | Sources | Storage | Projection | Capabilities |
|---|---|---|---|---|
| **store-owned** | `git:` / `https` / `ssh` / local path | cloned into `~/.agent-toolkit/pi-extensions/<slug>/` as an owned git repo | symlink into `~/.pi/agent/extensions/<slug>` (global) and/or `<proj>/.pi/extensions/<slug>` (project) | full skill parity: edit, commit, `push`, merge-aware `update` |
| **registry-tracked** | `npm:<spec>` | **not stored** | add/remove the entry in `settings.json` `packages[]` (global) | toggle install/uninstall only |

Rationale (carried from prior-gen non-goal): **do not re-implement `pi install`.**
For npm rows we do not even *call* `pi` — toggling just edits `packages[]` and Pi
resolves on next launch, consistent with "toolkit writes the projection, harness
reads it." This is a strictly weaker ownership story than git (no push-back, no
live upstream merge), which is why npm extensions are deliberately *not* vendored
into the store. A `git:` source the operator has forked gets full push-back; a
`git:` source pointing at someone else's repo gets clone + edit + update-merge with
push going to the fork — identical to how skills behave today.

```
SOURCE                         CANONICAL STORE                              PROJECTED INTO PI
git/https/ssh/local ──clone──> ~/.agent-toolkit/pi-extensions/<slug>  ─symlink─> ~/.pi/agent/extensions/<slug>   (global)
                               (owned git repo: edit/commit/push/update) ─symlink─> <proj>/.pi/extensions/<slug>  (project)

npm:<spec>          ───────────(NOT stored)─────────────────────────── ─entry──> settings.json packages[]         (toggle only)
```

---

## 4. Architecture

`pi-extension` is a **third `KindBinding`** on the v3.1.0-generalized machinery.
No new lock design (per decision: inherit whatever v3.1.0 lands — per-kind file
or `kind` discriminator).

### 4.1 New / changed modules

| Module | Change |
|---|---|
| `_paths_core.py` | add `PI_EXTENSION_BINDING` (`kind="pi-extension"`, `canonical_dirname="pi-extensions"`, `library_subdir="pi-extensions"`, `lock_filename` per v3.1.0, `general_harness_name` n/a — Pi-only). |
| `pi_extension_install.py` | new facade over `_install_core`, mirroring `skill_install` / future `agent_install`. Handles the **store-owned** projection (symlink into the two Pi extension dirs). |
| `_pi_settings.py` | **the one genuinely new module.** Read/write `settings.json` `packages[]` (and read `extensions[]` for inventory). Pure config edit; never shells out to `pi`. JSON read-modify-write that preserves unknown keys and formatting as much as practical. |
| `pi_extension` command group | `add` (global-only), `install`, `uninstall`, `remove`, `import`, `list`, `status`, `update`, `push`, `reset`; `doctor` learns the kind. Registered in `cli.py` alongside `skill`. |
| TUI: kind sidebar | `pi-extension` becomes a selectable kind. When active, grid shows Pi-only columns. |
| TUI: grid | Pi-only column set: `EXTENSION | Pi (global) | Pi (project) | State | Source`. npm rows render their two scope cells per Pi's `packages[]` reality (project scope shown as `—` if Pi has no project `packages[]`; confirm at impl time). |

### 4.2 Reused unchanged

Projection engine (`_install_core`), lockfile read/write, git ownership
(`skill_git`, `skill_ownership`), import/library reconstruction (`skill_source`,
monorepo parent handling), doctor reconciliation skeleton. These take the new
`KindBinding` and otherwise behave as for skills.

---

## 5. Inventory model

`list` / `status` surface **every extension Pi could load**, origin as a *column,
not a gate* (the #103 insight, preserved). One row per extension across all
surfaces:

| Origin / state | Where it comes from | Row capability |
|---|---|---|
| store-owned | lockfile + canonical store, symlinked into `extensions/` | full toggle + edit/push/update |
| untracked (loose) | a real dir / loose `.ts` / non-store symlink already in `extensions/` | `import` to adopt into store |
| registry-tracked (npm) | `packages[]` entry in `settings.json` | toggle via `packages[]` |

Example:

```
EXTENSION        Pi(g)  Pi(p)   State      Source
status-bar         ✔      ☐     clean      git:.../status-bar      (store-owned)
supacode           ✔      ☐     untracked  local dir               (importable)
superset-hooks     ✔      ☐     untracked  loose .ts               (importable)
rpiv-i18n          ✔      —     —          npm:@juicesharp/rpiv-i18n (tracked)
```

`State` reuses the skill state vocabulary (`clean` / `dirty` / `missing` /
`copy` / `library`) for store-owned rows; `untracked` is a new state for
loose/non-store extensions Pi will load but the toolkit doesn't own yet.

---

## 6. Verbs

Parallel `pi-extension <verb>` namespace mirroring the six+ skill verbs.

| Verb | Behaviour |
|---|---|
| `add <source>` | **global-only by construction** (same as `skill add`). `git`/`https`/`ssh`/local → clone into store + global lock entry. `npm:<spec>` → record as registry-tracked lock entry (no clone). |
| `install <slug> [-g/-p]` | project the store-owned symlink into the chosen Pi scope; for npm rows, add to `packages[]`. |
| `uninstall <slug> [-g/-p]` | remove the projection / `packages[]` entry; keep the store copy. |
| `remove <slug>` | drop the store copy + lock entry (dirty-guard like skills). |
| `import [--latest]` | adopt pre-existing git/local extensions in `extensions/` into the store (read-only library reconstruction, monorepo parent-symlink); record npm `packages[]` entries as tracked. |
| `list` / `status` | the §5 inventory (read-only). Ship **first** (PR1). |
| `update <slug>` | merge-aware upstream pull for store-owned git rows; no-op for npm. |
| `push <slug>` | push local commits upstream for store-owned rows (fork semantics as skills). |
| `reset <slug>` | discard local edits to the store copy (as skills). |

`doctor` learns the kind: detect stray symlinks in `extensions/`, orphaned
`packages[]` / `extensions[]` entries with missing paths, store-vs-projection
drift.

---

## 7. Sequencing (Approach A, C-sequenced)

Thin-binding architecture (A), landed inventory-first (C) so the discovery model
is proven by a shipped read-only slice before any write path commits.

- **PR1 — read-only inventory.** `PI_EXTENSION_BINDING`, `_pi_settings.py`
  reader, `list` / `status`, TUI kind-sidebar entry + Pi-only read-only grid.
  Proves Pi discovers store-symlinked + loose + `packages[]` extensions exactly
  as modelled. No mutation.
- **PR2 — write path.** `add` / `install` / `uninstall` / `remove` / `import` /
  `update` / `push` / `reset`, TUI toggles, `_pi_settings.py` writer, `doctor`.

(If v3.1.0's generalization is incomplete when PR1 starts, a pre-PR may be needed
to finish factoring `skill_*` onto the `kind` dimension; flag in the plan.)

---

## 8. Error handling

- **Fail loud** (per conventions): `_pi_settings.py` raises on malformed
  `settings.json` rather than silently rewriting; projection refuses to
  overwrite an existing non-toolkit path in `extensions/` (reuse
  `_install_core`'s existing-path guard) and emits the `doctor` hint.
- **No `pi` dependency:** npm toggling never shells out; works with `pi` absent
  from `PATH`.
- **Scope safety:** project-scope writes target `<cwd>/.pi/`; global target
  `~/.pi/agent/`. Never cross them.

---

## 9. Testing

- **Matrix/parity:** assert `pi-extension` is Pi-only — every non-Pi harness is
  excluded for this kind (mirror the subagent matrix-parity test pattern).
- **Discovery fixture:** a fixture `.pi/extensions/` tree (store symlink + loose
  `.ts` + `index.ts` dir + `package.json`-manifest dir) asserting the inventory
  classifies each correctly.
- **`_pi_settings.py`:** round-trip `packages[]` add/remove preserving unknown
  keys; raise on malformed JSON.
- **Projection:** symlink into both scopes, idempotent re-install, dirty-guard on
  `remove`, stray-symlink `doctor` clearance.
- **Lock round-trip:** `import` reconstructs store-owned rows and re-records npm
  rows; lock survives a round-trip under the v3.1.0 lock shape.
- **TUI:** Pilot/snapshot of the Pi-only grid + toggle (PR2).
- Follow `conventions/testing.md` floor + the CI shallow-clone scope-guard
  caveat (skip diff-based guards when the ref is missing).

---

## 10. Non-goals

- Vendoring npm packages into the store (explicitly rejected — no live upstream,
  inherits `node_modules` resolution).
- Re-implementing or shelling out to `pi install` / `pi remove`.
- Any other harness for this kind (Pi-only by definition).
- `command` / `hook` / `plugin` / `mcp` kinds (separate future majors).

---

## 11. Open items for the plan

1. Confirm the installed Pi version's loader matches the `pi-mono` source read
   here (esp. project-scope `packages[]` support — drives whether npm rows show
   a project cell or `—`).
2. Confirm v3.1.0's final lock shape so `PI_EXTENSION_BINDING.lock_filename` /
   discriminator is set correctly.
3. Decide the `extensions[]` (explicit-path) surface: fold into inventory as
   `source = local:<path>` tracked rows, or treat as untracked-importable. Prior
   gen (#109) recommended folding in; revisit under the owned-store model.
