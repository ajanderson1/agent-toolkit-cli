# Plan: agent (subagent) kind — PR3 → PR5 (finish #252)

- **Date:** 2026-05-30
- **Issue:** #252 (agent / subagent kind, v3.1.0)
- **Predecessors:** PR1 (kind-dimension foundation, #267), PR2 (#268 merged `98257bb` — install machinery: symlink + translate, 24 supported paths)
- **Companion decision:** `docs/superpowers/specs/2026-05-30-agent-kind-disabled-cells-decision.md`
- **Author:** planning agent
- **Builder note:** the merged PR2 code (`agent_install.py`, `agent_lock.py`, `agent_paths.py`, `agent_adapters/`, `subagent_mechanism` on `AgentConfig`) is on `origin/main` (`aff5467`). **Rebase onto latest `origin/main` before any work** — older local checkouts predate the merge. PR #285 already removed the throwaway PR2 scope-guard.

## Where #252 stands

PR2 shipped symlink (15) + translate (9). It deferred the 4 `config_file_folder` cells at `subagent_mechanism="none"`. **Reading the merged adapter changed the picture:** `aider-desk` and `dexto` write only self-owned per-slug files (no shared-file mutation) — they are effectively translate-shaped and safe to enable. Only `firebender` (mutates hot-reloaded `firebender.json`) and `codex` (mutates shared `config.toml`; registry-gated, no escape hatch) are genuinely high-stakes. See the companion decision for evidence.

Remaining #252 scope:
1. **"Generalize install/lock/paths to a kind dimension"** — **OBSOLETE** (PR3 closes it).
2. **Finish the deferred cells** — enable `aider-desk` + `dexto` (PR4); `codex` + `firebender` need an AJ decision (PR5a, spec-level).
3. **`agent` CLI verb set + `doctor` + TUI KindsSidebar** — #252's CLI/TUI items; PR5b (audit + fill).

## PR sequence

| PR | Scope | Risk | Builder-ready? |
|---|---|---|---|
| **PR3** | `universal`→`general` rename (PR #268 Concern #3) + close the "generalize to kind dimension" item as obsolete + pin per-kind-module architecture | Lowest | **Yes — full Task N below** |
| **PR4** | Enable `aider-desk` + `dexto` (self-owned per-slug writes) | Low | **Yes — full Task N below** |
| **PR5a** | `codex` + `firebender` (shared-registry mutation) | High | Spec-level — **needs AJ decision before building** |
| **PR5b** | `agent` CLI verb group + `doctor` + TUI KindsSidebar (audit then fill) | Low-Medium | Spec-level — scope after audit |

PR3 and PR4 are independent; PR3 first is cleaner (it lands the rename PR #268 named as PR3's opener and settles the architecture the cells slot into). **The lowest-risk next slice is PR3.** PR4 is also low-risk and could run in parallel.

---

## PR3 — `universal`→`general` rename + ratify per-kind modules (close the "generalize" item)

**Lowest-risk next slice. Fully builder-ready.** PR #268 said: *"PR3 starts by deleting `tests/test_cli/test_pr2_scope_guard.py` and renaming `universal`→`general` across the catalog + facades."* PR #285 already deleted the scope-guard, so PR3 = the rename + architecture close-out. No new behaviour for end users.

### Why the #252 "generalize to a kind dimension" item is OBSOLETE

#252 assumed install/lock/paths would grow a single `kind` discriminator (one `*_install.py` taking a `kind` arg, the lockfile gaining a `kind` field). The project instead shipped **parallel modules per kind**, now fact across four kinds:

- skills: `skill_install.py` / `skill_lock.py` / `skill_paths.py`
- agents: `agent_install.py` / `agent_lock.py` (re-export) / `agent_paths.py` (#268)
- instructions: instructions-kind modules (#269/#283, merged)
- pi-extension: `pi_extension_paths.py` / `pi_extension_lock.py` / `_pi_settings.py` (#273/#286, merged)

The shared seam is a kind-agnostic core (`_paths_core` `KindBinding` constants; `skill_lock` as the kind-blind lock primitive) consumed by per-kind facades. The lockfile did NOT get a `kind` discriminator — each kind has its own lock filename and a per-kind path field on the shared `LockEntry` (`skillPath`, `agentPath`, `piExtensionPath`). The dispatcher `get_adapter()` reads `AgentConfig.subagent_mechanism` and lazily imports the mechanism module — a single SSOT catalog, no parallel registry. The #252 "generalize-in-place" alternative was decided against and superseded four times over (memory `project_general_per_kind_convergence`; matches the v3.0.0 refold, deliberately diverges from vercel agents.ts). The item is obsolete, not pending.

### Tasks

#### Task 1 — Confirm the throwaway PR2 scope-guard is gone (defensive)

- **Impl:** verify `tests/test_cli/test_pr2_scope_guard.py` is absent (PR #285 removed it). If your branch still has it, delete it.
- **Commit:** `chore: confirm PR2 scope-guard removed`

#### Task 2 — Rename `universal`→`general`; fix the dual-flagged-cell mis-skip (failing test first)

- **Failing test:** add `tests/test_cli/test_agent_general_rename.py`:
  - assert the agent facade's synthetic name is `general-agent` (not `universal`) and `general-skill` for skills (catalog already has both — verify, don't duplicate).
  - assert the 7 agent cells that are `is_universal=True` but have a real mechanism (codex, cursor, dexto, firebender, gemini-cli, github-copilot, opencode — PR #268 Concern #3) are NOT silently skipped by `_install_core._should_skip_symlink` when installed AS AGENTS at global scope. Pick a currently-enabled one (e.g. `cursor`, symlink mechanism) and assert `agent_install.plan()` includes it. Fails today because `_should_skip_symlink` treats `is_universal` as a generic skip signal.
- **Impl:** rename `universal`→`general` across `skill_agents.py` + `_install_core.py` + facades; make `_should_skip_symlink` kind-aware (skill universals skip at global; agent cells dispatch via `get_adapter()` regardless of `is_universal`).
- **Verify:** new test green; full suite green.
- **Commit:** `refactor: rename universal→general; stop mis-skipping dual-flagged agent cells (#252)`

#### Task 3 — Guard test pinning the per-kind-module architecture

- **Failing test:** `tests/test_cli/test_kind_architecture.py::test_install_is_per_kind_not_discriminated` — assert `agent_install`/`agent_lock`/`agent_paths` import as separate modules AND no agent install/uninstall entrypoint accepts a `kind=` parameter (introspect signatures). Locks current intent; should pass on a correct tree, fail if the architecture drifts toward a discriminator.
- **Impl:** none expected.
- **Commit:** `test: pin per-kind-module architecture for the agent kind (#252)`

#### Task 4 — Document + close the #252 generalize item

- **Impl:** a few-line architecture note (module docstring in `agent_adapters/__init__.py` already states the catalog-as-SSOT/no-parallel-registry design — extend it, or add a `docs/` line) recording that install/lock/paths are intentionally per-kind, the #252 generalize item is closed as obsolete, link this plan.
- **PR body:** tick the #252 "generalize install/lock/paths to a kind dimension" box: "obsolete — superseded by per-kind modules across 4 kinds (#268/#269/#273)."
- **Commit:** `docs: close #252 generalize-to-kind-dimension item as obsolete`

**PR3 done-when:** rename complete; dual-flagged agent cells no longer mis-skipped; architecture guard green; obsolete item documented + ticked; CI green.

---

## PR4 — Enable `aider-desk` + `dexto` (the two self-owned-write cells)

**Builder-ready.** Both approved auto-actionable: the merged adapters write only per-slug self-owned files (no shared mutation), so the PR2 "config-mutation" concern does not apply. Work = (a) flip each cell's `subagent_mechanism` from `"none"` to `"config_file_folder"` and remove it from `test_pr2_disabled_cells_skip_cleanly`'s disabled set; (b) add the install-machinery test battery the cells lack; (c) confirm `_guard_foreign` sentinel handling. One commit pair per cell. **Re-read the merged adapter first** (`agent_adapters/config_file_folder.py`).

### Tasks

#### Task 1 — `aider-desk` round-trip + foreign-guard + both-scope (failing first)

- **Failing tests:**
  - `test_aider_desk_install_uninstall_round_trip` — install at global, then uninstall → `.aider-desk/agents/<slug>/` gone, no orphan; file content matches `{"name","subagent":{"enabled":true},"source":...}`.
  - `test_aider_desk_both_scopes` — global + project install→uninstall; lock records correct scope (note PR #268 Concern #4: global-scope uninstall doesn't drop the lock entry today — mirror skill_install's known shape, don't fix asymmetrically here).
  - `test_aider_desk_guard_foreign` — a pre-existing foreign `config.json` (no `.config.json.attk` sentinel) → install raises `FileExistsError` unless `overwrite=True`; a re-install over our own (sentinel present) succeeds.
  - `test_aider_desk_idempotent` + `test_aider_desk_fail_loud_unwritable_base`.
  - All fail today: dispatcher refuses `aider-desk` (`mechanism="none"`).
- **Impl:** flip `aider-desk` to `"config_file_folder"`; remove from disabled set. **Verify the install path writes the `.config.json.attk` sentinel** so `_guard_foreign` recognises our own file on re-install — if the merged adapter doesn't yet write the sentinel, add it (this is the one gap the foreign-guard contract needs).
- **Commit:** `feat: enable aider-desk subagent install (self-owned per-slug) (#252)`

#### Task 2 — `dexto` global-only round-trip + project-scope refusal (failing first)

- **Failing tests:**
  - `test_dexto_install_uninstall_global` — install global → `home/.dexto/agents/<slug>/<slug>.yml` valid YAML; parse it back and assert the `source: |` block round-trips a MULTI-LINE agent file (regression-guards the block-scalar indentation the PR2 review fixed); uninstall removes the subdir.
  - `test_dexto_project_scope_raises` — project-scope install raises `ValueError` ("global-only"); assert the agent facade/CLI surfaces this as a clean "dexto: global-only" message, not a crash.
  - `test_dexto_guard_foreign` + `test_dexto_idempotent` + `test_dexto_fail_loud_unwritable`.
- **Impl:** flip `dexto` to `"config_file_folder"`; remove from disabled set; add the `.<slug>.yml.attk` sentinel write if missing. Keep the global-only contract — do NOT add project support.
- **Commit:** `feat: enable dexto subagent install (global-only, self-owned) (#252)`

#### Task 3 — matrix-parity + doctor reflect the two new supported cells (failing first)

- **Failing test:** extend `test_subagent_matrix.py` so `aider-desk` + `dexto` are expected SUPPORTED via `config_file_folder`, `codex` + `firebender` remain expected DISABLED **with a reason string**. Update `test_pr2_disabled_cells_skip_cleanly` to 2 cells (codex, firebender), not 4.
- **Impl:** update matrix metadata + any doctor/capability listing so the two cells show supported and the two refused cells surface a human reason ("hot-reloaded IDE registry" / "registry-gated shared config.toml — pending decision") instead of silent omission. Note `dexto` should be flagged global-only in any scope-aware listing.
- **Commit:** `feat: surface aider-desk/dexto supported; codex/firebender reasoned-disabled (#252)`

**PR4 done-when:** `aider-desk` (both scopes) + `dexto` (global-only) install/uninstall round-trip, foreign-guarded with sentinel, idempotent, fail-loud; YAML/JSON parse-back asserted; matrix-parity + disabled-set (now 2) + doctor updated; `codex`/`firebender` still disabled with reasons; CI green.

---

## PR5a — `codex` + `firebender` (shared-registry cells) — SPEC LEVEL, **NEEDS AJ DECISION**

Do not build until AJ rules. Both mutate a shared file; the companion decision recommends KEEP DISABLED for both unless AJ authorizes shared-config mutation. The investigation closed two hypotheticals:

- **codex has NO escape hatch.** The research fragment (re-verified 2026-05-27 vs live codex-rs) confirms discovery is registry-gated: a self-owned `agents/<slug>.toml` is NOT loaded without an `[agents.<slug>]` block in `config.toml`. The OpenSpec `$CODEX_HOME/prompts/` pattern does not apply to subagents. So enabling codex = mutating shared `config.toml`, full stop.
- **firebender** = mutating the hot-reloaded shared `firebender.json`.

### The AJ decision

One question for both: **do we mutate a user's shared config registry to install a subagent?**

- **If YES:** enable both with the existing adapters, hardened to a config-preserve bar:
  - codex: round-trip-preserve test (unrelated keys/sections/comments survive install AND uninstall); cases the section-replace regex could mangle (array-of-tables `[[agents]]`, nested `[agents.<slug>.x]`); a "config.toml is still valid TOML after install and after uninstall" parse test; `$CODEX_HOME` resolution (env → `~/.codex`, already in catalog) test.
  - firebender: round-trip-preserve on `firebender.json`; assert the atomic write + relative-path + append-only (not clobber) behaviour; regression-guard the two PR2-review bugs (callable replace, relative paths).
- **If NO:** keep both disabled; surface clear reasons in doctor/capability output; document codex's registry-gating and firebender's hot-reload as the reasons. This is the recommended default.

**PR5a done-when (post-AJ):** either both cells enabled with config-preserve + valid-after-uninstall tests, OR both documented-disabled with reasons and matrix-parity asserting it.

---

## PR5b — `agent` CLI verb group + `doctor` + TUI KindsSidebar — SPEC LEVEL

#252 calls for a full `agent` command group (`add`/`install`/`uninstall`/`remove`/`import`/`list`/`status`/`update`/`push`/`reset`) + `doctor` learning the agent kind + a TUI `KindsSidebar`. PR2 shipped only the install machinery, not the CLI verbs or TUI. Scope via audit, then fill.

### Task — audit then fill

- **Audit (first):** diff the skill verbs (`commands/skill/*`) and the pi-extension read-only pattern (`commands/pi_extension/*` from #273) against what the agent kind needs. Clone `commands/skill/` → `commands/agent/` with `_common.scope_and_roots` parametrized on the agent lock filename. Honour scope defaults: all verbs default global outside a project, `read_only=True` on `scope_and_roots()` for read commands (memory `project_agent_toolkit_cli_scope_defaults`). `agent add` is global-only by construction (memory `project_skill_add_global_only`).
- **`agent import`** in scope per #252 (read_only library reconstruction, monorepo parent-symlink, `--latest`); `agentPath` must round-trip through import.
- **`doctor`:** the `kind_noun` parametrization landed in PR #268 (`_doctor_hint`). Wire agent doctor to repair agent symlinks/translate outputs as skill doctor does; clear stray legacy symlinks ("conflicting symlink" — memory `project_tui_apply_error_clobber`).
- **TUI KindsSidebar:** left rail switching Skills / Agents (per-kind counts, `1`/`2` hotkeys), other kinds dormant. Honour the universal-vs-additional grid model (memory `project_universal_agents_model`: universals toggle as a group; grid = one `general` col + Claude Code + Pi + collapsible long-tail). Avoid Textual `_render_*` method names (memory `feedback_textual_render_methods`).
- **Fill:** per confirmed gap, TDD failing test → impl → commit. Document intentionally-N/A verbs rather than leaving them silently missing.
- **Done-when:** agent kind has CLI + doctor + TUI parity with the skill kind for the verbs that make sense; intentional N/As documented.

---

## Cross-cutting requirements (all PRs)

- **TDD throughout** (superpowers `test-driven-development`): every behavioural change is a failing test first.
- **Install-machinery learning** on every enabled cell: install→uninstall round-trip + both-scope (or documented global-only) + config-preserve (shared cells) + foreign-guard (sentinel). Atomic write + `_guard_foreign` already exist in the adapter — use them.
- **Fail loud** on unwritable dirs / malformed configs / unknown schema — never silently skip a cell.
- **CI shallow-clone caveat:** diff-based scope guards break under `actions/checkout` fetch-depth=1; inherit the `pytest.skip` fallback (#267) for any new scope-guard test (memory `feedback_ci_shallow_clone_scope_guard`).
- **Release:** conventional PR-title prefixes (`feat:`/`test:`/`docs:`) so release-please cuts v3.1.0 (memory `project_flow_pr_titles_skip_release_please`).
- **No `config.toml` / `firebender.json` mutation** ships without an explicit AJ decision (PR5a) — PR4 touches neither.
- **Rebase onto latest `origin/main` first** — the agent kind code is merged but post-dates older local checkouts.
