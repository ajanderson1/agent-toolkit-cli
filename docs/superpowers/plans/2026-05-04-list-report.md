# Plan: list --report

**Spec:** `docs/superpowers/specs/2026-05-04-list-report-design.md`
**Issue:** #11
**Branch:** `feat/11-list-report`
**Mode:** TDD per scenario.

## T1 — Inventory builder helper (refactor seam)

Look at `_list_json.py`'s `list_json` command. It's currently a Click command that emits JSON to stdout. To re-use the inventory data for the report formatter, we need to extract the *building* of the dict into a callable that returns it.

Two options:
1. **(preferred)** Extract `_build_inventory(toolkit_root, project_root, kind, harness) -> dict` from the body of `list_json`. `list_json` becomes a thin shim: build dict, dump JSON. The new formatter calls the same builder.
2. Run `list_json` via `ctx.invoke` and capture stdout. Brittle — opaque.

Option 1: Refactor `_list_json.py` lines ~126-225:
- Move the dict-building body into module-level `def _build_inventory(toolkit_root: Path, project_root: Path, kind: str | None = None, harness: str | None = None) -> dict`.
- `list_json` becomes: resolve toolkit_root + project_root (the existing block), call `_build_inventory`, `click.echo(json.dumps(out, indent=2))`.

**Run:** `uv run pytest tests/test_cli_list.py -q` → expect zero regressions (the JSON path output must be byte-identical).

## T2 — Failing tests for the formatter (red)

`tests/test_list_report.py` (new):

```python
"""Tests for the list --report formatter (issue #11)."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.generators.list_report import format_report


def _empty_inventory(toolkit: Path) -> dict:
    return {
        "toolkit_root": str(toolkit),
        "harnesses": ["claude", "codex", "opencode", "pi"],
        "assets": [],
    }


def test_empty_inventory(tmp_path):
    inv = _empty_inventory(tmp_path / "toolkit")
    out = format_report(inv, project_root=tmp_path / "project")
    assert "Asset inventory report" in out
    assert "(no assets discovered)" in out


def test_single_harness_linked(tmp_path):
    inv = {
        "toolkit_root": str(tmp_path / "toolkit"),
        "harnesses": ["claude", "codex", "opencode", "pi"],
        "assets": [
            {
                "kind": "skill",
                "slug": "alpha",
                "origin": "first-party",
                "description": "Alpha skill.",
                "path": str(tmp_path / "toolkit" / "skills" / "alpha" / "SKILL.md"),
                "declared_harnesses": ["claude"],
                "cells": [
                    {"harness": "claude", "scope": "user", "status": "linked",
                     "target": str(tmp_path / "toolkit" / "skills" / "alpha"),
                     "allowlisted": True},
                    {"harness": "claude", "scope": "project", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    *[{"harness": h, "scope": s, "status": "unsupported",
                       "target": None, "allowlisted": False}
                      for h in ("codex", "opencode", "pi") for s in ("user", "project")],
                ],
            }
        ],
    }
    out = format_report(inv, project_root=tmp_path / "project")
    assert "claude" in out
    assert "user" in out and "project" in out
    assert "alpha" in out
    assert "linked" in out
    # Deterministic order: claude before codex
    assert out.index("claude") < out.index("codex")


def test_multi_harness_multi_scope_grouping(tmp_path):
    inv = {
        "toolkit_root": str(tmp_path / "toolkit"),
        "harnesses": ["claude", "codex", "opencode", "pi"],
        "assets": [
            {
                "kind": "skill", "slug": "alpha",
                "origin": "first-party", "description": "",
                "path": str(tmp_path / "toolkit" / "skills" / "alpha"),
                "declared_harnesses": ["claude", "codex"],
                "cells": [
                    {"harness": "claude", "scope": "user", "status": "linked",
                     "target": "x", "allowlisted": True},
                    {"harness": "claude", "scope": "project", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    {"harness": "codex", "scope": "user", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    {"harness": "codex", "scope": "project", "status": "unlinked",
                     "target": None, "allowlisted": False},
                    *[{"harness": h, "scope": s, "status": "unsupported",
                       "target": None, "allowlisted": False}
                      for h in ("opencode", "pi") for s in ("user", "project")],
                ],
            },
        ],
    }
    out = format_report(inv, project_root=tmp_path / "project")
    # Both claude and codex headers appear
    assert "\nclaude" in out
    assert "\ncodex" in out
    # alpha appears under both
    assert out.count("alpha") >= 2  # at least once per harness header


def test_deterministic_ordering(tmp_path):
    """Two consecutive runs against the same dict produce identical output."""
    inv = _empty_inventory(tmp_path / "toolkit")
    inv["assets"].append({
        "kind": "skill", "slug": "alpha",
        "origin": "first-party", "description": "",
        "path": "x", "declared_harnesses": ["claude"],
        "cells": [{"harness": "claude", "scope": "user", "status": "unlinked",
                   "target": None, "allowlisted": False}],
    })
    a = format_report(inv, project_root=tmp_path / "project")
    b = format_report(inv, project_root=tmp_path / "project")
    assert a == b
```

**Run:** `uv run pytest tests/test_list_report.py -x` → ImportError.

## T3 — Implement the formatter (green)

`src/agent_toolkit_cli/generators/list_report.py` (new):

