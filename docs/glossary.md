# Glossary

Vocabulary shared by the [matrix](matrix.md), harness pages and asset guides.
The repository's [GLOSSARY.md](https://github.com/ajanderson1/agent-toolkit-cli/blob/main/GLOSSARY.md)
is authoritative for product terminology; this page adds implementation detail.

## Verb model { #verb-model }

For **source-backed kinds**, two separate axes matter:

| Axis | Add | Take away | Effect |
|---|---|---|---|
| Global library membership | **add** | **remove** | Register/remove canonical source and its library record; removal can destroy local work. |
| Harness exposure | **enable** | **disable** | Project/retract an asset in a selected harness/scope; disabling keeps the library source. |

Use **add/remove** for global library membership and **enable/disable** for harness
exposure in explanations. Current source-backed CLI commands spell exposure
operations `install`/`uninstall`; retain those exact tokens in runnable examples,
without treating them as the product vocabulary. This does not introduce new CLI
verbs or aliases.

**Exceptions:** Instructions has no source library or installation lock, only user-owned canonical content and pointer operations. MCP `add` authors a global manifest entry; the current MCP `remove` command retracts scoped projections but **keeps library membership/files**. Native Pi npm has no Toolkit library registry: `add`/`install` downloads/configures packages and may activate resources, `remove`/`uninstall` removes the scoped installation/declaration, and `enable`/`disable` changes extension filters while retaining files. Bundles is a utility with `install`/`validate`, not a seventh kind. Verbs and flags are not uniform: see the [CLI reference](agent-toolkit/cli.md).

