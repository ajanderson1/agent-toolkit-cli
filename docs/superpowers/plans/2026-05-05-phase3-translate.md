# Phase 3 — `translate` projection mechanism Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-05-05-phase3-translate-design.md`

**Goal:** Add a fourth projection mechanism (`translate`) so the CLI can render per-harness flavored markdown into a per-scope cache, then symlink the harness slot to the cache. Wire up `(opencode, agent)` and `(opencode, command)` cells.

**Architecture:** Flat dispatch dict (`TRANSLATORS: dict[(harness, kind), Callable]`) consulted inside `maybe_link`. When a translator exists, render bytes → write cache atomically → symlink slot to cache. On `unlink`, when the slot's symlink target is inside `<scope>/.agent-toolkit-cache/`, delete the cache file alongside the slot symlink. Translator output is native top-level keys (`description`, `mode: subagent`) plus a nested `agent_toolkit_cli:` block preserving the SSOT wrapper.

**Tech Stack:** Python 3.13, Click 8.x, PyYAML, pytest, lefthook (pytest + schema-vendor-check pre-commit). No new dependencies.

---

## Cross-cutting context (read once before starting)

**Existing behavior to preserve:**

- `_link_lib.maybe_link` (current `src/agent_toolkit_cli/commands/_link_lib.py:150-195`) creates a symlink named `target_dir / slug` (no extension) pointing at the source asset path computed by `_expected_source(asset_path, kind)`. This works for Claude (slot `~/.claude/agents/<slug>` symlinks to source `<slug>.md`) because Claude reads through the symlink. The translator path will need to **diverge from this convention** — see CC1 below.
- `_link_lib._asset_harnesses(asset_path, kind)` resolves what harnesses an asset declares; this gates whether `maybe_link` proceeds at all. Translators must run AFTER this gate, never before.
- Counters (`created`/`updated`/`unchanged`/`would_link`/`would_unlink`/`removed`) are incremented based on symlink-equality checks. The translator path must keep these correct.
- `_PROJECT_TARGETS` in `_support.py` uses `.opencode/skills` (no `.config/`) for project-scope OpenCode. Project-scope cache must follow the same rule.

### CC1 — slot filename extensions (NEW finding from spec review)

Empirical observation:
- Claude agent slots: `~/.claude/agents/<slug>` (no `.md` extension).
- OpenCode agent slots: `~/.config/opencode/agents/<slug>.md` (WITH `.md`).
- Same pattern for commands: Claude `<slug>` vs OpenCode `<slug>.md`.

The existing `maybe_link` produces `target_dir / slug` for everyone. Phase 3 must extend this so translated cells produce `target_dir / "<slug>.md"`. The cache file MUST also be `<slug>.md` so the symlink and cache filenames match what OpenCode reads from disk.

This is captured in CC1 and explicitly handled in T3 (see below).

### CC2 — cache path layout (per spec D1)

| Scope | Cache root | Example |
|---|---|---|
| user | `~/.config/opencode/.agent-toolkit-cache/` | `~/.config/opencode/.agent-toolkit-cache/agent/foo.md` |
| project | `<project>/.opencode/.agent-toolkit-cache/` | `<project>/.opencode/.agent-toolkit-cache/command/bar.md` |

Subdirectory by kind, then `<slug>.md`. Note: project-scope drops the `.config/` (matches existing `_PROJECT_TARGETS` convention).

### CC3 — frontmatter rendering invariants

- Use `yaml.safe_dump(..., sort_keys=False, default_flow_style=False)` to ensure stable, human-readable output.
- Wrap output as `---\n<yaml>---\n<body>` — body comes from the source asset with its own frontmatter stripped.
- Body extraction: reuse the existing `walker._strip_frontmatter` (private, lives in `src/agent_toolkit_cli/walker.py:164`). It handles `\r\n` normalisation and tolerates absent frontmatter. Re-export it as `strip_frontmatter` from walker for translator use.
- The output bytes MUST be byte-identical when rendered twice from the same input (round-trip stability) — this is what makes the `unchanged` symlink-equality check work.
- Trailing newline: the body extracted by `_strip_frontmatter` already ends with whatever the source ended with. Don't add a second `\n`. Just concatenate.

### CC4 — module placement

Translator module: `src/agent_toolkit_cli/_translators.py` (leading underscore = internal-to-the-package). The `TRANSLATORS` symbol is the public surface within the package; tests and `_link_lib` import it directly.

---

## File structure

**New files:**

- `src/agent_toolkit_cli/_translators.py` — `TRANSLATORS` dict, two translator functions, one private render helper.
- `tests/test_translators.py` — unit tests for translator output and round-trip stability.

**Modified files:**

- `src/agent_toolkit_cli/walker.py` — re-export `_strip_frontmatter` as `strip_frontmatter` (one-line alias).
- `src/agent_toolkit_cli/commands/_link_lib.py` — add `_render_to_cache`, `_translated_slot_filename`, `_prune_translated_slot`; modify `maybe_link` to dispatch through `TRANSLATORS`.
- `src/agent_toolkit_cli/commands/unlink.py` — call `_prune_translated_slot` for slots whose symlink target is inside the per-scope cache.
- `docs/agent-toolkit/harness-matrix.md` — flip `(opencode, agent)` and `(opencode, command)` cells to `translate`; add Translation subsection under Mechanisms.
- `tests/test_harness_matrix.py` — add `TestTranslateParity` class.

**Unchanged (verified):** `_support.py`, `harness_adapters/`, `schema.py`, schema JSON, all other commands and tests.

---

## Branch & worktree

Already set up: worktree at `~/GitHub/projects/agent-toolkit-cli/.worktrees/phase3-translate-1777983146/`, branch `feat/phase3-translate-1777983146`. Spec already committed there as `25e2b5d`. All tasks below run inside that worktree.

```bash
cd ~/GitHub/projects/agent-toolkit-cli/.worktrees/phase3-translate-1777983146/
uv sync --all-extras   # ensure TUI extras are installed so pytest collects cleanly
```

---

## Task list

### Task 1: Re-export `strip_frontmatter` from walker (prep)

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py:164`

This is a tiny prep step: the translator module needs to extract markdown body from a source asset. The walker already has `_strip_frontmatter`; we just expose it as a public name.

- [ ] **Step 1: Read the existing helper**

```bash
grep -n "_strip_frontmatter" src/agent_toolkit_cli/walker.py
```

Confirm it's at line 164 with signature `def _strip_frontmatter(text: str) -> str:`.

- [ ] **Step 2: Add the alias just above it**

In `src/agent_toolkit_cli/walker.py`, immediately before the `def _strip_frontmatter(...)` definition (around line 163), add:

```python
def strip_frontmatter(text: str) -> str:
    """Public alias for `_strip_frontmatter` — return the markdown body
    of a frontmatter-bearing document (or the whole text if no frontmatter).
    """
    return _strip_frontmatter(text)
