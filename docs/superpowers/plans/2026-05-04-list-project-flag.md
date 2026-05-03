# Plan: add `--project` to `list`

**Spec:** `docs/superpowers/specs/2026-05-04-list-project-flag-design.md`
**Issue:** #7
**Branch:** `feat/7-list-project-flag`
**Mode:** TDD — failing test first.

## T1 — Failing test

Add to `tests/test_cli_list.py`:

```python
def test_list_project_flag_resolves_correctly(tmp_path, env, seed_skill, monkeypatch):
    """`list --project /x` reads /x/.agent-toolkit.yaml, not CWD's."""
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])

    # Set up a project dir with alpha installed
    proj = home / "myproject"
    proj.mkdir()
    (proj / ".agent-toolkit.yaml").write_text(
        "skills:\n  - alpha\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    (proj / ".claude" / "skills").mkdir(parents=True)
    (proj / ".claude" / "skills" / "alpha").symlink_to(toolkit / "skills" / "alpha")

    # Run from an unrelated cwd (tmp_path itself), pointing --project at proj.
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit), "list", "--project", str(proj)],
    )
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "alpha" in result.output
    assert "project:✓" in result.output
```

**Run:** `uv run pytest tests/test_cli_list.py::test_list_project_flag_resolves_correctly -x` → expect `--project: No such option`.

## T2 — Add the flag

Edit `src/agent_toolkit/commands/list.py`:

After the existing `--toolkit-repo` option (around line 91), add:

```python
@click.option(
    "--project",
    "project_flag",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
```

Add `project_flag: Path | None,` to the `list_cmd` signature.

Replace lines 149-150:

```python
project_root_raw: Path | None = (ctx.obj or {}).get("project_root")
project_root = project_root_raw.resolve() if project_root_raw else Path.cwd()
```

with the link.py pattern:

```python
if project_flag:
    project_root = Path(project_flag).resolve()
elif (group_proj := (ctx.obj or {}).get("project_root")) is not None:
    project_root = Path(group_proj).resolve()
else:
    project_root = Path.cwd()
```

**Run:** `uv run pytest tests/test_cli_list.py -x` → expect green.

## T3 — Full suite

```bash
uv run pytest -q
```

Expect: 299 passed (was 298), 2 skipped.

## T4 — Single commit

```
feat(list): accept --project DIR for symmetry with link/unlink/diff

Closes #7.

`list` previously only honoured the group-level --project. This adds
the per-command flag matching the resolution order in link.py:
  1. --project DIR flag
  2. group-level --project from ctx.obj
  3. CWD fallback
```

## Acceptance checklist

- [ ] `agent-toolkit list --project /tmp` is accepted (no "No such option").
- [ ] Group-level `--project` still works as fallback.
- [ ] `pytest -q` is 299 passed, 2 skipped.

## Subagent escalation triggers

- The new test passes immediately (before T2) → halt; the option might already exist somewhere I missed. Surface.
- Pytest count delta != +1 → halt, surface.