`update` refreshes source (merge-aware for skills/agents/Git Pi extensions; Commands has its own update behavior; MCP re-resolves and re-projects). `push` publishes owned source edits, normally through a PR. `reset` can discard local Git work; it is **not** a synonym for rebuilding visibility. `status` inspects; doctor behavior depends on kind. Enable/disable is the product terminology; a CLI command rename remains [unshipped](agent-toolkit/roadmap.md#verb-remap-enable-disable-for-projection).

## Toolkit application and distribution

**Toolkit package** { #toolkit-package }
:   The Python distribution `agent-toolkit`, containing the CLI and TUI.
    Root `atc update` / `att update` replaces this application; it does not
    refresh asset backing, change harness exposure, or migrate project data.
    [Package update rules](agent-toolkit/updates.md).

**Packaged entry point** { #packaged-entry-point }
:   An executable shipped by that distribution. `atc` and `att` are equivalent
    to `agent-toolkit-cli` and `agent-toolkit-tui`, respectively; they are not
    shell aliases and require no shell startup edits just to run. This is
    separate from singular asset-group aliases such as `skill` → `skills`.

**Shell completion** { #shell-completion }
:   Explicit shell integration for TAB suggestions from the current Click
    command tree. Supports commands, flags, declared choices and paths, not
    asset-name discovery or remote fetching. Its managed startup-file block is
    not an asset projection or application preference.
    [Setup and internals](agent-toolkit/shell-completion.md).

**Build receipt / provenance** { #build-receipt }
:   A record binding an artifact to source identity and its wheel hash. GitHub
    `deployment-receipt.json` describes published release artifacts; updater
    `receipt.json` describes a locally built wheel from a pinned canonical
    commit. Neither is an asset lock. A version string alone does not prove
    either source or artifact identity. [Verification](agent-toolkit/installation.md#verify-a-published-wheel).

## Core model

**Harness** { #harness }
:   A coding assistant/tool in the catalog. Catalog membership supplies metadata, not every-kind/every-scope support or proof an adapter is enabled.

**Asset type** { #asset-type }
:   One of six managed categories: [Skills](asset-types/skills.md), [Agents](asset-types/agents.md), [Commands](asset-types/commands.md), [Instructions](asset-types/instructions.md), [Pi extensions](asset-types/pi-extensions.md), [MCP servers](asset-types/mcp.md). Each has its own supported operations and storage model.

**Asset** { #asset }
:   One real managed item: a skill folder, agent definition, command prompt, canonical instruction file, extension or MCP registration.

**Kind** { #kind }
:   Code/internal shorthand for asset type.

**Shared asset catalogue** { #shared-asset-catalogue }
:   An optional Git-backed list of upstream skills, agents, commands and Pi extensions. Catalogue-only inventory has origin `catalog`, not local library membership. Admission inspection checks an upstream asset before publication; consumer acquisition is a separate action. Removing an entry does not delete or disable acquired assets. This is distinct from the harness compatibility matrix. [Reference](agent-toolkit/catalog.md).

**Collection** { #collection }
:   A derived source/ref group of real skill children. The TUI parent is not a separate skill to enable or an extra lock entry; controls include full membership even when children are collapsed/filter-hidden.

## Conventions and storage

**Adopted convention** { #adopted-convention }
:   The placement/format shared where possible: e.g. `AGENTS.md`, `SKILL.md` folders or a common harness slot.

**Standard (conforming)** { #standard }
:   A shared projection slot and its verified reader set, specific to asset type and scope. Skills uses `.agents/skills`; Agents/Commands share `.claude/agents` / `.claude/commands`. MCP Standard is project-only `.mcp.json` for Claude Code + Pi. It is not an extra harness.

**Non-standard (non-conforming)** { #non-standard }
:   A harness requiring its own slot, translation or config entry rather than a shared placement. Not a judgment about product quality.

**Canonical** { #canonical }
:   Authoritative asset content. For Instructions it is user-owned project `AGENTS.md` or global `~/.agent-toolkit/AGENTS.md`, possibly linked to a versioned source. Installation never authors those bytes.

**Library** { #library }
:   Source-backed canonical content, normally under `~/.agent-toolkit/<kind>/`. MCP instead has an authoritative global `mcps-library.json` manifest and materialized config/sidecar pairs. Instructions has no source-library membership workflow.

**Monorepo skill** { #monorepo-skill }
:   A real skill subpath in a shared repository checkout. `parentUrl`/`skillPath` locate it; canonical usually symlinks into the parent. Ref and observed upstream SHA are different metadata, not interchangeable pins. [Details](agent-toolkit/skill-lock.md).

**`_parents/` cache** { #parents-cache }
:   Shared source/ref backing checkouts, normally `~/.agent-toolkit/skills/_parents/<owner>/<repo>[@<ref>]/`. New projects share central library backing by default; recorded legacy private backing remains supported. Referenced checkout history/index/local work is not disposable cache noise.

**Owned / read-only (monorepo)** { #owned }
:   Publishing permission classification: recognized owned owner or explicit `--owned` allows subpath-only PR publishing; `readOnly: true` refuses push. Update still merges rather than intentionally discarding local work.

**Scope** { #scope }
:   Global user-level exposure versus one consumer project's exposure; neither is library membership. Defaults vary by verb; [scope rules](agent-toolkit/cli.md#scope-and-target-selection). A Git repository alone does not establish the default.

**General** { #general }
:   Older terminology for shared convergence placement. The CLI token is `standard`, not `general` or `universal`.

**Projection** { #projection }
:   Actual harness-visible link, translated file or named config entry. It can be missing/conflicted despite recorded metadata. Instructions installation truth is the actual pointer; canonical-source-chain participants are protected from removal.

**Mechanism** { #mechanism }
:   Native discovery (no projection), symlink, Instructions pointer, translated managed file, config entry + artifact, or dual symlink. Individual guarded writes do not imply cross-kind atomicity or universal rollback.

## State and compatibility

**Lock file** { #lock-file }
:   Source-backed per-scope source/ref/SHA and optional projection metadata, or MCP's per-scope projection records. Not proof that files/config entries exist. Instructions has no installation lock; old locks are ignored/preserved. [Formats](agent-toolkit/lock-files.md).

**Doctor** { #doctor }
:   Kind-specific diagnostics. MCP/Commands doctors are read-only. Other kinds offer only supported, explicitly confirmed repairs; Instructions regular-file adoption is opt-in, never content merging.

**Verdict** { #verdict }
:   A researched per-kind classification: native/supported mechanism, toolkit gap, not applicable, or unknown. Scope and enabled adapter status still matter.

**SSOT** { #ssot }
:   Single source of truth. [`harness-matrix.md`](agent-toolkit/harness-matrix.md) contains machine-read Instructions/subagent verdicts and is packaged in the wheel. Skills catalog and maintained generator constants supply other generated views; run `scripts/gen_harness_docs.py`, never hand-edit generated pages.

**Adapter** { #adapter }
:   Code implementing a kind/harness projection and its ownership guards. A researched supported mechanism can have a disabled adapter (e.g. Codex/Firebender subagents). Check the generated harness page rather than inferring enabled support from a tick.