```

- [ ] **Step 3: Run the existing walker tests**

```bash
uv run pytest tests/test_walker.py -q
```

Expected: green, same count as before.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_cli/walker.py
git commit -m "refactor(walker): expose strip_frontmatter as public helper"
```

---

### Task 2: Failing test for `_translate_opencode_agent`

**Files:**
- Create: `tests/test_translators.py`

Drive the translator function from a test that asserts the required output shape. This is the "red" of TDD.

- [ ] **Step 1: Write the failing test**

Create `tests/test_translators.py`:

```python
"""Unit tests for translator functions in agent_toolkit_cli._translators."""
from __future__ import annotations

import yaml

from agent_toolkit_cli._translators import TRANSLATORS, _translate_opencode_agent
from agent_toolkit_cli.walker import Asset, AssetRecord


def _make_record(slug: str, description: str, harnesses: list[str]) -> AssetRecord:
    """Build an AssetRecord with a minimal valid v1alpha2 metadata dict."""
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": slug,
            "description": description,
            "lifecycle": "stable",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": harnesses,
        },
    }
    asset = Asset(kind="agent", slug=slug, path=__import__("pathlib").Path(f"/fake/agents/{slug}.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_opencode_agent_emits_required_native_keys():
    record = _make_record("foo", "Foo agent — does foo things.", ["claude", "opencode"])
    body = "# Foo agent\n\nBody content.\n"

    out = _translate_opencode_agent(record, body)

    assert isinstance(out, bytes)
    text = out.decode("utf-8")
    assert text.startswith("---\n")
    end_idx = text.find("\n---\n", 4)
    assert end_idx != -1, "frontmatter missing closing fence"
    fm = yaml.safe_load(text[4:end_idx])

    assert fm["description"] == "Foo agent — does foo things."
    assert fm["mode"] == "subagent"


def test_translate_opencode_agent_preserves_wrapper_under_agent_toolkit_key():
    record = _make_record("foo", "desc", ["claude", "opencode"])
    out = _translate_opencode_agent(record, "")
    text = out.decode("utf-8")
    end_idx = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end_idx])

    assert fm["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"
    assert fm["agent_toolkit_cli"]["metadata"]["name"] == "foo"
    assert fm["agent_toolkit_cli"]["spec"]["harnesses"] == ["claude", "opencode"]


def test_translate_opencode_agent_appends_body():
    record = _make_record("foo", "desc", ["opencode"])
    body = "# Heading\n\nParagraph.\n"
    out = _translate_opencode_agent(record, body)
    text = out.decode("utf-8")
    # Body must appear after the closing fence
    closing_fence_at = text.find("\n---\n", 4)
    after = text[closing_fence_at + len("\n---\n"):]
    assert after == body


def test_translate_opencode_agent_round_trip_stable():
    record = _make_record("foo", "desc", ["opencode"])
    body = "Body.\n"
    a = _translate_opencode_agent(record, body)
    b = _translate_opencode_agent(record, body)
    assert a == b


def test_translators_dict_has_opencode_agent_entry():
    assert ("opencode", "agent") in TRANSLATORS
    assert TRANSLATORS[("opencode", "agent")] is _translate_opencode_agent
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_translators.py -x -q
```

Expected: collection error or 5 failures — `agent_toolkit_cli._translators` doesn't exist yet.

---

### Task 3: Minimal `_translators.py` with the agent translator (green)

**Files:**
- Create: `src/agent_toolkit_cli/_translators.py`

- [ ] **Step 1: Write the minimal implementation**

Create `src/agent_toolkit_cli/_translators.py`:

```python
"""Per-(harness, kind) translators producing harness-flavored markdown bytes.

A translator is a pure function `(record, body) -> bytes` consulted by
`commands/_link_lib.maybe_link` when projecting an asset into a harness
whose runtime frontmatter shape differs from the toolkit's wrapper.

The output is written to a per-scope cache directory; the harness slot
symlink targets the cache file. See
`docs/superpowers/specs/2026-05-05-phase3-translate-design.md`.
"""
from __future__ import annotations

from typing import Callable

import yaml

from agent_toolkit_cli.walker import AssetRecord


def _render(frontmatter: dict, body: str) -> bytes:
    """Compose `---\\n<yaml>---\\n<body>` and return UTF-8 bytes.

    `yaml.safe_dump(..., sort_keys=False)` is required so the key order in
    the output is stable across Python versions and matches the order we
    constructed the dict in.
    """
    fm_text = yaml.safe_dump(
        frontmatter, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    return f"---\n{fm_text}---\n{body}".encode("utf-8")


def _wrapper_block(record: AssetRecord) -> dict:
    """Verbatim subset of the source frontmatter, preserved under `agent_toolkit_cli:`."""
    md = record.metadata
    block: dict = {"apiVersion": md.get("apiVersion")}
    if "metadata" in md:
        block["metadata"] = md["metadata"]
    if "spec" in md:
        block["spec"] = md["spec"]
    return block


def _description(record: AssetRecord) -> str:
    return (record.metadata.get("metadata") or {}).get("description") or ""


def _translate_opencode_agent(record: AssetRecord, body: str) -> bytes:
    fm = {
        "description": _description(record),
        "mode": "subagent",
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)


TRANSLATORS: dict[tuple[str, str], Callable[[AssetRecord, str], bytes]] = {
    ("opencode", "agent"): _translate_opencode_agent,
}
```

- [ ] **Step 2: Run the test to verify it passes**

```bash
uv run pytest tests/test_translators.py -x -q
```

Expected: 5 passes.

- [ ] **Step 3: Commit**

```bash
git add src/agent_toolkit_cli/_translators.py tests/test_translators.py
git commit -m "feat(translators): add opencode agent translator (red→green)"
```

---

### Task 4: Failing test for `_translate_opencode_command`

**Files:**
- Modify: `tests/test_translators.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_translators.py`:

```python
from agent_toolkit_cli._translators import _translate_opencode_command


def _make_command_record(slug: str, description: str) -> AssetRecord:
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": slug,
            "description": description,
            "lifecycle": "stable",
        },
        "spec": {"origin": "first-party", "vendored_via": "none", "harnesses": ["opencode"]},
    }
    asset = Asset(kind="command", slug=slug, path=__import__("pathlib").Path(f"/fake/commands/{slug}.md"))
    return AssetRecord(asset=asset, metadata=metadata, body_excerpt="", requires={})


def test_translate_opencode_command_has_description_and_no_mode():
    record = _make_command_record("explain", "Explain something.")
    out = _translate_opencode_command(record, "Body.\n")
    text = out.decode("utf-8")
    end_idx = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end_idx])
    assert fm["description"] == "Explain something."
    assert "mode" not in fm
    assert fm["agent_toolkit_cli"]["metadata"]["name"] == "explain"


def test_translate_opencode_command_round_trip_stable():
    record = _make_command_record("explain", "desc")
    a = _translate_opencode_command(record, "x")
    b = _translate_opencode_command(record, "x")
    assert a == b


def test_translators_dict_has_opencode_command_entry():
    assert ("opencode", "command") in TRANSLATORS
    assert TRANSLATORS[("opencode", "command")] is _translate_opencode_command
```

