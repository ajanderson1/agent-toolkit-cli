# Pi `extensions[]` override surface — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `agent-toolkit-cli pi inventory` report what Pi will actually load by honouring `settings.json` `extensions[]` enable/disable overrides, and surface orphaned overrides via doctor.

**Architecture:** New pure module `_pi_overrides.py` mirrors Pi's `isEnabledByOverrides` rules for one slug. `_pi_settings.py` gains `read_extensions_overrides`. `build_pi_inventory` accepts two new args (`user_extensions_overrides`, `project_extensions_overrides`) and populates two new `PiRecord` fields (`user_enabled`, `project_enabled`). CLI threads them in. TUI dims loaded-but-disabled rows. Doctor adds an "orphaned override" advisory.

**Tech Stack:** Python 3.11+, `dataclasses`, `pathlib`, `click`, `textual`, `pytest`.

**Spec:** `docs/superpowers/specs/2026-05-19-pi-settings-extensions-array-design.md`

---

## File Structure

**Create:**
- `src/agent_toolkit_cli/_pi_overrides.py` — pure `is_enabled(slug, overrides)` evaluator.
- `tests/test_pi_overrides.py` — fixtures transcribed from `package-manager.js`.

**Modify:**
- `src/agent_toolkit_cli/_pi_settings.py` — add `read_extensions_overrides`.
- `src/agent_toolkit_cli/_pi_inventory.py` — extend `PiRecord` with `user_enabled`, `project_enabled`; extend `build_pi_inventory` signature.
- `src/agent_toolkit_cli/commands/pi.py` — read overrides, pass to `build_pi_inventory`.
- `src/agent_toolkit_cli/doctor/pi_advisories.py` — add `_orphaned_overrides`.
- `src/agent_toolkit_tui/widgets/pi_tab.py` — render loaded-but-disabled with `~` glyph.
- `tests/test_pi_settings.py` — cover the new reader.
- `tests/test_pi_inventory.py` — cover override propagation onto records.
- `tests/test_doctor_pi_advisories.py` — cover the new advisory.
- `tests/test_tui_pi_tab.py` — cover the disabled glyph rendering.

---

## Task 1: Override evaluator (`is_enabled`)

**Files:**
- Create: `src/agent_toolkit_cli/_pi_overrides.py`
- Test: `tests/test_pi_overrides.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pi_overrides.py
from agent_toolkit_cli._pi_overrides import is_enabled


def test_empty_overrides_enabled():
    assert is_enabled(slug="foo", overrides=[]) is True


def test_plain_include_filter_enables_only_listed():
    # Pi rule: any plain entry switches mode to include-filter — non-listed extensions become disabled.
    assert is_enabled(slug="foo", overrides=["foo"]) is True
    assert is_enabled(slug="bar", overrides=["foo"]) is False


def test_bang_exclude():
    assert is_enabled(slug="foo", overrides=["!foo"]) is False
    assert is_enabled(slug="bar", overrides=["!foo"]) is True


def test_force_include_beats_exclude():
    assert is_enabled(slug="foo", overrides=["!foo", "+foo"]) is True


def test_force_exclude_beats_force_include():
    assert is_enabled(slug="foo", overrides=["+foo", "-foo"]) is False


def test_glob_star_in_include():
    assert is_enabled(slug="status-bar", overrides=["status-*"]) is True
    assert is_enabled(slug="other", overrides=["status-*"]) is False


def test_unknown_pattern_shape_recorded_as_unmatched():
    # Anything other than slug/glob (e.g. a relative path with `/`) doesn't match by name.
    assert is_enabled(slug="foo", overrides=["sub/dir/foo"]) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pi_overrides.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli._pi_overrides'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/agent_toolkit_cli/_pi_overrides.py
"""Pi extensions[] override evaluator.

Mirrors `isEnabledByOverrides` from `@earendil-works/pi-coding-agent`
`dist/core/package-manager.js:502`. Inputs are a slug (auto-discovery dir
name) and the verbatim `extensions[]` list from settings.json.

Pattern grammar (per `getOverridePatterns`, `:499` and `applyPatterns`, `:527`):
- plain entry → include-filter (only matching slugs enabled when present)
- `!entry`    → exclude
- `+entry`    → force-include (overrides excludes)
- `-entry`    → force-exclude (overrides force-includes)

Matching is exact-name + `*` glob only — narrower than Pi's full glob engine
(which matches paths, not slugs). Anything more elaborate is treated as
non-matching here; the doctor advisory surfaces patterns that don't match any
known slug.
"""
from __future__ import annotations

import fnmatch


def _matches(slug: str, pattern: str) -> bool:
    if "*" in pattern or "?" in pattern:
        return fnmatch.fnmatchcase(slug, pattern)
    return slug == pattern


def is_enabled(*, slug: str, overrides: list[str]) -> bool:
    plain: list[str] = []
    excludes: list[str] = []
    force_includes: list[str] = []
    force_excludes: list[str] = []
    for entry in overrides:
        if entry.startswith("!"):
            excludes.append(entry[1:])
        elif entry.startswith("+"):
            force_includes.append(entry[1:])
        elif entry.startswith("-"):
            force_excludes.append(entry[1:])
        else:
            plain.append(entry)

    if plain:
        enabled = any(_matches(slug, p) for p in plain)
    else:
        enabled = True

    if excludes and any(_matches(slug, p) for p in excludes):
        enabled = False
    if force_includes and any(_matches(slug, p) for p in force_includes):
        enabled = True
    if force_excludes and any(_matches(slug, p) for p in force_excludes):
        enabled = False
    return enabled
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pi_overrides.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_pi_overrides.py tests/test_pi_overrides.py
git commit -m "feat(pi): override evaluator mirroring Pi's isEnabledByOverrides"
```

