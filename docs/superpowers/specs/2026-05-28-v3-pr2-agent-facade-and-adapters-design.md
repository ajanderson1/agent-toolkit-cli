# PR2 of #252 — Agent facade + 28 projection adapters

**Slice of #252.** Second of five PRs that together reintroduce the
`agent` (subagent) asset kind. PR1 cut the kind-agnostic seam
(`_install_core.py`, `_paths_core.py`, `KindBinding`); PR2 builds on
that seam and ships the *first user-visible v3 capability*: an
installed `agent` kind that lands files at every supported harness's
real subagent path.

Refs #252. Issue stays open; PR5 closes it.

## Scope (bundled per user choice)

Two chunks land together:

1. **Agent facade** — `agent_install.py`, `agent_paths.py`, `agent_lock.py`
   binding `AGENT_BINDING = KindBinding(kind="agent", ...)` over the
   existing kind-agnostic core. Pure mirror of PR1's `skill_*` facade
   pattern. **No mechanism dispatch here** — the facade is mechanism-blind.
2. **28 projection adapters** — one per supported subagent cell from
   `docs/agent-toolkit/harness-matrix.md`, grouped by mechanism: `symlink`
   (14), `translate` (9), `config_file+folder` (4), `dual-symlink` (1 — pi).
   Each adapter owns: where the agent file lands on disk + what its
   on-disk shape is + how to install/uninstall/round-trip it.

Bundled scope acknowledged upfront: this is the largest PR of the
sequence. Reviewer's blast radius is `agent_*.py` (small) + four
mechanism implementations + 28 cell-level adapters (mostly mechanical
once the four mechanisms exist). The acceptance criteria below give the
reviewer a checklist that scales.

## Open architecture decisions resolved upfront

Three decisions PR2 must make before any code is written. Resolved here
so build phase has no design drift.

### Decision 1: Where mechanism dispatch lives

**Resolution: per-harness adapter module, dispatched by mechanism field on `AgentConfig`.**

Add a single new field on `AgentConfig` (`skill_agents.py`):

```python
agent_mechanism: Literal["symlink", "translate", "config_file_folder", "dual_symlink", "none"] = "none"
```

`"none"` is the default (so all unsupported / by-design / unknown
cells stay zero-config). The 28 supported cells set the literal
matching their matrix verdict. The facade reads this field to pick an
adapter; the adapter implements `install_agent(slug, content, scope, …)`
and `uninstall_agent(slug, scope, …)`. The 14 `symlink` cells share a
single adapter parameterised by the per-cell destination directory; the
9 `translate` cells split into 5 sub-adapters (one per output format —
strict-yaml-only, json, toml, recursive-yaml, suffix-rename); the 4
`config_file_folder` cells share a "registry+file" adapter
parameterised by registry path + spawnable-flag key; the 1 `dual_symlink`
cell (pi) has its own adapter handling the two write sites.

**Alternative considered:** a stand-alone registry in `agent_adapters/__init__.py`
mapping `harness_name → adapter`. Rejected: duplicates the catalog
indirection PR1 already established (`AGENTS` dict is the single source
of harness facts; mechanism is a harness fact, not adapter-state).

### Decision 2: How `agent_lock.py` records the agent file path

**Resolution: use `LockEntry.extras["agent_path"]`. No new dataclass field.**

`LockEntry` today has `skill_path: str | None` for skills' SKILL.md
location. Adding `agent_path: str | None` would mean changing the
dataclass — touching `read_lock`, `write_lock`, `_V1_ENTRY_FIELDS`,
`_V3_ENTRY_FIELDS`, and risking lockfile-version churn for cosmetics.
`extras` exists exactly for kind-specific keys (see how `installedAt`,
`pluginName`, `sourceUrl` are round-tripped through it in
`_entry_from_dict_v3`/`_entry_to_dict_v3`). `agent_lock.py`'s reader
will pull `agent_path = entry.extras.get("agent_path")`; the writer
will put it back. No format version bump. Both
`skills-lock.json` and `agents-lock.json` use the same `LockFile`
struct, distinguished only by `KindBinding.lock_filename`.

**Acceptance criterion #6 (below) pins this:** any agent entry written
by the agent facade and re-read by the agent facade round-trips
losslessly through both v1 and v3 lockfile formats.

### Decision 3: Where adapter modules live on disk

**Resolution: `src/agent_toolkit_cli/agent_adapters/<mechanism>.py`.**

Four mechanism files:

- `agent_adapters/symlink.py` — handles all 14 symlink cells.
- `agent_adapters/translate.py` — dispatches into 5 per-format helpers.
- `agent_adapters/config_file_folder.py` — handles the 4 registry-pointed cells.
- `agent_adapters/dual_symlink.py` — handles pi.

