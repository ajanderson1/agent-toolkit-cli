# Plan: warn when target harness home is missing

**Spec:** `docs/superpowers/specs/2026-05-04-warn-missing-harness-home-design.md`
**Issue:** #13
**Branch:** `chore/13-warn-missing-harness-home`
**Mode:** TDD per task.

## T1 — Helper + tests for `harness_home_path`

Add to `tests/test_link_lib.py`:

```python
def test_harness_home_path_uses_home_env(monkeypatch, tmp_path):
    from agent_toolkit_cli.commands._link_lib import harness_home_path
    monkeypatch.setenv("HOME", str(tmp_path))
    assert harness_home_path("claude") == tmp_path / ".claude"
    assert harness_home_path("pi") == tmp_path / ".pi"

def test_harness_home_path_explicit_home_overrides_env(tmp_path):
    from agent_toolkit_cli.commands._link_lib import harness_home_path
    other = tmp_path / "other-home"
    assert harness_home_path("codex", home=other) == other / ".codex"
```

**Run:** `uv run pytest tests/test_link_lib.py -x` → expect ImportError on the helper.

Then add to `src/agent_toolkit_cli/commands/_link_lib.py` (after `ALL_HARNESSES`):

```python
import os

HARNESS_HOMES: dict[str, str] = {
    "claude":   ".claude",
    "codex":    ".codex",
    "opencode": ".opencode",
    "pi":       ".pi",
}


def harness_home_path(harness: str, home: Path | None = None) -> Path:
    """Return the absolute path to a harness's home directory under $HOME."""
    h = home if home is not None else Path(os.environ.get("HOME", ""))
    return h / HARNESS_HOMES[harness]
```

Note: the file already imports `Path` and `click`. Add `import os` if not present.

**Run:** `uv run pytest tests/test_link_lib.py -x` → green.

## T2 — Doctor group: `harness_homes` (red)

Add `tests/test_doctor_harness_homes.py`:

```python
"""Tests for doctor's harness_homes group."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.doctor import harness_homes
from agent_toolkit_cli.doctor.result import Status


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    h.mkdir()
    monkeypatch.setenv("HOME", str(h))
    return h


def test_all_present_returns_ok(home):
    for d in (".claude", ".codex", ".opencode", ".pi"):
        (home / d).mkdir()
    result = harness_homes.run()
    assert result.status == Status.OK
    assert result.name == "harness-homes"


def test_one_missing_returns_warn(home):
    # codex missing
    for d in (".claude", ".opencode", ".pi"):
        (home / d).mkdir()
    result = harness_homes.run()
    assert result.status == Status.WARN
    assert any("codex" in f for f in result.findings)


def test_all_missing_returns_warn(home):
    result = harness_homes.run()
    assert result.status == Status.WARN
    for h in ("claude", "codex", "opencode", "pi"):
        assert any(h in f for f in result.findings)
```

**Run:** `uv run pytest tests/test_doctor_harness_homes.py -x` → expect ImportError.

## T3 — Implement `harness_homes` group (green)

New file `src/agent_toolkit_cli/doctor/harness_homes.py`:

```python
"""Doctor: harness_homes group — checks ~/.{harness}/ exists per harness."""
from __future__ import annotations

from agent_toolkit_cli.commands._link_lib import ALL_HARNESSES, harness_home_path
from agent_toolkit_cli.doctor.result import GroupResult, Status


def run() -> GroupResult:
    findings: list[str] = []
    missing: list[str] = []
    for harness in ALL_HARNESSES:
        path = harness_home_path(harness)
        if path.is_dir():
            findings.append(f"{harness} home present at {path}")
        else:
            missing.append(
                f"{harness} home not present at {path} — install the harness "
                f"or stage symlinks anyway"
            )

    if missing:
        return GroupResult(
            name="harness-homes",
            status=Status.WARN,
            summary=f"{len(missing)} harness home(s) missing",
            findings=findings + missing,
            fix_hint="install the harness, or ignore — symlinks can be staged ahead of install",
        )

    return GroupResult(
        name="harness-homes",
        status=Status.OK,
        summary="all 4 harness homes present",
        findings=findings,
    )
```

