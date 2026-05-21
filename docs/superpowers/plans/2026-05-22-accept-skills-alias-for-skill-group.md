# Plan — accept `skills` as alias for `skill` command group

**Issue:** #180
**Spec:** `docs/superpowers/specs/2026-05-22-accept-skills-alias-for-skill-group-design.md`
**Type:** feat
**Date:** 2026-05-22

## Summary

Two-line change plus tests. Register the existing `skill` Click group under the additional name `"skills"` so `agent-toolkit-cli skills ...` is interchangeable with `agent-toolkit-cli skill ...`.

## Files touched

| File | Change |
|---|---|
| `src/agent_toolkit_cli/cli.py` | Add `main.add_command(skill, name="skills")` after the existing `main.add_command(skill)`. |
| `tests/test_cli/test_cli_skill_aliases.py` | Append three tests covering the group alias. |

That is the entire scope. No new modules. No refactor of the existing `skill`/`ls`/`rm` wiring.

## Implementation steps

### Step 1 — Wire the alias

In `src/agent_toolkit_cli/cli.py`, immediately after the existing line:

```python
main.add_command(skill)
```

add:

```python
# Plural alias for muscle memory (matches `npx -y skills`). See #180.
main.add_command(skill, name="skills")
```

One-line comment is justified: the *why* is non-obvious from the code alone and prevents a future cleanup from removing the duplicate registration.

### Step 2 — Tests (TDD; write first, watch fail, then satisfy via Step 1)

Append to `tests/test_cli/test_cli_skill_aliases.py`. Match the existing style (CliRunner, `git_sandbox`, `tmp_path`, `monkeypatch`). Add three tests:

#### 2a. `test_skills_group_help_matches_skill_group_help`

```python
def test_skills_group_help_matches_skill_group_help():
    """`skills --help` should resolve to the same group as `skill --help`."""
    runner = CliRunner()
    by_skill = runner.invoke(main, ["skill", "--help"])
    by_skills = runner.invoke(main, ["skills", "--help"])
    assert by_skill.exit_code == 0, by_skill.output
    assert by_skills.exit_code == 0, by_skills.output
    # Both should advertise the same subcommands.
    for verb in ("add", "install", "list", "ls", "remove", "rm", "status", "update", "push", "reset"):
        assert verb in by_skills.output, f"expected '{verb}' in `skills --help`"
```

Rationale: Click renders the usage line as `Usage: main skill [...]` vs `Usage: main skills [...]`, so a strict `==` comparison would fail on that one line. The contract we actually care about is "every subcommand surfaced by `skill` is surfaced by `skills`" — assert that directly.

#### 2b. `test_skills_list_behaves_like_skill_list`

```python
def test_skills_list_behaves_like_skill_list(git_sandbox, tmp_path: Path, monkeypatch):
    """A representative subcommand invoked via the plural alias behaves identically."""
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    runner = CliRunner()
    assert _add_demo(runner, git_sandbox.upstream).exit_code == 0

    by_skill = runner.invoke(main, ["skill", "list", "-g"])
    by_skills = runner.invoke(main, ["skills", "list", "-g"])
    assert by_skill.exit_code == 0, by_skill.output
    assert by_skills.exit_code == 0, by_skills.output
    assert by_skill.output == by_skills.output
    assert "demo" in by_skills.output
```

Reuses the existing `_add_demo` helper at the top of the file. Mirrors `test_skill_ls_is_list` structurally so the intent is obvious to a reader scanning the file.

#### 2c. `test_root_help_lists_both_skill_and_skills`

```python
def test_root_help_lists_both_skill_and_skills():
    """Root `--help` should advertise both the canonical name and the plural alias."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0, result.output
    assert "skill" in result.output
    assert "skills" in result.output
```

Note: `"skill"` is a prefix of `"skills"`, so this assertion is technically weaker than it looks. Acceptable — Click renders both as separate entries in the Commands block (`  skill   ...`, `  skills  ...`), so the substring test does fail if either is removed. Stronger forms (regex on the Commands block) add brittleness for no real gain.

### Step 3 — Run the full test suite locally

`uv run pytest -q` (or whatever the repo's verify.sh / pre-commit invokes). All existing tests must still pass.

## Verification (Step 9 of flow)

No `.claude/testing.md` recipe matches this diff (it's a Python-only change with no UI surface). The flow's verify menu will be **terminal**: capture `agent-toolkit-cli skills --help` and `agent-toolkit-cli skill --help` side by side to `assets/verification/180/run.log` as proof the alias works end-to-end via the installed entry point.

## Rollback

A single-line revert in `cli.py` plus removing the three appended tests. Zero data, zero migration.

## Out of scope (re-stated from spec)

- Renaming `skill` to `skills`.
- Aliasing other root groups.
- Touching any `skill_lock.py` data fields named `skills`.

## Open questions

None. The pattern is established (`ls`, `rm`), the change is surgical, the contract is testable.
