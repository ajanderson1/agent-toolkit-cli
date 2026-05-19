# Sidecar metadata discovery for skill + mcp — design

**Issue:** (to be filed against `agent-toolkit-cli`)
**Date:** 2026-05-19
**Status:** approved (brainstorm complete; awaiting implementation plan)
**Repo scope:** This spec lives in `agent-toolkit-cli`. Engineering work (PRs 1, 3) lands here. Content-repo work (PRs 2, 4) is delivered as copy-paste operator prompts at the end of this spec; the operator runs them in a fresh Claude Code session inside `~/GitHub/agent-toolkit/`.

## Goal

Add a sidecar metadata form for **skill** and **mcp** assets so that submoduled and vendored upstream content can be ingested without modifying upstream files. The sidecar lives alongside the asset directory as `<slug>.toolkit.yaml` and carries the same `apiVersion`/`metadata`/`spec` block that inline frontmatter carries today.

Sidecar becomes the **preferred** form for new skill and mcp assets. Inline frontmatter (skill: in `SKILL.md`; mcp: in `README.md`) remains valid but is treated as the legacy form. New asset scaffolding defaults to sidecar; `--inline` opts back to the single-file shape.

## Non-goals

- No sidecar support for agent, command, hook, plugin, or pi-extension. Each already uses the right convention for its body shape.
- No schema version bump. One in-place v1alpha2 relaxation is required (`fork` becomes optional under `vendored_via: submodule`), but no `v1alpha3` is introduced. The sidecar YAML's structure is byte-identical to what inline frontmatter would have been.
- No translator or harness-adapter changes. Both consume parsed metadata regardless of where it came from.
- No changes to the harness compatibility matrix.

## Motivation

Two pain points drive this change:

**Submoduled skills are invisible to the walker.** Four skills currently sit under `skills/` as git submodules (`deep-research`, `mindcraft`, `who-built-this-before-me`, `claude-d3js-skill`). The walker correctly skips submodule trees, but that means their `SKILL.md` files — which carry only upstream's own frontmatter, not the toolkit's `agent_toolkit_cli` wrapper — never become discoverable assets. To install one, today's options are forking upstream and adding wrapper frontmatter on a `local-patches` branch, or duplicating the content as a first-party copy. Both are heavyweight and brittle.

**MCP metadata lives in `README.md` as a load-bearing oddity.** The walker has a special `frontmatter_path()` branch: "for MCPs, the metadata isn't in the asset; go look in the sibling README." This works but is misleading (READMEs are user-facing documentation) and forces the convention that every MCP have a README that mixes operator docs with toolkit bookkeeping. Migrating to a dedicated `<slug>.toolkit.yaml` is a cleanup that the sidecar mechanism enables uniformly.

The toolkit already uses sidecars for hook (`<slug>.meta.yaml`) and pi-extension (`extension.meta.yaml`) — sidecars aren't a new pattern, just one that's currently scoped to two kinds. Extending it to skill and mcp is mechanically small and resolves both pain points.

## Prior art

Multiple ecosystems have wrestled with this exact problem of attaching metadata to upstream content without forking. Their lessons inform the design:

- **Backstage** (`catalog-info.yaml`): supports both inline-in-repo and out-of-band registration. Added "location keys" after dual-form drift became a production issue. **Lesson:** if both forms are supported, an explicit canonical-source rule is non-negotiable.
- **Bazel** (`http_archive(build_file = ...)`): pure sidecar — the build metadata for an external dependency lives in your tree, bound to a specific upstream SHA. **Lesson:** sidecar metadata bound by content address is drift-proof; sidecar bound by path is fragile.
- **Helm umbrella charts**: sidecar overrides in the parent's `values.yaml`. Works cleanly because the override namespace is flat and well-scoped.
- **pnpm** (`patch` vs `packageExtensions`): two metadata mechanisms coexist without confusion because they target non-overlapping problems. `patch` modifies code; `packageExtensions` fills metadata gaps. **Lesson:** dual-form is fine if the two forms have distinct semantics, not just different ergonomics.

The design that follows applies the Backstage lesson directly: both inline and sidecar are accepted for skill and mcp, but a single canonical-source rule (`check` exits 2 if both exist for the same slug) prevents drift.

## Architecture

### Single code surface: the walker

