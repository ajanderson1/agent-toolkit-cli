# Plan: extract test fixtures to `tests/conftest.py`

**Spec:** `docs/superpowers/specs/2026-05-04-extract-conftest-design.md`
**Issue:** #8
**Branch:** `chore/8-extract-conftest`
**Mode:** mechanical refactor — verify by re-running the suite after each step.

## Task list

### T1 — Capture the baseline

```bash
uv run pytest --collect-only -q | tail -3            # baseline test count
uv run pytest -q                                       # baseline pass/skip
```

Expected: ~298 passed, 2 skipped (post-#18 main).

### T2 — Create `tests/conftest.py`

Contents:

```python
"""Shared fixtures for tests/test_cli_*.py (link/unlink/list/diff).

Per pytest convention, this module is auto-imported by pytest. Tests
request the fixtures by name in their function signatures.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest


SKILL_FRONTMATTER = """\
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: {slug}
  description: {slug} skill.
  lifecycle: stable
spec:
  origin: first-party
  vendored_via: none
  harnesses:
{harness_lines}
---
"""


def _seed_toolkit_impl(tmp: Path) -> Path:
    root = tmp / "toolkit"
    root.mkdir()
    (root / ".agent-toolkit-source").write_text("tool: agent-toolkit-cli\n")
    (root / "schemas").mkdir()
    schema_src = (
        Path(__file__).resolve().parents[1] / "schemas" / "asset-frontmatter.v1alpha1.json"
    )
    (root / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(schema_src.read_text())
    return root


def _seed_skill_impl(toolkit_root: Path, slug: str, harnesses: list[str]) -> Path:
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(f"    - {h}" for h in harnesses)
    (skill_dir / "SKILL.md").write_text(
        SKILL_FRONTMATTER.format(slug=slug, harness_lines=lines)
    )
    return skill_dir


@pytest.fixture
def seed_toolkit() -> Callable[[Path], Path]:
    """Factory: returns a function that creates a minimal valid toolkit repo at `tmp/toolkit`."""
    return _seed_toolkit_impl


@pytest.fixture
def seed_skill() -> Callable[[Path, str, list[str]], Path]:
    """Factory: returns a function that drops a skill SKILL.md into a toolkit repo."""
    return _seed_skill_impl


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    monkeypatch.delenv("AGENT_TOOLKIT_QUIET", raising=False)
    toolkit_root = _seed_toolkit_impl(tmp_path)
    return {"home": home, "toolkit_root": toolkit_root}
```

**Verify:** `uv run pytest -q` — must still be ~298 passed (the 4 test files still have their own duplicated copies; conftest fixtures don't conflict because they have different names).

### T3 — Strip duplication from `tests/test_cli_link.py`

1. Delete lines 14-61 (the entire duplicated block: `SKILL_FRONTMATTER`, `_seed_toolkit`, `_seed_skill`, `env` fixture).
2. Keep the imports above (lines 1-12 — `os`, `shutil`, `Path`, `pytest`, `CliRunner`, `main`).
3. Find every test that takes `_seed_toolkit` or `_seed_skill` as a regular function call:
   - Add `seed_skill` (or `seed_toolkit`) to the function's parameter list.
   - Replace the call: `_seed_skill(...)` → `seed_skill(...)`.
4. Tests that already take `env` (which calls `_seed_toolkit_impl` internally) need no extra param for the toolkit-seeding side.

**Verify:** `uv run pytest tests/test_cli_link.py -q` — green.

### T4 — Strip duplication from `tests/test_cli_unlink.py`

Same pattern as T3.

**Verify:** `uv run pytest tests/test_cli_unlink.py -q` — green.

### T5 — Strip duplication from `tests/test_cli_list.py`

Same pattern. The local `multi_env` fixture stays in this file (only consumer).

**Verify:** `uv run pytest tests/test_cli_list.py -q` — green.

### T6 — Strip duplication from `tests/test_cli_diff.py`

Same pattern.

**Verify:** `uv run pytest tests/test_cli_diff.py -q` — green.

### T7 — Full-suite verification

```bash
uv run pytest --collect-only -q | tail -3            # match T1 count
uv run pytest -q                                       # match T1 pass/skip
```

Expected: identical numbers to T1.

### T8 — Single commit

```
chore(tests): extract shared fixtures to tests/conftest.py

Closes #8.

Move SKILL_FRONTMATTER, _seed_toolkit, _seed_skill, and the `env`
fixture out of tests/test_cli_{link,unlink,list,diff}.py into a
new tests/conftest.py. The helpers become factory fixtures
(`seed_toolkit`, `seed_skill`) so tests request them by name with
no `from conftest import …` line.

~190 lines of identical code removed across 4 files; suite count
and pass/skip totals unchanged.
```

## Acceptance checklist (Verify will run this)

- [ ] `tests/conftest.py` exists.
- [ ] None of `tests/test_cli_link.py / unlink.py / list.py / diff.py` define `SKILL_FRONTMATTER`, `_seed_toolkit`, `_seed_skill`, or the `env` fixture.
- [ ] `uv run pytest -q` reports the same `passed, skipped` counts as before (~298, 2).
- [ ] `uv run pytest --collect-only -q | wc -l` is unchanged.
- [ ] No `from conftest import …` lines appear anywhere.

## Subagent escalation triggers

- Suite count drops or rises post-refactor → halt; the refactor changed behaviour somewhere. Surface the failing/missing tests.
- A `_seed_skill` reference is missed and surfaces as `NameError` at collection → fix in place; don't escalate. (Mechanical fix.)
- A test imports `SKILL_FRONTMATTER` directly somewhere I haven't surveyed → expose it via a fixture instead of escalating.
