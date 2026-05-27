# v3.0.0 — `instructions` kind (AGENTS.md symlinker) — design spec

**Date:** 2026-05-27
**Status:** Design approved → ready for matrix research (Phase A) then `writing-plans` (Phase B)
**Scope:** Add a third asset kind — `instructions` — that manages per-harness
*pointer symlinks* to a project's own `AGENTS.md`, riding the same
kind-dimension pipeline introduced for `skill` and `agent` in
`spec/v3-agents-refold`.
**Sibling spec:** `docs/superpowers/specs/2026-05-27-v3-agents-refold-design.md`
(on branch `spec/v3-agents-refold`) — the `agent` (subagent) kind. Read its
**Terminology** section first; the same "agent" overloading trap applies here.

---

## Terminology (read first)

- **harness** — one of the ~54 AI coding tools the toolkit projects assets into
  (Claude Code, Cursor, Codex, Gemini CLI, Pi, …). Same meaning as the sibling
  spec.
- **instruction file** — the single root-level prompt-context file a harness
  reads by default for project/global guidance (`AGENTS.md`, `CLAUDE.md`,
  `GEMINI.md`, …). **This is the asset this kind manages.**
- **pointer** — a per-harness symlink (e.g. `CLAUDE.md`) whose target is the
  canonical `AGENTS.md`. Creating pointers is the only action this kind ever
  takes.

This kind is **not** a subagent (the `agent` kind), **not** a skill, **not** an
MCP. The name `instructions` is chosen deliberately over `agents-md` because the
latter re-overloads "agent" — the exact mistake the sibling spec warns against.

---

## Problem

`AGENTS.md` is the canonical project instruction file. A handful of harnesses
read it natively (Codex, OpenCode, Pi); others read only their own fixed-name
file by default (Claude Code → `CLAUDE.md`, Gemini → `GEMINI.md`). Today the
workaround is a **manual** convention (`~/.conventions/conventions/agents-md.md`
§ Harness portability): hand-create `CLAUDE.md` as a symlink to `AGENTS.md` so
one canonical file feeds every harness, recreated per-machine on fresh clone by
a bootstrap step.

That convention is unmanaged: the symlinks are created by hand, drift silently,
aren't tracked anywhere, and don't scale beyond the two or three harnesses we
happen to remember. We want the **central toolkit** to own it — lockfile as the
source of truth, pointers toggled on/off per harness, always pointing at an
`AGENTS.md`.

## Reframing (the core insight)

This is **not a special-case feature**. It is the same job the toolkit already
does — *managing a harness via lockfile-driven symlinks* — with a different
payload. For the `skill` kind the symlinked payload is skill files; for the
`agent` kind it is subagent files; for **`instructions`** it is `AGENTS.md`
itself (via per-harness pointer files). Same machine, different payload.

So `instructions` is simply the **third `kind`** flowing through the
kind-dimension pipeline the sibling spec generalizes (`skill_install.py`,
`skill_lock.py`, `skill_paths.py` taught a `kind` arg; the harness matrix as
contract; the per-kind "general" model; the restored TUI `KindsSidebar`). The
only per-kind specialness is **data, not new subsystems**: this kind has no
upstream repo, a tiny verb set, and a project-default scope.

## Goal

Ship the `instructions` kind alongside `skill` and `agent` in v3.0.0: an
`instructions-file` column re-verified across all ~54 harnesses, a single
`symlink` adapter that creates per-harness pointers to the project's `AGENTS.md`
driven by the lockfile, and the kind wired into the restored TUI `KindsSidebar`
as a third selectable kind.

## Non-goals

- **Authoring `AGENTS.md` content.** This is pure projection — managing pointers
  around an *existing* canonical file. The toolkit never writes, fetches, or
  edits `AGENTS.md`.
- **Mutating any harness config.** The toolkit only ever creates symlink
  pointers to satisfy a harness's *default* instruction-file behaviour. It never
  edits `.gemini/settings.json`, `.aider.conf.yml`, or any other config to
  opt a harness into reading `AGENTS.md`. Harnesses that read `AGENTS.md` only
  via such opt-in are therefore **out of scope** (recorded `gap`).
