# Default `skill install --agents` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `skill install`/`skill uninstall` `--agents` optional with a default (install→`standard`, uninstall→`all`), so skills install programmatically like the sibling asset kinds.

**Architecture:** A two-line behavioural change in one file — flip `required=True` to a `default=` on the two `@click.option("--agents", ...)` declarations. Everything downstream (`_resolve_agents`, `InstallPlan`, `engine_apply`, lock format) is unchanged; both tokens (`standard`, `all`) are already handled. The only test work is inverting the two existing "agents required" tests and adding one behavioural test for the maximal uninstall default.

**Tech Stack:** Python 3.12, Click, pytest with `CliRunner` + the existing `git_sandbox` / monkeypatched-HOME skill-install fixtures.

**Spec:** `docs/superpowers/specs/2026-06-12-skill-install-agents-default-design.md` (commit 8cac227). **Unblocks #369.**

---

## File structure

| File | Change |
|---|---|
| `src/agent_toolkit_cli/commands/skill/__init__.py` | `install_cmd` `--agents` (~:507): drop `required=True`, add `default="standard"`. `uninstall_cmd` `--agents` (~:611): drop `required=True`, add `default="all"` + a one-line rationale comment pointing at the agent-uninstall maximal precedent. |
| `tests/test_cli/test_cli_skill_install.py` | Invert `test_install_agents_required` (~:263) → `test_install_defaults_to_standard`. |
| `tests/test_cli/test_cli_skill_uninstall.py` | Invert `test_uninstall_agents_required` (~:130) → `test_uninstall_defaults_to_all_removes_everywhere` (behavioural: install to >1 agent, bare-uninstall, assert all gone). |

No other files. The `--help`-shows-default behaviour (AC4) falls out of the Click option change and needs no separate code.

---

## Task 1: Install defaults to `standard`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py` (`install_cmd` `--agents` option, ~:507)
- Test: `tests/test_cli/test_cli_skill_install.py` (replace `test_install_agents_required`, ~:263)

- [ ] **Step 1: Invert the existing required-test into a default-behaviour test**

Replace `test_install_agents_required` (lines ~263-269) with:

```python
def test_install_defaults_to_standard(git_sandbox, tmp_path, monkeypatch):
    """skill install with no --agents projects to the standard bundle."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    # No --agents — must default to 'standard', not error.
    result = runner.invoke(main, ["skill", "install", "demo"])
    assert result.exit_code == 0, result.output

    bundle_link = fake_home / ".agents" / "skills" / "demo"
    assert bundle_link.is_symlink(), "default install must create the standard bundle symlink"
    assert bundle_link.resolve() == (library_root / "demo").resolve()
```

- [ ] **Step 2: Run it to verify it fails (RED)**

Run: `uv run pytest tests/test_cli/test_cli_skill_install.py::test_install_defaults_to_standard -q`
Expected: FAIL — Click errors with `Missing option '--agents'` (exit code 2), so the `exit_code == 0` assert fails. This proves the default is not yet present.

- [ ] **Step 3: Make `--agents` default to `standard`**

In `src/agent_toolkit_cli/commands/skill/__init__.py`, the `install_cmd` option (~:507):

```python
# BEFORE
@click.option("--agents", "agents_str", required=True,
              help="Comma-separated agent names, 'standard', or 'all'.")
# AFTER
@click.option("--agents", "agents_str", default="standard", show_default=True,
              help="Comma-separated agent names, 'standard', or 'all'. "
                   "Defaults to the standard bundle.")
```

- [ ] **Step 4: Run it to verify it passes (GREEN)**

Run: `uv run pytest tests/test_cli/test_cli_skill_install.py -q`
Expected: PASS — the new test passes AND the existing explicit-`--agents` tests (claude-code, standard, project monorepo, windsurf) still pass unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_cli_skill_install.py
git commit -m "feat(skill): default skill install --agents to standard

Refs #393

Device: $(hostname -s)"
```

---

## Task 2: Uninstall defaults to `all` (maximal)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py` (`uninstall_cmd` `--agents` option, ~:611)
- Test: `tests/test_cli/test_cli_skill_uninstall.py` (replace `test_uninstall_agents_required`, ~:130)

- [ ] **Step 1: Invert the required-test into a maximal-default behavioural test**