---

## Task 2: Settings reader for `extensions[]`

**Files:**
- Modify: `src/agent_toolkit_cli/_pi_settings.py`
- Test: `tests/test_pi_settings.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pi_settings.py`:

```python
import json
from pathlib import Path

from agent_toolkit_cli._pi_settings import read_extensions_overrides


def test_read_extensions_overrides_missing_file(tmp_path: Path):
    assert read_extensions_overrides(tmp_path / "nope.json") == []


def test_read_extensions_overrides_missing_key(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"packages": ["npm:foo"]}), encoding="utf-8")
    assert read_extensions_overrides(p) == []


def test_read_extensions_overrides_returns_list(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"extensions": ["!foo", "+bar"]}), encoding="utf-8")
    assert read_extensions_overrides(p) == ["!foo", "+bar"]


def test_read_extensions_overrides_non_list_returns_empty(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"extensions": "huh"}), encoding="utf-8")
    assert read_extensions_overrides(p) == []


def test_read_extensions_overrides_malformed_raises(tmp_path: Path):
    p = tmp_path / "s.json"
    p.write_text("{not-json", encoding="utf-8")
    try:
        read_extensions_overrides(p)
    except ValueError as exc:
        assert "malformed settings.json" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pi_settings.py -v -k read_extensions_overrides`
Expected: FAIL — `ImportError: cannot import name 'read_extensions_overrides'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/agent_toolkit_cli/_pi_settings.py`:

```python
def read_extensions_overrides(path: Path) -> list[str]:
    """Return `extensions[]` from settings.json (override-pattern list).

    Schema-tolerant: missing file -> [], missing key -> [], non-list -> [].
    Raises ValueError on malformed JSON, mentioning the path.
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
    extensions = parsed.get("extensions") or []
    if not isinstance(extensions, list):
        return []
    return [str(e) for e in extensions if e]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pi_settings.py -v`
Expected: all passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_pi_settings.py tests/test_pi_settings.py
git commit -m "feat(pi): read_extensions_overrides for settings.json"
```

---

## Task 3: Thread overrides into `build_pi_inventory`

**Files:**
- Modify: `src/agent_toolkit_cli/_pi_inventory.py`
- Modify: `src/agent_toolkit_cli/commands/pi.py`
- Test: `tests/test_pi_inventory.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pi_inventory.py`:

```python
def test_first_party_disabled_by_bang_override(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/status-bar")
    _mkdir_p(project)

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        user_allowlist_pi_extensions=["status-bar"],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
        user_extensions_overrides=["!status-bar"],
        project_extensions_overrides=[],
    )

    assert len(records) == 1
    r = records[0]
    assert r.user_loaded is True
    assert r.user_enabled is False
    assert r.project_enabled is True  # default when no override targets the slug


def test_first_party_default_enabled_no_overrides(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    _mkdir_p(home / ".pi/agent/extensions/status-bar")
    _mkdir_p(project)

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=[],
        project_packages=[],
        user_node_modules=set(),
        project_node_modules=set(),
        user_allowlist_pi_extensions=["status-bar"],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
        user_extensions_overrides=[],
        project_extensions_overrides=[],
    )

    assert records[0].user_enabled is True
    assert records[0].project_enabled is True