```python
"""Pure formatter for `agent-toolkit list --report`.

Consumes the same inventory dict the JSON path produces; emits a grouped
human-readable view: harness → scope → kind → asset entries.
"""
from __future__ import annotations

from pathlib import Path

_HARNESSES = ("claude", "codex", "opencode", "pi")
_SCOPES = ("user", "project")
_KINDS = ("skill", "agent", "command", "hook", "plugin")


def format_report(inventory: dict, *, project_root: Path) -> str:
    lines: list[str] = []
    lines.append("Asset inventory report")
    lines.append("")
    lines.append(f"Toolkit:  {inventory['toolkit_root']}")
    lines.append(f"Project:  {project_root}")
    lines.append("")

    if not inventory.get("assets"):
        lines.append("(no assets discovered)")
        return "\n".join(lines) + "\n"

    # Group cells: harness -> scope -> kind -> [(slug, status, target)]
    groups: dict[str, dict[str, dict[str, list[tuple[str, str, str | None]]]]] = {}
    for asset in inventory["assets"]:
        for cell in asset["cells"]:
            h, s = cell["harness"], cell["scope"]
            groups.setdefault(h, {}).setdefault(s, {}).setdefault(asset["kind"], []).append(
                (asset["slug"], cell["status"], cell.get("target"))
            )

    for harness in _HARNESSES:
        if harness not in groups:
            continue
        lines.append(harness)
        for scope in _SCOPES:
            if scope not in groups[harness]:
                continue
            lines.append(f"  {scope}")
            present_kinds = groups[harness][scope]
            for kind in _KINDS:
                if kind not in present_kinds:
                    continue
                entries = sorted(present_kinds[kind], key=lambda t: t[0])
                lines.append(f"    {kind}")
                for slug, status, target in entries:
                    if target:
                        lines.append(f"      {slug:<12} {status:<12} {target}")
                    else:
                        lines.append(f"      {slug:<12} {status}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

**Run:** Tests pass.

## T4 — CLI flag in `list.py`

Edit `src/agent_toolkit_cli/commands/list.py`:

1. Add `--report` boolean flag.
2. In `list_cmd` body, after the `--quiet` block: if `report` AND `fmt == "json"` → click error exit 2 with "cannot combine --report with --format=json".
3. If `report`: resolve toolkit_root + project_root (already in the function), call `_build_inventory(...)` from `_list_json`, call `format_report(...)`, `click.echo(text)`. Then `_ui.summary("Done.")`. Skip the rest of the function.

```python
@click.option("--report", "report", is_flag=True, default=False,
              help="Emit a grouped human-readable inventory (harness → scope → kind).")
```

```python
if report and fmt == "json":
    click.echo("cannot combine --report with --format=json", err=True)
    ctx.exit(2)
    return

# (after the existing toolkit_root + project_root resolution)

if report:
    from agent_toolkit_cli.commands._list_json import _build_inventory
    from agent_toolkit_cli.generators.list_report import format_report
    inv = _build_inventory(toolkit_root, project_root, kind=kind_filter, harness=harness_filter)
    click.echo(format_report(inv, project_root=project_root))
    _ui.summary("Done.")
    return
```

## T5 — CLI smoke test in `test_cli_list.py`

```python
def test_list_report_smoke(env, seed_skill):
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    (home / ".claude" / "skills").mkdir(parents=True)
    (home / ".claude" / "skills" / "alpha").symlink_to(toolkit / "skills" / "alpha")
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(toolkit), "list", "--report"])
    assert result.exit_code == 0, (result.output, result.stderr)
    assert "Asset inventory report" in result.output
    assert "claude" in result.output
    assert "alpha" in result.output
    assert "linked" in result.output


def test_list_report_rejects_format_json(env):
    runner = CliRunner()
    result = runner.invoke(main, ["--toolkit-repo", str(env["toolkit_root"]),
                                    "list", "--report", "--format=json"])
    assert result.exit_code == 2
    assert "cannot combine" in result.stderr
```

## T6 — Docs

`docs/agent-toolkit/cli.md`: insert one paragraph + 6-line example near the existing `list` section, after the `--format=json` block.

## T7 — Full suite

```bash
uv run pytest -q
```

Expected: ~319 passed (was 313, +6: 4 list_report + 2 cli_list), 2 skipped.

## T8 — Single commit

```
feat(list): add --report for grouped human-readable inventory

Closes #11.

`agent-toolkit list --report` emits a grouped view: harness → scope
→ kind → asset entries. Deterministic ordering for stable diffs in
CI logs. Re-uses the existing inventory builder; the formatter is
the only new code.

--report and --format=json are mutually exclusive.
```

## Acceptance checklist

- [ ] `agent-toolkit list --report` emits the grouped report.
- [ ] Output is byte-identical across two consecutive runs (deterministic).
- [ ] Default `list` unchanged; `--format=json` unchanged.
- [ ] `--report --format=json` rejected.
- [ ] `pytest -q` ≥ 319 passed, 2 skipped.

## Subagent escalation triggers

- Refactor T1 changes the JSON output (any test in `test_cli_list.py` regresses) → halt; the extraction must be a true refactor.
- The formatter accidentally pulls in `mcp` cells (which the JSON path includes as `unsupported`) → ensure the kind filter `_KINDS` excludes `mcp` (it does — check the tuple).
