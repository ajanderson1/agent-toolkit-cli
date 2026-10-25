# Expanded Skill Catalogue Collections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make advertised and acquired monorepo children one expandable collection, with preservation-safe selection/Apply and catalogue-independent Git checks.

**Architecture:** Derive presentation groups from normalized Git identities after the existing catalogue/library join; do not persist virtual parents or feed unacquired siblings to installation engines. Freeze pending identities, validate/acquire selected missing children, then use the existing collection journal for one collection/scope across its requested harnesses. Broaden the existing revision-check service and Info without introducing automatic network checks.

**Tech Stack:** Python, Click, Textual, pytest, uv, local disposable Git remotes; no new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-25-expanded-skill-catalog-design.md`.

## Global Constraints

- Baseline: canonical GitHub `origin/main`, `74a41448cab89586fc4b048bd4d423da455e61a1` (6.1.0); isolated branch `feat/catalog-collections`.
- Child identity is normalized Git repository URL + configured ref + repository-relative directory; names are not identity.
- Catalogue version 1 and existing subscription/CLI contracts remain compatible; no schema migration or persisted collection registry.
- Browsing/expansion does not acquire or probe asset repositories; no stale catalogue listing fallback.
- Acquire only selected missing children; preserve backing, pins, local edits, private/legacy scope and foreign destinations.
- Failure unit: one repository/ref collection in one scope, across its requested harnesses. Failed preflight/acquisition leaves its enablement unchanged; projection uses journal rollback; safely acquired library content remains.
- Parent selection includes supported hidden/collapsed members from the observed set, never later additions.
- Git checks are explicit CLI-only; no automatic update, adoption or TUI upstream probing.
- Tests use disposable HOME/config/assets only. Preserve the dirty original checkout, local multi-kind design commit and active old demo worktree.
- No multi-kind implementation, deletion-policy redesign, remote catalogue edits, merge, release, live installation or manual version bump.

## Review Focus

- Same owner/repository on different hosts, or different configured refs at the same commit, must not fold into one identity; Task 1 pins this.
- Duplicate catalogue aliases for one exact selector must not create two actionable acquisitions, while a conflicting local slug must never be overwritten; Task 1 pins this.
- A late catalogue worker result or regrouping must not erase, broaden or redirect queued work, including scope and target; Task 2 pins this.
- A selected advertisement removed/changed between queue and Apply, or one acquisition failing after another succeeds, must not partially activate that collection; Task 3 pins this.
- Non-catalogue, missing/non-Git, private-backed and SHA-pinned library records must receive honest check/Info results without adoption or new source writes; Task 4 pins this.

---

## File responsibilities

- `src/agent_toolkit_cli/skill_catalog_ops.py`: shared normalized child identity and existing safe selector resolution/acquisition; optional supplied snapshot avoids repeated catalogue reads.
- `src/agent_toolkit_tui/skill_state.py`: identity-bearing rows, frozen pending intent data and derived mixed collection grouping.
- `src/agent_toolkit_tui/widgets/skill_grid.py`: existing controls, metadata capture and lossless pending preservation.
- New `src/agent_toolkit_tui/skill_catalog_apply.py`: bounded catalogue-dependent batch validation/acquisition and failure-unit bookkeeping; no projection implementation.
- `src/agent_toolkit_tui/app.py`: integrate preparation with real-record regrouping and one journalled projection call per collection/scope across requested harnesses.
- `src/agent_toolkit_cli/skill_update_check.py`, `commands/skill/check_cmd.py`, `src/agent_toolkit_tui/asset_info.py`: Git checks/Info independent of catalogue provenance.
- New `tests/test_tui/test_skill_catalog_collections.py` and `tests/test_cli/test_skill_check_library.py`; extend existing catalogue/collection tests where their fixtures fit.
- Current references: `docs/agent-toolkit/tui.md`, `docs/agent-toolkit/cli.md`, `docs/asset-types/skills.md`.

### Task 1: Derive one collection from library and advertised children

**Files:** `skill_catalog_ops.py`, `skill_state.py`, `tests/test_tui/test_skill_catalog_collections.py`, existing CLI catalogue acquisition/collection registration tests.

**Interfaces:**
- Add `SkillIdentity = tuple[str, str | None, str]`, `skill_identity(entry: LockEntry) -> SkillIdentity`, and `catalog_identity(item: CatalogSkill) -> SkillIdentity` in `skill_catalog_ops.py`; normalize legacy root `SKILL.md` to directory `.`.
- Add optional `identity: SkillIdentity | None` and `catalog_ref: str | None` row fields, preserving existing constructors.
- Keep `build_skill_rows(...) -> list[SkillRow]` and `merge_catalog_rows(...) -> list[SkillRow]` signatures. Their subscribed result assigns collection keys from repository/ref identity and preserves acquired row identity.

- [ ] Write failing tests `test_catalog_only_siblings_form_one_collection`, `test_mixed_collection_reuses_custom_slug_without_writes`, and `test_distinct_hosts_refs_and_slug_conflicts_do_not_merge`. Assert one derived parent, exact real child count, zero new locks/clones, local row wins, and distinct configured refs/hosts remain separate.
- [ ] Add `test_exact_selector_aliases_have_one_actionable_row`: repeated catalogue selectors collapse to one deterministic representative without writing provenance; conflicting selectors/local identities remain blocked rather than adopted.
- [ ] Add `test_individual_add_then_full_repo_add_folds_without_reacquisition`: custom slug, enabled project child, parent HEAD/index/local file unchanged, new siblings registered but not enabled. Add unused-child removal showing its still-present advertisement again.
- [ ] Run `uv run pytest -q tests/test_tui/test_skill_catalog_collections.py tests/test_cli/test_skill_collection_registration.py tests/test_cli/test_skill_catalog_acquire.py`; confirm the new collection tests fail for missing grouping/identity behavior.
- [ ] Implement identity-based dedup/grouping after the safe join. Leave unmanaged rows and unsupported/ambiguous backing protected. Preserve no-subscription inventory behavior and avoid displaying redundant catalogue membership on acquired children.
- [ ] Rerun the command to green; commit `feat(skills): fold advertised and library children into collections`.

### Task 2: Freeze exact child selection across view changes

**Files:** `skill_state.py`, `widgets/skill_grid.py`, catalogue-collection TUI tests, existing grid collection/pending tests.

**Interfaces:**
- Define frozen `SkillIntent` in `skill_state.py`: `identity: SkillIdentity`, `catalog_url: str | None`, `catalog_ref: str | None`, `catalog_item: CatalogSkill | None`.
- Preserve pending operation keys `(scope, harness, slug)` and link/unlink values. Add `SkillGrid.pending_skill_intents() -> dict[tuple[str, str, str], SkillIntent]`.
- Extend `restore_pending(..., *, intents=None)` compatibly; existing callers remain valid. Row refresh/regrouping must carry original metadata, not regenerate it against changed identities.

- [ ] Write failing tests `test_parent_all_captures_hidden_supported_children`, `test_collapse_filter_and_late_snapshot_preserve_exact_intents`, and `test_new_advertisement_does_not_join_pending_all`. Assert exact operation keys, original selectors and scopes, no acquisition, correct mixed indicator and unchanged queue after a new child appears.
- [ ] Add `test_revert_has_no_library_effect` and stale local/catalogue identity cases. Failed/removed selections must remain explicit pending failures rather than attach to a replacement row with the same slug. Preserve existing cross-scope pending semantics.
- [ ] Run `uv run pytest -q tests/test_tui/test_skill_catalog_collections.py tests/test_tui/test_skill_grid_collections.py tests/test_tui/test_skill_catalog.py`; confirm the new pending-preservation tests fail.
- [ ] Capture intent when controls queue work. Preserve metadata through inventory/worker refresh and regrouping; exclude unavailable/skipped/unmanaged cells. Keep parent operations over the observed member set and existing collapse/filter behavior.
- [ ] Rerun to green; commit `fix(tui): preserve exact skill collection selection intents`.

### Task 3: Apply selected acquisitions with collection-level failure isolation

**Files:** new `skill_catalog_apply.py`, `app.py`, `skill_catalog_ops.py`, catalogue-collection TUI tests, existing catalogue/collection recovery tests. Use existing `skill_collections.apply_selection`/facade rather than replacing its journal.

**Interfaces:**
- Add `CatalogPreparation` with `blocked: set[tuple[str, str, str]]`, `acquired: tuple[str, ...]`, `errors: tuple[str, ...]` in the new module.
- Add `prepare_catalog_acquisitions(pending: dict[tuple[str, str, str], str], intents: dict[tuple[str, str, str], SkillIntent], *, home: Path, project: Path | None) -> CatalogPreparation`.
- Extend `resolve_catalog_skill` with an optional already-fetched snapshot while preserving its existing live-read default. Never interpret an error/absent subscription as a valid empty snapshot.
- Preparation groups keys by normalized repository/ref/scope and blocks all requested keys in a failed unit; it retains acquired content and does not project. App integration handles projection from actual acquired/scoped entries only, batching all requested harness sets for each unit in one existing transaction.

- [ ] Write failing tests `test_all_fetches_catalog_once_and_acquires_only_selected_children`, `test_one_failed_acquisition_leaves_collection_enablement_unchanged`, and `test_unrelated_collection_can_succeed`. Assert retained safe library acquisitions, exact unchanged old exposure for the failed unit, and failed intents retained.
- [ ] Add stale subscription URL/ref, removed/changed selected child, alias/slug conflict, root/nested refusal and foreign destination cases. Invalid metadata/preflight must refuse before relevant acquisition/projection; catalogue outages must not block local-only changes.
- [ ] Add `test_projection_failure_restores_all_requested_harnesses_and_retry_succeeds`: force an owned projection failure after an earlier target write, verify journal recovery preserves old links/records and unrelated work, correct the failure and retry without advancing HEAD/reacquiring backing.
- [ ] Run `uv run pytest -q tests/test_tui/test_skill_catalog_collections.py tests/test_tui/test_skill_catalog.py tests/test_cli/test_skill_collection_recovery.py tests/test_cli/test_skill_collection_review_regressions.py`; confirm new failure-boundary tests fail.
- [ ] Implement one-snapshot preparation, exact intent validation, selected acquisition and per-unit failure bookkeeping. Before exposing anything, form desired sets from current actual records plus the original explicit operations. Do not materialize unselected advertisements. Preserve failed queues after refresh; report retained library acquisitions separately from exposure outcomes.
- [ ] Ensure singleton selected children and multiple harnesses obey the same failure contract without inventing virtual persisted parents or rewriting private backing. Preserve standalone/legacy engine paths where no catalogue collection is involved.
- [ ] Rerun to green; commit `fix(skills): isolate catalog collection apply failures`.

### Task 4: Catalogue-independent Git checks, references and final gates

**Files:** `skill_update_check.py`, `commands/skill/check_cmd.py`, `asset_info.py`, new CLI check tests, relevant Info/catalogue tests and the three current reference docs.

**Interfaces:** Preserve `check_skills(...) -> list[dict]`, `read_check(...) -> dict | None`, check JSON/cache schema and existing command flags. Reuse `catalog_skill_info(...)` compatibly or split its Git-only subsection behind a small helper; catalogue-free rows must not acquire a fictitious catalogue label.

- [ ] Write failing tests `test_check_named_and_default_git_library_without_catalog`, `test_check_missing_or_non_git_backing_is_not_clean`, and `test_info_without_catalog_shows_local_revision_and_observation`. Assert explicit/default scope, preserved files/HEAD, actual backing, timestamps/commands and no catalogue dependency.
- [ ] Cover SHA pins, private/central backing, origin mismatch, shared-parent query batching, stale observations after identity/HEAD change and failed probes replacing old green results. Keep existing catalogue check tests intact.
- [ ] Run `uv run pytest -q tests/test_cli/test_skill_check_library.py tests/test_cli/test_skill_catalog_check.py tests/test_tui/test_skill_catalog.py`; confirm the new non-catalogue tests fail.
- [ ] Remove provenance as a Git-check eligibility gate, retain recorded-selector/origin validation and honest revision semantics, and expose Git information without a catalogue association. Update CLI help/empty results and current docs for expansion, All semantics, retained acquisition on failure, and explicit Git checks. State the existing deletion-safety limitation without claiming it repaired.
- [ ] Rerun focused tests to green; commit `feat(skills): check Git library revisions independently of catalog`.
- [ ] Run clean-baseline/full regression gates as applicable: `uv sync --all-extras`, `uv run pytest -q`, `make docs-build`, `uv build`, `git diff --check`. Inspect outputs and record actual counts/source/wheel hash; do not claim tests/builds that were not run.
- [ ] Review the whole diff against the design and five Review Focus cases; use independent review only with user authorization. Address findings with regression tests. Confirm original checkout, old demo, live HOME/config/assets and separate multi-kind design unchanged by this branch. Commit any final docs/test corrections conventionally; no merge/release/install.

## Handoff and status

- [x] Feasibility checked against canonical 6.1.0; approved behavior and failure unit recorded.
- [x] Plan self-reviewed for spec coverage, interface consistency, identity/ownership hazards and scope boundaries.
- [ ] AJ reviews the written plan and confirms native execution (same-session implementation); independent whole-branch review requires authorization.
- [ ] Establish clean local baseline, then execute tasks 1–4 with RED/GREEN evidence and commits.

The separate active-consumer library-removal defect remains recorded, not hidden or fixed by this plan. Any expansion into its deletion-policy redesign or the multi-kind proposal must be raised before implementation.