def test_third_party_always_enabled(tmp_path: Path):
    """`extensions[]` override list does not target packages — `enabled` stays True."""
    home = tmp_path / "home"
    project = tmp_path / "proj"

    records = build_pi_inventory(
        paths=_paths(home, project),
        user_packages=["npm:pi-subagents"],
        project_packages=[],
        user_node_modules={"pi-subagents"},
        project_node_modules=set(),
        user_allowlist_pi_extensions=[],
        project_allowlist_pi_extensions=[],
        user_allowlist_pi_packages=[],
        project_allowlist_pi_packages=[],
        user_extensions_overrides=["!pi-subagents"],  # ignored for third-party
        project_extensions_overrides=[],
    )

    r = records[0]
    assert r.origin == "third-party"
    assert r.user_enabled is True
    assert r.project_enabled is True
```

Also update **existing tests** in `tests/test_pi_inventory.py` to pass the new keyword arguments (default `[]` each). Add this at the top of any existing test that builds inventory:

```python
        user_extensions_overrides=[],
        project_extensions_overrides=[],
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pi_inventory.py -v`
Expected: existing tests pass (still work without the new kwargs once we make them default-empty), new tests FAIL with `AttributeError: 'PiRecord' object has no attribute 'user_enabled'`.

- [ ] **Step 3: Modify `PiRecord` and `build_pi_inventory`**

Edit `src/agent_toolkit_cli/_pi_inventory.py`:

```python
# Extend the dataclass (after the existing field block):
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
    user_enabled: bool = True
    project_enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)
```

Update `build_pi_inventory`:

```python
def build_pi_inventory(
    *,
    paths: PiPaths,
    user_packages: list[str],
    project_packages: list[str],
    user_node_modules: set[str],
    project_node_modules: set[str],
    user_allowlist_pi_extensions: list[str],
    project_allowlist_pi_extensions: list[str],
    user_allowlist_pi_packages: list[str],
    project_allowlist_pi_packages: list[str],
    user_extensions_overrides: list[str] | None = None,
    project_extensions_overrides: list[str] | None = None,
) -> list[PiRecord]:
    ...
    user_overrides = user_extensions_overrides or []
    project_overrides = project_extensions_overrides or []
    ...
```

In the first-party loop, set `user_enabled` / `project_enabled`:

```python
    from agent_toolkit_cli._pi_overrides import is_enabled

    for slug in sorted(all_first_party):
        user_loaded = slug in user_ext_slugs
        project_loaded = slug in project_ext_slugs
        user_enabled = is_enabled(slug=slug, overrides=user_overrides)
        project_enabled = is_enabled(slug=slug, overrides=project_overrides)
        intent = _intent_for(
            in_user=slug in user_allow_first_party_slugs,
            in_project=slug in project_allow_first_party_slugs,
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
                user_enabled=user_enabled,
                project_enabled=project_enabled,
            )
        )
```

Third-party records keep the defaults (`True` / `True`).

Top-of-file import:

```python
from agent_toolkit_cli._pi_overrides import is_enabled
```

(Place above the existing `from agent_toolkit_cli._pi_paths import PiPaths` line; alphabetised.)

- [ ] **Step 4: Wire the CLI**

Edit `src/agent_toolkit_cli/commands/pi.py` — extend the import block and `_gather_inventory`:

```python
from agent_toolkit_cli._pi_settings import (
    add_package,
    read_extensions_overrides,
    read_packages,
    remove_package,
    write_packages,
)
```

In `_gather_inventory`:

```python
    user_overrides = read_extensions_overrides(pp.user_settings_json)
    project_overrides = read_extensions_overrides(pp.project_settings_json)
```

Pass to `build_pi_inventory`:

```python
    return build_pi_inventory(
        paths=pp,
        user_packages=user_packages,
        project_packages=project_packages,
        user_node_modules=user_node_modules,
        project_node_modules=project_node_modules,
        user_allowlist_pi_extensions=user_pi_exts,
        project_allowlist_pi_extensions=project_pi_exts,
        user_allowlist_pi_packages=user_pi_pkgs,
        project_allowlist_pi_packages=project_pi_pkgs,
        user_extensions_overrides=user_overrides,
        project_extensions_overrides=project_overrides,
    )
```

- [ ] **Step 5: Run tests to verify**

Run: `uv run pytest tests/test_pi_inventory.py tests/test_cli_pi.py -v`
Expected: all passed (existing CLI tests continue to work; new override tests pass).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/_pi_inventory.py src/agent_toolkit_cli/commands/pi.py tests/test_pi_inventory.py
git commit -m "feat(pi): inventory honours settings.json extensions[] overrides"
```