Replace `test_uninstall_agents_required` (lines ~130-135) with a test that installs the skill to TWO targets (the standard bundle + claude-code), then runs a bare `skill uninstall` and asserts BOTH are removed — proving the default is maximal (`all`), not `standard`:

```python
def test_uninstall_defaults_to_all_removes_everywhere(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill uninstall with no --agents removes the skill from ALL targets (maximal default)."""
    library_root = tmp_path / "lib" / "skills"
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    # Install to BOTH the standard bundle and claude-code explicitly.
    r = runner.invoke(main, ["skill", "install", "demo", "--agents", "standard,claude-code"])
    assert r.exit_code == 0, r.output

    bundle_link = fake_home / ".agents" / "skills" / "demo"
    claude_link = fake_home / ".claude" / "skills" / "demo"
    assert bundle_link.is_symlink()
    assert claude_link.is_symlink()

    # Bare uninstall — must default to 'all' and remove BOTH, not just standard.
    result = runner.invoke(main, ["skill", "uninstall", "demo"])
    assert result.exit_code == 0, result.output
    assert not bundle_link.exists(), "standard bundle symlink must be removed by default uninstall"
    assert not claude_link.exists(), "claude-code symlink must be removed by default uninstall (maximal)"

    # Library canonical untouched.
    assert (library_root / "demo").exists(), "library must be untouched"
```

> **Worker note:** `--agents all` resolves via `detect_installed_agents()` (the `all`
> branch in `_resolve_agents`). For the bundle-bundle symlink (`standard`) to also be
> removed by `all`, confirm `detect_installed_agents()` includes the standard bundle
> when `~/.agents/skills/demo` exists. If `all` does NOT cover the standard token (it
> may only enumerate per-agent dirs), the correct default is `"standard,all"` or a
> dedicated maximal token — adjust the `default=` in Step 3 to whatever makes this
> test's "both removed" assertion pass, and update the spec's AC2 wording to match.
> Pin the exact default with THIS test; do not assume `all` ⊇ `standard` without the
> green bar. (The agent-uninstall precedent resolves its maximal set as
> `standard + ALL enabled harnesses` for exactly this reason — mirror that if `all`
> alone is insufficient: `default="standard,all"`.)

- [ ] **Step 2: Run it to verify it fails (RED)**

Run: `uv run pytest tests/test_cli/test_cli_skill_uninstall.py::test_uninstall_defaults_to_all_removes_everywhere -q`
Expected: FAIL — bare `skill uninstall demo` errors with `Missing option '--agents'` (exit 2), so the `exit_code == 0` assert fails.

- [ ] **Step 3: Make `--agents` default to the maximal set**

In `src/agent_toolkit_cli/commands/skill/__init__.py`, the `uninstall_cmd` option (~:611):

```python
# BEFORE
@click.option("--agents", "agents_str", required=True,
              help="Comma-separated agent names, 'standard', or 'all'.")
# AFTER
# Deliberately asymmetric with install's `standard` default: a bare uninstall
# must clean up EVERYWHERE the skill was projected (standard bundle + every
# per-agent symlink), never leaving orphans. Mirrors the maximal default of
# `agent uninstall` (commands/agent/uninstall_cmd.py:_resolve_harnesses_for_uninstall).
@click.option("--agents", "agents_str", default="all", show_default=True,
              help="Comma-separated agent names, 'standard', or 'all'. "
                   "Defaults to all (remove everywhere).")
```

If the Step-1 worker note found `all` alone does not cover the standard bundle, use
`default="standard,all"` instead and keep the comment.

- [ ] **Step 4: Run it to verify it passes (GREEN)**

Run: `uv run pytest tests/test_cli/test_cli_skill_uninstall.py -q`
Expected: PASS — the new test passes AND the existing explicit-`--agents` uninstall tests (standard, idempotent, project) still pass unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_cli_skill_uninstall.py
git commit -m "feat(skill): default skill uninstall --agents to all (maximal)

Refs #393

Device: $(hostname -s)"
```

---

## Task 3: Help text, regression sweep, and PR

**Files:**
- Test: `tests/test_cli/test_cli_skill_install.py` (one `--help` assertion)

- [ ] **Step 1: Add a --help assertion (AC4)**

Append to `tests/test_cli/test_cli_skill_install.py`:

```python
def test_install_help_marks_agents_optional():
    """--agents is no longer required and its default is shown."""
    result = CliRunner().invoke(main, ["skill", "install", "--help"])
    assert result.exit_code == 0
    # Click renders the default for show_default=True options.
    assert "[required]" not in result.output or "--agents" not in result.output.split("[required]")[0][-40:]
    assert "standard" in result.output  # default surfaced in help
