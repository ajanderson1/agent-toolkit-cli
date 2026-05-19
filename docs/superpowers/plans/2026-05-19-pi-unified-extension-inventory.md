# Pi Unified Extension Inventory — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `agent-toolkit-cli` a `pi` command group that unifies both Pi extension channels (auto-discovery dirs + Pi packages) under one inventory view, with `load`/`unload`/`sync` verbs where the toolkit owns every config write and `pi install` is only invoked for the fetch step.

**Architecture:** Mirror the existing Codex-hooks/MCP-entries pattern — toolkit edits `~/.pi/agent/settings.json` directly via a `_pi_settings.py` helper, and shells out to `pi install` only to fetch `node_modules/`. Add one new `pi_packages:` section to the allowlist (additive — no schema bump). New `pi` Click group lives at `commands/pi.py`. TUI gains a Pi tab consuming `pi inventory --format json`. Doctor learns three advisories.

**Tech Stack:** Python 3.13, Click, ruamel.yaml (allowlist), stdlib `json` (settings.json), pytest, Textual (TUI).

**Spec:** `docs/superpowers/specs/2026-05-19-pi-unified-extension-inventory-design.md`

**Issue:** [#103](https://github.com/ajanderson1/agent-toolkit-cli/issues/103)

**Mode:** Single PR, five internal commits (per operator scope choice). Commit boundaries align with the spec's "internal commit slicing" table.

---

## File Structure

### New files

| Path | Responsibility |
|---|---|
| `src/agent_toolkit_cli/_pi_paths.py` | Path resolution for `~/.pi/agent/` and `<project>/.pi/` — single module so a Pi version bump moves these in one place. |
| `src/agent_toolkit_cli/_pi_settings.py` | Read/write helpers for `~/.pi/agent/settings.json` `packages[]`. Same role as `_yaml_edit.py` does for the allowlist. |
| `src/agent_toolkit_cli/_pi_inventory.py` | Pure function `build_pi_inventory(user_home, project_root, allowlist) → list[PiRecord]`. No I/O of its own — caller passes parsed inputs. |
| `src/agent_toolkit_cli/commands/pi.py` | Click group `pi` with four subcommands: `inventory`, `load`, `unload`, `sync`. |
| `src/agent_toolkit_cli/doctor/pi_advisories.py` | Three new advisory checks: hand-authored extension, drift, slug collision. |
| `src/agent_toolkit_tui/widgets/pi_tab.py` | Textual widget consuming `pi inventory --format json`. |
| `tests/test_pi_paths.py` | Unit tests for path resolver. |
| `tests/test_pi_settings.py` | Unit tests for settings.json read/write. |
| `tests/test_pi_inventory.py` | Unit tests for the inventory builder (pure function — fixture-driven). |
| `tests/test_cli_pi.py` | Click CLI tests for the four `pi` subcommands. |
| `tests/test_doctor_pi_advisories.py` | Unit tests for the new advisories. |
| `tests/test_tui_pi_tab.py` | Snapshot/interaction tests for the Pi tab. |

### Modified files

| Path | Change |
|---|---|
| `src/agent_toolkit_cli/_allowlist.py:15` | Append `"pi_packages"` to `SECTIONS`. Read-path test in `test_allowlist.py` updated. |
| `src/agent_toolkit_cli/commands/_yaml_edit.py` | No change — `add_slug`/`remove_slug` already accept any `section in SECTIONS`. |
| `src/agent_toolkit_cli/cli.py` | Register the new `pi` group via `main.add_command(pi)`. |
| `src/agent_toolkit_cli/doctor/__init__.py` (or doctor entry point) | Wire the new advisory module. |
| `src/agent_toolkit_tui/app.py` | Add Pi tab keybinding `Binding("8", ...)`. |
| `src/agent_toolkit_tui/widgets/kinds_sidebar.py` | Add Pi tab entry. |
| `tests/test_allowlist.py` | Add `pi_packages` to expected sections. |

---

## Commit 1 — Inventory read (no schema change)

Delivers PR 1's value: one read-only command that shows what Pi will load. No allowlist change. No write paths.

### Task 1.1: Path resolver — `_pi_paths.py`

**Files:**
- Create: `src/agent_toolkit_cli/_pi_paths.py`
- Test:   `tests/test_pi_paths.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pi_paths.py
from pathlib import Path
from agent_toolkit_cli._pi_paths import PiPaths

def test_pi_paths_user_scope(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    pp = PiPaths(home=home, project_root=project)

    assert pp.user_extensions_dir == home / ".pi" / "agent" / "extensions"
    assert pp.user_settings_json == home / ".pi" / "agent" / "settings.json"
    assert pp.user_node_modules_dir == home / ".pi" / "agent" / "npm" / "node_modules"

def test_pi_paths_project_scope(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    pp = PiPaths(home=home, project_root=project)

    # Project scope omits the /agent/ infix (see _support.py docstring).
    assert pp.project_extensions_dir == project / ".pi" / "extensions"
    assert pp.project_settings_json == project / ".pi" / "settings.json"
    assert pp.project_node_modules_dir == project / ".pi" / "npm" / "node_modules"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pi_paths.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement minimal `_pi_paths.py`**

```python
"""Pi filesystem path resolver.

Single module so a Pi version bump (path layout changes) is one diff.
Project scope omits the `/agent/` infix; see _support.py:55-60 for the rule.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PiPaths:
    home: Path
    project_root: Path

    # ---- user scope ----
    @property
    def user_extensions_dir(self) -> Path:
        return self.home / ".pi" / "agent" / "extensions"

    @property
    def user_settings_json(self) -> Path:
        return self.home / ".pi" / "agent" / "settings.json"

    @property
    def user_node_modules_dir(self) -> Path:
        return self.home / ".pi" / "agent" / "npm" / "node_modules"

    # ---- project scope ----
    @property
    def project_extensions_dir(self) -> Path:
        return self.project_root / ".pi" / "extensions"

    @property
    def project_settings_json(self) -> Path:
        return self.project_root / ".pi" / "settings.json"

    @property
    def project_node_modules_dir(self) -> Path:
        return self.project_root / ".pi" / "npm" / "node_modules"
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_pi_paths.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit (defer — accumulates with Task 1.2/1.3 below for one commit-1 boundary)**

### Task 1.2: Settings.json reader — `_pi_settings.read_packages()`

**Files:**
- Create: `src/agent_toolkit_cli/_pi_settings.py`
- Test:   `tests/test_pi_settings.py`

The reader is needed for inventory before the writer. Writer comes in Commit 3.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pi_settings.py
import json
from pathlib import Path
from agent_toolkit_cli._pi_settings import read_packages

def test_read_packages_missing_file(tmp_path: Path):
    assert read_packages(tmp_path / "nope.json") == []

def test_read_packages_empty_file(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text("")
    assert read_packages(p) == []

def test_read_packages_with_entries(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({
        "packages": ["npm:pi-subagents", "git:github.com/u/r@v1"],
        "unrelated": "ignored",
    }))
    assert read_packages(p) == ["npm:pi-subagents", "git:github.com/u/r@v1"]

def test_read_packages_packages_missing(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"other": "key"}))
    assert read_packages(p) == []

def test_read_packages_malformed_json_raises(tmp_path: Path):
    p = tmp_path / "settings.json"
    p.write_text("{ not json")
    import pytest
    with pytest.raises(ValueError) as exc:
        read_packages(p)
    assert "settings.json" in str(exc.value).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pi_settings.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `read_packages`**

```python
# src/agent_toolkit_cli/_pi_settings.py
"""Read/write helpers for `~/.pi/agent/settings.json`.

The toolkit treats this file as a JSON document with a `packages: [str]`
field. Read returns the list; write helpers (commit 3) preserve unknown keys.
This is the third-party-channel sibling of `_yaml_edit.py` (which owns the
allowlist YAML for the first-party channel).
"""
from __future__ import annotations

import json
from pathlib import Path


def read_packages(path: Path) -> list[str]:
    """Return the `packages[]` list from a Pi settings.json file.

    Missing file or empty file → []. Missing `packages` key → []. Malformed
    JSON raises ValueError with a friendly message — the toolkit fails loudly
    rather than silently swallowing a corrupt settings.json.
    """
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed settings.json at {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        return []
    packages = parsed.get("packages") or []
    if not isinstance(packages, list):
        return []
    return [str(p) for p in packages if p]
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_pi_settings.py -v`
Expected: PASS (5 tests).

### Task 1.3: Inventory builder — `_pi_inventory.build_pi_inventory()`

**Files:**
- Create: `src/agent_toolkit_cli/_pi_inventory.py`
- Test:   `tests/test_pi_inventory.py`

Pure function: no I/O. Caller passes already-read inputs (dirs to scan, packages list, allowlist sections).

- [ ] **Step 1: Write the failing test (table-driven, fixture-based)**

```python
# tests/test_pi_inventory.py
from pathlib import Path
from agent_toolkit_cli._pi_inventory import build_pi_inventory, PiRecord


def _mkdir_p(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def test_first_party_user_loaded(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/status-bar")
    _mkdir_p(project)

    records = build_pi_inventory(
        home=home,
        project_root=project,
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        allowlist_pi_extensions=["status-bar"],
        allowlist_pi_packages=[],
    )

    assert len(records) == 1
    r = records[0]
    assert r.slug == "status-bar"
    assert r.origin == "first-party"
    assert r.source == "extension:status-bar"
    assert r.user_loaded is True
    assert r.project_loaded is False
    assert r.toolkit_intent == "user"


def test_third_party_user_loaded_unmanaged(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"

    records = build_pi_inventory(
        home=home,
        project_root=project,
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules={"pi-subagents"},
        project_node_modules=set(),
        allowlist_pi_extensions=[],
        allowlist_pi_packages=[],
    )

    assert len(records) == 1
    r = records[0]
    assert r.slug == "pi-subagents"
    assert r.origin == "third-party"
    assert r.source == "npm:pi-subagents"
    assert r.user_loaded is True
    assert r.toolkit_intent == "none"


def test_third_party_declared_but_not_resolved(tmp_path: Path):
    """`packages[]` declares it, but node_modules/ has no matching dir — not loaded."""
    home = tmp_path / "home"
    project = tmp_path / "proj"

    records = build_pi_inventory(
        home=home,
        project_root=project,
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules=set(),  # fetch hasn't happened yet
        project_node_modules=set(),
        allowlist_pi_extensions=[],
        allowlist_pi_packages=["npm:pi-subagents"],
    )

    assert len(records) == 1
    r = records[0]
    assert r.user_loaded is False  # declared but not resolved
    assert r.toolkit_intent == "user"


def test_collision_first_party_wins(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/pi-subagents")

    records = build_pi_inventory(
        home=home,
        project_root=project,
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules={"pi-subagents"},
        project_node_modules=set(),
        allowlist_pi_extensions=["pi-subagents"],
        allowlist_pi_packages=["npm:pi-subagents"],
    )

    # One record, origin=first-party wins. Both presences should be reflected
    # in the loaded flags (true on both channels → still true overall).
    assert len(records) == 1
    assert records[0].origin == "first-party"


def test_git_source_slug_derivation(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"

    records = build_pi_inventory(
        home=home,
        project_root=project,
        user_packages=["git:github.com/user/my-ext@v1"],
        project_packages=[],
        user_node_modules={"my-ext"},
        project_node_modules=set(),
        allowlist_pi_extensions=[],
        allowlist_pi_packages=[],
    )

    assert len(records) == 1
    assert records[0].slug == "my-ext"
    assert records[0].source == "git:github.com/user/my-ext@v1"


def test_record_is_sorted_by_slug(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/zeta")
    _mkdir_p(home / ".pi/agent/extensions/alpha")

    records = build_pi_inventory(
        home=home, project_root=project,
        user_packages=[], project_packages=[],
        user_node_modules=set(), project_node_modules=set(),
        allowlist_pi_extensions=["zeta", "alpha"],
        allowlist_pi_packages=[],
    )

    assert [r.slug for r in records] == ["alpha", "zeta"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pi_inventory.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `_pi_inventory.py`**

```python
"""Pure inventory builder for Pi extensions.

No I/O. The caller resolves filesystem state and the allowlist sections; this
module synthesises one PiRecord per unique slug across both channels.

Slug derivation:
- first-party: directory name under <home>/.pi/agent/extensions/<slug>/
- npm: source string after `npm:` is the package name. Slug = same.
- git: last path segment of the URL, after stripping `@<ref>` suffix.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal


Origin = Literal["first-party", "third-party"]
Intent = Literal["user", "project", "both", "none"]


@dataclass(frozen=True)
class PiRecord:
    slug: str
    origin: Origin
    source: str
    user_loaded: bool
    project_loaded: bool
    user_installed_at: str | None
    project_installed_at: str | None
    toolkit_intent: Intent

    def to_dict(self) -> dict:
        return asdict(self)


def _slug_from_source(source: str) -> str:
    """Derive a display slug from a `packages[]` source string.

    Rules (see module docstring):
    - `npm:foo` → `foo`
    - `git:host/path/repo@ref` → last segment of path, ref stripped
    - any other shape → return source verbatim (caller may flag in doctor)
    """
    if source.startswith("npm:"):
        return source[len("npm:") :]
    if source.startswith("git:"):
        body = source[len("git:") :]
        body = body.split("@", 1)[0]  # strip @ref
        return body.rsplit("/", 1)[-1]
    return source


def build_pi_inventory(
    *,
    home: Path,
    project_root: Path,
    user_packages: list[str],
    project_packages: list[str],
    user_node_modules: set[str],
    project_node_modules: set[str],
    allowlist_pi_extensions: list[str],
    allowlist_pi_packages: list[str],
) -> list[PiRecord]:
    """Build the unified inventory across both Pi extension channels.

    See module docstring for slug derivation rules.
    """
    # Resolve filesystem state for first-party (auto-discovery dirs).
    user_ext_dir = home / ".pi" / "agent" / "extensions"
    project_ext_dir = project_root / ".pi" / "extensions"

    user_ext_slugs: set[str] = (
        {p.name for p in user_ext_dir.iterdir() if p.is_dir() or p.is_symlink()}
        if user_ext_dir.is_dir()
        else set()
    )
    project_ext_slugs: set[str] = (
        {p.name for p in project_ext_dir.iterdir() if p.is_dir() or p.is_symlink()}
        if project_ext_dir.is_dir()
        else set()
    )

    # Index third-party sources by derived slug.
    user_third_party: dict[str, str] = {
        _slug_from_source(s): s for s in user_packages
    }
    project_third_party: dict[str, str] = {
        _slug_from_source(s): s for s in project_packages
    }

    # Index allowlist intent.
    allowlist_third_party_slugs: set[str] = {
        _slug_from_source(s) for s in allowlist_pi_packages
    }
    allowlist_first_party_slugs: set[str] = set(allowlist_pi_extensions)

    # Union of all slugs across both channels.
    all_first_party = (
        user_ext_slugs | project_ext_slugs | allowlist_first_party_slugs
    )
    all_third_party = (
        set(user_third_party) | set(project_third_party) | allowlist_third_party_slugs
    )

    out: list[PiRecord] = []

    for slug in sorted(all_first_party):
        user_loaded = slug in user_ext_slugs
        project_loaded = slug in project_ext_slugs
        intent = _intent_for(
            in_user=slug in allowlist_first_party_slugs,
            in_project=False,  # allowlist_pi_extensions is user-scope today; project-scope intent is future work
        )
        out.append(
            PiRecord(
                slug=slug,
                origin="first-party",
                source=f"extension:{slug}",
                user_loaded=user_loaded,
                project_loaded=project_loaded,
                user_installed_at=str(user_ext_dir / slug) if user_loaded else None,
                project_installed_at=str(project_ext_dir / slug) if project_loaded else None,
                toolkit_intent=intent,
            )
        )

    # Third-party — skip slugs that won (first-party collision).
    first_party_won = {r.slug for r in out}
    for slug in sorted(all_third_party - first_party_won):
        user_source = user_third_party.get(slug)
        project_source = project_third_party.get(slug)
        display_source = user_source or project_source or f"npm:{slug}"

        user_loaded = (slug in user_third_party) and (slug in user_node_modules)
        project_loaded = (slug in project_third_party) and (slug in project_node_modules)

        intent = _intent_for(
            in_user=any(
                _slug_from_source(s) == slug for s in allowlist_pi_packages
            ),
            in_project=False,
        )

        out.append(
            PiRecord(
                slug=slug,
                origin="third-party",
                source=display_source,
                user_loaded=user_loaded,
                project_loaded=project_loaded,
                user_installed_at=str(home / ".pi/agent/npm/node_modules" / slug)
                if user_loaded
                else None,
                project_installed_at=str(project_root / ".pi/npm/node_modules" / slug)
                if project_loaded
                else None,
                toolkit_intent=intent,
            )
        )

    return out


def _intent_for(*, in_user: bool, in_project: bool) -> Intent:
    if in_user and in_project:
        return "both"
    if in_user:
        return "user"
    if in_project:
        return "project"
    return "none"
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_pi_inventory.py -v`
Expected: PASS (6 tests).

### Task 1.4: `pi inventory` Click subcommand

**Files:**
- Create: `src/agent_toolkit_cli/commands/pi.py`
- Modify: `src/agent_toolkit_cli/cli.py:18` (add import), `src/agent_toolkit_cli/cli.py:70` (register)
- Test:   `tests/test_cli_pi.py`

- [ ] **Step 1: Write the failing test (CLI integration)**

```python
# tests/test_cli_pi.py
import json
import os
from pathlib import Path
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _setup_pi_home(home: Path, ext_slugs: list[str], packages: list[str], node_modules: list[str]) -> None:
    (home / ".pi/agent/extensions").mkdir(parents=True, exist_ok=True)
    for s in ext_slugs:
        (home / ".pi/agent/extensions" / s).mkdir()
    if packages or True:
        (home / ".pi/agent").mkdir(parents=True, exist_ok=True)
        (home / ".pi/agent/settings.json").write_text(
            json.dumps({"packages": packages})
        )
    (home / ".pi/agent/npm/node_modules").mkdir(parents=True, exist_ok=True)
    for pkg in node_modules:
        (home / ".pi/agent/npm/node_modules" / pkg).mkdir()


def test_pi_inventory_json_format(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    _setup_pi_home(
        home,
        ext_slugs=["status-bar"],
        packages=["npm:pi-subagents"],
        node_modules=["pi-subagents"],
    )
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory", "--format", "json"],
    )
    assert result.exit_code == 0, result.output

    records = json.loads(result.output)
    slugs = {r["slug"] for r in records}
    assert slugs == {"status-bar", "pi-subagents"}

    sb = next(r for r in records if r["slug"] == "status-bar")
    assert sb["origin"] == "first-party"
    assert sb["user_loaded"] is True

    ps = next(r for r in records if r["slug"] == "pi-subagents")
    assert ps["origin"] == "third-party"
    assert ps["user_loaded"] is True


def test_pi_inventory_text_format(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    _setup_pi_home(home, ext_slugs=["status-bar"], packages=[], node_modules=[])
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory"],  # default --format text
    )
    assert result.exit_code == 0
    assert "status-bar" in result.output
    assert "first-party" in result.output


def test_pi_inventory_empty(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory", "--format", "json"],
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli_pi.py -v`
Expected: FAIL — `pi` is not a recognised command.

- [ ] **Step 3: Implement `commands/pi.py` (inventory only — load/unload/sync are stubbed for commit-3)**

```python
"""`agent-toolkit-cli pi …` — unified Pi extension view + manage verbs.

This module owns the `pi` Click group. Inventory landed in commit 1.
Load/unload/sync land in commit 3.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import click

from agent_toolkit_cli._allowlist import read_allowlist
from agent_toolkit_cli._pi_inventory import PiRecord, build_pi_inventory
from agent_toolkit_cli._pi_paths import PiPaths
from agent_toolkit_cli._pi_settings import read_packages


def _allowlist_path(scope: str, home: Path, project_root: Path) -> Path:
    if scope == "project":
        return project_root / ".agent-toolkit.yaml"
    return home / ".agent-toolkit.yaml"


def _read_node_modules_dir(d: Path) -> set[str]:
    if not d.is_dir():
        return set()
    return {p.name for p in d.iterdir() if p.is_dir() or p.is_symlink()}


def _gather_inventory(
    home: Path, project_root: Path
) -> list[PiRecord]:
    pp = PiPaths(home=home, project_root=project_root)

    user_packages = read_packages(pp.user_settings_json)
    project_packages = read_packages(pp.project_settings_json)
    user_node_modules = _read_node_modules_dir(pp.user_node_modules_dir)
    project_node_modules = _read_node_modules_dir(pp.project_node_modules_dir)

    user_allow = read_allowlist(home / ".agent-toolkit.yaml")
    project_allow = read_allowlist(project_root / ".agent-toolkit.yaml")
    pi_exts = list(
        dict.fromkeys(
            list(user_allow.get("pi_extensions", []))
            + list(project_allow.get("pi_extensions", []))
        )
    )
    pi_pkgs = list(
        dict.fromkeys(
            list(user_allow.get("pi_packages", []))
            + list(project_allow.get("pi_packages", []))
        )
    )

    return build_pi_inventory(
        home=home,
        project_root=project_root,
        user_packages=user_packages,
        project_packages=project_packages,
        user_node_modules=user_node_modules,
        project_node_modules=project_node_modules,
        allowlist_pi_extensions=pi_exts,
        allowlist_pi_packages=pi_pkgs,
    )


@click.group(name="pi")
def pi() -> None:
    """Pi: unified extension inventory and load/unload across both channels."""


@pi.command(name="inventory")
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "both"]),
    default="both",
    help="Restrict view to user, project, or both (default).",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "text"]),
    default="text",
)
@click.pass_context
def inventory_cmd(ctx: click.Context, scope: str, fmt: str) -> None:
    """Emit one record per extension Pi could load.

    Reads first-party auto-discovery dirs + third-party `settings.json` and
    `node_modules/` + the toolkit allowlist. Read-only.
    """
    home = Path(os.environ.get("HOME", ""))
    project_root = ctx.obj.get("project_root") if ctx.obj else None
    if project_root is None:
        project_root = Path.cwd()

    records = _gather_inventory(home=home, project_root=project_root)

    # Optional scope filter — keep simple: drop rows where the requested scope
    # has no loaded-or-intent presence.
    if scope == "user":
        records = [
            r
            for r in records
            if r.user_loaded or r.toolkit_intent in ("user", "both")
        ]
    elif scope == "project":
        records = [
            r
            for r in records
            if r.project_loaded or r.toolkit_intent in ("project", "both")
        ]

    if fmt == "json":
        click.echo(json.dumps([r.to_dict() for r in records], indent=2))
        return

    # text format — one row per record, ascii-only
    if not records:
        click.echo("(no Pi extensions found)")
        return
    click.echo(f"{'SLUG':<24} {'ORIGIN':<12} {'U':<3} {'P':<3} {'INTENT':<8} SOURCE")
    for r in records:
        click.echo(
            f"{r.slug:<24} {r.origin:<12} "
            f"{'✓' if r.user_loaded else ' ':<3} "
            f"{'✓' if r.project_loaded else ' ':<3} "
            f"{r.toolkit_intent:<8} {r.source}"
        )
```

- [ ] **Step 4: Register the group in `cli.py`**

Modify `src/agent_toolkit_cli/cli.py`. Add to the imports near line 18:

```python
from agent_toolkit_cli.commands.pi import pi
```

Add to the `main.add_command(...)` block near line 70:

```python
main.add_command(pi)
```

- [ ] **Step 5: Tests pass**

Run: `uv run pytest tests/test_cli_pi.py tests/test_pi_inventory.py tests/test_pi_paths.py tests/test_pi_settings.py -v`
Expected: PASS (all).

- [ ] **Step 6: Verify the binary works**

Run: `uv run agent-toolkit-cli pi inventory --help`
Expected: help text, exit 0.

- [ ] **Step 7: Commit (commit 1 — inventory read complete)**

```bash
git add src/agent_toolkit_cli/_pi_paths.py \
        src/agent_toolkit_cli/_pi_settings.py \
        src/agent_toolkit_cli/_pi_inventory.py \
        src/agent_toolkit_cli/commands/pi.py \
        src/agent_toolkit_cli/cli.py \
        tests/test_pi_paths.py \
        tests/test_pi_settings.py \
        tests/test_pi_inventory.py \
        tests/test_cli_pi.py
git commit -m "feat(pi): unified inventory read across both channels (#103)"
```

---

## Commit 2 — Allowlist schema + `pi sync`

Adds `pi_packages:` to `SECTIONS` and a `pi sync` verb that reconciles allowlist intent → settings.json. **No fetching yet** — sync writes settings.json declarations only. (Fetch-on-sync is part of commit 3.)

### Task 2.1: Extend `_allowlist.SECTIONS`

**Files:**
- Modify: `src/agent_toolkit_cli/_allowlist.py:15`
- Modify: `tests/test_allowlist.py`

- [ ] **Step 1: Update existing test to expect new section**

Find the test in `tests/test_allowlist.py` that asserts `SECTIONS` contents (likely a `test_sections_constant` or similar). Update the expected tuple to include `"pi_packages"` at the end:

```python
# tests/test_allowlist.py — update existing SECTIONS assertion
def test_sections_constant():
    from agent_toolkit_cli._allowlist import SECTIONS
    assert SECTIONS == (
        "skills", "agents", "commands", "hooks", "plugins", "mcps",
        "pi_extensions", "pi_packages",
    )
```

If no such test exists, add it.

- [ ] **Step 2: Run test — should fail**

Run: `uv run pytest tests/test_allowlist.py -v`
Expected: FAIL — `pi_packages` not in SECTIONS.

- [ ] **Step 3: Add `pi_packages` to `SECTIONS`**

Edit `src/agent_toolkit_cli/_allowlist.py:15`:

```python
SECTIONS: tuple[str, ...] = (
    "skills", "agents", "commands", "hooks", "plugins", "mcps",
    "pi_extensions", "pi_packages",
)
```

**Do NOT** add anything to `_KIND_TO_SECTION` — packages aren't schema-validated assets, they only appear in the allowlist as raw strings.

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_allowlist.py tests/test_yaml_edit.py -v`
Expected: PASS.

### Task 2.2: Settings.json writer — `_pi_settings.write_packages()`

**Files:**
- Modify: `src/agent_toolkit_cli/_pi_settings.py`
- Modify: `tests/test_pi_settings.py`

- [ ] **Step 1: Add tests for writer (preserves unknown keys, idempotent)**

Append to `tests/test_pi_settings.py`:

```python
import json
from agent_toolkit_cli._pi_settings import write_packages, add_package, remove_package

def test_write_packages_preserves_unknown_keys(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"packages": [], "other": {"keep": 1}}))
    write_packages(p, ["npm:foo"])
    parsed = json.loads(p.read_text())
    assert parsed["packages"] == ["npm:foo"]
    assert parsed["other"] == {"keep": 1}

def test_write_packages_creates_missing_file(tmp_path):
    p = tmp_path / "missing" / "settings.json"
    write_packages(p, ["npm:foo"])
    parsed = json.loads(p.read_text())
    assert parsed == {"packages": ["npm:foo"]}

def test_add_package_idempotent(tmp_path):
    p = tmp_path / "settings.json"
    add_package(p, "npm:foo")
    add_package(p, "npm:foo")  # second time: no-op
    parsed = json.loads(p.read_text())
    assert parsed["packages"] == ["npm:foo"]

def test_remove_package_idempotent(tmp_path):
    p = tmp_path / "settings.json"
    add_package(p, "npm:foo")
    remove_package(p, "npm:foo")
    remove_package(p, "npm:foo")  # second time: no-op
    parsed = json.loads(p.read_text())
    assert parsed["packages"] == []
```

- [ ] **Step 2: Run — should fail**

Run: `uv run pytest tests/test_pi_settings.py -v`
Expected: FAIL — `write_packages` / `add_package` / `remove_package` not defined.

- [ ] **Step 3: Implement writer + helpers in `_pi_settings.py`**

Append to `src/agent_toolkit_cli/_pi_settings.py`:

```python
def write_packages(path: Path, packages: list[str]) -> None:
    """Write `packages` as the `packages[]` field, preserving any other keys.

    Creates parent dirs and file if missing. The on-disk representation is
    `{"packages": [...], ...other-keys}`. We deliberately preserve any keys
    other than `packages` so Pi-internal settings survive toolkit edits.
    """
    parsed: dict
    if path.exists() and path.read_text(encoding="utf-8").strip():
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed settings.json at {path}: {exc}") from exc
        if not isinstance(parsed, dict):
            parsed = {}
    else:
        parsed = {}

    parsed["packages"] = list(packages)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(parsed, indent=2) + "\n", encoding="utf-8")


def add_package(path: Path, source: str) -> None:
    """Add SOURCE to `packages[]` (idempotent; creates file if missing)."""
    current = read_packages(path)
    if source in current:
        return
    write_packages(path, current + [source])


def remove_package(path: Path, source: str) -> None:
    """Remove SOURCE from `packages[]` (idempotent; no-op if missing)."""
    current = read_packages(path)
    if source not in current:
        return
    write_packages(path, [s for s in current if s != source])
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_pi_settings.py -v`
Expected: PASS (9 tests).

### Task 2.3: `pi sync` Click subcommand (no fetching yet)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi.py`
- Modify: `tests/test_cli_pi.py`

`sync` reconciles the allowlist's `pi_packages:` declaration → settings.json `packages[]`. **Idempotent: emits no output and changes nothing if already in sync.**

- [ ] **Step 1: Write tests**

Append to `tests/test_cli_pi.py`:

```python
import yaml
from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def test_pi_sync_adds_missing_package(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(json.dumps({"packages": []}))

    allow = home / ".agent-toolkit.yaml"
    allow.write_text(yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]}))

    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "sync", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output

    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert settings["packages"] == ["npm:pi-subagents"]


def test_pi_sync_removes_orphan_package(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-orphan"]})
    )
    allow = home / ".agent-toolkit.yaml"
    allow.write_text(yaml.safe_dump({"pi_packages": []}))

    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "sync", "--scope", "user"],
    )
    assert result.exit_code == 0
    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert settings["packages"] == []


def test_pi_sync_idempotent(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-subagents"]})
    )
    allow = home / ".agent-toolkit.yaml"
    allow.write_text(yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]}))

    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()
    # Run twice; both runs should exit 0 and produce no changes.
    before = (home / ".pi/agent/settings.json").read_text()
    runner.invoke(main, ["--project", str(project), "pi", "sync", "--scope", "user"])
    after_first = (home / ".pi/agent/settings.json").read_text()
    runner.invoke(main, ["--project", str(project), "pi", "sync", "--scope", "user"])
    after_second = (home / ".pi/agent/settings.json").read_text()
    assert before == after_first == after_second
```

- [ ] **Step 2: Run — should fail**

Run: `uv run pytest tests/test_cli_pi.py -v -k sync`
Expected: FAIL — `sync` subcommand missing.

- [ ] **Step 3: Implement `pi sync`**

Append to `src/agent_toolkit_cli/commands/pi.py`:

```python
from agent_toolkit_cli._pi_settings import write_packages


@pi.command(name="sync")
@click.option(
    "--scope",
    type=click.Choice(["user", "project", "both"]),
    default="both",
)
@click.pass_context
def sync_cmd(ctx: click.Context, scope: str) -> None:
    """Reconcile allowlist `pi_packages:` → settings.json `packages[]`.

    Writes only. Does NOT invoke `pi install` (fetch step is part of `load`).
    Use `pi sync` after manually editing the allowlist; use `pi load`/`unload`
    for the all-in-one flow.
    """
    home = Path(os.environ.get("HOME", ""))
    project_root = ctx.obj.get("project_root") if ctx.obj else None
    if project_root is None:
        project_root = Path.cwd()

    scopes = ("user", "project") if scope == "both" else (scope,)

    for s in scopes:
        allow_path = _allowlist_path(s, home, project_root)
        allow = read_allowlist(allow_path)
        desired = list(dict.fromkeys(allow.get("pi_packages", [])))
        pp = PiPaths(home=home, project_root=project_root)
        settings_path = pp.user_settings_json if s == "user" else pp.project_settings_json

        current = read_packages(settings_path)
        if current == desired:
            continue
        write_packages(settings_path, desired)
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_cli_pi.py -v`
Expected: PASS (all sync + inventory tests).

- [ ] **Step 5: Commit (commit 2)**

```bash
git add src/agent_toolkit_cli/_allowlist.py \
        src/agent_toolkit_cli/_pi_settings.py \
        src/agent_toolkit_cli/commands/pi.py \
        tests/test_allowlist.py \
        tests/test_pi_settings.py \
        tests/test_cli_pi.py
git commit -m "feat(pi): pi_packages allowlist section + pi sync verb (#103)"
```

---

## Commit 3 — `pi load` / `pi unload` (toolkit edits, Pi fetches)

`load`/`unload` are the operator-facing verbs. **Toolkit owns every config edit**; Pi is invoked **only** to fetch node_modules. Investigate Pi's fetch-only flag during this commit's TDD.

### Task 3.1: Investigate Pi's fetch-only flag

**Files:**
- Test:   none (investigation step, output recorded in commit message)

- [ ] **Step 1: Inspect `pi install --help` and the package-manager source**

```bash
# These commands are reference-only — the agent runs them, captures output to
# `assets/verification/103/pi-flag-investigation.txt`, and uses the finding to
# implement Task 3.3.
pi install --help 2>&1 | tee assets/verification/103/pi-flag-investigation.txt
# Inspect the source path referenced in the spec, if available:
find ~/.pi -path '*pi-coding-agent*/dist/core/package-manager.js' \
  -exec head -100 {} \; >> assets/verification/103/pi-flag-investigation.txt 2>/dev/null || true
```

- [ ] **Step 2: Document the finding**

The finding becomes one of two paths in Task 3.3:

- **A — Pi has a fetch-only flag.** Use it; the toolkit pre-writes settings.json, runs `pi install --<flag>`, done.
- **B — Pi does not.** The toolkit pre-writes settings.json with the desired packages list, runs `pi install` (which would normally re-resolve from settings), then verifies the post-state `packages[]` matches what the toolkit wrote. Any divergence becomes a doctor advisory in commit 5.

Record the chosen path in the eventual commit message. No code yet.

### Task 3.2: `_pi_fetch.py` — shell-out wrapper

**Files:**
- Create: `src/agent_toolkit_cli/_pi_fetch.py`
- Test:   `tests/test_pi_fetch.py`

Wrap the `pi install`/`pi remove` shell-out behind one helper that's easy to monkeypatch in tests. Tests use `subprocess.run` monkeypatched via `monkeypatch.setattr`.

- [ ] **Step 1: Write tests using monkeypatched subprocess**

```python
# tests/test_pi_fetch.py
import subprocess
from pathlib import Path
import pytest

from agent_toolkit_cli._pi_fetch import PiNotFoundError, fetch_package, remove_package_fetched


def test_fetch_package_invokes_pi_install(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)

    fetch_package("npm:pi-subagents", scope="user", home=tmp_path / "home", project_root=tmp_path / "proj")

    assert calls, "pi install was not invoked"
    assert "install" in calls[0]
    assert "npm:pi-subagents" in calls[0]


def test_fetch_package_raises_on_pi_missing(tmp_path, monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        raise FileNotFoundError("pi")
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(PiNotFoundError):
        fetch_package("npm:pi-subagents", scope="user", home=tmp_path / "home", project_root=tmp_path / "proj")


def test_fetch_package_raises_on_nonzero(tmp_path, monkeypatch):
    def fake_run(cmd, *args, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "", "boom")
    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc:
        fetch_package("npm:pi-subagents", scope="user", home=tmp_path / "home", project_root=tmp_path / "proj")
    assert "boom" in str(exc.value)
```

- [ ] **Step 2: Run — should fail**

Run: `uv run pytest tests/test_pi_fetch.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `_pi_fetch.py`**

```python
"""Shell-out wrapper around `pi install` / `pi remove`.

The toolkit owns the config edit (settings.json); this module only handles
the fetch step — populating `~/.pi/agent/npm/node_modules/`. We isolate the
subprocess call in one module so tests can monkeypatch `subprocess.run`
without touching CLI code.

If `pi` is not on PATH → PiNotFoundError. Callers surface this as an
actionable CLI error.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


class PiNotFoundError(RuntimeError):
    """Raised when the `pi` binary is not on PATH."""


def _build_install_cmd(source: str, scope: str) -> list[str]:
    # Scope-flag investigation (Task 3.1) determined whether Pi has a
    # fetch-only mode. If yes, append it here; otherwise the bare invocation
    # is good enough because we've already pre-written settings.json.
    cmd = ["pi", "install", source]
    if scope == "project":
        cmd.append("--scope=project")  # confirm during Task 3.1
    return cmd


def _build_remove_cmd(source: str, scope: str) -> list[str]:
    cmd = ["pi", "remove", source]
    if scope == "project":
        cmd.append("--scope=project")
    return cmd


def fetch_package(
    source: str, *, scope: str, home: Path, project_root: Path
) -> None:
    """Invoke `pi install` to populate node_modules for SOURCE."""
    try:
        result = subprocess.run(
            _build_install_cmd(source, scope),
            capture_output=True,
            text=True,
            cwd=str(project_root if scope == "project" else home),
        )
    except FileNotFoundError as exc:
        raise PiNotFoundError("`pi` binary not on PATH") from exc

    if result.returncode != 0:
        raise RuntimeError(
            f"pi install failed (exit {result.returncode}): {result.stderr.strip()}"
        )


def remove_package_fetched(
    source: str, *, scope: str, home: Path, project_root: Path
) -> None:
    """Invoke `pi remove` to purge node_modules for SOURCE.

    Errors here are non-fatal — caller can decide whether a missing/failing
    `pi remove` is a hard error. We still raise so caller has the choice.
    """
    try:
        result = subprocess.run(
            _build_remove_cmd(source, scope),
            capture_output=True,
            text=True,
            cwd=str(project_root if scope == "project" else home),
        )
    except FileNotFoundError as exc:
        raise PiNotFoundError("`pi` binary not on PATH") from exc
    if result.returncode != 0:
        raise RuntimeError(
            f"pi remove failed (exit {result.returncode}): {result.stderr.strip()}"
        )
```

- [ ] **Step 4: Tests pass**

Run: `uv run pytest tests/test_pi_fetch.py -v`
Expected: PASS (3 tests).

### Task 3.3: `pi load` Click subcommand

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi.py`
- Modify: `tests/test_cli_pi.py`

- [ ] **Step 1: Write tests for `load`**

Append to `tests/test_cli_pi.py`. Use `monkeypatch.setattr` on `subprocess.run` so tests don't hit a real `pi`.

```python
import subprocess
from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def test_pi_load_third_party_writes_allowlist_and_settings_then_fetches(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    # Fake `pi install` — record the call, simulate creating node_modules.
    calls: list[list[str]] = []
    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        # simulate fetch
        nm = home / ".pi/agent/npm/node_modules/pi-subagents"
        nm.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "npm:pi-subagents", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output

    # 1. Allowlist gained the entry
    allow = (home / ".agent-toolkit.yaml").read_text()
    assert "npm:pi-subagents" in allow
    # 2. settings.json has the entry
    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert "npm:pi-subagents" in settings["packages"]
    # 3. pi install was invoked
    assert any("install" in c and "npm:pi-subagents" in c for c in calls)
    # 4. node_modules dir exists (simulated by fake)
    assert (home / ".pi/agent/npm/node_modules/pi-subagents").is_dir()


def test_pi_load_idempotent_no_second_install(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent/npm/node_modules/pi-subagents").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-subagents"]})
    )
    (home / ".agent-toolkit.yaml").write_text(
        yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]})
    )
    monkeypatch.setenv("HOME", str(home))

    calls: list[list[str]] = []
    def fake_run(cmd, *args, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "npm:pi-subagents", "--scope", "user"],
    )
    assert result.exit_code == 0
    # No `pi install` call should have happened — already loaded.
    assert not any("install" in c for c in calls)


def test_pi_load_first_party_creates_symlink(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    # First-party assets live in the toolkit repo. For the test we don't need
    # a real toolkit; we just need an existing source dir to symlink to.
    src = tmp_path / "toolkit-extensions" / "status-bar"
    src.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(tmp_path / "toolkit"))
    # Place the asset where the toolkit walker can find it:
    toolkit_ext = tmp_path / "toolkit" / "extensions" / "status-bar"
    toolkit_ext.mkdir(parents=True)
    (toolkit_ext / "extension.meta.yaml").write_text(
        "kind: pi-extension\nslug: status-bar\nname: status-bar\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "status-bar", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    target = home / ".pi/agent/extensions/status-bar"
    assert target.is_symlink() or target.is_dir()
    # Allowlist gained entry under pi_extensions, not pi_packages
    allow = yaml.safe_load((home / ".agent-toolkit.yaml").read_text())
    assert "status-bar" in (allow.get("pi_extensions") or [])
    assert "status-bar" not in (allow.get("pi_packages") or [])


def test_pi_load_pi_missing_surfaces_actionable_error(tmp_path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))

    def fake_run(cmd, *args, **kwargs):
        raise FileNotFoundError("pi")
    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "npm:pi-subagents", "--scope", "user"],
    )
    assert result.exit_code != 0
    assert "pi" in result.output.lower()
    assert "path" in result.output.lower() or "not found" in result.output.lower()
```

- [ ] **Step 2: Run — should fail**

Run: `uv run pytest tests/test_cli_pi.py -v -k load`
Expected: FAIL — `load` not implemented.

- [ ] **Step 3: Implement `pi load`**

Append to `src/agent_toolkit_cli/commands/pi.py`:

```python
from agent_toolkit_cli._pi_fetch import PiNotFoundError, fetch_package
from agent_toolkit_cli._pi_settings import add_package
from agent_toolkit_cli.commands._yaml_edit import add_slug


def _is_third_party_source(target: str) -> bool:
    """`npm:`/`git:` prefix → third-party. Bare slug → first-party."""
    return target.startswith("npm:") or target.startswith("git:")


@pi.command(name="load")
@click.argument("target")
@click.option(
    "--scope",
    type=click.Choice(["user", "project"]),
    required=True,
    help="Which scope to load into. Required (no implicit default).",
)
@click.pass_context
def load_cmd(ctx: click.Context, target: str, scope: str) -> None:
    """Make TARGET loaded in SCOPE.

    TARGET is either a bare slug (first-party) or a `npm:`/`git:` source
    string (third-party). The toolkit writes its config (allowlist +
    settings.json for third-party) directly, then for third-party invokes
    `pi install` only to populate node_modules.
    """
    home = Path(os.environ.get("HOME", ""))
    project_root = ctx.obj.get("project_root") if ctx.obj else None
    if project_root is None:
        project_root = Path.cwd()

    allow_path = _allowlist_path(scope, home, project_root)
    pp = PiPaths(home=home, project_root=project_root)
    settings_path = pp.user_settings_json if scope == "user" else pp.project_settings_json

    if _is_third_party_source(target):
        slug = _slug_from_source(target)
        # Idempotency: if already loaded, no-op (no fetch).
        node_modules_dir = pp.user_node_modules_dir if scope == "user" else pp.project_node_modules_dir
        already_in_settings = target in read_packages(settings_path)
        already_fetched = (node_modules_dir / slug).is_dir()
        if already_in_settings and already_fetched:
            add_slug(allow_path, "pi_packages", target)
            return

        # 1. Toolkit writes its records first.
        add_slug(allow_path, "pi_packages", target)
        add_package(settings_path, target)
        # 2. Toolkit invokes `pi install` for the fetch only.
        try:
            fetch_package(target, scope=scope, home=home, project_root=project_root)
        except PiNotFoundError as exc:
            raise click.ClickException(
                "`pi` binary not on PATH — third-party fetch requires Pi installed."
            ) from exc
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        return

    # First-party path: symlink + allowlist entry.
    add_slug(allow_path, "pi_extensions", target)
    # Materialise the symlink via the existing linker. Importing inline to
    # avoid a top-level dependency cycle.
    from agent_toolkit_cli._link_lib import link_one_asset
    try:
        link_one_asset(
            slug=target, kind="pi-extension", harness="pi", scope=scope,
            project_root=project_root, toolkit_root=None,
        )
    except Exception as exc:
        raise click.ClickException(f"failed to link {target!r}: {exc}") from exc
```

The function `link_one_asset` is the existing helper used by `link` — if its exact name/signature differs, the build agent inspects `_link_lib.py` and uses the correct entry point (the goal is "symlink the first-party asset via the same code path `agent-toolkit-cli link` uses today"). Recording any divergence in the commit message.

- [ ] **Step 4: Implement `pi unload`**

Append:

```python
from agent_toolkit_cli._pi_fetch import remove_package_fetched
from agent_toolkit_cli._pi_settings import remove_package
from agent_toolkit_cli.commands._yaml_edit import remove_slug


@pi.command(name="unload")
@click.argument("target")
@click.option(
    "--scope",
    type=click.Choice(["user", "project"]),
    required=True,
)
@click.pass_context
def unload_cmd(ctx: click.Context, target: str, scope: str) -> None:
    """Make TARGET not-loaded in SCOPE.

    Toolkit removes its config first, then for third-party invokes `pi remove`
    to purge node_modules. First-party removes the symlink.
    """
    home = Path(os.environ.get("HOME", ""))
    project_root = ctx.obj.get("project_root") if ctx.obj else None
    if project_root is None:
        project_root = Path.cwd()

    allow_path = _allowlist_path(scope, home, project_root)
    pp = PiPaths(home=home, project_root=project_root)
    settings_path = pp.user_settings_json if scope == "user" else pp.project_settings_json

    if _is_third_party_source(target):
        # 1. Toolkit removes its records first.
        try:
            remove_slug(allow_path, "pi_packages", target)
        except FileNotFoundError:
            pass
        remove_package(settings_path, target)
        # 2. Toolkit invokes `pi remove` to purge node_modules.
        try:
            remove_package_fetched(target, scope=scope, home=home, project_root=project_root)
        except PiNotFoundError:
            # Non-fatal — config is removed; doctor will surface drift.
            pass
        except RuntimeError as exc:
            raise click.ClickException(str(exc)) from exc
        return

    # First-party: remove allowlist entry, remove symlink.
    try:
        remove_slug(allow_path, "pi_extensions", target)
    except FileNotFoundError:
        pass
    target_path = (
        pp.user_extensions_dir / target if scope == "user" else pp.project_extensions_dir / target
    )
    if target_path.is_symlink() or target_path.exists():
        if target_path.is_symlink():
            target_path.unlink()
        else:
            # Real dir (hand-authored) — don't delete; surface via doctor.
            raise click.ClickException(
                f"{target_path} is not a symlink — refusing to delete. "
                "Run `agent-toolkit-cli doctor` for context."
            )
```

Use `_slug_from_source` from `_pi_inventory` (re-export or import). If it's not already importable, the build agent adds the import: `from agent_toolkit_cli._pi_inventory import _slug_from_source`.

- [ ] **Step 5: Tests pass**

Run: `uv run pytest tests/test_cli_pi.py tests/test_pi_fetch.py -v`
Expected: PASS.

- [ ] **Step 6: Commit (commit 3)**

```bash
git add src/agent_toolkit_cli/_pi_fetch.py \
        src/agent_toolkit_cli/commands/pi.py \
        tests/test_pi_fetch.py \
        tests/test_cli_pi.py
git commit -m "feat(pi): load/unload verbs — toolkit owns config, pi fetches (#103)"
```

---

## Commit 4 — TUI Pi tab

The TUI consumes `pi inventory --format json` and renders a table with toggle bindings.

### Task 4.1: Pi tab widget

**Files:**
- Create: `src/agent_toolkit_tui/widgets/pi_tab.py`
- Modify: `src/agent_toolkit_tui/app.py:109` (add binding)
- Modify: `src/agent_toolkit_tui/widgets/kinds_sidebar.py:22, 31` (add Pi entry)
- Test:   `tests/test_tui_pi_tab.py`

- [ ] **Step 1: Write a Textual snapshot test**

```python
# tests/test_tui_pi_tab.py
import json
from pathlib import Path
import pytest

from agent_toolkit_tui.widgets.pi_tab import PiTab


def test_pi_tab_renders_one_row_per_record(tmp_path):
    records = [
        {
            "slug": "status-bar",
            "origin": "first-party",
            "source": "extension:status-bar",
            "user_loaded": True,
            "project_loaded": False,
            "user_installed_at": "/home/.pi/agent/extensions/status-bar",
            "project_installed_at": None,
            "toolkit_intent": "user",
        },
        {
            "slug": "pi-subagents",
            "origin": "third-party",
            "source": "npm:pi-subagents",
            "user_loaded": True,
            "project_loaded": False,
            "user_installed_at": "/home/.pi/agent/npm/node_modules/pi-subagents",
            "project_installed_at": None,
            "toolkit_intent": "user",
        },
    ]

    tab = PiTab(records=records)
    # Pure unit: the widget exposes a `rows()` method returning the row strings.
    rows = tab.rows()
    assert any("status-bar" in r and "1P" in r for r in rows)
    assert any("pi-subagents" in r and "3P" in r for r in rows)


def test_pi_tab_empty_state(tmp_path):
    tab = PiTab(records=[])
    rows = tab.rows()
    assert rows == [] or "no" in rows[0].lower()
```

- [ ] **Step 2: Run — fail**

Run: `uv run pytest tests/test_tui_pi_tab.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `pi_tab.py`**

```python
"""Pi tab — Textual widget consuming `agent-toolkit-cli pi inventory --format json`.

Pure-data widget: receives records via constructor, exposes `rows()` for
testing without spinning up the whole Textual app. The app wires `u`/`p`
key bindings to shell out to `pi load`/`unload` and refresh.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual.widget import Widget
from textual.widgets import DataTable, Static


@dataclass
class _Row:
    slug: str
    origin_badge: str
    source: str
    user_loaded: str
    project_loaded: str
    intent: str


class PiTab(Widget):
    """Pi extension inventory + toggle controls."""

    def __init__(self, *, records: list[dict[str, Any]], **kwargs):
        super().__init__(**kwargs)
        self._records = records

    def rows(self) -> list[str]:
        """Plain-string rows for unit testing without the full Textual rig."""
        if not self._records:
            return []
        out: list[str] = []
        for r in self._records:
            badge = "1P" if r["origin"] == "first-party" else "3P"
            out.append(
                f"{r['slug']:<24} {badge:<3} "
                f"{'✓' if r['user_loaded'] else ' ':<3} "
                f"{'✓' if r['project_loaded'] else ' ':<3} "
                f"{r['toolkit_intent']:<8} {r['source']}"
            )
        return out

    def compose(self):
        if not self._records:
            yield Static("(no Pi extensions found)")
            return
        table = DataTable()
        table.add_columns("Slug", "Origin", "U", "P", "Intent", "Source")
        for r in self._records:
            badge = "1P" if r["origin"] == "first-party" else "3P"
            table.add_row(
                r["slug"],
                badge,
                "✓" if r["user_loaded"] else " ",
                "✓" if r["project_loaded"] else " ",
                r["toolkit_intent"],
                r["source"],
            )
        yield table
```

- [ ] **Step 4: Wire app keybinding + sidebar entry**

Modify `src/agent_toolkit_tui/app.py:109` — add the Pi-tab binding alongside the existing `Binding("7", ...)`:

```python
Binding("8", "kind('pi-tab')", "Pi", show=False),
```

Modify `src/agent_toolkit_tui/widgets/kinds_sidebar.py` to expose the new tab. (Build agent applies the smallest delta — the existing pattern at lines 22/31 shows the shape.)

- [ ] **Step 5: Tests pass**

Run: `uv run pytest tests/test_tui_pi_tab.py -v`
Expected: PASS.

- [ ] **Step 6: Manual sanity check**

Run: `uv run agent-toolkit-tui` and tab to `8`. Verify the tab renders without crashing.

Capture a screenshot to `assets/verification/103/tui-pi-tab.png` for the PR (see Step 9 of the flow).

- [ ] **Step 7: Commit (commit 4)**

```bash
git add src/agent_toolkit_tui/widgets/pi_tab.py \
        src/agent_toolkit_tui/app.py \
        src/agent_toolkit_tui/widgets/kinds_sidebar.py \
        tests/test_tui_pi_tab.py
git commit -m "feat(tui): pi tab — unified extension inventory + toggle (#103)"
```

---

## Commit 5 — Doctor advisories

Three new advisories. **Read-only** — doctor doesn't fix things, only surfaces them.

### Task 5.1: Advisory module

**Files:**
- Create: `src/agent_toolkit_cli/doctor/pi_advisories.py`
- Modify: doctor entry point (the build agent finds the `Result`-yielding wiring; existing modules at `src/agent_toolkit_cli/doctor/*.py` show the pattern — likely a registry in `__init__.py` or an explicit list in a runner).
- Test:   `tests/test_doctor_pi_advisories.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doctor_pi_advisories.py
import json
from pathlib import Path

from agent_toolkit_cli.doctor.pi_advisories import audit_pi


def test_hand_authored_extension_warns(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    # A real dir under extensions/ that is NOT a symlink.
    (home / ".pi/agent/extensions/handmade").mkdir(parents=True)

    results = audit_pi(home=home, project_root=project)

    assert any("handmade" in r.message and "hand-authored" in r.message.lower() for r in results)


def test_drift_warns_when_pi_packages_declares_missing_resolution(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".agent-toolkit.yaml").write_text("pi_packages:\n  - npm:phantom\n")
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(json.dumps({"packages": []}))

    results = audit_pi(home=home, project_root=project)

    assert any("phantom" in r.message and "drift" in r.message.lower() for r in results)


def test_slug_collision_warns(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".agent-toolkit.yaml").write_text(
        "pi_extensions: [foo]\npi_packages: [npm:foo]\n"
    )

    results = audit_pi(home=home, project_root=project)

    assert any("foo" in r.message and "collision" in r.message.lower() for r in results)


def test_clean_repo_yields_no_warnings(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    home.mkdir()
    project.mkdir()

    results = audit_pi(home=home, project_root=project)
    assert results == []
```

- [ ] **Step 2: Run — fail**

Run: `uv run pytest tests/test_doctor_pi_advisories.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement `pi_advisories.py`**

The existing `src/agent_toolkit_cli/doctor/result.py` defines the `Result` type. Re-use it.

```python
"""Doctor advisories for Pi extensions.

Three checks (all read-only):
1. Hand-authored extension — a real (non-symlink) dir under
   `~/.pi/agent/extensions/<slug>/`. Likely operator-authored content the
   toolkit didn't create. Surface so operator can decide.
2. Drift — `pi_packages:` declares an entry that has no matching
   `settings.json` `packages[]` entry OR no resolved `node_modules/<slug>/`.
3. Slug collision — same slug appears in both `pi_extensions:` and
   `pi_packages:` (first-party wins for `origin`, but operator should know).
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli._allowlist import read_allowlist
from agent_toolkit_cli._pi_inventory import _slug_from_source
from agent_toolkit_cli._pi_paths import PiPaths
from agent_toolkit_cli._pi_settings import read_packages
from agent_toolkit_cli.doctor.result import Result


def audit_pi(*, home: Path, project_root: Path) -> list[Result]:
    out: list[Result] = []
    pp = PiPaths(home=home, project_root=project_root)

    # --- (1) hand-authored extensions ---
    for ext_dir in (pp.user_extensions_dir, pp.project_extensions_dir):
        if not ext_dir.is_dir():
            continue
        for child in ext_dir.iterdir():
            if child.is_symlink():
                continue
            if child.is_dir():
                out.append(
                    Result(
                        level="warn",
                        message=(
                            f"Hand-authored extension at {child} — not a symlink. "
                            "The toolkit didn't create this. If intentional, "
                            "ignore; otherwise consider `pi unload`."
                        ),
                    )
                )

    # --- (2) drift ---
    user_allow = read_allowlist(home / ".agent-toolkit.yaml")
    declared_packages = list(user_allow.get("pi_packages", []))
    resolved = read_packages(pp.user_settings_json)
    node_modules_present = (
        {p.name for p in pp.user_node_modules_dir.iterdir() if p.is_dir() or p.is_symlink()}
        if pp.user_node_modules_dir.is_dir()
        else set()
    )
    for source in declared_packages:
        in_settings = source in resolved
        slug = _slug_from_source(source)
        in_node_modules = slug in node_modules_present
        if not in_settings or not in_node_modules:
            missing = []
            if not in_settings:
                missing.append("settings.json")
            if not in_node_modules:
                missing.append("node_modules")
            out.append(
                Result(
                    level="warn",
                    message=(
                        f"drift: pi_packages declares {source!r} but missing from {', '.join(missing)}. "
                        "Run `agent-toolkit-cli pi load <source> --scope user` to reconcile."
                    ),
                )
            )

    # --- (3) slug collision ---
    first_party = set(user_allow.get("pi_extensions", []))
    third_party = {_slug_from_source(s) for s in declared_packages}
    for clash in sorted(first_party & third_party):
        out.append(
            Result(
                level="warn",
                message=(
                    f"slug collision: {clash!r} appears in both pi_extensions and pi_packages. "
                    "First-party wins for `origin`; remove one to disambiguate."
                ),
            )
        )

    return out
```

- [ ] **Step 4: Wire the advisory into the doctor runner**

Build agent finds the doctor runner — likely `src/agent_toolkit_cli/commands/doctor.py` — and appends a call to `audit_pi(home=..., project_root=...)`. Follow the pattern of the existing wiring of `audit_mcps`, `audit_allowlist`, etc.

- [ ] **Step 5: Tests pass**

Run: `uv run pytest tests/test_doctor_pi_advisories.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Run full doctor end-to-end**

Run: `uv run agent-toolkit-cli doctor` — verify no crash; the advisories integrate cleanly.

- [ ] **Step 7: Commit (commit 5)**

```bash
git add src/agent_toolkit_cli/doctor/pi_advisories.py \
        src/agent_toolkit_cli/commands/doctor.py \
        tests/test_doctor_pi_advisories.py
git commit -m "feat(doctor): pi advisories — hand-authored, drift, slug collision (#103)"
```

---

## Final pre-PR checks (Step 8/9/10 of flow)

After commit 5:

- [ ] **Full pytest**

Run: `uv run pytest -q`
Expected: PASS (no regressions; ~745+ tests).

- [ ] **CLI smoke**

Run:
```bash
uv run agent-toolkit-cli pi inventory --format json
uv run agent-toolkit-cli pi inventory
uv run agent-toolkit-cli pi --help
uv run agent-toolkit-cli doctor 2>&1 | head -40
```
Each should exit 0; capture to `assets/verification/103/`.

- [ ] **TUI screenshot**

Run the TUI, navigate to the Pi tab, capture `assets/verification/103/tui-pi-tab.png`.

---

## Notes for the builder

- **Where things are**: existing patterns to mirror — `commands/_yaml_edit.py` (config-write style), `commands/inventory.py` (Click subcommand shape), `doctor/*.py` (advisory `Result` pattern), `_support.py` (path-template style).
- **Two-flag contract**: every command must accept `--toolkit-repo` (via the group) and `--project` (via the group); they end up on `ctx.obj`.
- **No backwards-compat shims**. `_allowlist.SECTIONS` gains one element; tests update accordingly. We are not at v1alpha3 — additive only.
- **Avoid premature abstraction**: `_pi_inventory.build_pi_inventory` is one function with many keyword args. Don't refactor to a class unless a second caller appears.
- **Don't widen schema scope**: `pi_packages:` entries are raw strings (`npm:...`, `git:...`). No schema validation. Doctor's drift check is the safety net.
- **CommentedMap quirk**: when using `_yaml_edit.add_slug` for `pi_packages`, the section is initialised as a `CommentedSeq` automatically. No new code needed.

## Spec coverage self-check

- §3 acceptance #1 (fresh `pi install` → inventory shows third-party / loaded / intent=none) → covered by `test_pi_inventory.test_third_party_user_loaded_unmanaged` + `test_cli_pi.test_pi_inventory_json_format`.
- §3 acceptance #2 (`pi load` adds allowlist + flips intent; no second install) → covered by `test_pi_load_third_party_writes_allowlist_and_settings_then_fetches` + `test_pi_load_idempotent_no_second_install`.
- §3 acceptance #3 (`pi unload` purges) → covered by `test_pi_unload_*` (build agent adds analogous tests when implementing 3.4 — pattern is identical to load).
- §3 acceptance #4 (sync no-op after load) → covered by `test_pi_sync_idempotent`.
- §3 acceptance #5 (TUI renders inventory; toggles route via verbs) → covered by `test_pi_tab_renders_one_row_per_record` and the manual screenshot.
- §4.4 CLI surface — all four verbs land (commits 1, 2, 3).
- §4.6 Doctor advisories — covered by `test_doctor_pi_advisories.py`.
- §4.7 Toolkit owns writes — explicit in `pi load` ordering (allowlist write → settings.json write → fetch).

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-19-pi-unified-extension-inventory.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
