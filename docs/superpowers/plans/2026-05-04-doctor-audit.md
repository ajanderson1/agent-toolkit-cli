# Plan: doctor audit — allow-list and cross-toolkit symlinks

**Spec:** `docs/superpowers/specs/2026-05-04-doctor-audit-design.md`
**Issue:** #10
**Branch:** `feat/10-doctor-audit`
**Mode:** TDD per check.

## T1 — Test the empty/clean case (red)

`tests/test_doctor_allowlist_audit.py` (new):

```python
"""Tests for the allowlist-audit doctor group (issue #10)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.doctor import allowlist_audit
from agent_toolkit_cli.doctor.result import Status


@pytest.fixture
def env(tmp_path, monkeypatch, seed_toolkit, seed_skill):
    """Toolkit with one skill, empty home, no allowlist."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    toolkit_root = seed_toolkit(tmp_path)
    seed_skill(toolkit_root, "alpha", ["claude"])
    return {"home": home, "toolkit_root": toolkit_root}


def test_clean_returns_ok(env):
    result = allowlist_audit.run(env["toolkit_root"], project_root=env["home"])
    assert result.status == Status.OK
    assert result.name == "allowlist-audit"
```

**Run:** `uv run pytest tests/test_doctor_allowlist_audit.py -x` → ImportError.

## T2 — Stub the group module to make T1 pass (green)

`src/agent_toolkit_cli/doctor/allowlist_audit.py`:

```python
"""Doctor: allowlist-audit group — slug-existence + cross-toolkit symlinks."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.doctor.result import GroupResult, Status


def run(toolkit_root: Path, *, project_root: Path | None = None) -> GroupResult:
    findings: list[str] = []
    warns: list[str] = []
    # Checks added in T3, T4.
    if warns:
        return GroupResult(
            name="allowlist-audit",
            status=Status.WARN,
            summary=f"{len(warns)} drift issue(s)",
            findings=findings + warns,
            fix_hint="Edit ~/.agent-toolkit.yaml or re-link with the correct --toolkit-repo.",
        )
    return GroupResult(
        name="allowlist-audit",
        status=Status.OK,
        summary="allow-list and symlinks all reference current toolkit",
        findings=findings,
    )
```

**Run:** T1 passes.

## T3 — Test allow-list rot (red)

Add to `test_doctor_allowlist_audit.py`:

```python
def test_allowlist_phantom_slug_warns(env):
    home = env["home"]
    yaml_path = home / ".agent-toolkit.yaml"
    yaml_path.write_text(
        "skills:\n  - alpha\n  - phantom\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    result = allowlist_audit.run(env["toolkit_root"], project_root=home)
    assert result.status == Status.WARN
    assert any("phantom" in f for f in result.findings)
    # alpha exists, should NOT be in findings (or only as positive)
    assert not any("alpha" in f and "missing" in f for f in result.findings)


def test_project_allowlist_phantom_slug_warns(env, tmp_path):
    proj = tmp_path / "project"
    proj.mkdir()
    (proj / ".agent-toolkit.yaml").write_text(
        "skills:\n  - phantom\nagents: []\ncommands: []\nhooks: []\nplugins: []\n"
    )
    result = allowlist_audit.run(env["toolkit_root"], project_root=proj)
    assert result.status == Status.WARN
    assert any("phantom" in f for f in result.findings)
```

