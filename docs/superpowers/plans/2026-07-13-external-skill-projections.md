# External Skill Projection Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep declared Paperclip-owned Pi skill symlinks out of `skill doctor` stray findings without weakening detection for unknown or mismatched projections.

**Architecture:** Add an optional global JSON registry reader in `skill_doctor.py`. The global stray-symlink scanner checks exact projection paths and resolved target globs from that registry before emitting a finding; malformed registry input is surfaced by the CLI as a concise failure.

**Tech Stack:** Python 3.12+, Click, pytest, stdlib `json` and `glob`.

## Global Constraints

- Registry path: `~/.agent-toolkit/external-skill-projections.json`.
- Registry entries are relative to the runtime home and contain exact `path`, `targetGlob`, and `owner` strings.
- Suppress a projection only when its exact path and resolved target both match one registry entry.
- The registry is global-only; project-scope doctor behavior remains unchanged.
- Invalid registry content fails loudly; absent registry is a no-op.
- Never add external entries to `skills-lock.json` or allow doctor to mutate them.

---

### Task 1: Test external-projection matching and invalid input

**Files:**
- Modify: `tests/test_cli/test_cli_skill_doctor.py`

**Interfaces:**
- Consumes: `agent_toolkit_cli.skill_doctor.diagnose(slugs, scope, home, project)`.
- Produces: regression coverage for declared matching targets, changed targets, and invalid registry data.

- [ ] **Step 1: Write failing matching and mismatch tests**

Add fixtures that create a fake Pi skill directory, a `paperclip` symlink, its target, and `fake_home/.agent-toolkit/external-skill-projections.json`:

```python
registry.write_text(json.dumps({
    "version": 1,
    "projections": [{
        "path": ".pi/agent/skills/paperclip",
        "targetGlob": ".npm/_npx/*/node_modules/@paperclipai/server/skills/paperclip",
        "owner": "Paperclip",
    }],
}))
```

Assert a matching target yields no `stray_symlink`, then repoint the link outside the target glob and assert it yields one.

- [ ] **Step 2: Run the targeted tests and verify RED**

Run:

```bash
uv run pytest tests/test_cli/test_cli_skill_doctor.py -k external_projection -v
```

Expected: the matching test fails because the current doctor always reports undeclared-lock symlinks as stray.

- [ ] **Step 3: Write a failing malformed-registry CLI test**

Create an invalid registry file and invoke `skill doctor -g --no-fix`. Assert a non-zero exit and a concise `invalid external skill projection registry` message.

- [ ] **Step 4: Run the malformed-registry test and verify RED**

Run:

```bash
uv run pytest tests/test_cli/test_cli_skill_doctor.py -k malformed_external_projection -v
```

Expected: FAIL because current doctor ignores the file.

### Task 2: Read and apply the registry safely

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py`
- Modify: `src/agent_toolkit_cli/commands/skill/doctor_cmd.py`

**Interfaces:**
- Add: `ExternalProjectionRegistryError(ValueError)`.
- Add: `_is_declared_external_projection(link, runtime_home)` returning `bool`.
- Extend: `_scan_stray_symlinks(..., runtime_home)` to skip only matching declared projections.
- CLI contract: render registry parsing failures as `click.ClickException`.

- [ ] **Step 1: Add the minimal registry parser**

Use `runtime_home / ".agent-toolkit/external-skill-projections.json"`. Return an empty immutable collection if absent. Validate `version == 1`; validate every projection has non-empty string `path`, `targetGlob`, and `owner`; reject absolute or parent-traversing paths. Wrap JSON decoding and schema errors in `ExternalProjectionRegistryError`.

- [ ] **Step 2: Add exact path and resolved-target matching**

For each symlink not present in the lock, compare its absolute path with the runtime-home-relative configured path. Resolve the symlink only after the path matches. Expand the configured target glob under the same home and suppress only if the resolved symlink target equals one matched path.

- [ ] **Step 3: Surface invalid registry errors cleanly**

Catch `ExternalProjectionRegistryError` in `doctor_cmd` around diagnosis and raise `click.ClickException("invalid external skill projection registry: ...")`.

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_cli/test_cli_skill_doctor.py -k 'external_projection or stray_symlink' -v
```

Expected: the new matching, mismatch, malformed-input, and pre-existing stray tests pass.

### Task 3: Document and release the safe behavior

**Files:**
- Modify: `docs/agent-toolkit/cli.md`
- Create: `docs/superpowers/specs/2026-07-13-external-skill-projections.md`
- Create: `docs/superpowers/plans/2026-07-13-external-skill-projections.md`

**Interfaces:**
- Documents: the registry schema and the exact safety rule for `skill doctor`.

- [ ] **Step 1: Document the registry beside the doctor command**

Add a short JSON example and state that it is for live projections owned by another system, not a way to bypass agent-toolkit ownership.

- [ ] **Step 2: Run formatting and the full test suite**

Run:

```bash
uv run ruff check src tests
uv run pytest
```

Expected: zero lint findings and all tests pass.

- [ ] **Step 3: Commit the source, tests, and documentation**

```bash
git add src/agent_toolkit_cli/skill_doctor.py src/agent_toolkit_cli/commands/skill/doctor_cmd.py tests/test_cli/test_cli_skill_doctor.py docs/agent-toolkit/cli.md docs/superpowers/specs/2026-07-13-external-skill-projections.md docs/superpowers/plans/2026-07-13-external-skill-projections.md
git commit -m "fix(skills): preserve declared external projections" -m "Device: $(hostname -s)"
```