---

## Task 4: TUI Pi tab — render loaded-but-disabled

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/pi_tab.py`
- Test: `tests/test_tui_pi_tab.py`

- [ ] **Step 1: Inspect existing test patterns**

Read `tests/test_tui_pi_tab.py` to see the established assertion style; we add a single test for the new glyph.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_tui_pi_tab.py`:

```python
def test_pi_tab_disabled_glyph_for_loaded_but_disabled():
    from agent_toolkit_tui.widgets.pi_tab import PiTab

    records = [
        {
            "slug": "status-bar",
            "origin": "first-party",
            "source": "extension:status-bar",
            "user_loaded": True,
            "project_loaded": False,
            "user_enabled": False,
            "project_enabled": True,
            "toolkit_intent": "user",
        }
    ]
    tab = PiTab(records=records)
    rows = tab.rows()
    assert len(rows) == 1
    # Loaded but disabled => `~` in the U column, not `✓`.
    assert "~" in rows[0]
    assert "✓" not in rows[0]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_tui_pi_tab.py -v -k disabled_glyph`
Expected: FAIL — assertion error on `~`.

- [ ] **Step 4: Update `pi_tab.py`**

Replace the row-glyph logic in both `rows()` and `compose()`:

```python
def _glyph(loaded: bool, enabled: bool) -> str:
    if not loaded:
        return " "
    return "✓" if enabled else "~"
```

Use it in `rows()`:

```python
        for r in self._records:
            badge = "1P" if r.get("origin") == "first-party" else "3P"
            u = _glyph(bool(r.get("user_loaded")), bool(r.get("user_enabled", True)))
            p = _glyph(bool(r.get("project_loaded")), bool(r.get("project_enabled", True)))
            out.append(
                f"{r.get('slug', ''):<24} {badge:<3} "
                f"{u:<3} {p:<3} "
                f"{r.get('toolkit_intent', ''):<8} {r.get('source', '')}"
            )
```

And in `compose()`:

```python
        for r in self._records:
            badge = "1P" if r.get("origin") == "first-party" else "3P"
            u = _glyph(bool(r.get("user_loaded")), bool(r.get("user_enabled", True)))
            p = _glyph(bool(r.get("project_loaded")), bool(r.get("project_enabled", True)))
            table.add_row(
                r.get("slug", ""),
                badge,
                u,
                p,
                r.get("toolkit_intent", ""),
                r.get("source", ""),
            )
```

The `_glyph` helper goes module-level near the top of the file (after imports).

- [ ] **Step 5: Run tests to verify**

