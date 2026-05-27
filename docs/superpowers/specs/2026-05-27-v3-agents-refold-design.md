# v3.0.0 — Agents Refold (design spec)

**Date:** 2026-05-27
**Status:** Phase A complete (PR #253, epic #252) → Phase B ready for `writing-plans`
**Scope:** Reintroduce the `agent` (subagent-definition) asset kind, stripped out after v1.

---

## Terminology (read first)

The word "agent" is overloaded in this codebase. This spec uses:

- **harness** — one of the ~54 AI coding tools the toolkit projects assets into
  (Claude Code, Cursor, Codex, Gemini CLI, Pi, …). The catalog in
  `src/agent_toolkit_cli/skill_agents.py` confusingly calls these "agents"
  because that is `vercel-labs/skills`'s term. When this spec says **harness**,
  it means that catalog entry.
- **agent** / **subagent** — a *deployable artifact*: a spawnable, separately
  defined assistant with its own instructions/tools (e.g. Claude Code's
  `.claude/agents/<slug>.md`). This is the **new asset kind** we are
  reintroducing — a sibling of `skill`. When this spec says **agent kind** or
  **subagent**, it means this artifact.

A subagent is NOT a skill, NOT a slash command, NOT an MCP server. The research
must hold this distinction firmly.

---

## Problem

v1 was a broad multi-kind asset toolkit. Its TUI had a left-hand `KindsSidebar`
offering `skill | agent | command | hook | plugin | mcp | pi-extension`, and its
`harness_adapters/` projected each kind into 5 harnesses (Claude, Codex,
OpenCode, Gemini, Pi). The "strip-back" reduced the tool to **skills-only**:
the sidebar is gone, `harness_adapters/` is empty, and the TUI is a single skill
grid.

v3.0.0 brings back **one** of those kinds — `agent` (subagents) — and the
left-hand selector that switches between kinds. The functionality must be
**compliant with all ~54 supported harnesses**: for every harness we must know
whether it has a subagent concept and, if so, exactly how it locates and calls
subagents.

## Goal

Ship v3.0.0 with the `agent` kind fully wired for every harness that genuinely
supports subagents, the `agent` column of a harness compatibility matrix
re-verified across all ~54 harnesses, and the left-hand kind selector restored
in the TUI. Everything else (command/hook/plugin/mcp/pi-extension) stays out of
scope.

## Non-goals (v3.0.0)

- Reintroducing `command`, `hook`, `plugin`, `mcp`, or `pi-extension` kinds.
  The sidebar MAY list them disabled/greyed, but only `agent` gets wired.
- Authoring subagent *content*. This is plumbing — projecting/installing
  subagent artifacts — not writing subagents.

---

## Two phases

This effort is **research-first**. The bridging artifact is the harness matrix;
everything downstream implements against it.

```
Phase A (research)  ──produces──▶  harness-matrix.md (agent row)  ──feeds──▶  Phase B (implementation plan)
```

### Phase A — Research (active now)

**Deliverable:** a refreshed `docs/agent-toolkit/harness-matrix.md` with a
complete, citation-grade `agent` row covering all ~54 harnesses, plus a GitHub
issue capturing the v3.0.0 epic with the matrix as its backbone.

**Method:** winnow-then-deep-dive, batched by harness family, re-verifying ALL
54 (including v1's 5) against *current* upstream — v1's matrix data is ~3 weeks
old and harnesses move fast, so it is a prior to re-verify, not trusted.

**Per-harness two-stage protocol:**

1. **Winnow (fast triage, time-boxed):** Does this harness have any subagent
   concept distinct from skills/commands/MCPs? → `yes` / `no` / `unknown`.
2. **Deep-dive (only `yes`/`unknown`):** capture the matrix cell:
   - **Mechanism:** `symlink` / `translate` / `config_file` / `dual-symlink` /
     `config_file+folder` (definitions in the matrix doc's "Mechanisms"
     section).
   - **User-scope target path** + **project-scope path**.
   - **File format** (markdown+frontmatter / TOML / JSON) and **required vs
     forbidden frontmatter fields** (e.g. Gemini's zod `.strict()` rejects extra
     top-level keys).
   - **Loader source citation:** file:line in current upstream repo, or doc URL
     — re-verified, not copied from v1.
   - **Verdict:** `supported` / `unsupported (gap)` / `unsupported (by design)`
     + one-line reasoning.

**Unknowns policy:** each harness gets a bounded search effort. If no subagent
evidence surfaces (dead project, no public docs/source), record
`unknown — no public evidence found` with a "what I checked" trail and move on.
Do not chase ghosts.

**Dispatch:** ~9 research agents, batched by likely shared lineage so each
exploits shared conventions. Indicative batches (membership finalized against
the live `skill_agents.py` list at dispatch time):

| Batch | Harnesses (indicative) |
|---|---|
| 1. Claude-lineage | claude-code, openclaw, kode, mux, command-code, codemaker |
| 2. Google/Gemini | gemini-cli, antigravity, qwen-code, iflow-cli |
| 3. OpenCode + forks | opencode, crush, goose |
| 4. Codex/OpenAI-likes | codex, kimi-cli, dexto |
| 5. Pi + agents-std | pi, amp, cline, warp, deepagents, firebender |
| 6. JetBrains/IDE | junie, qoder, trae, trae-cn, windsurf, cursor, continue, kilo, roo |
| 7. Enterprise/cloud | bob, codearts-agent, cortex, devin, droid, rovodev, tabnine-cli, zencoder |
| 8. China-market CLIs | codebuddy, codestudio, forgecode, hermes-agent, kiro-cli |
| 9. Long-tail | mcpjam, mistral-vibe, openhands, replit, github-copilot, neovate, pochi, adal |

**Output contract:** each agent returns a **matrix fragment** (the `agent`-row
cells for its batch, in the matrix-cell format above) plus its "what I checked"
trail. Agents do NOT write the doc directly — the orchestrator assembles all
fragments into the single refreshed `harness-matrix.md` to avoid 9 agents racing
on one file.

**v1 baseline to re-verify** (from `harness-matrix.md` at tag `v1.0.0`):

- **Claude:** `symlink → ~/.claude/agents/<slug>.md`.
- **Codex:** `translate → ~/.codex/agents/<slug>.toml`; TOML schema
  `name`/`description`/`developer_instructions` + `[agent_toolkit_cli]` table
  (#140).
- **OpenCode:** `translate → ~/.config/opencode/agents/<slug>.md`; inject
  `mode: subagent`, strip toolkit wrapper.
- **Gemini:** `translate → ~/.gemini/agents/<slug>.md`; **only** top-level
  `name`+`description` (zod `.strict()` rejects extras — wrapper omitted) (#97).
- **Pi:** `dual-symlink → ~/.pi/agent/agents/<slug>.md` AND `~/.agents/<slug>.md`
  via the `pi-subagents` extension; project scope mirrors `.pi/agents/` +
  `.agents/` (#75).

### Phase A — outcome (landed 2026-05-27)

Research complete. All 54 harnesses re-verified against current upstream:
**28 supported · 11 unsupported (gap) · 10 unsupported (by design) · 5 unknown.**
SSOT is `docs/agent-toolkit/harness-matrix.md` (recreated — the v1 doc was
deleted in the strip-back, commit `04aed66`/#164); parity-tested by
`tests/test_subagent_matrix.py`; per-harness evidence + baseline deltas in
`docs/agent-toolkit/research/subagent-fragments/`. Tracked in #252, PR #253.

The supported set resolves into **four projection mechanisms**, which is the
shape Phase B implements against:

| Mechanism | Count | Harnesses | What the adapter does |
|---|---|---|---|
| `symlink` | 14 | augment, claude-code, codebuddy, command-code, cortex, cursor, droid, forgecode, junie, kode, neovate, pochi, qoder, rovodev | drop the asset's markdown into the harness slot dir, frontmatter unchanged |
| `translate` | 9 | devin, gemini-cli, github-copilot, kilo, kiro-cli, mistral-vibe, mux, opencode, qwen-code | reshape frontmatter / change format before symlinking (incl. non-md: TOML mistral-vibe, JSON kiro-cli, `.agent.md` suffix github-copilot, inject `mode:` opencode/kilo) |
| `config_file+folder` | 4 | aider-desk, codex, dexto, firebender | register the agent in a config file (`config.toml`/`firebender.json`/registry) that points at a materialized definition file |
| `dual-symlink` | 1 | pi | two slot dirs, read by the 3rd-party `@tintinweb/pi-subagents` extension |

**Three baseline deltas vs v1.0.0 the Phase B plan must honour** (full detail in
the fragments + matrix "Notes for Phase B"):
- `claude-code` — still `symlink`, but discovery is now recursive + much larger
  optional-frontmatter set.
- `codex` — v1 modelled pure `translate` (#140). Current source requires an
  `[agents.<role>]` declaration in `config.toml` pointing at the TOML via
  `config_file=` → reclassified `config_file+folder`. **#140's translate-only
  adapter is insufficient and must be reworked.**
- `pi` — the user-scope `~/.agents/` alias appears to be a *skills* path now, not
  an agent-discovery path; project `.agents/` survives only as a legacy fallback.
  Verify against the installed extension before relying on the dual user alias.

### Phase B — Implementation (separate `writing-plans` plan)

Direction below; gets its own bite-sized plan. **Four reintroductions**, each
generalizing existing skills machinery to a `kind` dimension (`skill` | `agent`).

**1. `agent` projection adapters — one behaviour per supported matrix cell.**
Reintroduce `harness_adapters/` covering the four mechanisms above. The matrix is
the contract; reintroduce the parity coupling (a `tests/test_harness_matrix.py`
analog asserting each supported cell maps to a live adapter). v1 shipped adapters
for only 5 of the now-28 — the new surface is ~6× larger but only four distinct
mechanism shapes, so the work is "implement four adapters, parameterize per
harness," not 28 bespoke adapters. The non-md translate targets (TOML/JSON/suffix)
are the genuinely new code beyond v1.

**2. Install/lock/paths generalized to a `kind` dimension.** `skill_install.py`,
`skill_lock.py`, `skill_paths.py` are skill-hardcoded today. Teach them `kind`
so subagents get the same canonical-clone + per-harness-projection + lockfile
treatment. The lockfile gains a `kind` discriminator; if that breaks
`vercel-labs/skills`'s lock readers it is the v3.0.0 (major) trigger.
- **OPEN — central architecture decision:** generalize in place (one set of
  `*_install.py` taking a `kind` arg) vs. parallel `agent_*` modules. `conventions`
  principle tension (simple defaults vs. avoiding duplication) — surface to user,
  do not silently pick.

**3. `general` model — rename `universal`, make it per-kind.** (Decided
2026-05-27.) "Universal" is replaced by **"general"** = the generally-accepted
convergence convention *for a given kind*. The current `is_universal` is a path
coincidence (`skill_agents.py:42-43`: `skills_dir == ".agents/skills"`) and
literally cannot describe the agent convergence point. Phase A proved the
convergence is **per-kind**: skills converge on `.agents/skills/`, but agents
converge on `~/.claude/agents/` (read natively by kode, neovate, cortex, devin)
with no `.agents/agents/` analog. So there is a separate "general" category per
kind, with different membership.
- **Rename scope: both code and user-facing.** `is_universal`→`is_general`,
  `get_universal_agents()`→`get_general_agents()`,
  `get_non_universal_agents()`→`get_non_general_agents()`,
  `show_in_universal_list`→`show_in_general_list`, synthetic `"universal"` entry
  → per-kind `"general"` entries. TUI/CLI labels say "General".
- **Accepted tradeoff:** this DIVERGES from `vercel-labs/skills`'s `agents.ts`
  (`getUniversalAgents()`), which the code mirrors on purpose today
  (`skill_agents.py:454-455`). Chosen deliberately — a coherent internal
  vocabulary beats upstream-mirroring, and the harness=agent label/code mismatch
  already bit this project. The Phase B plan records the divergence, doesn't
  re-litigate it.

**4. TUI `KindsSidebar`.** Reintroduce v1's left-hand rail (`Skills` / `Agents`,
per-kind counts, `1`/`2` hotkeys) driving the existing grid to re-render per
selected kind. Each kind's grid shows its own "General" column (per #3) plus the
harnesses supported for that kind. Other kinds stay defined-but-dormant.

**CLI surface (must mirror the full `skill` verb set).** Provide the `agent`
equivalent of `add`, `install`, `uninstall`, `remove`, `import`, `list`,
`status`, `update`, `push`, `reset` (+ `doctor` learning the `agent` kind).
- **OPEN — CLI shape:** **(a)** parallel `agent` command group
  (`agent-toolkit-cli agent add|install|…`) vs **(b)** `--kind` flag on existing
  verbs (`skill add --kind agent …`, or a renamed neutral group). Decide in the
  Phase B plan.
- **`agent import` is in scope** — reconstructs an agent library from a lock file
  exactly as `skill import` does (`import_cmd.py` — `read_only=True`, monorepo
  parent-symlink reconstruction, `--latest`). The lock's new `kind` discriminator
  must round-trip through import.
- **`doctor` learns the `agent` kind** — stray-symlink detection + orphan checks;
  the matrix tells it which harness paths are legitimate agent slots (and which of
  the 11 `gap`/5 `unknown` harnesses are NOT, so it doesn't flag them).

**Long-tail policy:** the 11 `gap` + 5 `unknown` harnesses are NOT blockers. They
stay unwired; each `unknown` that later publishes evidence becomes a follow-up
matrix update + adapter, not a v3.0.0 gate.

**Explicitly out of scope for v3.0.0:** command/hook/plugin/mcp/pi-extension
adapters and CLI/TUI wiring. One kind per major version keeps the blast radius
sane.

---

## Success criteria

**Phase A done — ✅ all met (PR #253):**
- `harness-matrix.md` has the all-harness subagent table (54 rows, verdict +
  mechanism + path + format + citation per supported cell). ✓
- Parity test `tests/test_subagent_matrix.py` green. ✓
- Epic issue #252 links the matrix and lists the 28-harness supported set as the
  Phase B work surface. ✓

**Phase B done when (defined fully in its own plan):**
- `agent` kind installs/projects correctly into every `supported` harness, via
  the four mechanism adapters, with the parity test green.
- `universal`→`general` rename complete (code + UI), per-kind general categories.
- CLI exposes the full agent verb set incl. `agent import`; lock round-trips the
  `kind` discriminator.
- TUI `KindsSidebar` switches between `Skills` and `Agents`.

## Risks / open questions (for Phase B)

**Resolved during/after Phase A:**
- ~~Long-tail unknowns~~ → policy set: 11 gap + 5 unknown stay unwired, not
  blockers (see Phase B "Long-tail policy").
- ~~`universal` naming/scope~~ → resolved: rename to `general`, per-kind, code +
  UI, accepting divergence from vercel `agents.ts`.
- ~~codex mechanism~~ → resolved: `config_file+folder`, not pure translate (#140
  insufficient).

**Still open — for the Phase B plan to decide:**
- **Generalize-in-place vs parallel modules:** the central Phase B architecture
  decision (`conventions` tension: simple defaults vs. avoiding duplication) —
  surface to user, do not silently pick.
- **CLI shape (a) vs (b):** parallel `agent` group vs `--kind` flag.
- **Lock schema compatibility:** does adding a `kind` discriminator break
  `vercel-labs/skills`'s lock readers? Determines whether the major bump is truly
  forced (likely yes; confirm by inspecting the lock reader).
- **`general` per-kind data model:** one synthetic `"general"` entry that varies
  by kind, vs. distinct `"general-skill"`/`"general-agent"` entries — a
  `skill_agents.py` shape question for the plan.
