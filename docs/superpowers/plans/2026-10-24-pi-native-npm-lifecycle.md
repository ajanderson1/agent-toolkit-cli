# Native Pi npm lifecycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Toolkit npm registration with native installation/configuration facts and consistent scoped lifecycle controls.

**Architecture:** One Python native-npm facade delegates resource resolution to a packaged, offline Node bridge using installed Pi. CLI and TUI use the same state and settings transactions; native CLI owns installation/removal. Existing Git and loose-local paths remain separate.

**Tech Stack:** Python, Click, Textual, pytest, Node ESM and installed Pi 1.4.0; no additional Python dependencies.

**Spec:** docs/superpowers/specs/2026-10-24-pi-native-npm-lifecycle.md

## Global Constraints

- Pi settings and npm's installation records are authoritative.
- No live Pi package/settings migration is authorized.
- No new Python runtime dependencies.
- Read-only discovery must not install, execute extension code, mutate settings, run project-provided commands or change trust.
- Release Please owns versions.
- Preserve local extension controls and other asset kinds.

## Review Focus

- A raw external npm installation is not a Pi declaration; controls must not activate or delete it implicitly.
- Project delta versus independent project install/version must never be collapsed into a global write or duplicate download.
- Package-level off must also exclude future and hidden entrypoints, while mixed custom filters remain visible.
- A concurrent change to package source, version, filters or entrypoints must not be silently overwritten by a queued intent.
- Removal may expose global fallback, retain a dependency's files, or leave another scope configured; success must describe actual native postconditions.

---

### Task 1: Lossless native settings and resolver-backed inventory

**Files:** Modify `src/agent_toolkit_cli/_pi_settings.py`, `pi_extension_inventory.py`, `pi_local_extensions.py`; create `pi_npm.py`, `data/pi_npm_bridge.mjs`; tests `tests/test_cli/test_pi_npm.py` and existing settings/inventory tests.

**Interfaces:** `read_npm_states(*, home: Path, project: Path | None) -> dict[str, NpmState]`; `NpmState` contains identity and per-scope declaration, root, version, effective resource tuples, mixed/enabled/mode values and a stable snapshot. Existing `InventoryRecord` gains optional `npm_state`.

- [ ] Write failing tests for mixed-array preservation; native configured/direct/absent inventory; version-independent scoped identity; direct versus transitive; missing state; no execution/installation.
- [ ] Run `uv run pytest tests/test_cli/test_pi_npm.py tests/test_cli/test_pi_settings.py tests/test_cli/test_pi_settings_writer.py -q`; confirm relevant assertions fail before implementation.
- [ ] Implement lossless parser and read-only bridge/facade. Skip legacy npm lock rows in inventory; keep non-npm precedence and local discovery.
- [ ] Update only superseded registration expectations; run targeted settings, inventory and native state tests green.
- [ ] Commit `feat(pi): derive npm inventory from native Pi state`.

### Task 2: Scoped package filters and transactional controls

**Files:** Extend `pi_npm.py`; test `tests/test_cli/test_pi_npm_controls.py`.

**Interfaces:** `set_npm_enabled(*, identity, enabled, scope, home, project, expected_snapshot=None) -> None`; `reset_npm_override(*, identity, scope, home, project) -> None`. Snapshot comes from Task 1; transactions reuse native-compatible settings lock and atomic/symlink-safe writer.

- [ ] Write/run failing native cases for inherited on/off, project-on/global-off, reset, owned project version, mixed/hidden/future resources, unrelated resources and entry forms, missing files, locks and stale changes.
- [ ] Implement settings-only filters and native prospective-state verification. All/none uses native glob coverage including dot-prefixed basenames in delta mode; normal package off uses `extensions: []`. Reset never deletes an owned project install.
- [ ] Run both new test files and local-selector regressions green.
- [ ] Commit `feat(pi): add native scoped npm enable and disable controls`.

### Task 3: Explicit CLI lifecycle and legacy record retirement

**Files:** `pi_npm.py`, `pi_extension_add.py`, `pi_extension_ops.py`, `commands/pi_extension/{__init__,add_cmd,install_cmd,uninstall_cmd,remove_cmd}.py`; create `native_cmd.py`; CLI/lifecycle/migration tests.

**Interfaces:** `install_npm(*, source, scope, home, project)`, `remove_npm(*, identity, scope, home, project, external=False)`, `migrate_npm_records(*, apply=False) -> report`. New enable/disable/reset/migrate verbs are scoped explicitly. Install/remove delegate to native CLI with controlled paths and no shell interpolation.

- [ ] Write/run failing tests for native add/install equivalence and flags, independent project install allowed, actual removal confirmation, external-origin refusal unless explicitly requested, meaningful postconditions, preserving errors, no lock writes, and backup-only migration.
- [ ] Implement native lifecycle and command registration; change npm branches only, preserve Git semantics and advise on breaking behavior. No automatic migration or third-party installation during upgrade.
- [ ] Run CLI tests green and help coverage for every new verb.
- [ ] Commit `feat(pi)!: unify npm CLI lifecycle with native Pi` with breaking-change explanation.

### Task 4: Real TUI controls and truthful scope information

**Files:** `src/agent_toolkit_tui/{pi_extension_state,app,column_info}.py`, `widgets/pi_grid.py`; TUI native npm tests and existing affected tests.

**Interfaces:** Task 1's `npm_state` travels into rows; Task 2 is the only checkbox backend. Pending npm snapshots survive refresh/scope changes; failed intents remain. A reset-inheritance action is exposed without physical removal.

- [ ] Write/run failing real-key tests: unmanaged/native npm toggle, project override without global modification, mixed Space→enable all, Ctrl+S→refresh→fresh app, pending survival, failed apply and reset.
- [ ] Implement native controls before lock lookup; retain library paths. Info explains installed location/version, configuration source, inherited versus owned policy, missing state and truthful origin-specific removal. Counters use the same state.
- [ ] Update superseded copy/registration tests without weakening other-kind checks; run targeted TUI suite green.
- [ ] Commit `feat(tui): use native npm scope and lifecycle state`.

### Task 5: Verification, review and delivery

**Files:** Current CLI/TUI/Pi extension docs; extend `scripts/verify_pi_local_controls.py` or add `scripts/verify_pi_npm_controls.py` as reusable installed verifier.

**Interfaces:** Installed verifier imports wheel modules under isolated HOME and compares native results; all paths are disposable. Native script/data must ship in both artifacts.

- [ ] Document operation separation, npm CLI compatibility transition, scopes and inheritance/reset, raw npm availability, migration, external removal and running-session distinction.
- [ ] Run `uv run pytest -q` and `make docs-build`; expected full green and strict docs success.
- [ ] Build wheel/sdist, compare source payload including bridge; run installed native npm and existing loose-local verifiers.
- [ ] Commit docs/verifier, request one independent read-only whole-branch review with exact base/head, spec, plan, ledger and native evidence. Parent fixes Important/Critical findings RED→GREEN and reruns suite.
- [ ] Recheck main; fast-forward merge locally, verify, push through pre-push suite and confirm exact-SHA CI. Do not merge a release PR without separately requested release authority.
- [ ] Build/install an explicitly labelled exact-commit candidate; retain rollback artifact and verify installed payload/native workflows and protected live-file hashes.

## Self-review / authorization

Every spec requirement maps to tasks 1–5. State/snapshot names are shared across
facade, CLI and TUI; preserve the interface rather than adding parallel paths.
The approved request explicitly says proceed through build/review/merge/push/install,
so no redundant execution-choice approval is requested. Any release publication
not needed for local exact-commit installation remains outside this authorization.