- [ ] **Step 2: Run to verify red**

```bash
uv run pytest tests/test_translators.py -x -q
```

Expected: 3 failures (`_translate_opencode_command` not defined, key not in `TRANSLATORS`).

---

### Task 5: Implement `_translate_opencode_command` (green)

**Files:**
- Modify: `src/agent_toolkit_cli/_translators.py`

- [ ] **Step 1: Add the function**

In `src/agent_toolkit_cli/_translators.py`, add **before** the `TRANSLATORS` definition:

```python
def _translate_opencode_command(record: AssetRecord, body: str) -> bytes:
    fm = {
        "description": _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)
```

Then update the `TRANSLATORS` dict to include the new entry:

```python
TRANSLATORS: dict[tuple[str, str], Callable[[AssetRecord, str], bytes]] = {
    ("opencode", "agent"): _translate_opencode_agent,
    ("opencode", "command"): _translate_opencode_command,
}
```

- [ ] **Step 2: Run all translator tests**

```bash
uv run pytest tests/test_translators.py -x -q
```

Expected: 8 passes (5 from Task 3 + 3 from Task 4).

- [ ] **Step 3: Commit**

```bash
git add src/agent_toolkit_cli/_translators.py tests/test_translators.py
git commit -m "feat(translators): add opencode command translator"
```

---

### Task 6: Smoke test — render every shipping opencode-eligible asset

**Files:**
- Modify: `tests/test_translators.py`