**Run:** Expect failures (allowlist_audit doesn't read yaml yet).

## T4 — Implement allow-list check (green)

Edit `allowlist_audit.py`. Add an inner check:

```python
import os

from agent_toolkit_cli._allowlist import SECTIONS, read_allowlist, section_to_kind
from agent_toolkit_cli.walker import discover_assets


def _check_allowlist(yaml_path: Path, source_label: str, declared_slugs: set[tuple[str, str]]) -> list[str]:
    """Return warning lines for slugs that don't match any declared (kind, slug) tuple."""
    warns: list[str] = []
    if not yaml_path.is_file():
        return warns
    parsed = read_allowlist(yaml_path)
    for section, slugs in parsed.items():
        kind = section_to_kind(section)
        for slug in slugs:
            if (kind, slug) not in declared_slugs:
                warns.append(
                    f"allow-list {source_label} ({yaml_path.name}) references "
                    f"{kind}/{slug} which is not in the toolkit repo"
                )
    return warns


def run(toolkit_root: Path, *, project_root: Path | None = None) -> GroupResult:
    declared = {(a.kind, a.slug) for a in discover_assets(toolkit_root)}

    findings: list[str] = []
    warns: list[str] = []

    home = Path(os.environ.get("HOME", str(Path.home())))
    user_yaml = home / ".agent-toolkit.yaml"
    warns.extend(_check_allowlist(user_yaml, "user", declared))

    if project_root is not None:
        proj_yaml = project_root / ".agent-toolkit.yaml"
        # Don't audit the same yaml twice if project == home
        if proj_yaml != user_yaml:
            warns.extend(_check_allowlist(proj_yaml, "project", declared))

    if not warns:
        findings.append(
            f"all allow-list entries (user + project) point at real assets in {toolkit_root}"
        )

    # Cross-toolkit symlink check added in T6.
    # ...
```

**Run:** T3 tests pass.

## T5 — Test cross-toolkit symlinks (red)

```python
def test_cross_toolkit_symlink_warns(env, tmp_path, seed_toolkit, seed_skill):
    home = env["home"]
    # Create a SECOND toolkit and a symlink pointing into it
    other_toolkit = seed_toolkit(tmp_path / "other")
    seed_skill(other_toolkit, "alpha", ["claude"])
    user_skills = home / ".claude" / "skills"
    user_skills.mkdir(parents=True)
    (user_skills / "alpha").symlink_to(other_toolkit / "skills" / "alpha")

    result = allowlist_audit.run(env["toolkit_root"], project_root=home)
    assert result.status == Status.WARN
    assert any("alpha" in f and "different toolkit" in f for f in result.findings)


def test_symlink_into_configured_toolkit_does_not_warn(env, tmp_path):
    home = env["home"]
    user_skills = home / ".claude" / "skills"
    user_skills.mkdir(parents=True)
    (user_skills / "alpha").symlink_to(env["toolkit_root"] / "skills" / "alpha")

    result = allowlist_audit.run(env["toolkit_root"], project_root=home)
    # The configured toolkit is the right one — no cross-toolkit warning.
    assert not any("different toolkit" in f for f in result.findings)
```

**Run:** Expect failures (cross-toolkit check not implemented).

## T6 — Implement cross-toolkit symlink check (green)

Add a helper:

```python
from agent_toolkit_cli.commands._link_lib import ALL_HARNESSES, HARNESS_HOMES
from agent_toolkit_cli.commands._list_json import _USER_TARGETS


def _is_toolkit_dir(p: Path) -> bool:
    """A directory is a toolkit if it (or an ancestor) contains .agent-toolkit-source."""
    cur = p.resolve()
    for ancestor in [cur, *cur.parents]:
        if (ancestor / ".agent-toolkit-source").is_file():
            return True
    return False


def _toolkit_root_for(p: Path) -> Path | None:
    """Return the toolkit root containing p, or None."""
    cur = p.resolve()
    for ancestor in [cur, *cur.parents]:
        if (ancestor / ".agent-toolkit-source").is_file():
            return ancestor
    return None


def _check_cross_toolkit_symlinks(toolkit_root: Path) -> list[str]:
    """Walk every harness's user-scope kind dirs; flag symlinks targeting a *different* toolkit."""
    warns: list[str] = []
    home = Path(os.environ.get("HOME", str(Path.home())))
    seen_dirs: set[Path] = set()
    for (harness, kind), tmpl in _USER_TARGETS.items():
        rel = tmpl.replace("{home}/", "")
        kind_dir = home / rel
        if kind_dir in seen_dirs or not kind_dir.is_dir():
            continue
        seen_dirs.add(kind_dir)
        for entry in kind_dir.iterdir():
            if not entry.is_symlink():
                continue
            target = Path(os.readlink(entry))
            if not target.is_absolute():
                target = (entry.parent / target).resolve()
            if not target.exists():
                # symlinks.py owns dangling-target detection
                continue
            tgt_root = _toolkit_root_for(target)
            if tgt_root is not None and tgt_root.resolve() != toolkit_root.resolve():
                warns.append(
                    f"{harness}/{entry.name}: symlink points into a different toolkit "
                    f"(target={target}, configured toolkit={toolkit_root})"
                )
    return warns


# In run():
warns.extend(_check_cross_toolkit_symlinks(toolkit_root))
```

Update the OK summary to mention both checks if no warnings.

**Run:** T5 tests pass.

## T7 — Wire into commands/doctor.py

```python
from agent_toolkit_cli.doctor import (
    allowlist_audit as g_allowlist_audit,
    ...
)

_GROUPS = (..., "harness-homes", "allowlist-audit")

# In _run_global:
("allowlist-audit", lambda: g_allowlist_audit.run(root, project_root=Path.cwd())),
```

## T8 — Negative control (broken symlink stays in symlinks group)

Add to test file:

```python
def test_broken_symlink_not_double_reported(env):
    """allowlist-audit must not report broken symlinks (symlink-integrity owns that)."""
    home = env["home"]
    user_skills = home / ".claude" / "skills"
    user_skills.mkdir(parents=True)
    (user_skills / "alpha").symlink_to(env["toolkit_root"] / "skills" / "nonexistent")

    result = allowlist_audit.run(env["toolkit_root"], project_root=home)
    # Should be OK (or only report unrelated drift, not the dangling link)
    assert not any("dangling" in f.lower() for f in result.findings)
```

**Run:** Pass.

## T9 — Full suite + smoke

```bash
uv run pytest -q
uv run agent-toolkit doctor --group allowlist-audit --verbose --toolkit-repo ~/GitHub/agent-toolkit
```

Expected: 311+ passed (was 307, +4-6 new tests), 2 skipped.

## T10 — Single commit

```
feat(doctor): audit allow-list rot and cross-toolkit symlinks

Closes #10.

New `allowlist-audit` doctor group with two checks:

  1. Allow-list slug existence — entries in user/project
     .agent-toolkit.yaml that name slugs not present in the
     toolkit repo are flagged as drift.
  2. Cross-toolkit symlinks — symlinks under ~/.{harness}/...
     that point into a *different* toolkit repo (recognised by
     the .agent-toolkit-source marker) are flagged.

Broken-target detection stays in the existing `symlinks` group
to avoid double-reporting.
```

## Acceptance checklist

- [ ] `agent-toolkit doctor` includes `allowlist-audit` group.
- [ ] Clean repo → OK.
- [ ] Drifted allow-list → WARN with the offending slug.
- [ ] Cross-toolkit symlink → WARN with paths.
- [ ] Broken symlink not double-reported.
- [ ] `pytest -q` ≥ 311 passed, 2 skipped.

## Subagent escalation triggers

- The cross-toolkit detection accidentally fires for the user's real `~/.claude/...` symlinks during the smoke run → review whether the `.agent-toolkit-source` heuristic should be tightened.
- Tests fail because `discover_assets` walks more than expected (e.g. picks up assets in the test toolkit fixture) → halt and surface, not paper over.
