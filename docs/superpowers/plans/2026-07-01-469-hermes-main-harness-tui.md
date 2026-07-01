# Plan: expose Hermes as a main TUI harness

Issue: #469  
Spec: `docs/superpowers/specs/2026-07-01-469-hermes-main-harness-tui.md`

## Implementation units

### U1 — Add Hermes to main-harness composition

**Goal:** Make `hermes-agent` part of the TUI's main harness set.

**Files:**

- `src/agent_toolkit_tui/composition.py`
- `tests/test_tui/test_composition.py`

**Approach:**

- Add `hermes-agent` to `MAIN_HARNESSES` after existing core harnesses.
- Update `test_main_harnesses_members` expected tuple.
- Update expected derived helper outputs:
  - `skills_nonstandard_main()` should include `hermes-agent` because `.hermes/skills` is not Standard.
  - `instructions_nonstandard_main()` should remain symlink-only and should not include Hermes because Hermes is native.
  - Add/adjust an automated assertion that Hermes is present in the native instructions matrix/Standard-reader coverage used by the instructions info surface.
  - `agents_nonstandard_main()` should not include Hermes because Hermes has `subagent_mechanism='none'`.
  - MCP helper remains separate from `MAIN_HARNESSES` and should not include Hermes.

**Test scenarios:**

- Composition unit tests fail before code change and pass after.
- Coverage guards confirm Hermes is either covered or rendered per supported asset type.

### U2 — Add Hermes display label

**Goal:** Render readable TUI column labels.

**Files:**

- `src/agent_toolkit_tui/display_names.py`
- Any affected snapshot/widget tests if present.

**Approach:**

- Add `_HARNESS_LABELS["hermes-agent"] = "Hermes"`.
- Verify skills column label uses `Hermes`.
- Do not change persisted keys or CLI identifiers.

**Test scenarios:**

- Add or update focused display-name test if existing coverage is absent.
- Existing label fallbacks remain unchanged.

### U3 — Verify skill-state/apply path handles Hermes

**Goal:** Ensure skills TUI can probe/toggle Hermes cells through existing generic skill machinery.

**Files:**

- `src/agent_toolkit_tui/skill_state.py` if assumptions need adjustment.
- Existing/applicable tests under `tests/test_tui/`.

**Approach:**

- Confirm `SkillGrid._active_agents()` derives from `skills_nonstandard_main()`, so Hermes appears automatically after U1.
- Confirm skill state builds cells from `AGENTS[harness]`; Hermes catalog entry already provides paths.
- Add a focused test if there is no existing coverage that non-standard main harnesses appear as skill cells.

**Test scenarios:**

- Hermes skill cell exists for a library skill at global and project scope.
- Toggling Hermes queues pending key `(scope, "hermes-agent", slug)`.
- Apply dispatch path accepts `hermes-agent` through existing skill install facade.

### U4 — Keep unsupported/unknown asset types from growing Hermes toggles

**Goal:** Avoid misleading columns for asset types Hermes cannot consume through toolkit adapters.

**Files:**

- `tests/test_tui/test_composition.py`
- `src/agent_toolkit_tui/command_state.py` only if a failing test reveals accidental coupling.
- MCP TUI tests only if needed.

**Approach:**

- Assert `agents_nonstandard_main()` excludes Hermes due `subagent_mechanism='none'`.
- Assert `agent_toolkit_tui.command_state.INTERACTIVE_HARNESSES` does not include Hermes while command support is unknown.
- Assert `_MCP_HARNESSES` does not include Hermes because MCP has only real adapter-backed harnesses.
- Leave pi-extension unchanged.

**Test scenarios:**

- Existing agent/command/MCP TUI tests pass unchanged except updated composition expectations.

### U5 — Docs and verification

**Goal:** Keep docs and evidence aligned.

**Files:**

- `docs/harnesses/hermes-agent.md` only if wording needs clarification.
- `docs/agent-toolkit/harness-matrix.md` only if tests/docs reveal drift.
- `assets/verification/<run-id>/` for evidence if implementation changes visible UI.

**Approach:**

- Prefer no compatibility-doc changes; Hermes support facts already exist.
- If implementation clarifies “main harness” semantics, update developer docs near the TUI or composition comments.
- Run focused tests first, then broader tests.

## Verification commands

Minimum:

- `uv run pytest tests/test_tui/test_composition.py -q`
- `uv run pytest tests/test_tui -q`

Preferred before PR:

- `uv run pytest -q`

Manual UI evidence if visible layout changed beyond constants:

- Launch TUI.
- Confirm Skills tab shows `Hermes` column.
- Confirm with automated test or captured TUI evidence that Instructions Standard/native info includes Hermes; do not close with documentation-only rationale.

## Risks

- Adding Hermes to `MAIN_HARNESSES` may alter Standard counts on instructions. Tests should assert intended count/coverage rather than hard-coding stale counts.
- Command support is currently unknown. Do not add Hermes to command defaults without public evidence and an adapter.
- “Main harness” and “dedicated column” are not identical under the Standard-collapse model. This issue explicitly preserves current model: dedicated column only where a per-harness projection/toggle is needed; native/no-toggle readers are exposed through Standard info/count.