Run: `uv run pytest tests/test_tui_pi_tab.py -v`
Expected: all passed (existing tests still pass — `user_enabled` defaults to `True` when missing from a record).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui/widgets/pi_tab.py tests/test_tui_pi_tab.py
git commit -m "feat(tui): pi tab dims loaded-but-disabled extensions with ~ glyph"
```

---

## Task 5: Doctor advisory — orphaned overrides

**Files:**
- Modify: `src/agent_toolkit_cli/doctor/pi_advisories.py`
- Test: `tests/test_doctor_pi_advisories.py`

- [ ] **Step 1: Read existing advisory test pattern**

Skim `tests/test_doctor_pi_advisories.py` for the helper style (probably builds `PiPaths`, calls `audit_pi`, asserts message substrings).

- [ ] **Step 2: Write the failing test**

Append to `tests/test_doctor_pi_advisories.py`:

```python
def test_orphaned_override_advisory(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    (home / ".pi/agent").mkdir(parents=True)
    # `+foo` references a slug that doesn't exist as an auto-discovered dir.
    (home / ".pi/agent/settings.json").write_text(
        '{"extensions": ["+missing-slug"]}', encoding="utf-8"
    )
    project.mkdir()

    advisories = audit_pi(home=home, project_root=project)
    messages = [a.message for a in advisories]
    assert any("orphaned" in m and "missing-slug" in m for m in messages)


def test_orphaned_override_skipped_for_globs(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        '{"extensions": ["status-*"]}', encoding="utf-8"
    )
    project.mkdir()

    advisories = audit_pi(home=home, project_root=project)
    assert not any("orphaned" in a.message for a in advisories)


def test_orphaned_override_skipped_when_dir_present(tmp_path: Path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    (home / ".pi/agent/extensions/status-bar").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        '{"extensions": ["!status-bar"]}', encoding="utf-8"
    )
    project.mkdir()

    advisories = audit_pi(home=home, project_root=project)
    assert not any("orphaned" in a.message for a in advisories)
```

If `audit_pi` isn't already imported in this test module, add: `from agent_toolkit_cli.doctor.pi_advisories import audit_pi`.

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_doctor_pi_advisories.py -v -k orphaned`
Expected: FAIL — the orphaned-override message isn't produced yet.

- [ ] **Step 4: Add the advisory function**

Edit `src/agent_toolkit_cli/doctor/pi_advisories.py`. Add this import near the others:

```python
from agent_toolkit_cli._pi_settings import read_extensions_overrides, read_packages
```

Add the new check:

```python
def _orphaned_overrides(pp: PiPaths) -> list[PiAdvisory]:
    """Warn when an `extensions[]` entry targets a slug that doesn't exist.

    Globs (`*` / `?`) are exempt — too easy to false-positive against a
    well-intentioned wildcard like `status-*`.
    """
    out: list[PiAdvisory] = []
    for scope, ext_dir, settings_path in (
        ("user", pp.user_extensions_dir, pp.user_settings_json),
        ("project", pp.project_extensions_dir, pp.project_settings_json),
    ):
        overrides = read_extensions_overrides(settings_path)
        if not overrides:
            continue
        known = (
            {p.name for p in ext_dir.iterdir() if p.is_dir() or p.is_symlink()}
            if ext_dir.is_dir()
            else set()
        )
        for entry in overrides:
            bare = entry
            for prefix in ("!", "+", "-"):
                if bare.startswith(prefix):
                    bare = bare[1:]
                    break
            if "*" in bare or "?" in bare:
                continue
            if bare in known:
                continue
            out.append(
                PiAdvisory(
                    level="warn",
                    message=(
                        f"orphaned settings.json extensions[] override "
                        f"{entry!r} ({scope}) — no auto-discovered extension "
                        f"with that name. Remove the entry from {settings_path}."
                    ),
                )
            )
    return out
```

Wire it into `audit_pi`:

```python
def audit_pi(*, home: Path, project_root: Path) -> list[PiAdvisory]:
    pp = PiPaths(home=home, project_root=project_root)
    out: list[PiAdvisory] = []
    out.extend(_hand_authored(pp))

    user_allow = read_allowlist(home / ".agent-toolkit.yaml")
    declared_packages = list(user_allow.get("pi_packages", []))
    first_party = list(user_allow.get("pi_extensions", []))

    out.extend(_drift(pp, declared_packages=declared_packages))
    out.extend(
        _slug_collisions(first_party=first_party, declared_packages=declared_packages)
    )
    out.extend(_orphaned_overrides(pp))
    return out
```

- [ ] **Step 5: Run tests to verify**

Run: `uv run pytest tests/test_doctor_pi_advisories.py -v`
Expected: all passed.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/doctor/pi_advisories.py tests/test_doctor_pi_advisories.py
git commit -m "feat(doctor): advisory for orphaned settings.json extensions[] overrides"
```

---

## Task 6: Full test suite + lint

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -x`
Expected: all passed.

- [ ] **Step 2: Run lint**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 3: Run typecheck**

Run: `uv run mypy src` (skip if not configured for strict mode in this repo — check `pyproject.toml` first).
Expected: no errors introduced.

- [ ] **Step 4: If any failed — fix and re-run**

Plan failure mode: if a previous task's mock/fixture didn't update existing tests for the new kwargs, fix here. Do not paper over; if a real bug surfaces, fix at root.

---

## Self-review

**Spec coverage:**
- §3.1 default-enabled when no overrides → Task 3 `test_first_party_default_enabled_no_overrides`.
- §3.2 `!slug` disables → Task 3 `test_first_party_disabled_by_bang_override`.
- §3.3 orphaned `+slug` advisory → Task 5 `test_orphaned_override_advisory`.
- §3.4 plain include-filter semantics → Task 1 `test_plain_include_filter_enables_only_listed`.
- §3.5 TUI dimming → Task 4 `test_pi_tab_disabled_glyph_for_loaded_but_disabled`.
- §3.6 third-party unaffected → Task 3 `test_third_party_always_enabled`.

**Placeholder scan:** no TBDs, all code blocks complete.

**Type consistency:** `is_enabled(slug=..., overrides=...)` signature is used the same way in `_pi_inventory.py` and `_pi_overrides.py` test. `read_extensions_overrides(path)` signature is consistent across reader, CLI wire-up, and doctor.

**Risk: existing inventory tests breaking.** The new `build_pi_inventory` kwargs default to `None`/`[]`, so existing tests keep passing without modification. Verified by Task 3 Step 2 expected outcome.