```

> **Worker note:** the `[required]` assertion above is deliberately loose because
> Click's help layout varies. The robust check is: the `--agents` line no longer
> carries `[required]`. If the loose assertion is awkward, replace it with a direct
> scan: find the `--agents` line in `result.output` and assert `[required]` is not on
> it. Keep `assert "standard" in result.output` (the shown default).

- [ ] **Step 2: Run the install/uninstall test files**

Run: `uv run pytest tests/test_cli/test_cli_skill_install.py tests/test_cli/test_cli_skill_uninstall.py -q`
Expected: PASS.

- [ ] **Step 3: Grep for any other suite caller that relied on the old required behaviour**

Run: `grep -rn '"skill", "install"\|"skill", "uninstall"' tests/ | grep -v -- "--agents"`
Expected: review each hit. `tests/test_cli_skill_help_examples.py` and any doc-example test should still pass (a bare invocation now succeeds instead of erroring). If any test asserted a *non-zero* exit on a bare `skill install`/`uninstall`, update it — that assumption is now inverted. (The only two such tests are the ones inverted in Tasks 1–2; this grep confirms there are no others.)

- [ ] **Step 4: Full suite gate**

Run: `uv run pytest -q 2>&1 | tail -20`
Expected: all green EXCEPT the 2 known-whitelisted env failures
(`test_pi_extension_inventory::test_empty_machine_is_empty`,
`test_instruction_state::test_build_instruction_rows_empty_lock_no_canonical`),
both pre-existing and HOME-isolation related, unrelated to this change. If only
those two fail, `--no-verify` is the documented precedent for the final commit.

- [ ] **Step 5: Lint/type check**

Run: `uv run ruff check src/agent_toolkit_cli/commands/skill/__init__.py && uv run mypy src/agent_toolkit_cli/commands/skill/__init__.py`
Expected: no NEW errors over the baseline.

- [ ] **Step 6: Commit + PR**

```bash
git add tests/test_cli/test_cli_skill_install.py
git commit -m "test(skill): assert skill install --help marks --agents optional

Refs #393

Device: $(hostname -s)"
git push -u origin <branch>
gh pr create --title "feat(skill): default skill install/uninstall --agents (#393)" \
  --body "Closes #393. skill install defaults --agents to standard; skill uninstall defaults to all (maximal, mirrors agent uninstall). Backward-compatible: only the omitted-flag case changes. Unblocks #369. Spec + plan in docs/superpowers/."
```

---

## Self-review (against the spec)

**Spec coverage**

| Spec AC | Task |
|---|---|
| AC1 install no-flag → standard | Task 1 |
| AC2 uninstall no-flag → all (maximal) | Task 2 (+ worker note pins `all` vs `standard,all`) |
| AC3 explicit `--agents` unchanged | Tasks 1/2 Step 4 (existing tests stay green) |
| AC4 `--help` shows optional + default | Task 3 Step 1 |
| AC5 change confined to two options, nothing else | Tasks 1/2 (no other file touched) |
| AC6 global + project scope | Task 1 (global) + existing project tests stay green; Task 2 global behavioural |

**Placeholder scan:** Two worker notes (Task 2 Step 1, Task 3 Step 1) flag genuine
unknowns — whether `all` covers the `standard` bundle, and Click's exact help
layout. Both are pinned by a written test that must go green; neither is a
behaviour placeholder. The `default=` value in Task 2 Step 3 is explicitly
contingent on the Step-1 test (`all` or `standard,all`), with the agent-uninstall
precedent naming the fallback — that is a resolved decision rule, not a TODO.

**Type consistency:** No new types/signatures — only Click option kwargs change
(`required=True` → `default=...`, `show_default=True`). `agents_str` stays a
`str`; `_resolve_agents(agents_str, scope)` is called unchanged in both commands.

**Known reality risk (carried into execution):** whether `--agents all` removes the
standard-bundle symlink. Task 2's behavioural test is the gate; if `all` is
insufficient the default becomes `standard,all` (precedent-backed) and AC2's wording
updates to match. This is the only non-mechanical unknown and it is test-pinned.