- **No upstream-asset verbs.** `add`, `import`, `push`, `update`, `reset` assume
  a Git-fetched asset and are meaningless here; they are not exposed for this
  kind.
- **Other kinds.** `command`/`hook`/`plugin`/`mcp`/`pi-extension` stay out of
  scope, same as the sibling spec.

---

## Mechanism model

The new matrix column `instructions-file`. Each harness gets exactly one verdict:

| Verdict | Meaning | Action |
|---|---|---|
| `native` | Reads `AGENTS.md` by default (no pointer needed) | **None** — already satisfied. This set **is** the per-kind "general" column. |
| `symlink` | Reads a fixed own-name file by default (e.g. `CLAUDE.md`, `GEMINI.md`) | Create `<OWN-NAME>.md` symlink → `AGENTS.md` |
| `unsupported (gap)` | Reads only via config opt-in / explicit flag, or via a directory, or support is unshipped/defunct | **None** — a same-name symlink can't satisfy it and we don't touch config |
| `unsupported (by design)` | No root instruction-file concept at all | **None** |
| `unknown — no public evidence found` | Bounded search surfaced no default instruction-file convention | **None** — revisit if the product publishes |

**Only `symlink` is an action.** There is no `translate`, no `config_file`, no
`dual-symlink` for this kind. It is the simplest of the three kinds.

**Verdict-assignment rules the research must hold:**

- **Default behaviour only.** Verdict follows what the harness reads *out of the
  box*. Gemini reads `GEMINI.md` by default (→ `symlink`) even though it *can*
  be pointed at `AGENTS.md` via `context.fileName` — that opt-in is irrelevant
  because we only satisfy defaults.
- **Runtime-load vs seed-only.** Claude Code's `/init` *reads* `AGENTS.md` to
  *seed* `CLAUDE.md` but does **not** load `AGENTS.md` at runtime → `symlink`
  (target `CLAUDE.md`), **not** `native`. Touching the file ≠ loading it.
