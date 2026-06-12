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
| `src/agent_toolkit_cli/commands/skill/__init__.py` | `install_cmd` `--agents` (~:507): drop `required=True`, add `default="standard"`. `uninstall_cmd` `--agents` (~:611): drop `required=True`, add `default=None`; when omitted, compute the maximal target `("standard", *detect_installed_agents())` in the command body (NOT via `_resolve_agents`, which can't parse `standard,all`) + a rationale comment pointing at the agent-uninstall maximal precedent. |
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

## Task 2: Uninstall defaults to the maximal set (`standard` + all detected)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/__init__.py` (`uninstall_cmd` `--agents` option ~:611 + its body ~:619-634)
- Test: `tests/test_cli/test_cli_skill_uninstall.py` (replace `test_uninstall_agents_required`, ~:130)

**Why this is NOT a one-line default** (verified against code in critical review):
`_resolve_agents("all")` returns `tuple(detect_installed_agents())`, and the
`standard` token has `detect_installed=lambda: False` (`skill_agents.py:499`) — so
`all` can **never** include `standard`, and only the `standard` token removes the
`~/.agents/skills/<slug>` bundle symlink. `default="all"` would orphan it.
`_resolve_agents("standard,all")` would **raise** `unknown agent(s): all` (the `all`
special-case only fires when it's the entire string, `:210`). So the maximal default
is computed in `uninstall_cmd` itself as `("standard", *detect_installed_agents())`,
mirroring `agent uninstall`'s `("standard", *sorted(detected))`. `detect_installed_agents`
is already imported in this module (`:15`). `_resolve_agents` is untouched.

- [ ] **Step 1: Invert the required-test into a maximal-default behavioural test**

Replace `test_uninstall_agents_required` (lines ~130-135) with a test that installs
the skill to TWO targets (the standard bundle + claude-code), then runs a bare
`skill uninstall` and asserts BOTH are removed — proving the default removes the
`standard` bundle (which `all` alone does not):

```python
def test_uninstall_defaults_to_maximal_removes_everywhere(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """skill uninstall with no --agents removes standard bundle + every detected agent."""
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

    # Bare uninstall — maximal default must remove BOTH (the standard bundle proves
    # the union, since `--agents all` alone would leave bundle_link orphaned).
    result = runner.invoke(main, ["skill", "uninstall", "demo"])
    assert result.exit_code == 0, result.output
    assert not bundle_link.exists(), "standard bundle symlink must be removed by default uninstall"
    assert not claude_link.exists(), "claude-code symlink must be removed by default uninstall (maximal)"

    # Library canonical untouched.
    assert (library_root / "demo").exists(), "library must be untouched"
```

- [ ] **Step 2: Run it to verify it fails (RED)**

Run: `uv run pytest tests/test_cli/test_cli_skill_uninstall.py::test_uninstall_defaults_to_maximal_removes_everywhere -q`
Expected: FAIL — bare `skill uninstall demo` errors with `Missing option '--agents'` (exit 2), so the `exit_code == 0` assert fails.

- [ ] **Step 3: Make `--agents` optional and compute the maximal union when omitted**

In `src/agent_toolkit_cli/commands/skill/__init__.py`, the `uninstall_cmd` option (~:611):

```python
# BEFORE
@click.option("--agents", "agents_str", required=True,
              help="Comma-separated agent names, 'standard', or 'all'.")
# AFTER
@click.option("--agents", "agents_str", default=None,
              help="Comma-separated agent names, 'standard', or 'all'. "
                   "Default (omitted): remove everywhere (standard bundle + all "
                   "detected agents).")
```

Then, in the `uninstall_cmd` body, replace the resolution block (currently
`try: target_agents = _resolve_agents(agents_str, scope) except ...`, ~:627-630) with:

```python
    if agents_str is None:
        # Maximal default — deliberately asymmetric with install's `standard`.
        # A bare uninstall must clean up EVERYWHERE the skill was projected, so we
        # union the synthetic `standard` token (the only thing that removes
        # ~/.agents/skills/<slug>; `--agents all` excludes it because the standard
        # AgentConfig has detect_installed=False) with every detected agent. This
        # mirrors `agent uninstall`'s maximal resolver
        # (commands/agent/uninstall_cmd.py:_resolve_harnesses_for_uninstall, which
        # returns ("standard", *sorted(detected))). We compute the union here rather
        # than via a token because _resolve_agents("standard,all") would raise.
        target_agents = ("standard", *detect_installed_agents())
    else:
        target_agents = _resolve_agents(agents_str, scope)
```

(The subsequent `if not target_agents: ... nothing to do` guard and the
global/project `InstallPlan` branches are unchanged.)

- [ ] **Step 4: Run it to verify it passes (GREEN)**

Run: `uv run pytest tests/test_cli/test_cli_skill_uninstall.py -q`
Expected: PASS — the new test passes AND the existing explicit-`--agents` uninstall tests (standard, idempotent, project) still pass unchanged.

- [ ] **Step 5: Add project-scope coverage for the maximal default**

Project scope removes the bundle symlink via a different path
(`<project>/.agents/skills/<slug>`) than global, so cover it explicitly. Append to
`tests/test_cli/test_cli_skill_uninstall.py` (model on the existing
`test_uninstall_project_preserves_canonical`, which shows the project install/
uninstall + external-canonical-preserved idiom):

```python
def test_uninstall_project_defaults_to_maximal(
    git_sandbox, tmp_path: Path, monkeypatch
):
    """Bare project-scope uninstall removes project standard + per-agent projections."""
    from agent_toolkit_cli.skill_paths import project_store_root
    library_root = tmp_path / "lib" / "skills"
    project = tmp_path / "proj"
    project.mkdir()
    (project / ".claude").mkdir()
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    r = runner.invoke(main, ["skill", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(main, [
        "--project", str(project), "skill", "install", "demo",
        "--scope", "project", "--agents", "standard,claude-code",
    ])
    assert r.exit_code == 0, r.output

    proj_bundle = project / ".agents" / "skills" / "demo"
    claude_link = project / ".claude" / "skills" / "demo"
    external_canonical = project_store_root(project) / "demo"
    assert proj_bundle.is_symlink() or proj_bundle.exists()
    assert claude_link.is_symlink()

    # Bare project uninstall — maximal default removes both projections.
    result = runner.invoke(main, [
        "--project", str(project), "skill", "uninstall", "demo", "--scope", "project",
    ])
    assert result.exit_code == 0, result.output
    assert not claude_link.exists(), "project claude-code symlink must be removed"
    assert not proj_bundle.exists(), "project standard bundle symlink must be removed"
    # Non-destructive: external canonical survives.
    assert external_canonical.is_dir(), "external canonical must survive uninstall"
```

> **Worker note:** confirm the project standard-bundle projection path is
> `<project>/.agents/skills/<slug>` (the install engine's project-standard link —
> `_project_standard_link`). If the real path differs, point `proj_bundle` at the
> actual location; the assertion (both projections gone, canonical preserved) is the
> invariant. `detect_installed_agents()` at project scope governs which per-agent
> projections the union targets — claude-code is detected via the `.claude/` dir
> seeded above.

- [ ] **Step 6: Run the project test (GREEN)**

Run: `uv run pytest tests/test_cli/test_cli_skill_uninstall.py -q`
Expected: PASS (all uninstall tests, global + project).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/__init__.py tests/test_cli/test_cli_skill_uninstall.py
git commit -m "feat(skill): default skill uninstall to maximal (standard + detected)

Computed as ('standard', *detect_installed_agents()) in uninstall_cmd
when --agents is omitted, mirroring agent uninstall. '--agents all'
alone excludes the standard bundle (detect_installed=False), so a bare
'all' default would orphan ~/.agents/skills/<slug>.

Refs #393

Device: \$(hostname -s)"
```

---

## Task 3: Help text, regression sweep, and PR

**Files:**
- Test: `tests/test_cli/test_cli_skill_install.py` (one `--help` assertion)

- [ ] **Step 1: Add a --help assertion (AC4)**

Append to `tests/test_cli/test_cli_skill_install.py`:

```python
def test_install_help_marks_agents_optional():
    """The --agents option is no longer [required] on skill install."""
    result = CliRunner().invoke(main, ["skill", "install", "--help"])
    assert result.exit_code == 0
    # Robust, layout-independent check: find the --agents line, assert no [required].
    agents_line = next(
        (ln for ln in result.output.splitlines() if "--agents" in ln), ""
    )
    assert agents_line, "--agents must appear in help"
    assert "[required]" not in agents_line, "--agents must no longer be required"
```

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

Device: \$(hostname -s)"
git push -u origin <branch>
gh pr create --title "feat(skill): default skill install/uninstall --agents (#393)" \
  --body "Closes #393. skill install defaults --agents to standard; skill uninstall defaults to the maximal set (standard + all detected agents, mirroring agent uninstall — a bare 'all' would orphan the standard bundle). Backward-compatible: only the omitted-flag case changes. Unblocks #369. Spec + plan in docs/superpowers/."
```

---

## Self-review (against the spec)

**Spec coverage**

| Spec AC | Task |
|---|---|
| AC1 install no-flag → standard | Task 1 |
| AC2 uninstall no-flag → maximal (`standard` + detected) | Task 2 (union computed in `uninstall_cmd`) |
| AC3 explicit `--agents` unchanged | Tasks 1/2 (existing explicit tests stay green) |
| AC4 `--help` no longer `[required]` | Task 3 Step 1 |
| AC5 install one-line; uninstall union local to `uninstall_cmd`, shared resolver untouched | Tasks 1/2 |
| AC6 global + project scope | Task 1 (install global) + Task 2 global behavioural + Task 2 Step 5 project behavioural |

**Placeholder scan:** No behaviour placeholders. The earlier "does `all` cover
`standard`" unknown is now **resolved** (it does not — verified in the critical
review against `skill_agents.py:499` `detect_installed=lambda: False`), so Task 2
computes the union `("standard", *detect_installed_agents())` directly and the
`default=None` sentinel is concrete, not contingent. The remaining worker note
(Task 2 Step 5) flags only the project standard-link path name, pinned by the
project behavioural test's invariant (both projections gone, canonical preserved).

**Type consistency:** `install_cmd` `--agents`: `required=True` → `default="standard"`.
`uninstall_cmd` `--agents`: `required=True` → `default=None`, with `agents_str: str
| None` and a union branch producing `target_agents: tuple[str, ...]`.
`_resolve_agents(agents_str, scope)` is still called for the explicit path in both
commands (unchanged signature); `detect_installed_agents()` (already imported,
`:15`) supplies the union. `mypy` note: `agents_str` param annotation on
`uninstall_cmd` becomes `str | None` — update it from `str`.

**Resolved reality risks (from critical review, now baked in):** (1) `all` excludes
`standard` → union in `uninstall_cmd`, not a token default. (2)
`_resolve_agents("standard,all")` raises → never constructed; union is a tuple. (3)
project-scope bundle-link removal is a distinct path → Task 2 Step 5 covers it.