**Run:** `uv run pytest tests/test_doctor_harness_homes.py -x` → green.

## T4 — Wire into `commands/doctor.py`

Edit `src/agent_toolkit_cli/commands/doctor.py`:

1. Add `harness_homes as g_harness_homes` to the `from agent_toolkit_cli.doctor import …` block.
2. Add `"harness-homes"` to `_GROUPS` tuple.
3. Add `("harness-homes", lambda: g_harness_homes.run()),` to `_run_global`'s `runners` list (at the end, just before `duplicates` for grouping by concept).

**Run:** `uv run agent-toolkit doctor --group harness-homes` (smoke); `uv run pytest tests/ -k doctor -q` (regression).

## T5 — Tests for link warning (red)

Add to `tests/test_cli_link.py`:

```python
# ===========================================================================
# Issue #13 — warn when the harness home doesn't exist
# ===========================================================================

def test_link_warns_when_harness_home_missing(env, seed_skill):
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    # ~/.codex deliberately not created
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "codex"],
    )
    assert result.exit_code == 0  # warn, not error
    assert "codex home not present" in result.stderr


def test_link_quiet_suppresses_missing_home_warning(env, seed_skill):
    home, toolkit = env["home"], env["toolkit_root"]
    seed_skill(toolkit, "alpha", ["codex"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "codex", "--quiet"],
    )
    assert result.exit_code == 0
    assert "home not present" not in (result.stderr or "")


def test_link_no_warning_when_harness_home_exists(env, seed_skill):
    home, toolkit = env["home"], env["toolkit_root"]
    (home / ".claude").mkdir()
    seed_skill(toolkit, "alpha", ["claude"])
    (home / ".agent-toolkit.yaml").write_text("skills:\n  - alpha\n")
    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit), "link", "user", "claude"],
    )
    assert result.exit_code == 0
    assert "home not present" not in (result.stderr or "")
```

**Run:** `uv run pytest tests/test_cli_link.py -k home -x` → expect 2 of 3 fail (the last one passes by accident since no warning is emitted today).

## T6 — Wire warning into `link.py` (green)

Edit `src/agent_toolkit_cli/commands/link.py`:

After `validate_harness(ctx, harness)` (line 73), insert:

```python
    if os.environ.get("AGENT_TOOLKIT_QUIET") != "1":
        home_path = harness_home_path(harness)
        if not home_path.is_dir():
            click.echo(
                f"warning: {harness} home not present at {home_path} — "
                f"linking anyway, but the symlinks won't be picked up until {harness} is installed",
                err=True,
            )
```

Add `harness_home_path` to the existing `from agent_toolkit_cli.commands._link_lib import (…)` block.

**Run:** `uv run pytest tests/test_cli_link.py -k home -x` → green.

## T7 — Full suite

```bash
uv run pytest -q
```

Expect: ~305 passed (was 299; +5 link_lib + harness_homes + link tests; minus whatever I miscount), 2 skipped.

## T8 — Smoke

```bash
uv run agent-toolkit doctor --group harness-homes --verbose
```

Should list each harness home with status.

## T9 — Single commit

```
feat(doctor,link): warn when target harness home is missing

Closes #13.

- New doctor group `harness-homes` checks ~/.{harness}/ for each of
  claude/codex/opencode/pi. Missing → WARN with a one-line hint.
- `link <harness>` prints a one-line stderr warning when the harness
  home is absent, then proceeds (warn, not error). --quiet suppresses
  via AGENT_TOOLKIT_QUIET=1.
- Helper `harness_home_path()` and `HARNESS_HOMES` map added to
  _link_lib.py as the single source of truth.
```

## Acceptance checklist

- [ ] `agent-toolkit doctor` includes `harness-homes` group; missing homes → WARN.
- [ ] `agent-toolkit link <harness>` prints warning on stderr when home missing; exits 0.
- [ ] `--quiet` suppresses the warning.
- [ ] Tests cover: all present, one missing, all missing (doctor); warn / quiet-suppressed / no-warn-when-present (link).

## Subagent escalation triggers

- A test that should fail at T1/T2/T5 passes immediately → halt; the helper or group might already exist somewhere I missed.
- Pytest count delta != +6 to +8 → halt, surface.