All discovery changes live in `src/agent_toolkit_cli/walker.py`. The `frontmatter_path()` helper and the per-kind discovery loops gain sidecar branches for skill and mcp. New helpers: `_sidecar_path(kind, slug, root)` and `_resolve_metadata(kind, slug, root)`.

For each candidate slug under `skills/` and `mcps/`, the walker now runs a three-step resolution:

1. **Sidecar probe.** Check for `<root>/<slug>.toolkit.yaml` (sibling of the asset directory). If present, parse as YAML.
2. **Inline probe.** Check for `<root>/<slug>/SKILL.md` (skills) or `<root>/<slug>/README.md` (mcps, pre-migration) carrying YAML frontmatter.
3. **Mutex check.** If both probes succeed for the same slug, raise `BothMetadataLocationsExist(slug, kind, sidecar_path, inline_path)`. The `check` command surfaces this as exit 2. **No silent merging, no precedence list.** One descriptor per asset.

If only one probe succeeds, that's the asset. If neither succeeds, the slug isn't a toolkit asset (today's silent-skip behavior preserved; surfaced as an `OrphanBody` advisory in `doctor`, not a `check` failure).

### Sidecar location: sibling of the asset directory

The sidecar lives **next to** the asset directory, not inside it:

```
skills/
  deep-research/                  ← submodule (untouched)
    SKILL.md
    reference/
    scripts/
  deep-research.toolkit.yaml      ← sidecar (this repo)
  agent-toolkit/                  ← first-party (inline frontmatter — legacy form)
    SKILL.md
```

This placement is non-negotiable for the submoduled-content case: a sidecar *inside* the submodule directory would itself be inside a `.gitmodules`-registered path, and the walker would skip it.

### Body location: implicit by name

The sidecar does not carry a `body_path` field. The walker derives the body location from the slug and kind:

| Kind | Body path | Bundled resources |
|---|---|---|
| skill | `<root>/<slug>/SKILL.md` | `<root>/<slug>/**/*` (all siblings of SKILL.md) |
| mcp | `<root>/<slug>/config.json` (discovery trigger) | `<root>/<slug>/**/*` excluding submodule trees |

Implicit-by-name keeps the sidecar's surface area minimal. If a future kind needs non-implicit body location, a `spec.body` block can be added then; YAGNI until that case appears.

### Submodule interaction

The existing rule — walker skips paths registered in `.gitmodules` — stands unchanged. The sidecar lives outside the submodule path, so it's discovered normally. The submodule body at `<root>/<slug>/SKILL.md` is *referenced* by the walker but **never read for frontmatter** — the sidecar supplies all metadata. At link time, the body is symlinked or translated as-is, with no expectation that it carries toolkit frontmatter.

**This is the key architectural win:** submodule trees stay opaque to the metadata layer but become reachable as bodies via the sidecar.

### Schema

No `v1alpha3` bump. The sidecar YAML has the same `apiVersion: agent-toolkit/v1alpha2`, the same `metadata` and `spec` keys, the same validation rules. The schema validator can validate a sidecar identically to inline frontmatter; the only change is which file the parser reads.

**One schema relaxation required, in-place within v1alpha2.** Today the schema's `allOf` block requires `fork` whenever `vendored_via: submodule`, on the assumption that every submodule carries a `local-patches` fork. This assumption is invalid for the unpatched-submodule case this spec enables — `deep-research` is tracked directly from upstream, no fork. PR 1 relaxes the rule so `fork` becomes optional even when `vendored_via: submodule`. The `AGENTS.md` "Submodule fork convention" continues to recommend forking when patches exist; it just stops being mandatory when there are no patches.

This is an **additive** schema change (it removes a requirement, doesn't add one), so it does not break any existing valid asset and does not force a version bump. Both schema copies (this repo's `schemas/asset-frontmatter.v1alpha2.json` and the CLI's vendored `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json`) update in lockstep; the byte-identity parity test still passes.

## Components

### CLI repo changes

| File | Change | Size estimate |
|---|---|---|
| `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json` (and parity copy in content repo) | Relax `fork` requirement when `vendored_via: submodule` (additive change). | ~3 lines modified |
| `src/agent_toolkit_cli/walker.py` | Sidecar discovery for skill + mcp; new helpers `_sidecar_path()`, `_resolve_metadata()`; mutex error class. | ~60 lines added, ~10 modified |
| `src/agent_toolkit_cli/commands/check.py` | Two new validators: `_check_metadata_mutex()`, `_check_orphan_sidecar()`. Wired into existing check runner. | ~40 lines added |
| `src/agent_toolkit_cli/commands/new.py` | Sidecar templates for skill + mcp; sidecar is the default; `--inline` opts back. Update help text. | ~30 lines modified |
| `src/agent_toolkit_cli/doctor/orphans.py` (new) | OrphanBody advisory: walks asset roots, flags directories with no metadata source. Surfaced in `doctor` output. | ~30 lines |
| `src/agent_toolkit_cli/doctor/autofix.py` (new) | Write-capable autofix for three error classes: mutex violation, orphan sidecar (refuses), orphan body (emits stub sidecar). | ~80 lines |
| `src/agent_toolkit_cli/commands/doctor.py` | `--fix` flag (off by default), `--dry-run`, `--yes`. Prompts per finding unless `--yes`. | ~30 lines modified |
| `src/agent_toolkit_cli/commands/migrate_mcps_to_sidecar.py` (new, temporary) | One-shot migration script. Removed in PR 3. | ~50 lines |
| `tests/test_walker_sidecar.py` (new) | Fixture tests covering all discovery branches and error cases. | ~150 lines |
| `tests/test_check_mutex.py` (new) | Mutex exit-2 semantics, error format, fix-hint string. | ~60 lines |
| `tests/test_doctor_autofix.py` (new) | Each autofixer in isolation; `--dry-run` writes nothing; `--yes` no-prompts. | ~120 lines |
| `tests/test_new_command_sidecar.py` (new) | `new skill foo` creates two files; `--inline` creates one; templates schema-valid. | ~50 lines |
| `docs/agent-toolkit/cli.md` | New "Sidecar metadata" section; updated `new` and `doctor` subcommand docs; rationale paragraph for sidecar-default policy. | ~80 lines |
| `docs/agent-toolkit/harness-matrix.md` | Brief §1 note confirming sidecar applies to skill/mcp metadata only, not to projection. | ~5 lines |
| `AGENTS.md` | Update "Asset identity," "Discovery," "Validation gate" invariants to reflect sidecar-first policy and mutex rule. | ~20 lines |

### Content-repo changes (this repo handles via copy-paste prompt)

These are not engineered through a CLI-repo issue. The spec includes a ready-to-paste operator prompt (see "Content-repo execution prompt" below) that the user drops into a fresh Claude Code session in `~/GitHub/agent-toolkit/`.

| File | Change |
|---|---|
| `mcps/<slug>/<slug>.toolkit.yaml` × 17 | New sidecars carrying what was in `README.md` frontmatter. |
| `mcps/<slug>/README.md` × 17 | Strip the `agent_toolkit_cli:` frontmatter block. READMEs return to plain documentation. |
| `skills/deep-research.toolkit.yaml` (and 3 other submoduled skills) | New sidecars. Worked example below. |
| `skills/agent-toolkit/SKILL.md` | Two new sections: "Adding a skill" (sidecar-first scaffolding) and "Ingesting an upstream skill via submodule + sidecar." |
| `AGENTS.md` | Mirror CLI repo's updated invariants. |
| `docs/agent-toolkit/schema.md` | New "Metadata location" section showing the two valid locations per kind. |
| `docs/agent-toolkit/harness-handbook.md` | §1 paragraph; §4 skill dossier note. |
| `README.md` | One sentence under "Use the toolkit" mentioning sidecar support. |

## Data flow

End-to-end discovery with a sidecar (using `deep-research` as the example):

```
1. Walker boot
   |
   v
2. Read .gitmodules → submodule paths set
   |
   v
3. For each candidate root (skills/, mcps/, …):
   |     For each subdirectory <slug>:
   |       a. Probe sidecar:  <root>/<slug>.toolkit.yaml      ← exists for deep-research
   |       b. Probe inline:   <root>/<slug>/<body-file>       ← SKILL.md exists, no frontmatter
   |       c. Mutex check                                      ← only sidecar found, OK
   |       d. Parse sidecar YAML against v1alpha2 schema
   |       e. Construct AssetRecord:
   |            kind = skill
   |            slug = deep-research
   |            metadata = parsed sidecar
   |            body_path = skills/deep-research/SKILL.md     (implicit-by-name)
   |            body_dir  = skills/deep-research/             (implicit-by-name)
   v
4. AssetRecord enters the normal pipeline:
   |     - inventory listing
   |     - allowlist intersection (~/.agent-toolkit.yaml)
   |     - link projection (symlink or translate per harness/kind)
   v
5. Link time:
       - Claude / Pi / Gemini → symlink body_dir into ~/<harness>/skills/<slug>/
       - Codex / OpenCode → translator reads sidecar metadata, renders harness-flavored
         frontmatter to cache, copies body verbatim into cache below the rendered
         frontmatter. Bundled resources (reference/, scripts/) copied into the cache
         directory to preserve relative-path references from the body.
```

Two flow changes from today:
- Step 3a/3b/3c is new (was: just read frontmatter from the body file).
- Step 5's translator path for sidecar-only assets reads the body raw from the submodule and copies bundled resources into the cache directory.

## Error handling

| Situation | Walker behavior | `check` behavior | User-visible message |
|---|---|---|---|
| Sidecar only, body present | Asset discovered | Pass | (none) |
| Inline only, no sidecar | Asset discovered (today's path) | Pass | (none) |
| Both sidecar AND inline for same slug | Asset not added; error recorded | Exit 2 | `MutexViolation: skills/deep-research has both skills/deep-research.toolkit.yaml and inline frontmatter in skills/deep-research/SKILL.md. Delete one or run \`agent-toolkit-cli doctor --fix\`.` |
| Sidecar exists, body directory missing | Error recorded | Exit 2 | `OrphanSidecar: skills/deep-research.toolkit.yaml has no body at skills/deep-research/. Delete sidecar or create the body.` |
| Body exists, no metadata anywhere | Slug silently skipped | Pass; doctor advisory | `Orphan body: skills/foo/SKILL.md has no metadata. Add inline frontmatter or skills/foo.toolkit.yaml.` |
| Sidecar YAML parse error | Error recorded | Exit 2 | `InvalidSidecar: skills/deep-research.toolkit.yaml: <yaml parser error>` |
| Sidecar passes parse but fails v1alpha2 schema | Error recorded | Exit 2 | `SchemaViolation: skills/deep-research.toolkit.yaml: <jsonschema error path>` |
| Sidecar declares slug X but lives at `skills/Y.toolkit.yaml` | Error recorded | Exit 2 | `SlugMismatch: skills/Y.toolkit.yaml declares metadata.name=X. Filename slug and metadata.name must match.` |
| Sidecar for unsupported kind (e.g. `agents/foo.toolkit.yaml`) | Error recorded | Exit 2 | `UnexpectedSidecar: agents/foo.toolkit.yaml — sidecars are only supported for skill and mcp.` |
| Sidecar inside a submodule path | Error recorded | Exit 2 | `SidecarInSubmodulePath: <path> is inside a submoduled tree.` |

The general principle: **fail loudly, never silently merge or pick one.** The mutex rule has teeth because the lefthook gate runs `check --exit-code` on every commit; malformed state can't reach a PR.

### `doctor --fix` autofix

Today's `doctor` is read-only. The new errors are mechanical enough that human judgment isn't always required, so `doctor` learns a `--fix` mode (off by default; `--dry-run` shows what would change; `--yes` no-prompts).

Three new autofixers:

| Error class | Autofix logic | Confidence |
|---|---|---|
| **Mutex violation** | If the body file is under a `.gitmodules` path: sidecar wins, delete inline frontmatter from the body file (but only if we authored that frontmatter — refuse if the body is in a submodule, since we shouldn't be editing upstream files). Otherwise prompt the user. With `--yes`, always favour the sidecar. | High when submoduled; medium otherwise. |
| **Orphan sidecar** | Refuse to autofix. Surface the sidecar path; suggest `git submodule update --init <path>` if the path matches a known submodule, or `rm <sidecar>` otherwise. | Low — user error, autofix could destroy intent. |
| **Orphan body** | Emit a stub `<slug>.toolkit.yaml` with `metadata.name` derived from the directory, `description` extracted from the body's first H1 or paragraph, `spec.origin` defaulting to `first-party`. User reviews and edits. | Medium — produces a starting point. |

Autofix is opt-in per invocation and per finding. The lefthook gate still uses `check --exit-code` (read-only); autofix happens only via explicit `doctor --fix`. This preserves the contract that commits don't trigger writes.

## Edge cases

- **Empty body after frontmatter strip.** With a sidecar + submodule, the submodule's body is already non-empty by construction. Not a new failure mode.
- **Sidecar with leading `---` markers.** The YAML parser accepts both bare YAML and document-marker form. Same loader as the inline path.
- **Sidecar in a `.gitmodules`-registered path.** Walker refuses defensively (`SidecarInSubmodulePath`). The mutex check would also catch this if a body exists, but the standalone case needs its own error.
- **Case sensitivity.** Slug-equality invariant (filename slug == `metadata.name`) is already enforced. Sidecars inherit this rule unchanged.
- **Renaming a slug.** Rename both the directory and the sidecar in one commit. `check` catches any half-renamed state.

## Migration plan

Five commits, sequenced across two repos. Each leaves the lefthook gate green.

**PR 1 (CLI repo): Walker sidecar discovery + check additions + new-command templates.**
- Walker learns sidecar-or-inline resolution for skill and mcp.
- Mutex check active (no-op today since no sidecars exist yet).
- Legacy MCP "frontmatter in README" path still functional in parallel.
- `agent-toolkit-cli new skill <slug>` defaults to sidecar; `--inline` opts back.
- Doctor autofix scaffolding (read path); fix path lands in PR 3.
- Unit tests + integration tests + doc updates.
- Ships green; CI parity test passes; lefthook gate passes.

**PR 2 (content repo, via copy-paste prompt): MCP migration.**
- Atomic: 17 new sidecars + 17 README strips in one commit.
- `agent-toolkit-cli list` output unchanged (verified before/after).
- `~/.claude.json` re-link diff is empty (metadata-only change).

**PR 3 (CLI repo): Remove MCP README-frontmatter path; activate doctor autofix write logic.**
- Walker's `frontmatter_path()` no longer special-cases MCP. Sidecar-or-inline applies uniformly.
- README-frontmatter parsing for MCPs deleted.
- `doctor --fix` actual write logic activated for the three classes.
- Temporary `migrate-mcps-to-sidecar` script removed.
- Smallest of the three CLI PRs.

**PR 4 (content repo, via copy-paste prompt): Submoduled skill sidecars + docs.**
- `skills/deep-research.toolkit.yaml`, `skills/mindcraft.toolkit.yaml`, `skills/who-built-this-before-me.toolkit.yaml`, `skills/claude-d3js-skill.toolkit.yaml`.
- Update `skills/agent-toolkit/SKILL.md` with two new sections (scaffold, ingestion).
- Update `AGENTS.md`, `schema.md`, `harness-handbook.md`, `README.md`.

**Operator action (manual, not a PR):**
- Edit `~/.agent-toolkit.yaml` to add the new skills under desired harnesses.
- Run `agent-toolkit-cli link user <harness>`.

## Test plan

**Unit (CLI repo, new):**
- `tests/test_walker_sidecar.py` — sidecar-only, inline-only, both-present mutex, orphan sidecar, orphan body skip, sidecar at submoduled-body path, parse error, schema violation, slug mismatch, unexpected-kind, sidecar-in-submodule.
- `tests/test_check_mutex.py` — exit-2 semantics, error format, fix-hint, multi-slug aggregation.
- `tests/test_doctor_autofix.py` — each autofixer in isolation; `--dry-run` writes nothing; `--yes` no-prompts.
- `tests/test_new_command_sidecar.py` — `new skill foo` creates two files; `--inline` creates one; templates schema-valid.

**Integration (CLI repo, extend existing):**
- `test_link_user_skill_sidecar` — sidecar-described skill links identically to inline-described.
- `test_link_user_mcp_sidecar` — same for MCPs; byte-identical adapter output before/after migration.
- `test_parity_after_migration` — golden-file baseline for `agent-toolkit-cli list` after migration script runs against a fixture content-repo.

**Content-repo verification:**
- `agent-toolkit-cli check --exit-code` passes after PR 2 (MCP migration).
- `agent-toolkit-cli check --exit-code` passes after PR 4 (skill sidecars).
- `agent-toolkit-cli list mcp claude` lists the same 17 MCPs before and after.
- `agent-toolkit-cli list skill claude` lists 4 new skills after PR 4.
- Diff `~/.claude.json` before/after re-linking MCPs is empty.
- Existing parity test in CLI repo still passes.

**Manual end-to-end:**
Once `deep-research` is sidecar-described, linked at user scope, and a Claude Code session starts: Claude auto-loads the skill description, the body loads on invocation, and the submodule's `reference/` and `scripts/` directories are reachable via the body's relative paths.

## Acceptance criteria

- Walker accepts sidecar metadata for skill and mcp; mutex rule active.
- All 17 MCPs migrated; no `agent_toolkit_cli:` frontmatter remains in any `mcps/<slug>/README.md`.
- All 4 submoduled skills have sidecars; `agent-toolkit-cli inventory skill` includes them.
- `agent-toolkit-cli new skill foo` produces a sidecar by default; `--inline` produces inline.
- `agent-toolkit-cli doctor --fix --dry-run` reports what it would change; `doctor --fix --yes` applies the three autofixers.
- `agent-toolkit-cli check` exit code remains 0 in this repo throughout the migration.
- All docs in the consolidated list (see Components) are updated; no doc-update-matrix drift.
- `deep-research` skill, linked at user scope on Claude, loads in a real Claude Code session; relative paths to `reference/` and `scripts/` resolve.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Migration script bug corrupts an MCP's metadata mid-migration. | Script is dry-runnable; PR 2 description includes a before/after diff. Schema validates each emitted sidecar. |
| Autofix in `doctor --fix` deletes the wrong file on a mutex violation. | Prompts per finding by default. `--yes` is documented as "favour sidecar always" — predictable, deterministic. Never edits files inside submodule paths. |
| User confused about sidecar vs inline for new skills. | `new skill foo` default is sidecar; `--help` and `cli.md` lead with sidecar; inline framed as legacy. |
| Submoduled body's relative-path links into `reference/`, `scripts/` break post-translation. | Translator copies the body verbatim and bundled resources into the cache directory, preserving sibling structure. Covered by `test_link_user_skill_sidecar`. |
| Doc drift across repos about sidecar form. | `AGENTS.md` is canonical wording; other docs reference it. Extend conventions prose-leak check to include metadata-location wording. |
| Operator runs PR 2 (content-repo migration) before PR 1 (CLI repo) ships, breaking discovery. | The copy-paste prompt for PR 2 instructs the operator to verify `agent-toolkit-cli --version` is on a build with sidecar support before proceeding. PR 1 release notes flag the dependency. |

## Worked example: `deep-research` as a sidecar-described submoduled skill

### Before (today)

```
skills/
  deep-research/                  ← submodule, walker skips it
    SKILL.md                      ← upstream's frontmatter only (name, description)
    reference/
    scripts/
```

`agent-toolkit-cli inventory skill | grep deep-research` returns nothing. The skill is invisible to the toolkit.

### After PR 4

```
skills/
  deep-research/                  ← submodule, unchanged
    SKILL.md                      ← upstream's content, untouched
    reference/
    scripts/
  deep-research.toolkit.yaml      ← new sidecar in this repo
```

Sidecar content:

```yaml
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: deep-research
  description: Use when the user needs multi-source research with citation tracking, evidence persistence, and structured report generation. Triggers on "deep research", "comprehensive analysis", "research report", "compare X vs Y", "analyze trends", or "state of the art". Not for simple lookups, debugging, or questions answerable with 1-2 searches.
  lifecycle: stable
spec:
  origin: third-party
  vendored_via: submodule
  upstream: https://github.com/199-biotechnologies/claude-deep-research-skill
  harnesses: [claude, codex, opencode, gemini, pi]
  # No `fork:` field — submodule tracks upstream directly. This requires
  # the schema relaxation noted under "Schema" above: today's v1alpha2
  # mandates `fork` when `vendored_via: submodule`, on the assumption
  # that submodules always carry a `local-patches` fork. That assumption
  # is invalid for the unpatched-submodule case this spec enables.
```

`agent-toolkit-cli inventory skill | grep deep-research` now returns the skill. To install: add `deep-research` to `~/.agent-toolkit.yaml` under `claude.skills` (or another harness), run `agent-toolkit-cli link user claude`.

## Content-repo execution prompt

The content-repo work (PRs 2 and 4) is delivered as a ready-to-paste prompt the operator drops into a fresh Claude Code session in `~/GitHub/agent-toolkit/`. The prompt for each PR is self-contained: it tells the agent what to do, what to verify, and what to commit.

### Prompt for PR 2 (MCP migration)

```
Migrate this repo's MCP metadata from README.md frontmatter to sidecar files,
per docs/superpowers/specs/2026-05-19-sidecar-metadata-discovery-design.md
(spec lives in ~/GitHub/projects/agent-toolkit-cli/).

Prerequisites to verify before starting:
- `agent-toolkit-cli --version` is on a build with sidecar support (PR 1 merged in CLI repo).
- This repo's working tree is clean.

For each MCP under mcps/<slug>/:
1. Read mcps/<slug>/README.md, extract the YAML frontmatter block (between the
   two `---` lines at the top).
2. Write that frontmatter as mcps/<slug>/<slug>.toolkit.yaml (no `---`
   wrappers — just the bare YAML).
3. Strip the frontmatter block (and any leading blank line) from
   mcps/<slug>/README.md so the README starts at its first heading or paragraph.

Verify after migration:
- `agent-toolkit-cli check --exit-code` exits 0.
- `agent-toolkit-cli list mcp claude` lists the same 17 MCPs as before
  (compare to a saved pre-migration listing).
- For each MCP currently linked at user scope: re-running
  `agent-toolkit-cli link user claude` produces no diff in ~/.claude.json.

Commit as one atomic commit:
- Subject: `chore(mcps): migrate metadata from README frontmatter to sidecar`
- Body: brief explanation linking to the spec.

Do not commit until all verifications pass. If `check` reports a
MutexViolation, that means a README still has frontmatter — finish stripping
those before commiting.
```

### Prompt for PR 4 (submoduled skill sidecars + docs)

```
Add toolkit sidecars for the four submoduled skills in this repo, and update
the documentation per the spec at
~/GitHub/projects/agent-toolkit-cli/docs/superpowers/specs/2026-05-19-sidecar-metadata-discovery-design.md.

The four submoduled skills are:
- skills/deep-research (upstream: 199-biotechnologies/claude-deep-research-skill)
- skills/mindcraft (upstream: beknazar/mindcraft)
- skills/who-built-this-before-me (upstream: iagochavarry/who-built-this-before-me)
- skills/claude-d3js-skill (upstream: chrisvoncsefalvay/claude-d3js-skill)

For each, write skills/<slug>.toolkit.yaml as a sibling of the submodule
directory. Pull metadata.description from the upstream SKILL.md's frontmatter
(do not modify the submodule). spec.origin: third-party; spec.vendored_via:
submodule; spec.upstream: the URL from .gitmodules. spec.harnesses: use
upstream's declared compatibility if their frontmatter names it; otherwise
default to [claude] (these are Claude-native skills published before
multi-harness existed). The user can widen the harness list later after
verifying the skill works on additional harnesses.

Documentation updates:
- skills/agent-toolkit/SKILL.md — add two sections: "Adding a skill" (lead with
  sidecar; mention inline as legacy) and "Ingesting an upstream skill via
  submodule + sidecar" (the deep-research case made canonical).
- AGENTS.md — update §"Asset identity" invariant to reflect per-kind
  conventions: skill = sidecar (preferred) or inline (legacy); mcp = sidecar;
  agent/command = inline; hook = sidecar; plugin = inline-JSON;
  pi-extension = sidecar.
- docs/agent-toolkit/schema.md — add "Metadata location" section after the
  field reference, showing both valid locations per kind with worked YAML.
- docs/agent-toolkit/harness-handbook.md — add a paragraph in §1
  "What sits underneath" mentioning the two metadata locations; add a note
  in §4 skill dossier pointing to schema.md.
- README.md — one sentence under "Use the toolkit" mentioning sidecar support.

Verify:
- `agent-toolkit-cli check --exit-code` exits 0.
- `agent-toolkit-cli inventory skill` includes the four new slugs.

Commit:
- One commit for the four sidecars: `feat(skills): ingest 4 submoduled skills
  as sidecar-described assets`.
- A second commit for the docs: `docs: document sidecar metadata convention`.

Mention in the commit body that the four skills are now installable via
~/.agent-toolkit.yaml allowlist edits.
```

## See also

- `docs/agent-toolkit/harness-matrix.md` — the contract this work does not touch.
- `~/GitHub/agent-toolkit/docs/agent-toolkit/harness-handbook.md` — narrative companion; gains light updates in PR 4.
- `~/GitHub/agent-toolkit/AGENTS.md` — content-repo invariants; updated in PR 4.
- Prior art: Backstage entity providers, Bazel `http_archive(build_file=...)`, pnpm `packageExtensions`.