This catches metadata-shape bugs against real toolkit content. It currently has zero matching assets (no opencode is in any agent's `harnesses` yet), but the test is structured so it activates automatically once the post-Phase-3 sweep adds them. For now it asserts "no matching assets" is fine.

- [ ] **Step 1: Add the smoke test**

Append to `tests/test_translators.py`:

```python
import pytest

from agent_toolkit_cli._repo_resolution import resolve_toolkit_root
from agent_toolkit_cli.walker import discover_assets, load_asset_record, strip_frontmatter


@pytest.mark.parametrize("kind,harness", [("agent", "opencode"), ("command", "opencode")])
def test_translator_renders_every_shipping_eligible_asset(kind: str, harness: str):
    """For each (harness, kind) the translator handles, render every shipping
    asset in the toolkit repo whose `spec.harnesses` includes the harness.
    Asserts the output parses as YAML frontmatter + body. Catches
    metadata-shape bugs against real assets. Skips with no error if no
    matching assets exist (expected pre-sweep)."""
    toolkit_root = resolve_toolkit_root(explicit=None)
    translator = TRANSLATORS[(harness, kind)]

    matching_assets = []
    for asset in discover_assets(toolkit_root):
        if asset.kind != kind:
            continue
        record = load_asset_record(asset)
        harnesses = ((record.metadata.get("spec") or {}).get("harnesses") or [])
        if harness not in harnesses:
            continue
        matching_assets.append((asset, record))

    if not matching_assets:
        pytest.skip(f"no shipping {kind}s declare {harness} yet (pre-sweep)")

    for asset, record in matching_assets:
        text = asset.path.read_text(encoding="utf-8")
        body = strip_frontmatter(text)
        out = translator(record, body)
        out_text = out.decode("utf-8")
        # Frontmatter parses
        end_idx = out_text.find("\n---\n", 4)
        assert end_idx != -1, f"{asset.slug}: missing closing fence"
        fm = yaml.safe_load(out_text[4:end_idx])
        assert isinstance(fm, dict)
        assert "description" in fm
```

- [ ] **Step 2: Run the smoke test**

```bash
uv run pytest tests/test_translators.py::test_translator_renders_every_shipping_eligible_asset -v
```

Expected: both parametrizations skip with the "pre-sweep" message.

- [ ] **Step 3: Commit**

```bash
git add tests/test_translators.py
git commit -m "test(translators): add shipping-asset smoke test (skips pre-sweep)"
```

---

### Task 7: Failing integration test — link translates an opencode agent

**Files:**
- Modify: `tests/test_link.py` (or whichever test file currently covers `link` — verify by `ls tests/test_link*` and `grep -l 'def test_.*link' tests/`)

This test stages a real toolkit fixture, runs `link`, and asserts both the cache file and the slot symlink end up correct.

- [ ] **Step 1: Find existing link tests and the fixture pattern**

```bash
ls tests/test_link*
grep -l 'project_from_file\|invoke.*"link"' tests/*.py
```

Read whatever test file covers link end-to-end (most likely `tests/test_link.py` or `tests/test_link_lib.py`). Identify the existing fixture that builds a fake toolkit + HOME.

- [ ] **Step 2: Add the failing test**

In the appropriate test file, add (adapt fixture names to whatever's already there — read the file first):

```python
def test_link_user_opencode_agent_translates_and_symlinks(tmp_path, monkeypatch):
    """A toolkit asset declaring `harnesses: [opencode]` projects via the
    translate mechanism: cache file written under the per-scope cache,
    slot symlink targets the cache."""
    # Build a minimal toolkit with one agent that declares opencode.
    toolkit_root = tmp_path / "toolkit"
    (toolkit_root / "agents").mkdir(parents=True)
    asset_path = toolkit_root / "agents" / "foo.md"
    asset_path.write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: foo\n"
        "  description: Foo description.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [opencode]\n"
        "---\n"
        "# Foo agent body\n",
        encoding="utf-8",
    )

    # Per-user HOME with allowlist.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    allowlist = home / ".agent-toolkit.yaml"
    allowlist.write_text("[agents]\nfoo\n", encoding="utf-8")

    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main

    runner = CliRunner()
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit_root), "link", "user", "opencode"]
    )
    assert result.exit_code == 0, result.output

    slot = home / ".config" / "opencode" / "agents" / "foo.md"
    cache = home / ".config" / "opencode" / ".agent-toolkit-cache" / "agent" / "foo.md"
    assert slot.is_symlink(), "slot symlink should exist"
    import os
    assert Path(os.readlink(slot)) == cache, "slot must point at the cache file"
    assert cache.is_file(), "cache file must exist"

    text = cache.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "mode: subagent\n" in text
    assert "description: Foo description." in text
    assert "agent_toolkit_cli:" in text
    assert text.endswith("# Foo agent body\n")
```

Adapt allowlist file format / location to whatever the existing tests use — the snippet above assumes user-scope allowlist at `$HOME/.agent-toolkit.yaml`, which matches `_allowlist.py`. Check first.

- [ ] **Step 3: Run to verify red**

```bash
uv run pytest tests/test_link.py::test_link_user_opencode_agent_translates_and_symlinks -x -v
```

Expected: failure — `(opencode, agent)` is currently `unsupported (gap)`, so `maybe_link` raises `UnsupportedPair` (or `link` exits non-zero before reaching the translator).

---

### Task 8: Wire translation into `_support.py` and `maybe_link`

**Files:**
- Modify: `src/agent_toolkit_cli/_support.py:23-46`
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py:150-195`

This is the largest task. It does three things in one logical step (they're tightly coupled — splitting them creates an inconsistent intermediate state):

1. Add `(opencode, agent)` and `(opencode, command)` to `_USER_TARGETS` and `_PROJECT_TARGETS` so `is_supported` returns True.
2. Add `_render_to_cache` and `_translated_slot_filename` helpers in `_link_lib`.
3. Modify `maybe_link` to dispatch through `TRANSLATORS` when applicable.

- [ ] **Step 1: Update `_support.py` target tables**

Add to `_USER_TARGETS`:

```python
    ("opencode", "agent"):     "{home}/.config/opencode/agents",
    ("opencode", "command"):   "{home}/.config/opencode/commands",
```

Add to `_PROJECT_TARGETS`:

```python
    ("opencode", "agent"):     ".opencode/agents",
    ("opencode", "command"):   ".opencode/commands",
```

These additions place the translated slots into `SUPPORTED_PAIRS`, which `maybe_link` checks via `is_supported`.

- [ ] **Step 2: Add helpers to `_link_lib.py`**

Near the top of `src/agent_toolkit_cli/commands/_link_lib.py`, after the existing imports and `HARNESS_HOMES` constant, add:

```python
from agent_toolkit_cli._translators import TRANSLATORS
from agent_toolkit_cli.walker import load_asset_record, strip_frontmatter


CACHE_DIR_NAME = ".agent-toolkit-cache"


def _scope_cache_root(harness: str, scope: str, project_root: Path) -> Path:
    """Return the per-scope cache root for a harness.

    user scope:    $HOME/<harness-home>/<CACHE_DIR_NAME>/
    project scope: <project_root>/<harness-home>/<CACHE_DIR_NAME>/

    where harness-home is `.config/opencode` for user opencode but `.opencode`
    for project opencode (matches the slot path conventions in _support.py).
    """
    if harness != "opencode":
        # No other harness has a translate cell yet; defensively raise.
        raise ValueError(f"no cache layout defined for harness {harness!r}")
    if scope == "user":
        home = Path(os.environ.get("HOME", ""))
        return home / ".config" / "opencode" / CACHE_DIR_NAME
    return project_root / ".opencode" / CACHE_DIR_NAME


def _translated_slot_filename(slug: str, kind: str, harness: str) -> str:
    """Return the filename used for the slot symlink in this (harness, kind).

    OpenCode requires `.md` extension on agent and command slot files; Claude
    does not. Today only opencode has translate cells, so this is `<slug>.md`."""
    if harness == "opencode" and kind in {"agent", "command"}:
        return f"{slug}.md"
    return slug


def _render_to_cache(
    *,
    harness: str,
    kind: str,
    slug: str,
    asset_path: Path,
    scope: str,
    project_root: Path,
    dry_run: bool,
) -> tuple[Path, bytes]:
    """Render translated bytes for an asset and return the (cache_path, bytes).

    In dry_run, computes bytes in-memory and returns the would-be cache path
    without writing. Out of dry_run, writes the bytes atomically (tmp+rename),
    creating parent directories as needed.

    Raises if `(harness, kind)` has no translator.
    """
    translator = TRANSLATORS.get((harness, kind))
    if translator is None:
        raise RuntimeError(
            f"no translator registered for ({harness!r}, {kind!r}) — "
            "_render_to_cache should not be called for non-translated cells"
        )
    record = load_asset_record(_asset_for_record(asset_path, kind, slug))
    text = asset_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    body = strip_frontmatter(text)
    rendered = translator(record, body)

    cache_dir = _scope_cache_root(harness, scope, project_root) / kind
    cache_path = cache_dir / f"{slug}.md"
    if not dry_run:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
        tmp.write_bytes(rendered)
        tmp.replace(cache_path)
    return cache_path, rendered


def _asset_for_record(asset_path: Path, kind: str, slug: str) -> Asset:
    """Construct the lightweight Asset object load_asset_record expects."""
    return Asset(kind=kind, slug=slug, path=asset_path)
```

(The `Asset` import is already present at the existing `from agent_toolkit_cli.walker import Asset, AssetRecord, ...` line.)

- [ ] **Step 3: Modify `maybe_link` to dispatch through `TRANSLATORS`**

Replace the body of `maybe_link` (currently at `_link_lib.py:150-195`) with:

```python
def maybe_link(
    *,
    harness: str,
    kind: str,
    slug: str,
    asset_path: Path,
    target_dir: Path,
    toolkit_root: Path,
    dry_run: bool,
    counters: LinkCounters,
    stdout: IO[str],
    scope: str = "user",
    project_root: Path | None = None,
) -> None:
    """Create/replace/skip a symlink for one asset; update counters.

    For (harness, kind) pairs in TRANSLATORS, render to a per-scope cache
    file and point the slot symlink at the cache. Otherwise symlink the
    slot directly to the asset source.
    """
    if not is_supported(harness, kind):
        raise UnsupportedPair(harness, kind)

    declared = _asset_harnesses(asset_path, kind)
    is_translated = (harness, kind) in TRANSLATORS
    slot_filename = _translated_slot_filename(slug, kind, harness) if is_translated else slug
    link_path = target_dir / slot_filename

    if harness not in declared:
        if link_path.is_symlink():
            if dry_run:
                print(f"would-unlink: {link_path}", file=stdout)
                counters.would_unlink += 1
            else:
                link_path.unlink()
                counters.removed += 1
        return

    if is_translated:
        if project_root is None:
            project_root = Path.cwd()
        cache_path, rendered = _render_to_cache(
            harness=harness, kind=kind, slug=slug,
            asset_path=asset_path, scope=scope,
            project_root=project_root, dry_run=dry_run,
        )
        source_path = cache_path
        # Cache-staleness rule: if the cache exists and its bytes match the
        # rendered output, AND the slot symlink already points at the cache,
        # this is unchanged. Any drift counts as updated.
        cache_in_sync = cache_path.is_file() and cache_path.read_bytes() == rendered if cache_path.exists() else False
        slot_correct = link_path.is_symlink() and Path(os.readlink(link_path)) == cache_path
        if slot_correct and cache_in_sync:
            counters.unchanged += 1
            return
        if dry_run:
            rel_asset = _relative_to_toolkit(asset_path, toolkit_root)
            print(
                f"would-link: {link_path} -> {cache_path} (translated from {rel_asset})",
                file=stdout,
            )
            counters.would_link += 1
            return
    else:
        source_path = _expected_source(asset_path, kind)
        if link_path.is_symlink() and Path(os.readlink(link_path)) == source_path:
            counters.unchanged += 1
            return
        if dry_run:
            print(f"would-link: {link_path} -> {source_path}", file=stdout)
            counters.would_link += 1
            return

    if link_path.is_symlink() or link_path.exists():
        link_path.unlink()
        counters.updated += 1
    else:
        counters.created += 1
    link_path.symlink_to(source_path)
```

Add the `_relative_to_toolkit` helper just below `_expected_source`:

```python
def _relative_to_toolkit(asset_path: Path, toolkit_root: Path) -> str:
    """Best-effort relative path for dry-run output. Falls back to absolute."""
    try:
        return str(asset_path.resolve().relative_to(toolkit_root.resolve()))
    except (ValueError, OSError):
        return str(asset_path)
```

- [ ] **Step 4: Update `project_from_file` to pass `scope` and `project_root` to `maybe_link`**

Find the `maybe_link(...)` call in `project_from_file` (currently `_link_lib.py:300-310`). Add `scope=scope, project_root=project_root,` to the keyword arguments:

```python
                maybe_link(
                    harness=harness,
                    kind=kind,
                    slug=asset.slug,
                    asset_path=asset.path,
                    target_dir=target_dir,
                    toolkit_root=toolkit_root,
                    dry_run=dry_run,
                    counters=counters,
                    stdout=stdout,
                    scope=scope,
                    project_root=project_root,
                )
```

- [ ] **Step 5: Run the integration test from Task 7**

```bash
uv run pytest tests/test_link.py::test_link_user_opencode_agent_translates_and_symlinks -x -v
```

Expected: green.

- [ ] **Step 6: Run the full suite**

```bash
uv run pytest -q
```

Expected: all green. If any test in `tests/test_link*.py` regressed, it's likely because it called `maybe_link` directly without the new `scope` argument — those should still work (default `scope="user"`).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/_support.py src/agent_toolkit_cli/commands/_link_lib.py tests/test_link.py
git commit -m "feat(linker): wire translate mechanism into maybe_link

Adds (opencode, agent) and (opencode, command) to _USER_TARGETS /
_PROJECT_TARGETS, plus _render_to_cache, _translated_slot_filename,
and _relative_to_toolkit helpers. maybe_link now dispatches through
TRANSLATORS, rendering bytes to a per-scope cache and pointing the
slot symlink at the cache file. Cache-staleness counts as updated."
```

---

### Task 9: Failing test — re-link with no source change is `unchanged`

**Files:**
- Modify: `tests/test_link.py`

- [ ] **Step 1: Add the test**

```python
def test_link_user_opencode_agent_idempotent(tmp_path, monkeypatch):
    """Running link twice with no source change reports `unchanged` the second
    time and does not rewrite the cache file."""
    # ... same toolkit + allowlist setup as test_link_user_opencode_agent_translates_and_symlinks ...
    # (factor into a fixture if it'll be reused N times — for now duplicate is fine)
    # First link:
    runner.invoke(main, ["--toolkit-repo", str(toolkit_root), "link", "user", "opencode"])
    cache = home / ".config" / "opencode" / ".agent-toolkit-cache" / "agent" / "foo.md"
    first_mtime = cache.stat().st_mtime
    first_bytes = cache.read_bytes()

    # Second link should be a no-op for counters and contents.
    result2 = runner.invoke(
        main, ["--toolkit-repo", str(toolkit_root), "link", "user", "opencode"]
    )
    assert result2.exit_code == 0
    assert "Already in sync" in result2.output or "already in sync" in result2.output

    assert cache.read_bytes() == first_bytes  # contents unchanged
    # mtime: tmp+rename always touches mtime when we write — only assert if we
    # changed semantics to skip rewrite-on-unchanged. (We did — _render_to_cache
    # always writes the tmp+rename. That's fine; what matters is the slot stays
    # pointing at the cache and the user-facing summary says "already in sync".)
```

Note the comment: this test asserts user-facing semantics (summary text + cache contents). It does NOT assert mtime is preserved, because `_render_to_cache` writes unconditionally. If a later optimization adds "skip rewrite on unchanged bytes" we can tighten the assertion. **YAGNI: don't add the optimization now.**

- [ ] **Step 2: Run and verify it passes**

```bash
uv run pytest tests/test_link.py::test_link_user_opencode_agent_idempotent -x -v
```

Expected: green out of the box (cache-staleness rule from Task 8 covers this case). If it fails, check the summary string the test asserts matches `format_summary` output.

- [ ] **Step 3: Commit**

```bash
git add tests/test_link.py
git commit -m "test(link): assert opencode agent link is idempotent"
```

---

### Task 10: Failing test — source change re-renders cache

**Files:**
- Modify: `tests/test_link.py`

- [ ] **Step 1: Add the test**

```python
def test_link_user_opencode_agent_updates_on_source_change(tmp_path, monkeypatch):
    """Modifying the source asset's metadata.description and re-linking
    rewrites the cache and reports updated."""
    # ... same setup ...
    # First link
    runner.invoke(main, ["--toolkit-repo", str(toolkit_root), "link", "user", "opencode"])
    cache = home / ".config" / "opencode" / ".agent-toolkit-cache" / "agent" / "foo.md"
    assert "description: Foo description." in cache.read_text()

    # Mutate source
    new_text = asset_path.read_text().replace(
        "description: Foo description.", "description: Foo (updated)."
    )
    asset_path.write_text(new_text, encoding="utf-8")

    # Re-link
    result2 = runner.invoke(
        main, ["--toolkit-repo", str(toolkit_root), "link", "user", "opencode"]
    )
    assert result2.exit_code == 0
    # Cache should now reflect the updated description
    assert "description: Foo (updated)." in cache.read_text()
```

- [ ] **Step 2: Run and verify green**

```bash
uv run pytest tests/test_link.py::test_link_user_opencode_agent_updates_on_source_change -x -v
```

Expected: green. The cache-staleness rule + always-write-on-non-unchanged in Task 8 covers this.

- [ ] **Step 3: Commit**

```bash
git add tests/test_link.py
git commit -m "test(link): assert opencode agent cache updates on source change"
```

---

### Task 11: Failing test — `link --dry-run` for translated cell

**Files:**
- Modify: `tests/test_link.py`

- [ ] **Step 1: Add the test**

```python
def test_link_dry_run_opencode_agent_prints_translated_line_no_writes(tmp_path, monkeypatch):
    """`link --dry-run` for a translate cell prints `would-link: ... (translated from ...)`
    and writes nothing to disk."""
    # ... same toolkit + allowlist setup ...
    cache_dir = home / ".config" / "opencode" / ".agent-toolkit-cache"
    slot_dir = home / ".config" / "opencode" / "agents"

    result = runner.invoke(
        main,
        ["--toolkit-repo", str(toolkit_root), "link", "user", "opencode", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "would-link:" in result.output
    assert "(translated from" in result.output
    assert "agents/foo.md" in result.output  # source path appears

    # Nothing on disk
    assert not cache_dir.exists()
    assert not slot_dir.exists() or not any(slot_dir.iterdir())
```

- [ ] **Step 2: Run and verify green**

```bash
uv run pytest tests/test_link.py::test_link_dry_run_opencode_agent_prints_translated_line_no_writes -x -v
```

Expected: green.

- [ ] **Step 3: Commit**

```bash
git add tests/test_link.py
git commit -m "test(link): dry-run for translated cell shows translation line"
```

---

### Task 12: Failing test — `unlink` removes slot AND cache

**Files:**
- Modify: `tests/test_unlink.py` (or wherever existing unlink tests live — confirm with `ls tests/test_unlink*`)

- [ ] **Step 1: Add the test**

```python
def test_unlink_user_opencode_agent_removes_slot_and_cache(tmp_path, monkeypatch):
    """Unlinking a translated agent removes both the slot symlink and the
    cache file it points at."""
    # Setup: link first, then unlink.
    # ... toolkit + allowlist setup ...
    runner.invoke(main, ["--toolkit-repo", str(toolkit_root), "link", "user", "opencode"])
    slot = home / ".config" / "opencode" / "agents" / "foo.md"
    cache = home / ".config" / "opencode" / ".agent-toolkit-cache" / "agent" / "foo.md"
    assert slot.is_symlink()
    assert cache.is_file()

    # Remove from allowlist, then unlink.
    allowlist.write_text("[agents]\n", encoding="utf-8")
    result = runner.invoke(
        main, ["--toolkit-repo", str(toolkit_root), "unlink", "user", "opencode", "agent:foo"]
    )
    assert result.exit_code == 0

    assert not slot.exists() and not slot.is_symlink(), "slot symlink should be gone"
    assert not cache.exists(), "cache file should be gone"
```

(Adapt the unlink invocation to the actual signature — read `unlink.py` to confirm `unlink user opencode agent:foo` is valid.)

- [ ] **Step 2: Run to verify red**

```bash
uv run pytest tests/test_unlink.py::test_unlink_user_opencode_agent_removes_slot_and_cache -x -v
```

Expected: failure — the slot symlink is removed but the cache file lingers.

---

### Task 13: Implement `_prune_translated_slot` and wire into unlink

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py`
- Modify: `src/agent_toolkit_cli/commands/unlink.py`

- [ ] **Step 1: Add the helper to `_link_lib.py`**

Below `_prune_if_into_repo` in `_link_lib.py`, add:

```python
def _prune_translated_slot(
    link_path: Path,
    harness: str,
    scope: str,
    project_root: Path,
    dry_run: bool,
    counters: LinkCounters,
    stdout: IO[str],
) -> bool:
    """If `link_path` is a symlink whose target is inside the per-scope
    translation cache, remove both the symlink and the cache file. Returns
    True if it acted (slot was a translated slot), False otherwise so the
    caller can fall through to other prune paths.

    Edge case: cache file already missing (manual tampering) — silently
    delete the dangling symlink and return True.
    """
    if not link_path.is_symlink():
        return False
    try:
        cache_root = _scope_cache_root(harness, scope, project_root).resolve()
    except ValueError:
        return False  # no cache layout for this harness
    target = Path(os.readlink(link_path))
    try:
        target_resolved = target.resolve()
    except (OSError, RuntimeError):
        return False
    try:
        target_resolved.relative_to(cache_root)
    except ValueError:
        return False  # target is outside our cache

    if dry_run:
        print(f"would-unlink: {link_path}", file=stdout)
        counters.would_unlink += 1
    else:
        link_path.unlink()
        if target.exists():
            target.unlink()
        counters.removed += 1
    return True
```

- [ ] **Step 2: Wire it into `project_from_file` orphan-sweep and prune paths**

In `_link_lib.py:_prune_if_into_repo`-using sites within `project_from_file` (the "remove from-allow-list" path and the "orphan symlink sweep"), replace each call with a check-translated-first-then-fall-back pattern. Find the two calls in `project_from_file` (around lines 312-322) and refactor:

```python
            else:
                slot_path = target_dir / asset.slug  # extensionless slot path
                slot_path_translated = target_dir / _translated_slot_filename(asset.slug, kind, harness)
                # Try the translated slot path first; fall back to the regular path.
                if _prune_translated_slot(
                    slot_path_translated, harness, scope, project_root,
                    dry_run, counters, stdout,
                ):
                    pass
                else:
                    _prune_if_into_repo(
                        slot_path, toolkit_root, dry_run, counters, stdout,
                    )
```

And for the orphan sweep:

```python
        if target_dir.is_dir():
            for entry in target_dir.iterdir():
                if not entry.is_symlink():
                    continue
                # discovered_slugs uses bare slugs; check both naming conventions
                bare_name = entry.name
                if bare_name in discovered_slugs:
                    continue
                # Strip a `.md` suffix to compare against bare slugs
                if bare_name.endswith(".md") and bare_name[:-3] in discovered_slugs:
                    continue
                if _prune_translated_slot(
                    entry, harness, scope, project_root,
                    dry_run, counters, stdout,
                ):
                    continue
                _prune_if_into_repo(entry, toolkit_root, dry_run, counters, stdout)
```

- [ ] **Step 3: Run the unlink integration test**

```bash
uv run pytest tests/test_unlink.py::test_unlink_user_opencode_agent_removes_slot_and_cache -x -v
```

Expected: green.

- [ ] **Step 4: Run the full suite**

```bash
uv run pytest -q
```

Expected: all green. The orphan-sweep change touches the symlink-projected path too; verify nothing regressed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py
git commit -m "feat(unlink): prune translated cache files alongside slots"
```

---

### Task 14: Update `harness-matrix.md` (flip cells + add Translation subsection)

**Files:**
- Modify: `docs/agent-toolkit/harness-matrix.md`

- [ ] **Step 1: Flip the two cells**

In the Matrix table (around line 33), change the OpenCode cells for `agent` and `command`:

Current:
```
| **agent** | symlink → `~/.claude/agents/<slug>.md` | unsupported (by design) — Codex has no `~/.codex/agents/` drop-in; agents are plugin-internal, distributed via `codex plugin marketplace add` | unsupported (gap) — slot exists at `~/.config/opencode/agents/<slug>.md` and OpenCode does register drop-ins, but our wrapper frontmatter lacks `mode: subagent` so they register as `mode: all` (primary). Phase 3 `translate` adapter will inject the mode at link time. | symlink → `~/.pi/agent/agents/<slug>.md` |
| **command** | symlink → `~/.claude/commands/<slug>.md` | unsupported (by design) — Codex has no `~/.codex/commands/`; commands surface as `$skill` invocations from inside skills | unsupported (gap) — slot exists at `~/.config/opencode/commands/<slug>.md`. OpenCode commands have a different frontmatter shape (`agent`, `model`, `subtask`, `template`) than Claude's. Phase 3 `translate` adapter will bridge. | unsupported (by design) — Pi has no command concept |
```

Replace with:
```
| **agent** | symlink → `~/.claude/agents/<slug>.md` | unsupported (by design) — Codex has no `~/.codex/agents/` drop-in; agents are plugin-internal, distributed via `codex plugin marketplace add` | translate → `~/.config/opencode/.agent-toolkit-cache/agent/<slug>.md` (slot at `~/.config/opencode/agents/<slug>.md` symlinks to cache; renderer injects `mode: subagent` and preserves wrapper under `agent_toolkit_cli:`) | symlink → `~/.pi/agent/agents/<slug>.md` |
| **command** | symlink → `~/.claude/commands/<slug>.md` | unsupported (by design) — Codex has no `~/.codex/commands/`; commands surface as `$skill` invocations from inside skills | translate → `~/.config/opencode/.agent-toolkit-cache/command/<slug>.md` (slot at `~/.config/opencode/commands/<slug>.md` symlinks to cache; renderer emits native `description` and preserves wrapper under `agent_toolkit_cli:`) | unsupported (by design) — Pi has no command concept |
```

- [ ] **Step 2: Add a Translation subsection under Mechanisms**

After the "Mechanisms" bullet list (around line 27), insert:

```markdown
### Translation cache layout

The `translate` mechanism writes flavored markdown into a per-scope cache,
then the harness slot symlinks to the cache file. Cache layout:

| Scope | Cache root |
|---|---|
| user | `~/.config/<harness>/.agent-toolkit-cache/<kind>/<slug>.md` |
| project | `<project>/.<harness>/.agent-toolkit-cache/<kind>/<slug>.md` |

The output preserves the toolkit's wrapper frontmatter under a nested
`agent_toolkit_cli:` key (with `apiVersion`, `metadata`, `spec`) for SSOT
traceability — the harness ignores this key, but `agent-toolkit` and
human readers can trace any cache file back to its source asset.

`unlink` removes both the slot symlink and its cache file together.
```

- [ ] **Step 3: Run the parity test**

```bash
uv run pytest tests/test_harness_matrix.py -x -v
```

Expected: failure — `TestSymlinkParity::test_symlink_cell_path_matches_user_target` should still pass (no symlink cell changed); but tests for "every translate cell has a translator" don't exist yet (Task 15 adds them). The existing `TestMechanismStrings` should pass — `translate` is already in `VALID_MECHANISMS`.

If anything fails unexpectedly here, investigate before proceeding.

- [ ] **Step 4: Commit**

```bash
git add docs/agent-toolkit/harness-matrix.md
git commit -m "docs(matrix): flip opencode agent/command to translate

Both cells now point at the per-scope translation cache. Adds a
Translation subsection under Mechanisms describing the cache layout
and the SSOT-traceability property."
```

---

### Task 15: Add `TestTranslateParity` class

**Files:**
- Modify: `tests/test_harness_matrix.py`

- [ ] **Step 1: Add the test class**

At the end of `tests/test_harness_matrix.py`, add:

```python
import re as _re

from agent_toolkit_cli._translators import TRANSLATORS


_TRANSLATE_PATH_RE = _re.compile(
    r"\.agent-toolkit-cache/(agent|command)/<slug>\.md\s*$"
)


class TestTranslateParity:
    def test_every_translate_cell_has_translator_entry(self, matrix):
        bad: list[tuple[str, str, str]] = []
        for (harness, kind), cell in sorted(matrix.items()):
            if _cell_mechanism(cell) != "translate":
                continue
            if (harness, kind) not in TRANSLATORS:
                bad.append((harness, kind, cell))
        assert not bad, (
            "Doc says 'translate' but TRANSLATORS has no entry:\n"
            + "\n".join(f"  ({h!r}, {k!r}): {c!r}" for h, k, c in bad)
        )

    def test_every_translator_entry_has_translate_cell(self, matrix):
        bad: list[tuple[str, str, str]] = []
        for (harness, kind) in sorted(TRANSLATORS.keys()):
            cell = matrix.get((harness, kind))
            if cell is None:
                bad.append((harness, kind, "pair not in matrix"))
                continue
            mech = _cell_mechanism(cell)
            if mech != "translate":
                bad.append((harness, kind, f"doc says {mech!r}, expected 'translate'"))
        assert not bad, (
            "TRANSLATORS has entries the doc does not mark as 'translate':\n"
            + "\n".join(f"  ({h!r}, {k!r}): {reason}" for h, k, reason in bad)
        )

    def test_translate_cell_path_matches_cache_convention(self, matrix):
        """Every `translate` cell's `→ <path>` fragment ends with the cache convention."""
        bad: list[tuple[str, str, str]] = []
        for (harness, kind), cell in sorted(matrix.items()):
            if _cell_mechanism(cell) != "translate":
                continue
            doc_path = _cell_target_path(cell)
            if doc_path is None:
                bad.append((harness, kind, f"no `→` arrow in cell: {cell!r}"))
                continue
            if not _TRANSLATE_PATH_RE.search(doc_path):
                bad.append((harness, kind, f"path does not match convention: {doc_path!r}"))
        assert not bad, (
            "Translate cell path does not match `.agent-toolkit-cache/<kind>/<slug>.md`:\n"
            + "\n".join(f"  ({h!r}, {k!r}): {reason}" for h, k, reason in bad)
        )
```

- [ ] **Step 2: Run the parity test**

```bash
uv run pytest tests/test_harness_matrix.py -x -v
```

Expected: all green, including the three new tests.

- [ ] **Step 3: Commit**

```bash
git add tests/test_harness_matrix.py
git commit -m "test(matrix): add TestTranslateParity for translate cells"
```

---

### Task 16: Run the full suite + lefthook gate

- [ ] **Step 1: Run pytest**

```bash
uv run pytest -q
```

Expected: all green. Existing 472 + ~13 new tests = ~485 passing.

- [ ] **Step 2: Verify the lefthook hook passes for a no-op commit**

This is implicitly verified by the per-task commits above (lefthook runs on every commit). If you've been letting it run, you've already confirmed pre-commit is clean.

If you want a final standalone check:

```bash
uv run agent-toolkit --toolkit-repo ~/GitHub/agent-toolkit check --exit-code
```

Expected: `OK`.

- [ ] **Step 3: Run schema-vendor-check explicitly**

```bash
diff schemas/asset-frontmatter.v1alpha2.json src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json
```

Expected: no output (schemas in sync — we didn't touch them).

---

### Task 17: Empirical verification gates (manual)

These run **after** code is green and before the toolkit-repo sweep. The PR description records the result.

- [ ] **Gate A: OpenCode agent registration**

Render a translated agent file using a real shipping agent's frontmatter, drop it in `~/.config/opencode/agents/`, run `opencode agent list`. Confirm:
- The agent appears in the list.
- The classification matches `mode: subagent` (not "primary"/"all").
- No errors or warnings about unrecognised frontmatter keys.

Quick recipe:

```bash
# From the worktree
uv run python -c "
from pathlib import Path
from agent_toolkit_cli._translators import _translate_opencode_agent
from agent_toolkit_cli.walker import Asset, AssetRecord, strip_frontmatter

src = Path('/Users/ajanderson/GitHub/agent-toolkit/agents/surface.md')
text = src.read_text()
import yaml
fm_end = text.find('\n---\n', 4)
metadata = yaml.safe_load(text[4:fm_end])
record = AssetRecord(
    asset=Asset(kind='agent', slug='surface', path=src),
    metadata=metadata,
    body_excerpt='',
    requires={},
)
body = strip_frontmatter(text)
out = _translate_opencode_agent(record, body)
target = Path.home() / '.config/opencode/agents/__phase3_probe_surface.md'
target.write_bytes(out)
print(f'wrote {target}')
"
opencode agent list
# After confirming, clean up:
rm ~/.config/opencode/agents/__phase3_probe_surface.md
```

If any error or wrong classification: STOP, document the failure, revise the spec (probably drop the nested `agent_toolkit_cli:` block per the spec's risk fallback) before proceeding.

- [ ] **Gate B: OpenCode command surfacing**

Same recipe but for a command:

```bash
uv run python -c "
from pathlib import Path
from agent_toolkit_cli._translators import _translate_opencode_command
from agent_toolkit_cli.walker import Asset, AssetRecord, strip_frontmatter

src = Path('/Users/ajanderson/GitHub/agent-toolkit/commands/explain.md')
text = src.read_text()
import yaml
fm_end = text.find('\n---\n', 4)
metadata = yaml.safe_load(text[4:fm_end])
record = AssetRecord(
    asset=Asset(kind='command', slug='explain', path=src),
    metadata=metadata,
    body_excerpt='',
    requires={},
)
body = strip_frontmatter(text)
out = _translate_opencode_command(record, body)
target = Path.home() / '.config/opencode/commands/__phase3_probe_explain.md'
target.write_bytes(out)
print(f'wrote {target}')
"
# Open opencode and check the command is surfaced (e.g. via /help). Then:
rm ~/.config/opencode/commands/__phase3_probe_explain.md
```

- [ ] **Step 3: Record results**

In the PR description, add a "Empirical verification" section summarising:
- Gate A pass/fail and what `opencode agent list` showed.
- Gate B pass/fail and how the command surfaced.

If either gate failed, the spec needs revision before merge.

---

### Task 18: Push and open PR

- [ ] **Step 1: Push the branch**

```bash
cd ~/GitHub/projects/agent-toolkit-cli/.worktrees/phase3-translate-1777983146/
git push -u origin feat/phase3-translate-1777983146
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "feat: Phase 3 — translate projection mechanism for OpenCode" \
  --body "$(cat <<'EOF'
## Summary

- Adds the fourth projection mechanism: `translate`. Generates per-harness
  flavored markdown into a per-scope cache (`<scope>/.agent-toolkit-cache/`),
  then symlinks the harness slot to the cache file.
- Wires up `(opencode, agent)` and `(opencode, command)` cells. Both flip
  from `unsupported (gap)` to `translate` in the matrix doc.
- Translator output is native top-level keys (`description`, `mode: subagent`)
  plus a nested `agent_toolkit_cli:` block preserving the SSOT wrapper.
- `unlink` removes both the slot symlink and the cache file together.
- Pi is **deferred** to a follow-up — its symlink projection remains as-is
  pending empirical verification.

## Spec

`docs/superpowers/specs/2026-05-05-phase3-translate-design.md`

## Empirical verification

- **Gate A (opencode agent registration):** [PASTE RESULT]
- **Gate B (opencode command surfacing):** [PASTE RESULT]

## Test plan

- [x] `pytest -q` green (existing + ~13 new tests)
- [x] Lefthook (pytest + schema-vendor-check) green on every commit
- [x] `agent-toolkit check --exit-code` returns OK
- [x] Manual gate A passed
- [x] Manual gate B passed

## Follow-ups (not in this PR)

- Sweep `opencode` into `spec.harnesses` for shipping agents and applicable
  commands in the toolkit repo (gated on this PR landing).
- Empirically verify Pi symlink projection.
- Consider an `agent-toolkit gc` command for stranded cache files.
EOF
)"
```

- [ ] **Step 3: Return the PR URL to the user**

---

## Self-review

**Spec coverage:**
- D1 (cache location) → Tasks 8 (`_scope_cache_root`), 13 (`_prune_translated_slot`).
- D2 (TRANSLATORS dict) → Task 3 (initial), Task 5 (command added).
- D3 (inline in `maybe_link`) → Task 8.
- D4 (cache cleanup on unlink) → Tasks 12-13.
- D5 (`check` adds nothing) → no task needed; tests/`test_translators.py` covers it.
- D6 (dry-run output) → Task 11 (test), Task 8 (implementation).
- D7 (parity test) → Task 15.
- D8 (translator output shape) → Tasks 2-5.
- AC1-AC10 → covered by Tasks 7-15.
- Empirical gates → Task 17.

**Placeholder scan:**
- "STOP, document the failure" in Gate A — that's an instruction, not a placeholder. ✓
- "[PASTE RESULT]" in PR body — is intentional, the implementer fills these post-gates. ✓
- All test code blocks contain real assertions, not "assert appropriate behavior". ✓

**Type consistency:**
- `TRANSLATORS` is consistently capitalised throughout.
- `_render_to_cache` signature: `(harness, kind, slug, asset_path, scope, project_root, dry_run) → tuple[Path, bytes]` — used the same way in Task 8 step 2 and step 3 (the `maybe_link` call site).
- `_prune_translated_slot(link_path, harness, scope, project_root, dry_run, counters, stdout) → bool` — used the same way in Task 13.
- `_translated_slot_filename(slug, kind, harness)` — same args at both call sites in `maybe_link` and the orphan sweep.

**Note for the implementing agent:** Task 8 is the riskiest task — the `maybe_link` rewrite is structural. If the test suite goes red after Step 7's commit, the most likely culprits are (a) `maybe_link` callers in tests that pass positional args (the new `scope`/`project_root` are kwargs with defaults, so positional calls should still work) or (b) a test that checks the exact text of `format_summary` output and trips on the new "(translated from ...)" line. Read the failure carefully before patching.
