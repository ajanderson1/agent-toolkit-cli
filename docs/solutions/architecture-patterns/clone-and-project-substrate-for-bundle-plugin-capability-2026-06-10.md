---
title: Clone-and-project is the right substrate for a future bundle/plugin capability
date: 2026-06-10
category: architecture-patterns
module: agent-toolkit-cli
problem_type: architecture_pattern
component: tooling
severity: high
applies_when:
  - Designing a new asset kind (mcp, claude-plugin, composite bundle) on top of the clone-and-project model
  - Deciding where bundle install state lives when a harness-native plugin manager wants to own it
  - Extending the per-kind library/lock layout (~/.agent-toolkit/<kind>/<slug>/) to multi-kind composites
  - Choosing between projecting source files and materializing runtimes in a harness adapter
  - Sequencing bundle work (mcp kind first, then claude-plugin, then composite bundle as a meta-kind)
tags: [clone-and-project, bundles, plugins, lockfile, projection, asset-kinds, mcp, meta-kind]
related_components: [development_workflow]
---

# Clone-and-project is the right substrate for a future bundle/plugin capability

## Context

Harnesses are converging on multi-asset bundles (Claude Code plugins, Copilot CLI's shared plugin format, Gemini extensions, Pi packages, Codex plugins — see the companion landscape survey in `tooling-decisions/`), and no cross-harness bundle standard exists. agent-toolkit-cli's existing model is **clone-and-project**: a canonical git clone at `~/.agent-toolkit/<kind>/<slug>/` (per-kind `library_subdir` on the frozen `KindBinding` dataclass in `src/agent_toolkit_cli/_paths_core.py`), a lockfile pin per kind (source/ref/sha in `skills-lock.json`, `agents-lock.json`, `pi-extensions-lock.json`, `instructions-lock.json`), and per-harness projection via adapters — symlink, translate, config_file_folder, dual-symlink (counts per kind live in `docs/agent-toolkit/harness-matrix.md`). The question this ADR answers: does that substrate extend to bundles, or do bundles need something new?

**Terminology note:** "bundle" here means a multi-asset plugin-style unit (skills + agents + MCP + commands in one repo). It is NOT the older "bundle dir" sense used in the doctor docs (`2026-05-22-doctor-classify-dying-bundle-target-as-drift.md`, issue #192), where "bundle" means a skill's on-disk directory shape.

## Guidance

**Decision: keep clone-and-project as the substrate. A bundle is NOT a fifth kind — it is a composite over existing kinds.** Install fans out into the existing per-kind installers; the lock gains a grouping field; uninstall rolls back the whole group atomically.

### Why the substrate fits (three structural arguments)

1. **A bundle IS a repo with subdirectories.** The monorepo-skills machinery — parent clone cache at `~/.agent-toolkit/skills/_parents/`, `--skill <subpath>`, one shared fetch_ref+reset_hard clone since v2.13.0 — is structurally identical to bundle handling. A `plugin.json` or Pi `"pi"` key is just a machine-readable version of `--skill` that selects subdirectories AND kinds.
2. **Symlink projection beats native installers on updates.** Claude Code copies plugin content into its cache; Pi materializes npm packages. With clone-and-project, one `git pull` on the canonical updates every projection in every harness atomically — one update instead of N per-harness reinstalls.
3. **Per-kind decomposition solves partial harness support for free.** A bundle's skills project to ~40 harnesses, agents to 28, MCP to 4 — per-kind verdicts compose. No "bundle support matrix" is needed, and we never have to answer "what does installing this plugin into codebuddy even mean".

### Three strains on the model (acknowledged, not disqualifying)

| Strain | Problem | Resolution |
|---|---|---|
| 1. Per-kind siloed library/lock layout | Each kind owns `~/.agent-toolkit/<kind>/<slug>/` + its own lockfile, and `LockEntry` assumes the canonical IS the asset. A bundle wants ONE clone (e.g. `~/.agent-toolkit/bundles/<slug>/`) with entries in SEVERAL lockfiles pointing into it via subpaths, plus group bookkeeping (atomic group uninstall; doctor knows membership) | Seams already exist: `skill_path` subpaths, the v3 extras dict (already has a `pluginName` slot), the parent-cache precedent. Cross-kind references into one shared clone is new plumbing — an engineering cost, not a conceptual mismatch |
| 2. "Project" delivers source files, not materialized runtimes | Symlinks handle markdown perfectly, but Pi package extensions may need npm deps installed (`pi install` does this; a bare symlink into `~/.pi/agent/extensions/` does not), and MCP entries need runnable commands | Clone-and-project covers the DECLARATIVE half; the RUNTIME half needs a post-clone materialization hook (e.g. `npm install` in the canonical) or delegation to the harness installer. The MCP kind plan (`docs/superpowers/plans/2026-06-07-mcp-kind-v3-foundations.md`) already concedes this by being config-injection-shaped |
| 3. Harness-native plugin managers want to own state | Claude Code tracks plugins in `installed_plugins.json` with enable/disable + version pinning; a symlink is invisible to it | For Claude: register the canonical clone as a LOCAL-PATH MARKETPLACE and let Claude "install" from it — clone stays SSOT, Claude's bookkeeping stays consistent (matches the drafted config-file adapter in `docs/superpowers/plans/2026-05-20-claude-plugin-asset-kind.md`). For Pi: observe-don't-own (`pi_extension_doctor` already inventories npm packages as a separate source it doesn't own) |

### Implementation order

1. **`mcp` kind first** — already planned (`docs/superpowers/plans/2026-06-07-mcp-kind-v3-foundations.md`, issue #329), config-injection-shaped, independently valuable, and bundles are usually anchored on an MCP server: it's the blocking dependency.
2. **`claude-plugin` kind** — the 2026-05-20 plan and its spec twin were scoped against the v1 architecture (issue #149, milestone v1.0.0); this ADR reaffirms the approach but it must be re-mapped into the v3 per-kind architecture, exactly as the mcp plan re-mapped its v1 predecessor. Cheap, and validates the config-file plumbing against a real marketplace.
3. **Only then the composite bundle** — the grouping field in the lock, fan-out install, atomic group uninstall. No GitHub issue exists for this yet; it is genuinely new ground.

### Open question (recorded, not decided)

Should Claude's `plugin.json` itself BE the input manifest we decompose from (Copilot proved it travels), versus a toolkit-native manifest? Defer until step 3.

## Why This Matters

The composite is the genuinely novel piece — nobody ships "one bundle projected into Claude Code, Pi, Gemini, and Copilot natively" — but it is also where the maintenance tail lives: N manifest translators and divergent security constraints (Claude bans plugin agents from declaring `mcpServers`; Pi packages can't carry MCP at all). Decomposition hedges exactly this risk: we translate a foreign manifest INTO our own kinds once, and the existing 54-harness matrix does the fan-out — instead of maintaining pairwise translation between four foreign manifest formats. Rejecting the "fifth kind" framing now prevents the worst outcome: a monolithic bundle unit whose support matrix, doctor semantics, and uninstall story would all have to be invented from scratch and would still degrade to per-kind answers anyway.

## When to Apply

- Designing or implementing the bundle/composite feature — this is the controlling decision.
- Reviewing any PR that adds a `bundles` library dir, a bundle lockfile, or cross-kind lock references: check it against strain 1's "one clone, several lockfiles, group bookkeeping" shape.
- Touching the MCP kind or claude-plugin kind plans — both are now sequenced as bundle prerequisites; scope changes there ripple here.
- Encountering an asset that needs a build/install step after clone (npm deps, compiled extension): that's strain 2 — reach for the materialization hook or harness delegation, don't bend projection.
- Revisit trigger: if a cross-harness bundle manifest standard emerges (SKILL.md-style), the open question about input manifest format should be reopened immediately.

## Examples

**Composite install fan-out.** Installing a bundle containing 2 skills, 1 agent, 1 MCP server: one clone lands at `~/.agent-toolkit/bundles/<slug>/`; the manifest is decomposed into 2 entries in `skills-lock.json`, 1 in `agents-lock.json`, 1 in the future MCP lock — each pointing into the shared clone via subpath, all carrying the same group id. `bundle uninstall <slug>` walks the group and rolls back all four atomically.

**Update advantage in practice.** Upstream bundles a fix touching one skill and the MCP config. Native path: re-install the plugin in Claude Code, `pi install` again, re-add the Gemini extension. Clone-and-project path: one `git pull` (or `update`) on the canonical; every symlink projection is instantly current; only config-injected and materialized pieces need a refresh pass.

**Strain 3 reconciliation.** Rather than symlinking into Claude's plugin cache (invisible to `installed_plugins.json`, liable to be clobbered), the toolkit registers `~/.agent-toolkit/bundles/<slug>/` as a local-path marketplace and drives plugin install from it — Claude believes it owns the install; the clone remains the single source of truth.

**What a bundle does NOT become.** No fifth `KindBinding` is added to `_paths_core.py` for bundles-as-assets; `KindBinding` stays the per-kind primitive, and the bundle layer composes over it.

## Related

- Companion survey: `docs/solutions/tooling-decisions/cross-harness-plugin-bundle-landscape-2026-06-10.md`
- MCP kind plan (step 1, live): `docs/superpowers/plans/2026-06-07-mcp-kind-v3-foundations.md` + spec `docs/superpowers/specs/2026-05-04-mcp-management-design.md`, issue #329 (open, v4.0.0 milestone)
- Claude-plugin kind plan (step 2, needs v3 re-mapping): `docs/superpowers/plans/2026-05-20-claude-plugin-asset-kind.md` + spec `docs/superpowers/specs/2026-05-20-claude-plugin-asset-kind-design.md`, issue #149 (closed, v1-scoped)
- Substrate origin: `docs/superpowers/specs/2026-05-27-v3-agents-refold-design.md` (v3 per-kind refold)
- Per-harness SSOT: `docs/agent-toolkit/harness-matrix.md`
