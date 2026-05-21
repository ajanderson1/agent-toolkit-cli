# Deprecate legacy CLI commands — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip the `agent-toolkit-cli` Python CLI down to a single top-level command (`skill`). Delete every other command's module, tests, support code, and docs from `main`. Keep the TUI intact.

**Architecture:** Surgical deletion in dependency order — top-down from the Click group registration, then commands, then internal helpers, then the now-orphaned top-level support modules, then tests, then docs, then dead infrastructure (`audit/`, `schemas/`, lefthook hook). The keep-set is fixed: `cli.py`, `__init__.py`, `__main__.py`, `_repo_resolution.py`, `_support.py`, all `skill_*.py` modules, and the `commands/skill/` subpackage. Everything else under `src/agent_toolkit_cli/` is deleted.

**Tech Stack:** Python 3.12+, Click, uv, pytest, lefthook. No new dependencies.

**Spec:** [`docs/superpowers/specs/2026-05-21-deprecate-legacy-cli-design.md`](../specs/2026-05-21-deprecate-legacy-cli-design.md)

**Issue:** [#160](https://github.com/ajanderson1/agent-toolkit-cli/issues/160)

---

## Pre-flight: baseline capture

The build phase begins by capturing the *before* state for the verification artifacts (per spec § Verification plan). The agent should do this **before any deletion** so the artifacts reflect the actual baseline:

- Capture `agent-toolkit-cli --help` to `assets/verification/160/helptext-before.txt`.
- Capture `tree src/agent_toolkit_cli/ -L 2` (or `ls -R` if `tree` is unavailable) to `assets/verification/160/tree-before.txt`.
- Capture initial pytest pass count (already known: 1129 passed, 3 skipped — confirmed from spec commit's pre-commit hook output).

### Task 0: Capture baseline verification artifacts

**Files:**
- Create: `assets/verification/160/helptext-before.txt`
- Create: `assets/verification/160/tree-before.txt`

- [ ] **Step 1: Capture current --help output**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run agent-toolkit-cli --help > assets/verification/160/helptext-before.txt 2>&1
```

Expected: file contains the full 13-command listing.

- [ ] **Step 2: Capture current src tree**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
( cd src && find agent_toolkit_cli -type f -not -path '*/__pycache__/*' | sort ) > assets/verification/160/tree-before.txt
```

Expected: ~80 files listed.

- [ ] **Step 3: Commit baseline artifacts**

```bash
git add assets/verification/160/helptext-before.txt assets/verification/160/tree-before.txt
git commit -m "chore(verify): capture pre-removal baseline for #160"
```

Note: `assets/verification/` is *not* yet gitignored (the spec verification step adds it later). Committing the baseline is fine — it's a one-time forensic artifact pinned to this PR. If `assets/verification/` becomes gitignored later, the existing commits in history still preserve the file.

Actually — `.gitignore` lives in the worktree root. Check it before committing:

```bash
grep -n "assets/verification" /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli/.gitignore || echo "not gitignored — safe to commit"
```

If `assets/verification` *is* in `.gitignore`, use `git add -f` to force-add the two baseline files (they are intentional forensic artifacts, not transient logs).

---

## Phase A — Unregister and delete commands

The CLI dispatcher is in `src/agent_toolkit_cli/cli.py`. Every `main.add_command(<x>)` call for a non-`skill` command goes. The `--toolkit-repo` and `--project` group-level options also go — `skill` does not consume them, and the surviving CLI no longer needs the four-step toolkit-repo resolver at the group level.

### Task 1: Rewrite cli.py to expose only `skill`

**Files:**
- Modify: `src/agent_toolkit_cli/cli.py` (full rewrite — keep file, replace contents)
- Test: `tests/test_cli_help.py` (rewritten in Task 13)

- [ ] **Step 1: Write the new cli.py**

Replace the entire file with:

```python
"""agent-toolkit-cli Python CLI dispatcher."""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.skill import skill


@click.group(
    help=(
        "agent-toolkit-cli — manage skills via per-skill upstream git repos + "
        "lockfile. Run `agent-toolkit-cli skill --help` for subcommands.\n\n"
        "Pre-v2 commands (check, link, doctor, etc.) were removed in v2.3.0. "
        "The frozen v1 surface lives at the v1.0.0 tag; install it via "
        "`uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit`."
    )
)
def main() -> None:
    """agent-toolkit-cli."""


main.add_command(skill)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the CLI still imports**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run python -c "from agent_toolkit_cli.cli import main; print(main.commands.keys())"
```

Expected: `dict_keys(['skill'])` — and exit code 0. If `ImportError` fires here it means a transitive import is still broken (most likely `commands/skill/__init__.py` re-exports something gone). Investigate before continuing.

- [ ] **Step 3: Verify --help renders**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run agent-toolkit-cli --help
```

Expected: help text mentions `skill` and only `skill` in the Commands table. No `check`, `link`, `doctor` etc.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_cli/cli.py
git commit -m "refactor(cli): unregister pre-v2 commands; keep only \`skill\` (#160)"
```

### Task 2: Delete top-level command modules (the 12 legacy commands)

**Files:**
- Delete: `src/agent_toolkit_cli/commands/check.py`
- Delete: `src/agent_toolkit_cli/commands/diff.py`
- Delete: `src/agent_toolkit_cli/commands/doctor.py`
- Delete: `src/agent_toolkit_cli/commands/fix.py`
- Delete: `src/agent_toolkit_cli/commands/ingest.py`
- Delete: `src/agent_toolkit_cli/commands/inventory.py`
- Delete: `src/agent_toolkit_cli/commands/link.py`
- Delete: `src/agent_toolkit_cli/commands/list.py`
- Delete: `src/agent_toolkit_cli/commands/migrate_skills.py`
- Delete: `src/agent_toolkit_cli/commands/new.py`
- Delete: `src/agent_toolkit_cli/commands/pi.py`
- Delete: `src/agent_toolkit_cli/commands/unlink.py`

- [ ] **Step 1: Delete the 12 modules in one batch**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
git rm src/agent_toolkit_cli/commands/check.py \
       src/agent_toolkit_cli/commands/diff.py \
       src/agent_toolkit_cli/commands/doctor.py \
       src/agent_toolkit_cli/commands/fix.py \
       src/agent_toolkit_cli/commands/ingest.py \
       src/agent_toolkit_cli/commands/inventory.py \
       src/agent_toolkit_cli/commands/link.py \
       src/agent_toolkit_cli/commands/list.py \
       src/agent_toolkit_cli/commands/migrate_skills.py \
       src/agent_toolkit_cli/commands/new.py \
       src/agent_toolkit_cli/commands/pi.py \
       src/agent_toolkit_cli/commands/unlink.py
```

- [ ] **Step 2: Verify CLI still imports cleanly**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run python -c "from agent_toolkit_cli.cli import main; print('ok')"
```

Expected: `ok` (and exit 0). If `ImportError` mentions any of the removed modules, find the stray import and fix it. The expected callers are all in code paths we're about to delete in Phase B, but a stray import in `commands/_hook_dispatch.py` (which we will keep transiently) or `commands/skill/` is possible.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: delete pre-v2 CLI command modules (#160)"
```

### Task 3: Delete command-private internal helpers

The internal helpers in `commands/` exist only to support the deleted commands.

**Files:**
- Delete: `src/agent_toolkit_cli/commands/_link_lib.py`
- Delete: `src/agent_toolkit_cli/commands/_mcp_dispatch.py`
- Delete: `src/agent_toolkit_cli/commands/_plugin_dispatch.py`
- Delete: `src/agent_toolkit_cli/commands/_hook_dispatch.py`
- Delete: `src/agent_toolkit_cli/commands/_list_json.py`
- Delete: `src/agent_toolkit_cli/commands/_yaml_edit.py`

Note: spec listed `_hook_dispatch.py`, `_list_json.py`, `_yaml_edit.py` as conditional keeps. **Reachability sweep done during planning confirms: nothing in `commands/skill/` or `src/agent_toolkit_tui/` imports any of these. They go.**

- [ ] **Step 1: Confirm no surviving import of these helpers**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
grep -rn "from agent_toolkit_cli.commands._hook_dispatch\|from agent_toolkit_cli.commands._link_lib\|from agent_toolkit_cli.commands._mcp_dispatch\|from agent_toolkit_cli.commands._plugin_dispatch\|from agent_toolkit_cli.commands._list_json\|from agent_toolkit_cli.commands._yaml_edit" src/ || echo "no surviving imports"
```

Expected: `no surviving imports`. If any matches appear, they are inside files we already deleted in Task 2 (orphan refs that `git rm` should have removed); re-run after a `find . -name __pycache__ -type d -exec rm -rf {} +` to clear stale `.pyc`.

- [ ] **Step 2: Delete the helpers**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
git rm src/agent_toolkit_cli/commands/_link_lib.py \
       src/agent_toolkit_cli/commands/_mcp_dispatch.py \
       src/agent_toolkit_cli/commands/_plugin_dispatch.py \
       src/agent_toolkit_cli/commands/_hook_dispatch.py \
       src/agent_toolkit_cli/commands/_list_json.py \
       src/agent_toolkit_cli/commands/_yaml_edit.py
```

- [ ] **Step 3: Verify CLI still imports**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run python -c "from agent_toolkit_cli.cli import main; print(list(main.commands.keys()))"
```

Expected: `['skill']`.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: delete command-private legacy helpers (_link_lib, _mcp_dispatch, _plugin_dispatch, _hook_dispatch, _list_json, _yaml_edit) (#160)"
```

---

## Phase B — Delete orphaned top-level support modules and subpackages

With every legacy command gone, the top-level support modules under `src/agent_toolkit_cli/` become orphaned. The keep-set (TUI + `skill` dependencies) is:

- `__init__.py`, `__main__.py`, `cli.py`
- `_repo_resolution.py` (TUI uses it)
- `_support.py` (TUI uses `USER_LINKED_STATUSES`)
- `skill_agents.py`, `skill_git.py`, `skill_install.py`, `skill_lock.py`, `skill_paths.py`, `skill_source.py`
- `commands/__init__.py`, `commands/skill/` (untouched)

Everything else under `src/agent_toolkit_cli/` is deleted.

### Task 4: Delete `_pi_*.py` sibling modules

**Files:**
- Delete: `src/agent_toolkit_cli/_pi_fetch.py`
- Delete: `src/agent_toolkit_cli/_pi_inventory.py`
- Delete: `src/agent_toolkit_cli/_pi_overrides.py`
- Delete: `src/agent_toolkit_cli/_pi_paths.py`
- Delete: `src/agent_toolkit_cli/_pi_settings.py`

- [ ] **Step 1: Confirm no surviving import**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
grep -rn "from agent_toolkit_cli._pi_\|from agent_toolkit_cli import _pi_" src/agent_toolkit_cli/commands/skill src/agent_toolkit_tui || echo "no surviving imports"
```

Expected: `no surviving imports`.

- [ ] **Step 2: Delete and verify**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
git rm src/agent_toolkit_cli/_pi_*.py
uv run python -c "from agent_toolkit_cli.cli import main; print('ok')"
```

Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: delete legacy _pi_*.py support modules (#160)"
```

### Task 5: Delete legacy top-level support modules

**Files:**
- Delete: `src/agent_toolkit_cli/_allowlist.py`
- Delete: `src/agent_toolkit_cli/_requires.py`
- Delete: `src/agent_toolkit_cli/_translators.py`
- Delete: `src/agent_toolkit_cli/_ui.py`
- Delete: `src/agent_toolkit_cli/inventory.py`
- Delete: `src/agent_toolkit_cli/schema.py`
- Delete: `src/agent_toolkit_cli/walker.py`

**Keep (TUI / skill needs them):**
- `_repo_resolution.py`, `_support.py`, `skill_*.py`

- [ ] **Step 1: Confirm no surviving import**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
grep -rn "from agent_toolkit_cli._allowlist\|from agent_toolkit_cli._requires\|from agent_toolkit_cli._translators\|from agent_toolkit_cli._ui\|from agent_toolkit_cli.inventory\|from agent_toolkit_cli.schema\|from agent_toolkit_cli.walker" src/agent_toolkit_cli/commands/skill src/agent_toolkit_tui || echo "no surviving imports"
```

Expected: `no surviving imports`.

- [ ] **Step 2: Delete**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
git rm src/agent_toolkit_cli/_allowlist.py \
       src/agent_toolkit_cli/_requires.py \
       src/agent_toolkit_cli/_translators.py \
       src/agent_toolkit_cli/_ui.py \
       src/agent_toolkit_cli/inventory.py \
       src/agent_toolkit_cli/schema.py \
       src/agent_toolkit_cli/walker.py
```

- [ ] **Step 3: Verify CLI imports + TUI imports still work**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run python -c "from agent_toolkit_cli.cli import main; print('cli-ok')"
uv run python -c "from agent_toolkit_tui.app import main; print('tui-ok')"
```

Expected: `cli-ok` then `tui-ok`.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: delete legacy support modules (_allowlist, _requires, _translators, _ui, inventory, schema, walker) (#160)"
```

### Task 6: Delete legacy subpackages

**Files:**
- Delete: `src/agent_toolkit_cli/_schemas/` (entire directory)
- Delete: `src/agent_toolkit_cli/doctor/` (entire directory)
- Delete: `src/agent_toolkit_cli/generators/` (entire directory)
- Delete: `src/agent_toolkit_cli/harness_adapters/` (entire directory)
- Delete: `src/agent_toolkit_cli/ingest/` (entire directory)
- Delete: `src/agent_toolkit_cli/security/` (entire directory)

- [ ] **Step 1: Confirm no surviving import**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
grep -rn "from agent_toolkit_cli.doctor\|from agent_toolkit_cli.generators\|from agent_toolkit_cli.harness_adapters\|from agent_toolkit_cli.ingest\|from agent_toolkit_cli.security\|from agent_toolkit_cli import doctor\|from agent_toolkit_cli import generators\|from agent_toolkit_cli import harness_adapters\|from agent_toolkit_cli import ingest\|from agent_toolkit_cli import security" src/agent_toolkit_cli/commands/skill src/agent_toolkit_tui || echo "no surviving imports"
```

Expected: `no surviving imports`.

- [ ] **Step 2: Delete the six subpackages**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
git rm -r src/agent_toolkit_cli/_schemas \
          src/agent_toolkit_cli/doctor \
          src/agent_toolkit_cli/generators \
          src/agent_toolkit_cli/harness_adapters \
          src/agent_toolkit_cli/ingest \
          src/agent_toolkit_cli/security
```

- [ ] **Step 3: Verify imports**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run python -c "from agent_toolkit_cli.cli import main; print('cli-ok')"
uv run python -c "from agent_toolkit_tui.app import main; print('tui-ok')"
```

Expected: both `ok` lines print.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: delete legacy subpackages (_schemas, doctor, generators, harness_adapters, ingest, security) (#160)"
```

---

## Phase C — Delete dead infrastructure outside src/

`audit/` is a top-level directory of bash scripts that probes the legacy harness/kind matrix via `agent_toolkit_cli.harness_adapters` (now gone). `schemas/` is the top-level vendored copy of the JSON schema that lefthook's `schema-vendor-check` keeps in sync with `src/agent_toolkit_cli/_schemas/` (also gone). Both are dead.

### Task 7: Delete `audit/` directory

**Files:**
- Delete: `audit/` (entire top-level directory)

- [ ] **Step 1: Verify audit/ only depends on now-removed modules**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
grep -rn "agent_toolkit_cli\." audit/ 2>&1 || true
```

Expected: matches reference `harness_adapters` / `walker` / `schema` (all deleted). Confirms the audit/ scripts are dead.

- [ ] **Step 2: Delete**

```bash
git rm -r audit
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: delete audit/ (probes the deleted harness/kind matrix) (#160)"
```

### Task 8: Delete top-level `schemas/`

**Files:**
- Delete: `schemas/` (entire top-level directory)

- [ ] **Step 1: Verify nothing live imports the schema file**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
grep -rn "schemas/asset-frontmatter" src/ tests/ pyproject.toml lefthook.yml 2>&1 || true
```

Expected: matches reference `schemas/asset-frontmatter.v1alpha2.json` only from `lefthook.yml`'s `schema-vendor-check` hook (to be removed in Task 10), `pyproject.toml`'s `[tool.hatch.build.targets.wheel.force-include]` (to be cleaned in Task 11), and `AGENTS.md` (to be cleaned in Task 15). No live src/ or tests/ reference.

- [ ] **Step 2: Delete**

```bash
git rm -r schemas
```

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: delete top-level schemas/ (no live consumer) (#160)"
```

---

## Phase D — Tests

The test suite has 80+ test files. Most exercise removed commands; some exercise the TUI or `skill` and stay. Pruning is per-file.

### Task 9: Delete tests for removed CLI commands and removed support modules

The deletion list comes from a per-file inspection of `tests/`. Tests that exercise *only* removed code go. The TUI test suite (`tests/test_tui/`), the skill test suite (`tests/test_cli/test_*skill*` and friends), and shared infrastructure (`conftest.py`, fixtures referenced by surviving tests) stay.

**Files to delete (top-level `tests/`):**

```
tests/test_allowlist.py
tests/test_check.py
tests/test_check_conventions_drift.py
tests/test_check_mutex.py
tests/test_check_skill_shape.py
tests/test_claude_plugin_adapter.py
tests/test_cli_diff.py
tests/test_cli_link.py
tests/test_cli_list.py
tests/test_cli_pi.py
tests/test_cli_unlink.py
tests/test_codex_hook_adapter.py
tests/test_doctor.py
tests/test_doctor_allowlist_audit.py
tests/test_doctor_autofix.py
tests/test_doctor_autofix_dryrun.py
tests/test_doctor_groups.py
tests/test_doctor_harness_homes.py
tests/test_doctor_mcps.py
tests/test_doctor_orphans.py
tests/test_doctor_per_resource.py
tests/test_doctor_pi_advisories.py
tests/test_doctor_skill_shape.py
tests/test_doctor_strict_flag.py
tests/test_doctor_user_scope_coverage.py
tests/test_fix.py
tests/test_generators.py
tests/test_get_adapter_kind_aware.py
tests/test_harness_adapters_base.py
tests/test_harness_matrix.py
tests/test_hook_dispatch.py
tests/test_ingest_finalize.py
tests/test_ingest_identify.py
tests/test_ingest_stage.py
tests/test_inventory.py
tests/test_link_codex_agent.py
tests/test_link_lib.py
tests/test_link_lib_sidecar.py
tests/test_link_sidecar_parity.py
tests/test_list_json.py
tests/test_list_report.py
tests/test_mcp_adapters_base.py
tests/test_mcp_adapters_claude.py
tests/test_mcp_adapters_codex.py
tests/test_mcp_adapters_gemini.py
tests/test_mcp_adapters_opencode.py
tests/test_mcp_dispatch.py
tests/test_migrate_skills.py
tests/test_new.py
tests/test_new_command_sidecar.py
tests/test_new_skill_shape.py
tests/test_pi_extension.py
tests/test_pi_fetch.py
tests/test_pi_inventory.py
tests/test_pi_overrides.py
tests/test_pi_paths.py
tests/test_pi_project_paths.py
tests/test_pi_settings.py
tests/test_repo_resolution.py
tests/test_schema.py
tests/test_schema_hook.py
tests/test_schema_per_harness.py
tests/test_security_report.py
tests/test_security_signals.py
tests/test_spec_requires.py
tests/test_support.py
tests/test_tomlkit_roundtrip.py
tests/test_translate_directory_slots.py
tests/test_translate_opencode_skill.py
tests/test_translate_pi_skill.py
tests/test_translate_status_reporting.py
tests/test_translators.py
tests/test_tui_hook_integration.py
tests/test_tui_mcp_integration.py
tests/test_tui_pi_tab.py
tests/test_tui_pi_tab_bindings.py
tests/test_ui.py
tests/test_validator.py
tests/test_validator_schema_path.py
tests/test_walker.py
tests/test_walker_mcp_legacy_removed.py
tests/test_walker_sidecar.py
tests/test_walker_skill_shape.py
tests/test_yaml_edit.py
```

**Files to keep (top-level `tests/`):**

```
tests/conftest.py                         # shared git_sandbox fixture
tests/test_cli_help.py                    # rewritten in Task 13
tests/test_skill_agents_interop.py        # ← wait — this is in tests/test_cli/, not top-level. See note below.
```

**Note on `tests/test_tui_*.py`:** `test_tui_hook_integration.py`, `test_tui_mcp_integration.py`, `test_tui_pi_tab.py`, `test_tui_pi_tab_bindings.py` are *top-level* tests that exercise TUI flows for legacy asset kinds (hook/MCP/pi-extension) — but the TUI itself was already narrowed to skill-grid + claude-code + pi in v2.1.0. Each one imports legacy machinery (`_mcp_dispatch`, `_hook_dispatch`, `pi` command). They go. The surviving TUI tests live in `tests/test_tui/` (a separate subdirectory).

**`tests/integration/` and `tests/test_cli/`:**
- `tests/integration/test_plugin_link_cycle.py` — exercises the removed `link` command for plugins. Delete.
- `tests/test_cli/` — all `test_skill_*.py`, `test_cli_skill_*.py`. Keep entire directory.

**`tests/audit/`:** wraps shell tests for the now-removed `audit/` directory. Delete the entire dir.

**`tests/_fixtures/` and `tests/fixtures/`:**
- `tests/_fixtures/` — contains `codex_config_realistic*.toml`, `hook_assets/`. Used only by legacy tests (the hook/codex configs feed the deleted `_mcp_dispatch` / `_hook_dispatch` tests). Delete.
- `tests/fixtures/` — contains `migrate_skills_input/`, `migrate_skills_expected/`, `plugin_sidecars/`, `vercel-labs-skills-agents.ts`. **Keep `vercel-labs-skills-agents.ts`** (used by surviving `tests/test_cli/test_skill_agents_interop.py` and runtime `src/agent_toolkit_cli/skill_agents.py`). Delete `migrate_skills_input/`, `migrate_skills_expected/`, `plugin_sidecars/`.

**`tests/aj-workflow/`:** contains `test_shape.bats`. The bats file tests shape conventions for the `aj-workflow` skill, not the CLI commands. **Keep** (verify by reading it in Step 1 below; remove only if confirmed legacy-tied).

- [ ] **Step 1: Sanity-check `tests/aj-workflow/test_shape.bats`**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
head -50 tests/aj-workflow/test_shape.bats
```

Decision rule: if it tests CLI commands (`agent-toolkit-cli check`, `link`, etc.), delete the directory. If it tests skill-file structure or aj-workflow conventions, keep.

- [ ] **Step 2: Delete the top-level test files listed above**

Use one batched `git rm` to keep the diff coherent. Build the command from the list:

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
git rm tests/test_allowlist.py tests/test_check.py tests/test_check_conventions_drift.py \
       tests/test_check_mutex.py tests/test_check_skill_shape.py tests/test_claude_plugin_adapter.py \
       tests/test_cli_diff.py tests/test_cli_link.py tests/test_cli_list.py tests/test_cli_pi.py \
       tests/test_cli_unlink.py tests/test_codex_hook_adapter.py tests/test_doctor.py \
       tests/test_doctor_allowlist_audit.py tests/test_doctor_autofix.py tests/test_doctor_autofix_dryrun.py \
       tests/test_doctor_groups.py tests/test_doctor_harness_homes.py tests/test_doctor_mcps.py \
       tests/test_doctor_orphans.py tests/test_doctor_per_resource.py tests/test_doctor_pi_advisories.py \
       tests/test_doctor_skill_shape.py tests/test_doctor_strict_flag.py tests/test_doctor_user_scope_coverage.py \
       tests/test_fix.py tests/test_generators.py tests/test_get_adapter_kind_aware.py \
       tests/test_harness_adapters_base.py tests/test_harness_matrix.py tests/test_hook_dispatch.py \
       tests/test_ingest_finalize.py tests/test_ingest_identify.py tests/test_ingest_stage.py \
       tests/test_inventory.py tests/test_link_codex_agent.py tests/test_link_lib.py \
       tests/test_link_lib_sidecar.py tests/test_link_sidecar_parity.py tests/test_list_json.py \
       tests/test_list_report.py tests/test_mcp_adapters_base.py tests/test_mcp_adapters_claude.py \
       tests/test_mcp_adapters_codex.py tests/test_mcp_adapters_gemini.py tests/test_mcp_adapters_opencode.py \
       tests/test_mcp_dispatch.py tests/test_migrate_skills.py tests/test_new.py \
       tests/test_new_command_sidecar.py tests/test_new_skill_shape.py tests/test_pi_extension.py \
       tests/test_pi_fetch.py tests/test_pi_inventory.py tests/test_pi_overrides.py tests/test_pi_paths.py \
       tests/test_pi_project_paths.py tests/test_pi_settings.py tests/test_repo_resolution.py \
       tests/test_schema.py tests/test_schema_hook.py tests/test_schema_per_harness.py \
       tests/test_security_report.py tests/test_security_signals.py tests/test_spec_requires.py \
       tests/test_support.py tests/test_tomlkit_roundtrip.py tests/test_translate_directory_slots.py \
       tests/test_translate_opencode_skill.py tests/test_translate_pi_skill.py \
       tests/test_translate_status_reporting.py tests/test_translators.py tests/test_tui_hook_integration.py \
       tests/test_tui_mcp_integration.py tests/test_tui_pi_tab.py tests/test_tui_pi_tab_bindings.py \
       tests/test_ui.py tests/test_validator.py tests/test_validator_schema_path.py \
       tests/test_walker.py tests/test_walker_mcp_legacy_removed.py tests/test_walker_sidecar.py \
       tests/test_walker_skill_shape.py tests/test_yaml_edit.py
```

- [ ] **Step 3: Delete `tests/audit/`, `tests/integration/`, `tests/_fixtures/`, and selected `tests/fixtures/` subdirs**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
git rm -r tests/audit tests/integration tests/_fixtures \
          tests/fixtures/migrate_skills_input tests/fixtures/migrate_skills_expected \
          tests/fixtures/plugin_sidecars
```

- [ ] **Step 4: Verify surviving test imports still resolve**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run python -c "import tests.conftest; print('conftest-ok')"
uv run pytest --collect-only -q 2>&1 | tail -20
```

Expected: `conftest-ok` first. `--collect-only` should list only skill tests, TUI tests, and `test_cli_help.py` (still in its old form — Task 13 rewrites it). If collection errors out citing a deleted module, find the surviving test that imports it and delete it (it was missed by the list above).

- [ ] **Step 5: Commit**

```bash
git commit -m "test: delete tests for removed CLI commands and support modules (#160)"
```

### Task 10: Rewrite `test_cli_help.py` to assert the new minimal help

**Files:**
- Modify: `tests/test_cli_help.py` (full rewrite)

- [ ] **Step 1: Write the failing test**

Replace the entire file with:

```python
"""Top-level CLI help should advertise only the `skill` command (post-#160)."""
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def test_top_level_help_lists_only_skill():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    # The only command we still advertise is `skill`.
    assert "skill" in result.output
    # The removed pre-v2 commands MUST NOT appear in --help.
    removed_commands = (
        "check", "diff", "doctor", "fix", "ingest", "inventory",
        "link", "list", "migrate-skills", "new", "pi", "unlink",
    )
    for cmd in removed_commands:
        # Look for the command-name *as it would appear in the Commands: table*
        # (i.e. surrounded by whitespace/start-of-line). A naive substring check
        # would false-positive on words like "checklist" or "doctor" appearing
        # in prose. We grep line-by-line for an exact token match.
        for line in result.output.splitlines():
            tokens = line.strip().split()
            assert cmd not in tokens, (
                f"Removed command {cmd!r} still appears in --help output: {line!r}"
            )


def test_top_level_help_describes_skill_purpose():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    # The new group docstring should orient the user toward `skill`.
    assert "skill" in result.output.lower()
```

- [ ] **Step 2: Run it**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run pytest tests/test_cli_help.py -v
```

Expected: PASS. (The CLI was already trimmed in Task 1; this test enforces that property going forward.)

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli_help.py
git commit -m "test(cli-help): assert --help advertises only \`skill\` post-#160"
```

### Task 11: Full test suite green check (mid-build)

After all deletions and the help-test rewrite, the suite should pass with a much smaller footprint.

- [ ] **Step 1: Clear pycache and run pytest**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
find . -type d -name __pycache__ -not -path '*/.venv/*' -exec rm -rf {} + 2>/dev/null || true
uv run pytest -q 2>&1 | tail -30
```

Expected: all tests pass (probably ~100-300 tests remaining, all skill + TUI + CLI-help). If anything fails, diagnose: most likely a test that wasn't in the delete list imports something we removed. Either delete the test or fix its import.

- [ ] **Step 2: If green, no commit needed — proceed to Phase E. If red, fix and commit fixes individually with messages like `fix(test): unbreak <test_file> post-removal`.**

---

## Phase E — Infrastructure cleanup

### Task 12: Clean up `lefthook.yml`

The `schema-vendor-check` hook diffs two schema files that no longer exist. Remove it. Keep `pytest`.

**Files:**
- Modify: `lefthook.yml`

- [ ] **Step 1: Rewrite lefthook.yml**

Replace contents with:

```yaml
pre-commit:
  parallel: true
  commands:
    pytest:
      run: uv run pytest -q
      stage_fixed: false
```

- [ ] **Step 2: Sanity-check by running pre-commit dry-run**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run lefthook run pre-commit 2>&1 | tail -20
```

Expected: exits 0; only `pytest` command runs.

- [ ] **Step 3: Commit**

```bash
git add lefthook.yml
git commit -m "chore(lefthook): drop schema-vendor-check (schemas/ deleted) (#160)"
```

### Task 13: Clean up `pyproject.toml`

The `[tool.hatch.build.targets.wheel.force-include]` block force-includes a deleted schema file. The wheel `packages` list still includes `src/agent_toolkit_cli` (correct) — leave that alone.

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Show current force-include block**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
sed -n '/force-include/,/^\[/p' pyproject.toml
```

Expected output includes:
```
[tool.hatch.build.targets.wheel.force-include]
"src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json" = "agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json"
```

- [ ] **Step 2: Delete the force-include block**

Edit `pyproject.toml` to remove the two-line `[tool.hatch.build.targets.wheel.force-include]` block entirely. Use the `Edit` tool with exact strings:

```
old_string:
[tool.hatch.build.targets.wheel.force-include]
"src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json" = "agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json"

new_string:
(empty — also remove the blank line preceding/following it as needed for clean formatting)
```

- [ ] **Step 3: Verify the package still builds**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv build 2>&1 | tail -10
```

Expected: a wheel + sdist appear in `dist/` with no errors. The wheel will be much smaller than before.

- [ ] **Step 4: Clean up build artifacts (they shouldn't be committed)**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
rm -rf dist
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "chore(pyproject): drop force-include for deleted _schemas/ (#160)"
```

### Task 14: Verify `assets/verification/` is gitignored

The spec calls this out as a Step-9 contract. Defensive — may already be present.

**Files:**
- Modify (conditional): `.gitignore`

- [ ] **Step 1: Check current state**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
grep -n "assets/verification" .gitignore || echo "not present"
```

- [ ] **Step 2: If "not present", append**

Use `Edit` to append the following line to `.gitignore` (at the bottom):

```
assets/verification/
```

(The baseline `helptext-before.txt` / `tree-before.txt` committed in Task 0 are pinned to history regardless of this rule, but any new artifacts created during Step 9 verify will be gitignored.)

- [ ] **Step 3: Commit (if step 2 ran)**

```bash
git add .gitignore
git commit -m "chore(gitignore): exclude assets/verification/ (#160)"
```

---

## Phase F — Docs

### Task 15: Rewrite `README.md`

**Files:**
- Modify: `README.md`

The current README has these sections:
1. Header + v2.1.0 callout — keep.
2. Install — keep (the editable-install warning about `uv tool install` shadowing is still relevant).
3. Two-flag contract — **remove**. The `--toolkit-repo` / `--project` flags don't exist anymore at the group level. `skill` doesn't use them.
4. "Commands → Skills (new in v2.0.0 — lock-file driven)" — keep, but drop the parenthetical (it's the only command now).
5. "Other asset kinds (CLI unchanged; TUI deferred to v3)" — **remove entirely**.
6. "Full reference" — keep but trim to skill-only.
7. Development — keep.
8. License — keep.

- [ ] **Step 1: Read the current README**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
cat README.md
```

- [ ] **Step 2: Rewrite to the new shape**

Use `Write` to replace the entire README with:

````markdown
# agent-toolkit-cli

Python CLI and Textual TUI for managing AI-agent **skills** across Claude Code, Codex, OpenCode, Gemini CLI, and Pi. Lock-file-driven, byte-compatible with [`vercel-labs/skills`](https://github.com/vercel-labs/skills).

> **v2.3.0 — single-command CLI.** The pre-v2 surface (`check`, `link`, `doctor`, `fix`, `ingest`, `inventory`, `migrate-skills`, `new`, `diff`, `list`, `unlink`, `pi`) was removed in #160. The frozen v1 surface lives on at the `v1.0.0` tag — install it with `uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit` if you need it. v2 commands will be rebuilt one by one in follow-up issues; see the tracker issue linked from PR #160.

## Install

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli agent-toolkit
# SSH form: git+ssh://git@github.com/ajanderson1/agent-toolkit-cli
```

> **Don't `pip install -e .` into a Python that comes earlier on `$PATH` than `~/.local/bin/`** (e.g., pyenv-managed Pythons). The pip shim will shadow `uv tool install`'s shim. If you must install editable for development, either:
>
> - Use a venv that you activate per-session (`python -m venv .venv && source .venv/bin/activate && pip install -e .`), or
> - First `uv tool uninstall agent-toolkit` to make the precedence explicit, and re-install from uv when you're done.

## Commands

### Skills — lock-file driven, agent-aware

```text
agent-toolkit-cli skill add <source> [-g|-p] [--ref <ref>] [--harness <h>]...
agent-toolkit-cli skill list [-g|-p]
agent-toolkit-cli skill status [<slug>...] [-g|-p]
agent-toolkit-cli skill update [<slug>...] [-g|-p]      # merge-aware
agent-toolkit-cli skill push   [<slug>...] [-g|-p]      # self-improvements upstream
agent-toolkit-cli skill remove <slug>... [-g|-p] [--force]
```

`<source>` accepts `owner/repo`, full URL, SSH URL, or local path — same scheme as `npx skills add`. See [`docs/agent-toolkit/skill-lock.md`](docs/agent-toolkit/skill-lock.md) for the lock-file format and skills.sh interop details.

The CLI uses the 55-agent catalog ported from [vercel-labs/skills](https://github.com/vercel-labs/skills/blob/main/src/agents.ts). Universal agents (codex, opencode, gemini-cli, +11 more whose `skillsDir == .agents/skills`) skip per-harness symlinks at global scope. Non-universal agents (claude-code, pi, windsurf, +37 more) still get their per-harness symlink. Interactive wizard groups by universality; TUI skill grid covers the two we explicitly support (claude-code, pi). v2.0.0's `AGENT_TOOLKIT_TUI_LEGACY=1` escape hatch is preserved.

### TUI

```text
agent-toolkit-tui                  # interactive skill grid (claude-code + pi)
AGENT_TOOLKIT_TUI_LEGACY=1 agent-toolkit-tui   # restore the legacy multi-tab layout
```

Full reference: [`docs/agent-toolkit/cli.md`](docs/agent-toolkit/cli.md).

## Development

```bash
git clone https://github.com/ajanderson1/agent-toolkit-cli ~/GitHub/projects/agent-toolkit-cli
cd ~/GitHub/projects/agent-toolkit-cli
uv sync --all-extras
uv run pytest -q
```

The `lefthook.yml` runs pytest on pre-commit.

## License

MIT (c) AJ Anderson
````

(Note: the literal `(c)` is intentional — avoid the `©` glyph in source per project conventions.)

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): trim to v2.3.0 single-command surface (#160)"
```

### Task 16: Rewrite `docs/agent-toolkit/cli.md`

The full command reference. Every removed command's section goes; the intro and `skill` section stay.

**Files:**
- Modify: `docs/agent-toolkit/cli.md`

- [ ] **Step 1: Read the current file to identify section boundaries**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
grep -n '^#' docs/agent-toolkit/cli.md | head -50
```

- [ ] **Step 2: Rewrite the file**

The new file should contain:

1. Top-level intro (one paragraph: what `agent-toolkit-cli` is, post-v2.3.0).
2. `## Skills` section — full reference (move existing content here, prune any cross-references to removed commands).
3. `## TUI` section — short pointer to `agent-toolkit-tui`.
4. Drop every section for `check`, `diff`, `doctor`, `fix`, `ingest`, `inventory`, `link`, `list`, `migrate-skills`, `new`, `pi`, `unlink`.

Use `Read` to load the current file, then `Write` to replace it with the trimmed version. If the file is large, use multiple `Edit` calls to remove each removed-command section individually. The two-flag contract section also goes (it described `--toolkit-repo` / `--project`, which no longer exist at group level).

- [ ] **Step 3: Verify no dead cross-references**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
grep -n "check\|doctor\|link\|unlink\|inventory\|ingest\|migrate" docs/agent-toolkit/cli.md | head -20
```

Expected: matches only in headings/paragraphs that legitimately mention the deprecation, not in syntax/usage examples.

- [ ] **Step 4: Commit**

```bash
git add docs/agent-toolkit/cli.md
git commit -m "docs(cli.md): trim to v2.3.0 single-command reference (#160)"
```

### Task 17: Rewrite `AGENTS.md`

Heavily references the legacy surface. Needs surgical pruning.

**Files:**
- Modify: `AGENTS.md`

The current AGENTS.md has:
1. Header — keep.
2. Data source / schema / drift gate paragraphs — **trim heavily** (schema vendoring is gone; drift gate is gone).
3. Two-flag contract section + applicability table — **remove**. No subcommand uses these flags now.
4. Code map — **rewrite** to reflect the new minimal layout.
5. Layered contract (do not invert) — **remove**. The contract described validator / walker / generator layers that are deleted.
6. Development workflow — **simplify**. `uv sync --all-extras && uv run pytest -q && uv run agent-toolkit-cli skill list`.
7. Schema sync — **remove**. No more vendored schema.
8. Asset identity (slug equality, mutex rule) — **remove**. These are toolkit-repo concerns now; this CLI only handles skills.
9. "Adding a new harness / asset kind / CLI subcommand" — **remove**. The spec it links to lives in the toolkit repo.

The new AGENTS.md should be ~30-50 lines, focused on: package layout (cli.py + commands/skill/ + skill_*.py), TUI sibling package, development workflow (uv sync, pytest), and a "Where to add a new skill subcommand" pointer.

- [ ] **Step 1: Rewrite `AGENTS.md`**

Use `Write` to replace the entire file with:

```markdown
# AGENTS.md — agent-toolkit-cli

The Python CLI (`src/agent_toolkit_cli`) and the Textual TUI (`src/agent_toolkit_tui`) for managing AI-agent skills. v2.3.0 removed the pre-v2 surface (`check`, `link`, `doctor`, …); only `skill` remains. The frozen v1 surface is pinned at the `v1.0.0` tag — see `README.md` for the install command.

## Code map

```
src/agent_toolkit_cli/             Python package: skill command + lockfile machinery.
  cli.py                           Click group; only `skill` is registered.
  commands/skill/                  `skill add | list | status | update | push | remove`.
  skill_agents.py                  55-agent catalog (ported from vercel-labs/skills).
  skill_git.py                     Git operations against per-skill upstream repos.
  skill_install.py                 Install/uninstall a skill into a harness home.
  skill_lock.py                    Read/write the `skill-lock.toml` lockfile.
  skill_paths.py                   Canonical paths for skills, lockfiles, projections.
  skill_source.py                  Parse `<owner/repo>` / URL / SSH / local-path sources.
  _repo_resolution.py              Resolve toolkit-repo root (used by TUI).
  _support.py                      Status constants used by TUI.
src/agent_toolkit_tui/             Textual TUI: skill grid (claude-code + pi).
docs/agent-toolkit/                Human-readable reference (cli.md, skill-lock.md).
tests/                             pytest. TUI tests live in tests/test_tui/.
```

## Development workflow

```bash
uv sync --all-extras
uv run pytest -q
uv run agent-toolkit-cli skill list
```

`lefthook.yml` runs `uv run pytest -q` on pre-commit.

## Adding a new `skill` subcommand

1. Add a new module under `src/agent_toolkit_cli/commands/skill/<name>_cmd.py`.
2. Define a Click command; import shared helpers from `_common.py`.
3. Register the command in `src/agent_toolkit_cli/commands/skill/__init__.py`.
4. Add a test under `tests/test_cli/test_cli_skill_<name>.py`.

## What lives elsewhere

- **Skill content** (the actual skill markdown / source) lives in each skill's upstream git repo; this CLI clones into a canonical lockfile-driven directory.
- **Schema** for skill-lock entries: see `docs/agent-toolkit/skill-lock.md`.
- **Agent catalog** (which harnesses are universal vs. per-harness): ported from `vercel-labs/skills` at the v2.1.0 cut; lives in `skill_agents.py`.
```

- [ ] **Step 2: Commit**

```bash
git add AGENTS.md
git commit -m "docs(AGENTS): trim to v2.3.0 skill-only architecture (#160)"
```

---

## Phase G — Follow-up tracker issue

The DoD requires a follow-up tracker so the v2 rebuild has a home. This is filed as part of the build phase so the PR body can link to it.

### Task 18: File the follow-up tracker issue

**Files:** *(none — this creates a GitHub issue)*

- [ ] **Step 1: Confirm v2.3.0 milestone exists**

```bash
gh api repos/ajanderson1/agent-toolkit-cli/milestones --jq '.[] | select(.state=="open") | "\(.number) \(.title)"'
```

Expected: list includes `4 v2.3.0` (created during issue #160 filing).

- [ ] **Step 2: File the tracker**

```bash
gh issue create \
  --repo ajanderson1/agent-toolkit-cli \
  --title "Rebuild v2-native replacements for deprecated CLI commands (tracker)" \
  --label "type:chore" \
  --assignee "@me" \
  --milestone "v2.3.0" \
  --body "$(cat <<'EOF'
Tracker for the rebuild work that follows #160 (the deprecation PR).

Each command removed in #160 needs an explicit decision: rebuild for v2, defer, or drop entirely. This issue is the index — open a focused issue per command if/when you decide to rebuild.

## Removed in #160

| Command | Rebuild decision | Notes |
|---|---|---|
| `check` | TBD | Was the asset-frontmatter validator. v2 has no frontmatter to validate yet. |
| `diff` | TBD | Alias for `link --dry-run`. Only relevant if `link` is rebuilt. |
| `doctor` | TBD | Five-group health check. Some checks (skill-shape, pi-advisories) may still be useful for v2. |
| `fix` | TBD | Regenerates AGENTS.md auto-regions. Useful if AGENTS.md auto-regions return. |
| `ingest` | TBD | Pulls an asset from URL/name/file. The v2 skill-add already covers the URL case. |
| `inventory` | TBD | Library-scoped catalog browser. The TUI skill grid covers this for skills. |
| `link` | TBD | Project assets per allow-list. v2 universals don't need per-project linking. |
| `list` | TBD | Project-scoped install state. The TUI covers this. |
| `migrate-skills` | **Drop** | One-shot migration tool; lives at v1.0.0 for anyone still needing it. |
| `new` | TBD | Scaffolds a new asset with frontmatter. Useful if a v2 scaffolder is desired. |
| `pi` | TBD | Pi-specific extension load/unload. Replaced (partially) by skill-grid in TUI. |
| `unlink` | TBD | Inverse of `link`. Only relevant if `link` is rebuilt. |

## Frozen v1 surface

For anyone still needing the legacy commands, install from the `v1.0.0` tag:

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit
```

This is the install path documented in the PR body and the v2.3.0 README.
EOF
)"
```

Capture the returned issue URL — the PR body in Task 19 references it.

- [ ] **Step 3: Record the tracker issue number in `flow.log`**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
echo "$(date '+%H:%M:%S') tracker issue filed: <URL>" >> assets/verification/160/flow.log
```

(Substitute the actual URL from Step 2's output.)

---

## Phase H — Final verification artifacts

The verification step (Step 9 of `aj-workflow flow`) runs *after* the build phase. But two pieces of evidence are easier to capture inside the build phase, before the flow harness takes over: the `--help` after, and the source tree after. The `pytest.log` and `ruff.log` artifacts are produced in flow Step 8 (pre-flight CI) and Step 9 (verify).

### Task 19: Capture post-removal verification artifacts

**Files:**
- Create: `assets/verification/160/helptext-after.txt`
- Create: `assets/verification/160/tree-after.txt`

- [ ] **Step 1: Capture --help after**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
uv run agent-toolkit-cli --help > assets/verification/160/helptext-after.txt 2>&1
```

- [ ] **Step 2: Capture source tree after**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
( cd src && find agent_toolkit_cli -type f -not -path '*/__pycache__/*' | sort ) > assets/verification/160/tree-after.txt
```

Expected: tree-after.txt has ~15-20 files versus tree-before.txt's ~80.

- [ ] **Step 3: Compute the diff for the PR body**

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
wc -l assets/verification/160/tree-before.txt assets/verification/160/tree-after.txt
diff assets/verification/160/tree-before.txt assets/verification/160/tree-after.txt | head -40
```

(For the human reviewer's sanity; not committed.)

- [ ] **Step 4: Commit the post-removal artifacts**

If `assets/verification/` is now gitignored (Task 14), force-add:

```bash
cd /Users/ajanderson/GitHub/projects/agent-toolkit-cli/.worktrees/chore-160-deprecate-legacy-cli
git add -f assets/verification/160/helptext-after.txt assets/verification/160/tree-after.txt
git commit -m "chore(verify): capture post-removal artifacts for #160"
```

If not gitignored:

```bash
git add assets/verification/160/helptext-after.txt assets/verification/160/tree-after.txt
git commit -m "chore(verify): capture post-removal artifacts for #160"
```

---

## Pre-flight expectations (for flow Step 8)

After the build phase completes, the flow harness runs pre-flight CI:

```bash
uv sync --all-extras
uv run pytest -q
```

Both should be green. There is no ruff or mypy in `lefthook.yml` or CI — only pytest — so the pre-flight is just the test suite.

If `pytest` is red after the build phase, the most likely causes (in order of probability):

1. A test outside the deletion list still imports a deleted module. Search with `grep -rn 'from agent_toolkit_cli\.' tests/ | grep -v skill_` to find stragglers.
2. A test inside `tests/test_tui/` still expects legacy TUI tabs (hook/mcp/pi). The v2.1.0 TUI strip should have already handled this, but verify by running the TUI tests in isolation: `uv run pytest tests/test_tui -v`.
3. A test in `tests/test_cli/` (skill tests) imports a now-deleted helper that it shouldn't have. Investigate per-test.

Each failure is a separate fix commit (`fix(test): unbreak <file> post-removal`), not amended into the deletion commits.

---

## Self-review (writing-plans checklist)

**1. Spec coverage:**

| Spec section | Plan task(s) |
|---|---|
| § Goal | All tasks |
| § Code map — `commands/` deletions | Task 2, 3 |
| § Code map — `_pi_*.py` siblings | Task 4 |
| § Code map — top-level support modules | Task 5, 6 |
| § Tests — delete legacy tests | Task 9 |
| § Tests — rewrite test_cli_help.py | Task 10 |
| § TUI — safety check (no TUI changes) | Implicitly verified by `uv run python -c "from agent_toolkit_tui.app import main"` in Tasks 5, 6 |
| § Docs — README | Task 15 |
| § Docs — cli.md | Task 16 |
| § Docs — AGENTS.md | Task 17 |
| § CI and release — lefthook | Task 12 |
| § CI and release — pyproject.toml | Task 13 |
| § DoD — Follow-up tracker | Task 18 |
| § Verification plan — helptext-before/after, tree-before/after | Tasks 0, 19 |
| § Risks — `yaml-edit` / `list-json` survival | Resolved during planning: both deleted (Task 3) |
| § Risks — TUI imports | Verified post-each-deletion |
| § Risks — CI / lefthook shellouts | Task 12 |

No spec section without a task.

**2. Placeholder scan:**

- No "TBD" in the deletion lists.
- No "implement later" anywhere.
- The follow-up tracker body (Task 18) does use "TBD" — but that is *intentional content* of the tracker issue, not a placeholder in the plan. Each "TBD" cell is a real decision to be made when that command's rebuild is taken on.
- Test code is fully written out (Task 10).
- Every file path is exact.

**3. Type consistency:**

- `main` (the Click group) is referenced consistently across Task 1 (write), Task 10 (test).
- `skill` (the imported subcommand) — imported from `agent_toolkit_cli.commands.skill` in Task 1, matches `commands/skill/__init__.py` which exports it.
- File paths cross-checked against the actual repo layout listed in spec § Code map.

No inconsistencies.

---

## Execution

**Plan complete and saved to `docs/superpowers/plans/2026-05-21-deprecate-legacy-cli.md`.**

Per the calling flow (`/aj-workflow flow 160` in `--auto` mode), the next step is the **plan-acceptance gate**, then execution via `superpowers:subagent-driven-development`. The flow harness owns dispatch.
