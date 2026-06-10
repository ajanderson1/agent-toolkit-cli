# Glossary

Terms with a precise meaning in this toolkit. The
[compatibility matrix](matrix.md), the per-harness pages, and the kind pages
all use this vocabulary.

### Harness

A coding agent / AI dev tool the toolkit can target — Claude Code, Codex,
Gemini CLI, Cursor, Pi, … 54 are catalogued; see the
[compatibility matrix](matrix.md). Called "agent" in the upstream
`vercel-labs/skills` catalog, but this toolkit reserves *agent* for the
subagent kind.

### Kind

A category of installable asset, each with its own lock file, CLI surface,
and projection rules: [instructions](kinds/instructions.md),
[skills](kinds/skills.md), [agents](kinds/agents.md),
[pi extensions](kinds/pi-extensions.md), and (planned)
[MCP servers](kinds/mcp.md).

### Asset

One installable thing of a given kind — a skill folder, a subagent
definition, the canonical `AGENTS.md`.

### Canonical

The single authoritative copy of an asset that all projections point back to —
e.g. the library clone of a skill, or `AGENTS.md` for the instructions kind.

### Library

The toolkit's store of canonical asset sources at `~/.agent-toolkit/`
(e.g. `~/.agent-toolkit/skills/<slug>`, a git clone of the skill's repo).

### Projection

Making an asset visible to one harness — usually a symlink from the
harness's slot directory to the canonical copy, sometimes a translated file
or a registry entry. Projections are reconciled against the lock file and are
always safe to delete and re-create.

### Mechanism

*How* a kind projects into a particular harness:

- **native** — the harness already reads the canonical file/dir; zero work.
- **symlink** — a per-asset symlink into an auto-scanned directory.
- **pointer** — the instructions-kind special case: a same-name symlink
  (`CLAUDE.md → AGENTS.md`).
- **translate** — generate a per-harness flavored file (different
  frontmatter, suffix, or format) in a managed cache, then symlink to it.
- **config_file / config_file+folder** — mutate a named config file to
  register the asset, optionally alongside a managed artefact folder; both
  commit and roll back together.
- **dual-symlink** — two slot directories mirroring one source (Pi).

### Scope

Where an asset is installed: **project** (committed paths inside one repo) or
**global** (per-user, under `~`). Most verbs take `-p`/`-g`; defaults vary by
kind and cwd.

### Lock file

The per-kind, per-scope JSON record of what is installed and from where
(`skills-lock.json`, `instructions-lock.json`, …). The lock is the source of
truth; projections are derived state that `doctor` can always rebuild.

### Doctor

The per-kind reconciler: compares lock ↔ canonical ↔ projections, reports
findings (missing, foreign, drifted, unmanaged), and offers fixes.

### General

The per-kind convergence directory that many harnesses read directly —
`.agents/skills` for skills, `.agents/agents` for agents. Harnesses reading
it need no per-harness projection. Successor of the legacy "universal" model
(general is per-kind; universal was skills-only).

### Verdict

A harness's classification for one kind in the
[SSOT](#ssot): a supported mechanism, **unsupported (gap)** (could be filled,
isn't yet), **unsupported (by design)** (no such concept — rendered — in the
matrix), or **unknown** (no public evidence found).

### SSOT

Single source of truth. For harness compatibility it is
`docs/agent-toolkit/harness-matrix.md` — machine-read by the CLI (shipped in
the wheel) and guarded by parity tests. The [matrix](matrix.md) and harness
pages are generated from it by `scripts/gen_harness_docs.py`.

### Adapter

The per-(kind × harness) code that implements a supported verdict — writes
the projection, guards foreign files, and rolls back on failure. A verdict
can be *supported* while the adapter is *disabled* (e.g. Codex subagents,
pending the shared-config decision).
