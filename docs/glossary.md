# Glossary

The shared vocabulary of the [compatibility matrix](matrix.md), the
per-harness pages, and the asset-type pages — grouped for skimming, highest-level
terms first.

## Core model

**Harness** { #harness }
:   A coding agent / AI dev tool the toolkit can target — Claude Code, Codex,
    Gemini CLI, Pi, … 54 catalogued in the [matrix](matrix.md). (The upstream
    `vercel-labs/skills` catalog calls these "agents"; this toolkit reserves
    *agent* for the subagent asset type.)

**Asset type** { #asset-type }
:   The toolkit's central organising concept: a category of installable asset
    that harnesses consume in structurally the same way, so one set of verbs
    can manage it across all of them. Each asset type owns its own
    [adopted convention](#adopted-convention), [lock file](#lock-file),
    [doctor](#doctor), projection [mechanisms](#mechanism), and CLI namespace.
    Five asset types: [instructions](asset-types/instructions.md) (always-loaded context),
    [skills](asset-types/skills.md) (on-demand instruction folders),
    [agents](asset-types/agents.md) (delegable subagents),
    [pi extensions](asset-types/pi-extensions.md) (Pi-only packages), and (planned)
    [MCP servers](asset-types/mcp.md). The [matrix](matrix.md) has one column — and
    every harness page one section — per asset type.

**Asset** { #asset }
:   One installable thing of an asset type — a skill folder, a subagent definition,
    the canonical `AGENTS.md`.

**Kind** { #kind }
:   Former name for [asset type](#asset-type).

## Conventions & conformance

**Adopted convention** { #adopted-convention }
:   The cross-harness standard the toolkit converges on for an asset type —
    `AGENTS.md` for instructions, `SKILL.md` folders for skills, the
    [general](#general) directory layout. The canonical copy always follows
    the convention; everything else is projected from it.

**Standard (conforming)** { #standard }
:   A harness that follows the adopted convention for an asset type natively — reads
    `AGENTS.md` or the general directory directly. Zero projection work.

**Non-standard (non-conforming)** { #non-standard }
:   A harness with its own equivalent surface that diverges from the adopted
    convention — an own-name file (`CLAUDE.md`), a different format, or a
    config registry. Still supported, via a pointer, translate, or config
    [mechanism](#mechanism).

## On disk

**Canonical** { #canonical }
:   The single authoritative copy of an asset that all projections point back
    to — the library clone of a skill, `AGENTS.md` for instructions.

**Library** { #library }
:   The store of canonical sources at `~/.agent-toolkit/` (e.g.
    `~/.agent-toolkit/skills/<slug>`, a git clone of the skill repo).

**Scope** { #scope }
:   Where an asset is installed: **project** (committed paths inside one
    repo) or **global** (per-user, under `~`). Most verbs take `-p`/`-g`.

**General** { #general }
:   The per-asset-type convergence directory many harnesses read directly —
    `.agents/skills` for skills, `.agents/agents` for agents. Its readers
    need no per-harness projection. (Successor of the legacy skills-only
    "universal" model.)

**Projection** { #projection }
:   Making an asset visible to one harness — usually a symlink into its slot
    directory, sometimes a translated file or a registry entry. Derived
    state: always safe to delete and rebuild.

**Mechanism** { #mechanism }
:   *How* an asset type projects into a particular harness:

    - **native** — already reads the canonical file/dir; zero work.
    - **symlink** — per-asset symlink into an auto-scanned directory.
    - **pointer** — same-name symlink (`CLAUDE.md → AGENTS.md`);
      instructions-asset-type only.
    - **translate** — per-harness flavored copy in a managed cache, then a
      symlink to it.
    - **config_file / config_file+folder** — registers the asset in a named
      config file, optionally with a managed artefact folder; commits and
      rolls back together.
    - **dual-symlink** — two slot directories mirroring one source (Pi).

## State & repair

**Lock file** { #lock-file }
:   The per-asset-type, per-scope JSON record of what is installed and from where
    (`skills-lock.json`, `instructions-lock.json`, …). The source of truth;
    projections are derived.

**Doctor** { #doctor }
:   The per-asset-type reconciler: compares lock ↔ canonical ↔ projections, reports
    findings (missing, foreign, drifted, unmanaged), offers fixes.

## Compatibility data

**Verdict** { #verdict }
:   A harness's classification for one asset type in the [SSOT](#ssot): a supported
    mechanism (✅ in the [matrix](matrix.md)), **unsupported (gap)** (could be
    filled, isn't yet — rendered —), **unsupported (by design)** (the harness
    has no such concept — rendered N/A), or **unknown** (no public evidence
    found — rendered ?).

**SSOT** { #ssot }
:   Single source of truth for harness compatibility:
    [`harness-matrix.md`](agent-toolkit/harness-matrix.md) — machine-read by
    the CLI (shipped in the wheel), guarded by parity tests, and published
    here as part of the site. The [matrix](matrix.md) and harness pages are
    generated views of it.

**Adapter** { #adapter }
:   The per-(asset type × harness) code implementing a supported verdict — writes
    the projection, guards foreign files, rolls back on failure. A verdict
    can be *supported* while the adapter is *disabled* (e.g. Codex subagents,
    pending the shared-config decision).