- **File vs directory.** Cline reads a `.clinerules/` *directory*, not a single
  pointer file → `gap` (a symlink to one file can't satisfy a directory loader;
  native `AGENTS.md` support is proposed but unmerged, issue #5033).
- **Unshipped / defunct.** Record `gap` with the evidence trail; do not wire.

---

## Data model, lockfile, scope

### Canonical source resolution

- **Project scope (default):** the `AGENTS.md` at the project root that
  `scope_and_roots()` resolves. Pointers are siblings: `./CLAUDE.md → ./AGENTS.md`.
- **Global scope:** a global canonical instruction file with
  `~/.claude/CLAUDE.md → <global canonical>`. The exact global canonical path is
  a **plan-level open question** (candidates: `~/.config/agents/AGENTS.md`, or
  `~/.claude/AGENTS.md` as the source itself). Not blocking the design.

**Scope default diverges from skills.** The existing convention is that the six
skill verbs default to *global* outside a project
(`project_agent_toolkit_cli_scope_defaults`). This kind defaults to **project**,
because instruction-file pointers are inherently project-rooted (a `CLAUDE.md`
sits next to a project's `AGENTS.md`). Both scopes are supported; the lock
records scope per entry.

### Precondition

The canonical `AGENTS.md` **must already exist**. If it does not, `install`
refuses with a clear message (`no AGENTS.md at <root> to point to`). The toolkit
manages pointers, never the source content.

### Lockfile

Rides the sibling spec's `kind` discriminator. An `instructions` entry is
deliberately thin — no `repo`/`ref`/`commit` (no upstream):

```toml
# Exact shape follows the sibling spec's lock decision
# (one set of `[[asset]]` entries with kind="instructions"
#  vs. parallel `[[instructions]]` tables). Illustrative:
[[instructions]]
scope = "project"          # project | global
source = "AGENTS.md"        # relative to scope root
harnesses = ["claude-code", "gemini-cli"]   # pointers that are ON
```

The `harnesses` array **is** the on/off switch: presence = pointer exists,
removal = pointer is cleaned up. The lock is the SSOT; `install`/`uninstall`
reconcile the filesystem to match it.

### Per-kind "general" set

Per the sibling spec's per-kind "general" model, each kind has its own
convergence point: `skill` → `.agents/skills/`; `agent` → `~/.claude/agents/`;
**`instructions` → `AGENTS.md` itself.** The "general" column for this kind is
the set of **native readers** (Codex, OpenCode, Pi) — harnesses the canonical
file satisfies with zero projection. "General" here literally means "needs no
per-harness pointer."

### Idempotency & the no-clobber guarantee

This is the primary breaking-change risk, so the rule is strict — **refuse +
report, never clobber:**

- Target absent → create symlink, record in lock.
- Target is already our exact symlink (correct target) → **no-op** (idempotent).
- Target is a real file with content → **refuse + report**, never touched.
- Target is a symlink pointing elsewhere → **refuse + report**, never touched.

Surfaced the same way `doctor` already reports conflicting symlinks
(`project_tui_apply_error_clobber`). No user content is ever destroyed. A
fresh-clone bootstrap that previously hand-made `CLAUDE.md` continues to work;
re-running `install` over an already-correct symlink is a safe no-op.

---

## CLI surface — minimal projection set

No upstream → no `add`/`import`/`push`/`update`/`reset`. The kind rides
whatever CLI shape the sibling spec picks (parallel `instructions` group vs.
`--kind` flag — its open question).

| Verb | Behaviour |
|---|---|
| `install` | Reconcile pointers ON for the resolved scope. Refuses if no `AGENTS.md`; refuses (never clobbers) on conflict; no-op on already-ours. `--harness <name>` scopes to one; default = all `symlink`-verdict harnesses for that scope. |
| `uninstall` | Remove only pointers we own (recorded in the lock). Foreign files/symlinks left untouched. |
| `list` | Per-harness verdict for this kind (`native` / `symlink` / `gap` / `by-design` / `unknown`). |
| `status` | Per harness: pointer present / missing / conflicting, vs the lock. |
| `doctor` | Learns this kind: conflicting pointers, orphaned pointers (lock on but `AGENTS.md` gone), stray pointers we don't own. The matrix tells it which pointer paths are legitimate so it doesn't flag `gap`/`by-design` harnesses. |

---

## TUI

A third row in the restored `KindsSidebar`: `Skills` / `Agents` / `Instructions`
(`1`/`2`/`3` hotkeys), driving the existing grid to re-render for the selected
kind.

The `instructions` grid shows:

- One **"General"** column = the native readers (Codex, OpenCode, Pi) —
  informational, always satisfied, no toggle.
- The `symlink`-verdict harnesses as **toggle cells** (on = pointer exists).
  Toggling flips the lock's `harnesses` array and reconciles the filesystem —
  the on/off switch, in the UI.
- `gap`/`by-design`/`unknown` harnesses render disabled, consistent with how
  unsupported subagent cells render.

---

## Matrix research (Phase A — the bridging deliverable)

Mirrors the sibling spec's research-first method exactly: **the matrix is the
contract; everything downstream implements against it.** A new column,
`instructions-file`, re-verified across **all ~54 harnesses** against *current*
upstream, citation-grade, parity-tested.

### The research question, per harness

> By default — **no config changes, no flags** — what file (and at what path,
> **per scope**) does this harness read for its project/global instruction
> context? Is that `AGENTS.md` natively, a fixed own-name file, a config-gated
> opt-in, a directory, or nothing?

**Both scopes must be located.** For every harness, capture *where the global/
user-scope instruction file lives* **and** the project-scope path — e.g.
`./CLAUDE.md` (project) vs `~/.claude/CLAUDE.md` (global). The global location is
an explicit, required research output, not an afterthought.

### Per-harness matrix cell

- **Verdict:** `native` / `symlink` / `unsupported (gap)` /
  `unsupported (by design)` / `unknown — no public evidence found`.
- **Default instruction file name** (e.g. `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`)
  — or the directory (e.g. `.clinerules/`), or `none`.
- **Project-scope path** and **global/user-scope path** (the "where does the
  global instructions file live" answer).
- **Reads `AGENTS.md` natively by default?** yes/no (the bucket discriminator).
- **Mechanism** if actionable: `symlink` (the only action verdict), else blank.
- **Loader citation:** file:line in current upstream, or doc URL — re-verified,
  not assumed.
- **One-line reasoning** for the verdict.

### Method

Same as the sibling spec's Phase A: **winnow-then-deep-dive**, batched by harness
family (reuse the nine batches: Claude-lineage, Google/Gemini, OpenCode+forks,
Codex/OpenAI-likes, Pi+agents-std, JetBrains/IDE, enterprise/cloud, China-market
CLIs, long-tail). ~9 research agents each return a **matrix fragment** (the
`instructions-file` cells for its batch) plus a "what I checked" trail. Agents do
**not** write the doc directly — the orchestrator assembles fragments into one
doc to avoid a race on a single file. Bounded effort per harness; `unknown` is a
valid honest verdict, not a failure.

### Reusable priors (re-verify, don't trust)

- The four-harness seed table from the user's own research (Claude →
  `CLAUDE.md`; Gemini → `GEMINI.md` default, `AGENTS.md` only via
  `context.fileName` opt-in; Aider → `CONVENTIONS.md` by convention, auto-loads
  nothing without `--read`/`.aider.conf.yml`; Cline → `.clinerules/` directory,
  native `AGENTS.md` proposed but unmerged #5033).
- The conventions native-reader table (Codex / OpenCode / Pi read `AGENTS.md`
  natively).
- Per the sibling spec's lesson — these are **priors to re-verify against
  current upstream**, not trusted data. Harnesses move fast.

### Output & guard

- New section/column in `docs/agent-toolkit/harness-matrix.md` (the doc already
  exists from the sibling spec's Phase A and is built to grow per-kind).
- Per-harness evidence trails in
  `docs/agent-toolkit/research/instructions-fragments/`.
- Parity test `tests/test_instructions_matrix.py` (analog of
  `test_subagent_matrix.py`) fails if the doc and the catalog
  (`skill_agents.py`) disagree.

---

## Phasing

Mirrors the sibling spec.

- **Phase A — research.** Produce the `instructions-file` matrix column across
  all ~54 harnesses + parity test + epic issue. No code.
- **Phase B — implementation** (its own `writing-plans` plan, depends on the
  sibling spec's kind-dimension generalization landing): the single `symlink`
  adapter, the `instructions` lock entry, the minimal CLI verbs, and the TUI
  third kind — implemented against the frozen matrix.

---

## Success criteria

**Phase A done when:**
- `harness-matrix.md` has the `instructions-file` column for all ~54 harnesses
  (verdict + default file name + project & global paths + native? + citation).
- `tests/test_instructions_matrix.py` green.
- Epic issue links the matrix and lists the `symlink`-verdict harnesses as the
  Phase B work surface.

**Phase B done when:**
- The `instructions` kind installs/removes per-harness pointers correctly into
  every `symlink`-verdict harness, in both scopes, lockfile-driven.
- The no-clobber guarantee holds: real files and foreign symlinks are never
  touched; already-ours is a no-op; the lock round-trips the `instructions`
  `kind`.
- `doctor` learns the kind (conflicting / orphaned / stray pointers).
- The TUI `KindsSidebar` switches to a third `Instructions` kind with a
  "General" column and toggleable `symlink` cells.

## Risks / open questions (for the Phase B plan)

- **Global canonical path.** Where does the global-scope `AGENTS.md` live
  (`~/.config/agents/AGENTS.md` vs `~/.claude/AGENTS.md`)? Decide in the plan.
- **Lock shape.** Inherits the sibling spec's open decision (unified `[[asset]]`
  + `kind` vs. parallel per-kind tables). This kind does not re-litigate it.
- **CLI shape.** Inherits the sibling spec's open `instructions`-group vs
  `--kind`-flag decision.
- **Gitignore interaction.** `AGENTS.md` and pointers are often gitignored and
  per-machine (convention). Confirm `install`/`doctor` behave sanely when the
  canonical file is gitignored and when a fresh clone has neither file yet.
