# Shared Skill Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Subscribe to one private Git skill catalog, discover live listings, acquire selected upstream skills, and check/update acquired content explicitly through CLI.

**Architecture:** Add a small catalog module for config, manifest parsing and fresh Git reads; reuse existing source/registration/projection engines. Keep update observations separate from catalog listings; extend existing inventory, Info and doctor rather than add another screen or service.

**Tech Stack:** Existing Python/Click/Textual/pytest, system Git; no new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-10-25-shared-skill-catalog-design.md` (approved by AJ).

## Global Constraints

- One user-global subscription; existing scope and asset lifecycle behavior unchanged.
- No subscription: existing behavior, no network or required configuration writes.
- Catalog reads are live; failure hides catalog-only entries, never acquired content.
- CLI-only upstream checks and content updates; timestamped results in TUI Info.
- Preserve local edits, foreign content, private backing, shared checkouts and locks.
- No LiteLLM, well-known, background update checks, profiles or version solver.
- Public Toolkit source remains GitHub; catalog repository is private Broadpeak Gitea.
- Preserve unrelated changes in the original checkout; implementation is isolated.

## Review Focus

- A live catalog selection changes between browse and Apply: refuse, never change source silently (Task 2/4).
- Same slug belongs to a different source or private backing: retain local row and refuse catalog collision (Task 2).
- Last check used different local HEAD/source: label stale/unchecked rather than current (Task 3).
- Refresh finishes after scope/pending selections change: do not restore obsolete rows or discard local intents (Task 4).
- Git remote asks for credentials or hangs: bounded noninteractive failure and local inventory retained (Task 1/4).

---

### Task 1: Catalog subscription and fresh discovery

**Files:** Create `src/agent_toolkit_cli/skill_catalog.py`, `src/agent_toolkit_cli/commands/skill/catalog_cmd.py`, `tests/test_cli/test_skill_catalog.py`; modify `src/agent_toolkit_cli/commands/skill/__init__.py`.

**Interfaces:** Produce frozen `CatalogSkill(key: str, description: str, source: ParsedSource)`, `CatalogSnapshot(url: str, revision: str, skills: tuple[CatalogSkill, ...], error: str | None)`. `read_catalog(*, home: Path | None = None) -> CatalogSnapshot | None`; `configure_catalog(url: str | None, ref: str | None = None, *, home: Path | None = None) -> None`. None means no subscription; error snapshot has no skills. Expose `skills catalog subscribe URL [--ref REF]`, `unsubscribe`, and `list [--json]`.

- [ ] Write local Git fixture tests for missing config, preservation of other config keys, valid manifest, changed remote listing, unavailable remote after previous success, malformed schema/path/ref, credential-bearing URL and timeout. Expected: missing module/command RED.
- [ ] Run `uv run pytest tests/test_cli/test_skill_catalog.py -q`; verify RED.
- [ ] Implement version-1 `catalog.json`: `{"version":1,"skills":[{"key":"demo","description":"...","source":"https://host/org/repo.git","path":"skills/demo","ref":"main"}]}`. Validate safe unique keys, explicit relative path and existing source/ref syntax. Read a fresh `FETCH_HEAD:catalog.json` in temporary bare Git storage (no checkout or skill repo fetch). Git reads have bounded noninteractive execution; error messages redact credentials. Store `skillCatalog: {url, ref}` in shared behavior config while preserving other keys and file identity conventions. Subscribe validates remote before persisting; unsubscribe changes only config.
- [ ] Run catalog tests, `tests/test_cli/test_cli_skill_aliases.py`, `tests/test_cli_skill_help_examples.py`; expect PASS.
- [ ] Commit `feat(skills): add optional live Git catalog subscription`.

### Task 2: Explicit acquisition and shared inventory matching

**Files:** Create `src/agent_toolkit_cli/skill_catalog_ops.py`, `tests/test_cli/test_skill_catalog_acquire.py`; modify `commands/skill/catalog_cmd.py`, `commands/skill/list_cmd.py`.

**Interfaces:** Consume Task 1. Produce `catalog_match(entry: LockEntry, item: CatalogSkill) -> bool`; `acquire_catalog_skill(item: CatalogSkill, *, catalog_url: str, home: Path | None = None) -> str` (returns actual existing/custom library slug). `resolve_catalog_skill(key: str, *, expected: CatalogSkill | None = None, home: Path | None = None) -> tuple[CatalogSnapshot, CatalogSkill]` performs fresh validation. CLI: `skills catalog add KEY` and `skills catalog enable KEY --scope global|project --agents TARGETS` (current harness selection defaults). Ordinary `skills install` semantics remain unchanged.

- [ ] Write tests proving add has no exposure, enable selects exact child/scope, matching custom slug reuses backing, same-name/different-ref conflicts preserve bytes, unavailable/changed selection refuses, and explicit action alone records provenance. RED expected for new command/interface.
- [ ] Run `uv run pytest tests/test_cli/test_skill_catalog_acquire.py -q`; verify RED.
- [ ] Delegate acquisition to existing `add` command callback via Click context (or its extracted minimal reusable callable), using exact source/path/ref; no second clone engine. Use existing install callback for CLI exposure after validation. Store small `catalog` provenance in LockEntry.extras only after successful acquisition. Resolve dedup from recorded source URL/path/ref, never names alone. Missing or unproven backing refuses, not adopts. Revalidate identity before apply; preserve successfully acquired library backing if later projection refuses (do not claim enable succeeded).
- [ ] Extend existing skills list to append live catalog-only entries when subscribed, dedup exact local matches, emit warnings on stderr. Existing no-subscription JSON/table contracts remain byte-compatible; catalog-only JSON has an explicit origin and no invented SHA. Agent filter excludes disabled catalog-only rows.
- [ ] Run acquisition and catalog tests plus `tests/test_cli/test_cli_skill_list*.py`, existing add/install/collection tests; expect PASS.
- [ ] Commit `feat(skills): acquire catalog selections through existing library engines`.

### Task 3: CLI update checks and catalog-aware doctor

**Files:** Create `src/agent_toolkit_cli/skill_update_check.py`, `commands/skill/check_cmd.py`, `tests/test_cli/test_skill_catalog_check.py`; modify skill command registration and `commands/skill/doctor_cmd.py`.

**Interfaces:** `check_skills(slugs: tuple[str, ...], *, scope: Scope, home: Path | None, project: Path | None) -> list[dict]`; `read_check(slug: str, *, scope: Scope, home: Path | None, project: Path | None) -> dict | None`. Records contain selector/backing identity, local SHA, remote SHA, checked-at UTC, status and error. Use `skills check [SLUGS...] -g|-p`; default selects catalog-associated entries. Explicit unsupported/nonassociated targets report clearly, without changing existing status/update verbs.

- [ ] Write moving-branch, fixed-pin, unreachable remote, changed HEAD/source, shared-parent, local-edit and no-subscription tests with local remotes. Check must not change backing HEAD/index/working files/projections. Test doctor never updates/adopts catalog-only rows. Verify RED.
- [ ] Implement read-only bounded remote revision comparison via `git ls-remote` (reuse existing Git environment scrubbing; never merge/fetch into backing). Distinguish branch/tag/default selectors and full commit pin. Label unequal SHAs as available upstream revision difference, not proof of ancestry/content changes. Persist observations atomically next to skill lock in `skills-update-checks.json`; read validates backing identity/current HEAD, marks old observations historical. No stale catalog snapshot stored. Never write from Info/doctor.
- [ ] Add catalog diagnostics to CLI doctor without inserting remote-only listings into locks or existing corruption scans. Connectivity warnings are separate; update observations advisory. `--no-fix` never writes; no subscription is a no-op. Keep existing repair behavior unchanged.
- [ ] Run `uv run pytest tests/test_cli/test_skill_catalog_check.py tests/test_cli/test_cli_skill_doctor.py tests/test_cli/test_cli_skill_update.py tests/test_cli/test_skill_update_monorepo.py -q`; expect PASS. If existing pin update is unsupported, Info says pinned/no update rather than falsely suggesting a moving update.
- [ ] Commit `feat(skills): check catalog upstream revisions from CLI`.

### Task 4: Live TUI inventory, Apply and Info

**Files:** Modify `src/agent_toolkit_tui/skill_state.py`, `widgets/skill_grid.py`, `asset_info.py`, `app.py`; create `tests/test_tui/test_skill_catalog.py`.

**Interfaces:** Consume Task 1 snapshot, Task 2 matching/acquisition and Task 3 observations. Extend `SkillRow` with defaulted `catalog_item: CatalogSkill | None`, `catalog_url: str`, `origin: str` and an explicit catalog-only state, preserving existing constructors. `build_skill_rows(..., catalog_snapshot: CatalogSnapshot | None = None)` does no network itself. A pure `merge_catalog_rows(rows: list[SkillRow], snapshot: CatalogSnapshot, *, scope: Scope, home: Path | None, project: Path | None) -> list[SkillRow]` appends/dedups; never changes local files.

- [ ] Write Textual pilot tests: catalog-only row queues enable without acquisition, Revert unchanged, Apply acquires only selected skill, duplicate local row remains singular, failed refresh removes remote rows, offline retains local pending intents, stale source refuses, Info shows timestamp and correct CLI guidance, no TUI update action. Verify RED.
- [ ] Load local rows immediately and use existing Textual worker/thread support for bounded catalog read on skill inventory load/explicit refresh. Apply only results for the current refresh generation/scope; no fetch on render/filter/Info. Missing subscription follows existing synchronous path. Failed refresh removes catalog-only rows but retains local intents. Retain catalog selection snapshots separately from ordinary pending keys so refreshed rows cannot change queued source silently.
- [ ] Before collection/projection grouping in `_apply_skill_pending`, validate targets and revalidate/acquire catalog-only link selections once per key, then reuse existing group/engine handling. Keep failed pending operations actionable; successful operations are not replayed. Existing local enables/disables do not require catalog connectivity. Info uses read-only observation rendering and escaping; catalog-only rows explain fetch-on-enable, no fictitious local directory.
- [ ] Run `uv run pytest tests/test_tui/test_skill_catalog.py tests/test_tui/test_skill_grid_apply.py tests/test_tui/test_cross_asset_save_revert.py tests/test_tui/test_project_collection_apply.py -q`; expect PASS.
- [ ] Commit `feat(tui): expose live skill catalog and CLI update guidance`.

### Task 5: Private demo catalog, docs and delivery

**Files:** Modify `docs/asset-types/skills.md`, `docs/agent-toolkit/cli.md`; separate repo `skill-catalog`: create `catalog.json`, `README.md`, `LICENSE`, `.gitignore`, a small validation test/script only if needed for independent catalog checks.

**Interfaces:** Demo manifest is exactly Task 1's schema. Use two verified public monorepo children pinned to one full SHA; content remains upstream. README includes subscription and CLI check/update usage, explains pins and zero automatic activation. Use existing infrastructure/credential runbooks; do not expose tokens, change service config, or enable a live subscription implicitly.

- [ ] Verify chosen upstream directories/SKILL.md/resources/license at exact commit with read-only acquisition; run the real parser and disposable-HOME add/enable/disable for each demo. Use local fixture branch for update-available smoke testing (pinned demos intentionally do not advance).
- [ ] Resolve existing Broadpeak Gitea, verify actor and remote, create private `skill-catalog` only if absent. Establish minimal base main with repository orientation, then feature branch with manifest/docs so a meaningful PR exists. Never overwrite an existing repo or push feature directly to its main. Read back private visibility.
- [ ] Update public Toolkit docs/help, with no speculative shipped commands. Run `uv run pytest -q` and `make docs-build`, save logs and inspect failures. Run `uv build` and `git diff --check`; expect successful exit. Validate demo manifest through actual Toolkit parser.
- [ ] Fresh read-only reviewer checks whole Toolkit branch and demo repository against approved spec, tests and privacy requirements. Fix consequential findings with RED→GREEN coverage; record deferred complexity rather than add features.
- [ ] Commit final changes, push feature branches and open Toolkit GitHub PR and private catalog Gitea PR, never merge. PR bodies name verification, no-subscription/offline behavior and deferred complexity. Report exact URLs, commits, checks and any infrastructure blocker honestly.

## Execution notes

AJ authorized autonomous build/review/commit/PR for both repositories. Implement inline
with one final fresh review to minimize repeated context and cost. Maintain a short
ledger of task progress and rulings. No installed Toolkit replacement, live skill
activation, merge or release is requested.