Plus `agent_adapters/__init__.py` exposing a single `get_adapter(harness_name)`
that reads `AGENTS[harness_name].agent_mechanism` and returns the matching
module. Per-cell quirks (recursive discovery, suffix rename, reserved
names, name validation) live in per-cell dicts inside the mechanism
module — not as separate adapter classes per harness, which would
explode to 28 files. Mechanism = code path; cell = data row.

**Alternative considered:** `src/agent_toolkit_cli/adapters/agent/<harness>.py`
(one file per harness). Rejected: 28 files for 4 patterns is wrong
factoring; reviewers would have to spot-check each, and reuse becomes
copy-paste.

## What ships

### Code

- **`src/agent_toolkit_cli/_paths_core.py`** — additive: `AGENT_BINDING = KindBinding(kind="agent", canonical_dirname="agents", library_subdir="agents", lock_filename="agents-lock.json", general_harness_name="general-agent")`. Existing `SKILL_BINDING` untouched.
- **`src/agent_toolkit_cli/agent_paths.py`** (new) — mirror of `skill_paths.py`. Same public symbols renamed: `canonical_agent_dir`, `library_agent_path`, etc. One-line delegations through `library_root_for_kind(AGENT_BINDING, …)` / `library_lock_path_for_kind(AGENT_BINDING, …)`.
- **`src/agent_toolkit_cli/agent_install.py`** (new) — mirror of `skill_install.py`. Defines `_AGENT_SYNTHETIC_NAMES = frozenset({"general-agent"})` (no `"universal"` — that's skill-only by PR1's by-design fact). `plan()` and `_current_linked_agents()` shims pass `synthetic_names=_AGENT_SYNTHETIC_NAMES` and `universal_bundle_link=None` (agents don't bundle into a universal megaprompt). `apply()` calls the per-harness adapter from `agent_adapters.get_adapter(harness_name)` instead of unconditional `symlink_to`.
- **`src/agent_toolkit_cli/agent_lock.py`** (new) — mirror of `skill_lock.py`. Re-uses the same `LockEntry`/`LockFile` from `skill_lock.py` (they are kind-blind); ships its own `read_lock`/`write_lock` only if the agent format needs to diverge. Otherwise re-exports from `skill_lock` and the divergence is reserved for a future PR.
- **`src/agent_toolkit_cli/agent_adapters/`** (new package) — `symlink.py`, `translate.py`, `config_file_folder.py`, `dual_symlink.py`, `__init__.py`. Public API: `get_adapter(harness_name) -> AgentAdapter`; `AgentAdapter` exposes `install(slug, content_path, *, scope, home, project)` and `uninstall(slug, *, scope, home, project)`. Each adapter is a function (not a class) where possible.
- **`src/agent_toolkit_cli/skill_agents.py`** — modify `AgentConfig`: add `agent_mechanism: Literal["symlink", "translate", "config_file_folder", "dual_symlink", "none"] = "none"`. Set the 28 supported cells to their matrix mechanism. Add a `"general-agent"` synthetic entry mirroring `"general-skill"`. Now 57 catalog entries (54 real + `universal` + `general-skill` + `general-agent`).
- **`src/agent_toolkit_cli/commands/`** — no changes in PR2. The new `agent` CLI verb group is PR4. PR2 ships only the engine and the adapters; user-visible CLI is added in PR4 *unchanged from PR1*. PR2 is invokable from Python (and from tests) but not from the CLI yet.

### Tests

All test additions must execute the new code paths; none may be doc-only.

- **`tests/test_cli/test_agent_paths.py`** (new) — pin `agent_paths`'s public-symbol surface (mirror of `test_skill_facade_parity.py` § `skill_paths`). Mirrored sweep of every test in `test_paths_core.py` for `AGENT_BINDING`.
- **`tests/test_cli/test_agent_install.py`** (new) — `plan()` shim binds `_AGENT_SYNTHETIC_NAMES`; `apply()` invokes the correct adapter for each mechanism; uninstall + reinstall are idempotent; lock round-trip preserves `agent_path` via `extras`.
- **`tests/test_cli/test_agent_lock.py`** (new) — write + read + add_entry + remove_entry with `agent_path` in `extras`; round-trip through both v1 and v3 formats.
- **`tests/test_cli/test_agent_adapters/`** (new directory) — one file per mechanism: `test_symlink.py`, `test_translate.py`, `test_config_file_folder.py`, `test_dual_symlink.py`. Per-mechanism shape tests; per-cell quirk tests (gemini-cli `.strict()` rejection; copilot `.agent.md` suffix; codex `config.toml` mutation; pi dual-write).
- **`tests/test_cli/test_skill_agents.py`** — extend catalog-size test for 57 entries; add a `agent_mechanism` field-existence test; add a "every matrix-supported row has a non-`none` mechanism" parity test.
- **`tests/test_subagent_matrix.py`** — extend `_catalog_harnesses()` synthetic exclusion to `{"universal", "general-skill", "general-agent"}` (one-line change). Add a new test `test_supported_rows_have_matching_adapter` that for every supported matrix row imports `agent_adapters.get_adapter(harness)` and asserts it doesn't raise. (This is the parity-test coupling Phase A flagged as a Phase B deliverable.)
- **`tests/test_cli/test_pr2_scope_guard.py`** (throwaway) — same shape as PR1's scope guard, with `pytest.skip` fallback for shallow CI clones (per `feedback_ci_shallow_clone_scope_guard`). Deleted at the start of PR3.

### Docs

- **`docs/agent-toolkit/harness-matrix.md`** — no change. The matrix is already the source of truth for which cells should be supported. PR2 makes it executable.

## Public API contract (what must not break)

Every name in the table below remains callable from outside the
module with the same signature, the same return type, and the same
exception types. Implementations may move; import paths do not.

| Module | Names preserved (unchanged from main as of f3508f2) |
|---|---|
| `skill_install` | `InstallError`, `LockMismatchError`, `DirtyCanonicalError`, `InstallPlan`, `InstallResult`, `plan`, `apply`, `install`, `uninstall`, `migrate_project_canonical`, `ensure_project_canonical`, `_universal_bundle_link`, `_project_universal_link` |
| `skill_paths` | `Scope`, `canonical_skill_dir`, `lock_file_path`, `library_root`, `library_skill_path`, `library_lock_path`, `project_id`, `project_store_root`, `project_parents_root`, `parent_clone_path`, `agent_projection_dir`, `harness_projection_dir`, `SUPPORTED_HARNESSES` |
| `skill_lock` | `LockEntry`, `LockFile`, `SUPPORTED_VERSIONS`, `read_lock`, `write_lock`, `add_entry`, `remove_entry`, `clone_url_from_entry` |
| `_install_core` | All current symbols. `_current_linked_agents` signature unchanged. |
| `_paths_core` | All current symbols. `KindBinding` unchanged. `SKILL_BINDING` unchanged. `AGENT_BINDING` **added**. |
| `skill_agents` | `AgentConfig` (with new optional `agent_mechanism` field — default `"none"` keeps every existing caller working), `AGENTS`, `is_universal`, `get_universal_agents`, `UnknownAgentError` |

| Module | Names introduced (new, callable by PR2 itself and PR4+) |
|---|---|
| `agent_paths` | `Scope`, `canonical_agent_dir`, `lock_file_path`, `library_root`, `library_agent_path`, `library_lock_path`, plus shared helpers (`project_id`, `project_store_root`, `project_parents_root`, `parent_clone_path` — re-exported or re-implemented mirroring `skill_paths`) |
| `agent_install` | `InstallError`, `LockMismatchError`, `DirtyCanonicalError`, `InstallPlan`, `InstallResult`, `plan`, `apply`, `install`, `uninstall` |
| `agent_lock` | `LockEntry`, `LockFile`, `SUPPORTED_VERSIONS`, `read_lock`, `write_lock`, `add_entry`, `remove_entry` (likely re-exported from `skill_lock` initially) |
| `agent_adapters` | `get_adapter(harness_name) -> AgentAdapter`; `AgentAdapter` protocol (`install`, `uninstall`) |

## Acceptance criteria

PR2 is done when **all** of these hold simultaneously:

1. **Zero existing tests modified.** Every test in `tests/` that passed on `f3508f2` (main as of PR1 merge) still passes byte-identical, except for the catalog-size assertion (54+1+1 → 54+1+1+1 = 57) and the synthetic-exclusion set in `test_subagent_matrix.py`. These are mechanical bumps, not behavioural changes.
2. **No callers of any `skill_*` module need to be edited.** `commands/skill/`, `tui/`, `skill_doctor.py`, etc. all build against the same public surface PR1 froze.
3. **The 28 supported cells are *installable*** through `agent_install.install()` — each adapter produces the file/symlink/registry entry the matrix row describes. Smoke-tested by a parametrised pytest that iterates the 28 cells in a tmp HOME.
4. **Lockfile round-trip is lossless** for both kinds in both v1 and v3 formats. An agent entry written by `agent_lock.write_lock` and re-read by `agent_lock.read_lock` reproduces the original `LockEntry` exactly, including `extras["agent_path"]`. A skill entry round-trips unchanged.
5. **Matrix parity test asserts mechanism alignment** — every supported row in `harness-matrix.md` has an `agent_mechanism` value on its `AgentConfig` matching the row's verdict prefix. Failures produce a one-line diagnostic naming the harness + the divergence.
6. **No CLI surface change.** `agent-toolkit-cli --help` output is byte-identical to main. `commands/agent/` does not exist. (PR4 introduces it.)
7. **The four mechanisms are not co-mingled.** No `symlink.py` adapter imports from `translate.py`. Each mechanism's code is self-contained; the only shared abstraction is the `AgentAdapter` protocol.
8. **Scope guard passes (with skip fallback for CI shallow clones).** `tests/test_cli/test_pr2_scope_guard.py` enforces the file-allowlist. Caller-module edits are forbidden; spec deviation needs explicit allowlist entry with `# why` comment.

## Spec deviations allowed (and that's a feature)

PR1 deviated from its plan three times — each documented in commit
messages and the PR body. That discipline carries forward here.

If the build phase discovers that:

- A new mechanism shape is needed (e.g. a 29th cell with no matrix
  match) — **deviate**, document in the commit + PR body.
- The `agent_path` in `extras` collides with an existing extras key for
  some reason — **deviate**, add a real `LockEntry` field after the
  receiving-code-review pass weighs the lockfile-churn cost.
- The `agent_adapters/` package needs a 5th file (e.g. a `_shared.py`
  helper) — **deviate**, justify in the commit message.

Spec deviations that mean acceptance criterion #1, #2, #4, or #6 fails
are NOT permitted without raising a safety stop and re-soliciting user
approval.

## What's explicitly out of scope (and why)

- **CLI `agent` verb group.** PR4. Adding the CLI surface in PR2 doubles
  the review burden for no functional gain — PR2's adapters work from
  Python today; PR4 is the wrapping.
- **`universal` → `general` rename.** PR3. The synthetic-set widening
  to include `"general-agent"` is the *only* general-* change PR2 makes;
  the larger rename (field renames, `is_universal` → `is_general`,
  removal of `"universal"` synthetic, UI label updates) is reserved.
- **TUI `KindsSidebar`.** PR5.
- **A new lockfile format version.** The `agents-lock.json` ships in v1
  format (no `kind:` field; kind owned by the filename). If a future PR
  wants kind discrimination *inside* a single file, it'll be a v4 spec
  change with its own brainstorm.
- **`agent reset` / `agent doctor`.** PR4 introduces the CLI verbs; PR2
  ensures the engine they'll call exists.

## How this connects to PR3 / PR4 / PR5

- **PR3** does the `universal`→`general` rename across `skill_agents.py`,
  `skill_install.py`, the TUI, and the CLI labels. PR2 introduces
  `"general-agent"` as a new entry parallel to `"general-skill"` (which
  PR1 added) so PR3's rename has both halves to work with.
- **PR4** introduces `commands/agent/__init__.py` mirroring
  `commands/skill/__init__.py`, with `add`, `install`, `uninstall`,
  `remove`, `import`, `list`, `status`, `update`, `push`, `reset` verbs
  + `doctor` learning the agent kind. PR4's verbs call into
  `agent_install`, `agent_paths`, `agent_lock` — the modules PR2 builds.
- **PR5** introduces the TUI `KindsSidebar` switching skills / agents.
  PR5 calls into `agent_paths.library_root()`, `agent_install.install()`,
  etc. — built in PR2.

## Test plan

| Layer | Test files | What they prove |
|---|---|---|
| Binding | `test_agent_paths.py` | `AGENT_BINDING` resolves to `~/.agent-toolkit/agents/` (override via env vars TBD), `agents-lock.json` lives at the right place, public surface frozen. |
| Engine | `test_agent_install.py` | `plan()` injects `_AGENT_SYNTHETIC_NAMES`; `apply()` invokes the right adapter; uninstall is idempotent. |
| Lock | `test_agent_lock.py` | Round-trip of `agent_path` in `extras` for v1 + v3. |
| Adapter mechanism | `test_agent_adapters/test_symlink.py` etc. | Each mechanism produces the on-disk shape the matrix describes; cell-level quirks honoured. |
| Catalog parity | `test_skill_agents.py` (extended) + `test_subagent_matrix.py` (extended) | Every supported matrix row has a matching `agent_mechanism` + adapter. |
| Public API | `test_skill_facade_parity.py` (unchanged) + new `test_agent_facade_parity.py` | PR1's facade contract still holds; PR2's facade contract pinned. |
| Smoke (end-to-end) | parametrised test in `test_agent_install.py` | Iterate the 28 supported cells in tmp HOMEs; install agent; assert file exists at matrix-table path. |
| Scope guard | `test_pr2_scope_guard.py` (throwaway) | Diff vs `origin/main` stays inside ALLOWED file set. Skip-on-CI fallback included. |

## Verification (post-build)

The verify step will exercise:

1. `uv run pytest -q` — full suite must be green.
2. CLI smoke: `agent-toolkit-cli --help` (no agent verbs yet — confirms #6).
3. Python smoke against a fake HOME: `from agent_toolkit_cli import agent_install; agent_install.install("test-agent", target_harnesses=["claude-code", "codex", "gemini-cli", "pi"], …)` and inspect the resulting tree.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| 28 cells means 28 bug surfaces. | Matrix parity test catches structural mismatches; per-cell smoke tests catch behavioural ones; the four mechanism modules contain the algorithmic surface. |
| Translate adapters need 5 sub-formats (yaml-strict, json, toml, suffix-rename, recursive-yaml). | Each gets its own helper inside `translate.py` with a fixture-driven test. |
| `codex` adapter has to mutate `config.toml` (concurrent-write risk if two installs run at once). | Use atomic file-replace pattern (write to `.tmp` + rename); document in adapter docstring. |
| `pi` matrix row flagged as needing verification (the `~/.agents/` global slot may now be skills not agents). | Spec defers to `~/.pi/agent/agents/<slug>.md` (the third-party-extension path) as canonical; legacy `~/.agents/` global slot is **NOT** written by PR2. If user reports need, PR2.5 can add. Memory updated. |
| Lockfile schema drift if `extras["agent_path"]` collides with a future v3+ field. | Acceptance criterion #4 (round-trip) catches collision in tests. v3 has no `agent_path` field today (per `_V3_ENTRY_FIELDS`); future v3+ would have to migrate before colliding. |

## Build sub-skill

The writing-plans skill should produce a plan suitable for
`superpowers:subagent-driven-development`. Estimated task count: 8-12
(facade × 3 modules; mechanism × 4 modules + their tests; parity test
extension; scope guard; smoke harness; doc updates). TDD throughout.
Fresh implementer subagent per task with two-stage review after each.

---

# Addendum: Risk resolution (research findings, 2026-05-28)

This section documents the live verification of every assumption the spec
above made. Each finding **overrides** any conflicting statement earlier
in the spec. The five research clusters were dispatched as background
subagents during the spec-acceptance gate; findings here are cited to
upstream docs / source so PR3..PR5 inherit verified ground truth.

## Spec-level corrections triggered by research

These supersede earlier sections of this spec. Build phase MUST follow
these, not the original text.

### Correction A: Mechanism taxonomy collapses 4 → 3

| Original spec | Verified mechanism | Why |
|---|---|---|
| `symlink` (14) | **`symlink` (15)** — gains `pi` | `pi` writes a single .md per slug to `~/.pi/agent/agents/`. No second write site. Phase A's "dual-symlink" was a misread of cross-harness convergence (which is a *read* convention, not a write convention). |
| `translate` (9) | **`translate` (10)** — gains `codex` | Codex auto-discovers `~/.codex/agents/*.toml`. No `config.toml` registration. Adapter writes one TOML per agent — translate-class behaviour. |
| `config_file+folder` (4) | **`config_file+folder` (3)** — loses `codex`, gains nothing | Now: `aider-desk`, `dexto`, `firebender`. `codex` moves out. |
| `dual_symlink` (1) | **REMOVED** — empty group | `pi` was the only member; it's actually plain symlink. |

**Build implication:** `agent_adapters/` package ships **three** mechanism
modules: `symlink.py`, `translate.py`, `config_file_folder.py`. The
`dual_symlink.py` file proposed in Decision 3 is NOT created.

### Correction B: Lockfile `agent_path` is a real LockEntry field, NOT extras

Original Decision 2 said "use `LockEntry.extras['agent_path']`". After
re-reading `skill_lock.py`, `skill_path: str | None = None` is a real
top-level field on `LockEntry`, serialised explicitly as `"skillPath"`
in both v1 and v3. Adding `agent_path` to `extras` breaks symmetry.

**Resolved:** add `agent_path: str | None = None` as a real top-level
field on `LockEntry`. Serialise as `"agentPath"` (camelCase parity with
`skillPath`, `sourceUrl`, `skillFolderHash`). Read it back in both
`_entry_from_dict_v1` and `_entry_from_dict_v3`. Append `"agentPath"`
to `_V1_ENTRY_FIELDS` and `_V3_ENTRY_FIELDS` so it's recognised as a
known key (not stashed into `extras` on read).

**Collision check (Cluster E):** vercel-labs/skills @ v1.5.9 has no
`extras` bag, no `agent_path`/`agentPath`/`agent_file` key, no `agent`
kind concept. Collision risk = **none**. `agentPath` camelCase matches
upstream conventions in case vercel adopts an agent kind later.

### Correction C: AgentConfig field name

Original spec proposed `agent_mechanism` as the new field. To avoid
overloading the word "agent" (which already means "harness" in this
catalog AND now means "asset kind"), the field is renamed:

**`agent_mechanism` → `subagent_mechanism`**.

The field's domain (which harnesses support subagent installation, and
how) makes "subagent" the precise term. The literal values stay the same:
`Literal["symlink", "translate", "config_file_folder", "none"]`
(dual_symlink dropped per Correction A).

## Per-harness verified facts (28 cells)

Format: harness name → mechanism, global path, project path, format,
required frontmatter, key adapter quirks, citation.

### symlink (15 cells — write single .md to harness's agents/ dir)

| Harness | Global path | Project path | Format / required | Quirks | Cite |
|---|---|---|---|---|---|
| `augment` | `~/.augment/agents/<slug>.md` | `.augment/agents/<slug>.md` | md+frontmatter; `name` req | `tools`/`disabled_tools` mutually exclusive | Phase A batch-8 |
| `claude-code` | `~/.claude/agents/<slug>.md` | `.claude/agents/<slug>.md` | md+frontmatter; `name`+`description` req | Recursive discovery; 15 optional fields; extras ignored | Phase A batch-1 |
| `codebuddy` | `~/.codebuddy/agents/<slug>.md` | `.codebuddy/agents/<slug>.md` | md+frontmatter; `name`+`description` req | `name` must be lowercase+hyphens | Phase A batch-8 |
| `command-code` | `~/.commandcode/agents/<slug>.md` | `.commandcode/agents/<slug>.md` | md+frontmatter | Reserved names blocked: `explore`, `plan`, `review`, `general` | Phase A batch-1 |
| `cortex` | `~/.snowflake/cortex/agents/<slug>.md` | `.cortex/agents/<slug>.md` | md+frontmatter | **DO NOT write to `~/.claude/agents/` or `.claude/agents/`** (claude-code's territory; collision). Cortex reads those as convergence; never writes there. | https://docs.snowflake.com/en/user-guide/cortex-code/extensibility |
| `cursor` | `~/.cursor/agents/<slug>.md` | `.cursor/agents/<slug>.md` | md+frontmatter; nothing required | Optional: `name`, `description`, `model` (default `inherit`), `readonly`, `is_background`. Strict-mode UNVERIFIED. | https://cursor.com/docs/subagents |
| `droid` | `~/.factory/droids/<slug>.md` | `.factory/droids/<slug>.md` | md+frontmatter | Dir is `droids/` not `agents/`; name restricted `lc/digits/-/_` | Phase A batch-7 |
| `forgecode` | `~/.forge/agents/<slug>.md` | `.forge/agents/<slug>.md` | md+frontmatter | `id` auto-derived from filename; project > global; legacy `~/forge/agents/` global also read | Phase A batch-8 |
| `junie` | `~/.junie/agents/<slug>.md` | `.junie/agents/<slug>.md` | md+frontmatter | Also reads `~/.agents/` + `.agents/` as fallback global (skill territory — DO NOT write there) | Phase A batch-6 |
| `kode` | `~/.claude/agents/<slug>.md` AND `~/.kode/agents/<slug>.md` (kode reads both) | `.claude/agents/<slug>.md` | md+frontmatter; `description` req | `model` deprecated → `model_name`. Write to `~/.kode/agents/` (kode-private); `.claude/agents/` is claude-code adapter's job. | Phase A batch-1 |
| `neovate` | `~/.neovate/agents/<slug>.md` | `.neovate/agents/<slug>.md` | md+frontmatter | `name` ≤64, `description` ≤1024. Also reads `.claude/agents/` (don't write there from neovate adapter). | Phase A batch-4 |
| `pi` | `~/.pi/agent/agents/<slug>.md` (env override `$PI_CODING_AGENT_DIR/agents/`) | `.pi/agents/<slug>.md` | md+frontmatter | Optional: `description`, `tools`, `model`, `thinking`, `max_turns`. **DO NOT write to `~/.agents/` or `.agents/`** (those are pi *skills* paths per the @tintinweb/pi-subagents README). | https://github.com/tintinweb/pi-subagents |
| `pochi` | `~/.pochi/agents/<name>.md` | `.pochi/agents/<name>.md` | md+frontmatter; `description` req | Spawn via `newTask(<name>)` allowlist | Phase A batch-9 |
| `qoder` | `~/.qoder/agents/<name>.md` | `.qoder/agents/<name>.md` | md+frontmatter; `name`+`description` req | Optional: `tools` (comma-sep), `skills`, `mcpServers` | Phase A batch-6 |
| `rovodev` | `~/.rovodev/subagents/<slug>.md` | `.rovodev/subagents/<slug>.md` | md+frontmatter; `name`+`description`+`tools` (list) req | Dir is `subagents/` not `agents/` | Phase A batch-7 |

### translate (10 cells — reshape frontmatter / non-md format)

| Harness | Global path | Project path | Format | Required | Adapter must do / not do | Cite |
|---|---|---|---|---|---|---|
| `codex` | `~/.codex/agents/<name>.toml` | `.codex/agents/<name>.toml` | TOML | `name`, `description`, `developer_instructions` | Map our canonical prompt → `developer_instructions`. Optional: `model`, `model_reasoning_effort`, `sandbox_mode`, `mcp_servers`, `skills.config`, `nickname_candidates`. **DO NOT touch `[agents]` in `config.toml`** (global knobs, not registration). | https://developers.openai.com/codex/subagents |
| `devin` | `~/.config/devin/agents/<profile>/AGENT.md` | `.devin/agents/<profile>/AGENT.md` AND `.agents/agents/<profile>/AGENT.md` | md+frontmatter (file named literally `AGENT.md`) | none | `{profile}` has **no user-default**; adapter requires a `profile` arg (or default convention slug like `default`). Devin also reads `.claude/agents/*.md` and auto-translates `tools`↔`allowed-tools`. | https://cli.devin.ai/docs/subagents |
| `gemini-cli` | `~/.gemini/agents/<slug>.md` | `.gemini/agents/<slug>.md` | md+frontmatter; **zod `.strict()`** | `name`, `description` | Adapter must filter frontmatter to allowed 10-field set (`name`, `description`, `display_name`, `tools`, `mcp_servers`, `model`, `temperature`, `max_turns`, `timeout_mins`, `kind`). Extras throw at load time. | https://github.com/google-gemini/gemini-cli/blob/main/packages/core/src/agents/agentLoader.ts |
| `github-copilot` | `~/.copilot/agents/<name>.agent.md` | `.github/agents/<name>.agent.md` (NOT `.copilot/`) | md+frontmatter | `description` (string) | Always emit `.agent.md` suffix (works in CLI + IDE + Cloud Coding Agent). Optional pass-through: `name`, `target`, `tools`, `model`, `disable-model-invocation`, `user-invocable`, `infer`, `mcp-servers`, `metadata`. No documented reserved-name list. | https://docs.github.com/en/copilot/reference/custom-agents-configuration |
| `kilo` | `~/.config/kilo/agent/<slug>.md` (singular `agent/`) | `.kilo/agents/<slug>.md` (plural `agents/`) | md+frontmatter | none documented | Must inject `mode: subagent` in frontmatter to restrict to `task`-tool invocation. Note global path is singular, project path is plural — adapter must handle the asymmetry. | Phase A batch-6 |
| `kiro-cli` | `~/.kiro/agents/<name>.json` | `.kiro/agents/<name>.json` | JSON (not markdown) | none | Filename (sans `.json`) = agent ID (overridable via explicit `name`). Always emit `prompt` (no implicit fallback). `prompt` accepts `file://` URI for externalization. | https://kiro.dev/docs/cli/custom-agents/configuration-reference/ |
| `mistral-vibe` | `~/.vibe/agents/<name>.toml` | `.vibe/agents/<name>.toml` | TOML | `agent_type` (must be exactly `"subagent"`), `display_name`, `description`, `safety`, `enabled_tools` | `safety` enum: `"safe"|"neutral"|"destructive"|"yolo"` (cosmetic only — doesn't enforce; pair with restrictive `enabled_tools`). Adapter default `safety = "neutral"`. | https://docs.mistral.ai/mistral-vibe/agents-skills |
| `mux` | `~/.mux/agents/<slug>.md` | `.mux/agents/<slug>.md` | md+frontmatter | top-level `subagent:` block with nested `runnable: true` | **Nested form is mandatory** — flat `runnable: true` silently leaves the agent un-spawnable. Optional inside `subagent`: `skip_init_hook`, `append_prompt`. Non-recursive; project overrides user. | https://mux.coder.com/agents |
| `opencode` | `~/.config/opencode/agents/<slug>.md` (PLURAL) | `.opencode/agents/<slug>.md` (PLURAL) | md+frontmatter | none documented | Must inject `mode: subagent`. **Write to plural `agents/` only** — the singular `agent/` path is a CLI bug (issue #14410); docs and runtime loader prefer plural. | https://opencode.ai/docs/agents/ |
| `qwen-code` | `~/.qwen/agents/<slug>.md` | `.qwen/agents/<slug>.md` | md+frontmatter (NOT strict, despite being "Gemini-derived") | none | System prompt = markdown body (NOT a `systemPrompt` frontmatter key — Phase A claim was WRONG). Optional pass-through: `name`, `description`, `model`, `approvalMode`, `tools`, `disallowedTools`. | https://qwenlm.github.io/qwen-code-docs/en/users/features/sub-agents/ |

### config_file+folder (3 cells — registry-pointed)

| Harness | Definition path | Registry file | Registry edit | Spawnable marker | Cite |
|---|---|---|---|---|---|
| `aider-desk` | `~/.aider-desk/agents/<slug>/config.json` (per-slug subdir) | `~/.aider-desk/agents/order.json` (controls sort) | Hot-reloaded; use atomic rename | `subagent.enabled: true` in config.json | Phase A batch-3 |
| `dexto` | `~/.dexto/agents/<agent-id>/<slug>.yml` (YAML, per-agent subdir) | Inside *parent agent's* `tools[].type: agent-spawner` block, `allowedAgents: [...]` array | Per-agent config edit (must touch parent agent's yml to make this agent spawnable). **NO project-scope convention** — global-only writes. | `agent-spawner.allowedAgents` list membership | https://docs.dexto.ai/docs/guides/installing-custom-agents |
| `firebender` | `~/.firebender/agents/<slug>.md` (global, location flexible) OR `.firebender/agents/<slug>.md` (project) | `firebender.json` top-level `{"agents": [...]}` array of string paths | Atomic rename (`os.replace`) — hot-reloaded by IntelliJ plugin watcher. NO CLI exists; must edit JSON ourselves. Round-trip JSON preserving insertion order + unrelated keys. | `callable: true` in agent .md frontmatter, NOT in firebender.json | https://docs.firebender.com/multi-agent/subagents |

### Dropped harness: dual_symlink mechanism (0 cells)

`pi` reclassified to `symlink` per Cluster B finding. Mechanism removed
from the taxonomy entirely; no `dual_symlink.py` adapter file is created.

## Open items the research did not fully resolve

These are noted so the build-phase implementer subagents know to either
defer (with a TODO and a sensible default) or surface a safety stop.

| Open item | Spec disposition |
|---|---|
| **`cursor` strict-mode** — docs silent on whether extras are rejected | Adapter emits only the documented optional set; if cursor adds strict-mode later, adapter is already conservative. Acceptable defer. |
| **`devin` profile default** — no built-in convention for "default" profile name | Adapter requires `profile` arg from caller; if omitted, default to `"default"` (a project-convention slug). Surface in adapter docstring. |
| **`github-copilot` reserved names** — no documented denylist | Adapter does not implement a denylist. If GitHub publishes one, PR2.5 adds it. |
| **`opencode` singular-bug timing** — CLI #14410 may be fixed someday | Adapter writes plural only (docs-canonical). Fix re-checks doc URL quarterly via a `# cite: <url>` comment in the adapter; no runtime check. |
| **`codex` API churn** — multiple May 2026 PRs in codex agent loader | Pin `# cite: developers.openai.com/codex/subagents (verified 2026-05-28)` in adapter. PR3+ may need to re-verify if codex contract shifts. |
| **`codex` #19399 Windows loader bug + #15250 named-invocation gap** — projection succeeds ≠ runtime usability | Acceptance criterion #3 (smoke test) catches projection. Runtime usability is the user's problem; out of PR2 scope. |
| **`dexto` parent-agent edit** — making a new agent spawnable requires editing another agent's yml | Adapter writes the new agent's yml; documents in adapter docstring that the user must register it as spawnable from a parent agent. Out of PR2 scope to traverse the parent-graph. |
| **`junie` `~/.agents/` and `.agents/` reads** — junie reads these as fallback globals, but those paths are skill territory | Adapter writes only to `~/.junie/agents/` and `.junie/agents/`. Junie cross-reading skill paths is a layering issue out of PR2's scope. |
| **`kode` and `neovate` claude-path reads** — both read `~/.claude/agents/` as a convergence | Adapters write only to harness-private paths (`~/.kode/`, `~/.neovate/`). Convergence is a PR3 / PR5 concern (the "shared symlink" question the issue's Open #5 raises). |

## How this addendum's findings feed into PR3..PR5

- **PR3** (`universal`→`general` rename + cross-harness convergence): now
  has a clean list of the cross-harness *read* paths (`~/.claude/agents/`
  is read by 4 harnesses: cortex, kode, neovate, devin). The convergence
  question — single shared symlink vs per-harness explicit slot — gets
  to weigh actual data, not speculation.
- **PR4** (CLI `agent` verb group): can rely on the same engine PR2 ships.
  No verb needs codex's `config.toml` mutation logic (correction A makes
  the engine simpler than originally planned).
- **PR5** (TUI `KindsSidebar`): unaffected by these findings.

## Citation freshness contract

Every adapter file gets a `# cite: <URL> (verified YYYY-MM-DD)` comment
at the top of the per-cell quirks dict. A subsequent PR (or a quarterly
audit skill) can re-fetch the URL and check whether the contract has
drifted. This is the cheapest sustainable answer to the "active churn"
problem cluster A flagged for codex.
