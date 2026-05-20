# Skill sidecar shape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt a two-file shape for skill assets — harness-facing `SKILL.md` frontmatter (top-level `name` + `description`) plus toolkit-facing `<slug>.toolkit.yaml` sidecar (full v1alpha2 wrapper + CLI-facing `metadata.description`) — and ship the engineering side (translators, walker, check, doctor, scaffolder, one-shot `migrate-skills` command).

**Architecture:** Walker exposes two distinct descriptions on `AssetRecord` (`harness_description` from SKILL.md, `cli_description` from sidecar). Translators read `harness_description` instead of the v1alpha2 `metadata.description`. `check` enforces both descriptions present, both end with a period, names agree, sidecar mandatory for new skills. A new `migrate-skills` subcommand performs the one-time content-repo rewrite using deterministic string-templated YAML emission (no round-trip library required).

**Tech Stack:** Python 3.11, click, jsonschema, PyYAML (load-only; no comment round-trip needed), pytest. Existing module layout under `src/agent_toolkit_cli/`.

**Spec:** `docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md`

**Out of scope here:** Skill-file rewrites in `~/GitHub/agent-toolkit/` (separate follow-up PR after this lands; uses the new `migrate-skills` command).

---

## File Structure

Files created or modified by this plan, with their single responsibility:

| Status | Path | Responsibility |
|---|---|---|
| Modify | `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json` | Schema: add `spec.per_harness` (object, `additionalProperties: true`). |
| Modify | `src/agent_toolkit_cli/walker.py` | Walker: add `AssetRecord.harness_description` and `AssetRecord.cli_description`; backfill from inline frontmatter during the tolerance window. |
| Modify | `src/agent_toolkit_cli/_translators.py` | Translators: add `_translate_pi_skill`; reroute codex/opencode skill translators to read `harness_description`; register `(pi, skill)`. |
| Modify | `src/agent_toolkit_cli/commands/_link_lib.py` | Link lib: extend `_translate_slot_layout` to return `dir-with-file-symlink` for `(codex, skill)` and `(pi, skill)`. |
| Modify | `src/agent_toolkit_cli/commands/new.py` | Scaffolder: sidecar template gets CLI-facing description; body template includes SKILL.md harness frontmatter; `--inline` for `skill` exits 2. |
| Modify | `src/agent_toolkit_cli/commands/check.py` | Check: enforce SKILL.md top-level frontmatter, both descriptions present, period rule on harness description, name agreement. |
| Create | `src/agent_toolkit_cli/doctor/skill_shape.py` | Doctor: new advisory module reporting skill-shape drift. |
| Modify | `src/agent_toolkit_cli/doctor/__init__.py` | Register the new advisory module. |
| Create | `src/agent_toolkit_cli/commands/migrate_skills.py` | One-shot content-repo migration subcommand. |
| Modify | `src/agent_toolkit_cli/cli.py` | Register `migrate-skills` in the click group. |
| Create | `tests/test_translate_pi_skill.py` | Unit tests for the new pi skill translator. |
| Create | `tests/test_walker_skill_shape.py` | Unit tests for walker's two-description exposure + legacy fallback. |
| Modify | `tests/test_translators.py` (if present, else use existing per-translator test files) | Update codex/opencode skill translator tests to source from `harness_description`. |
| Create | `tests/test_check_skill_shape.py` | Unit tests for the new `check` rules. |
| Create | `tests/test_new_skill_shape.py` | Unit tests for the updated `new` command. |
| Create | `tests/test_migrate_skills.py` | Unit tests for `migrate-skills` (dry-run golden file + idempotency). |
| Create | `tests/test_link_pi_skill.py` | Integration test: link a fixture skill to pi and verify slot layout + frontmatter. |
| Create | `tests/fixtures/skills/example-new-shape/SKILL.md` | Test fixture: skill in new shape. |
| Create | `tests/fixtures/skills/example-new-shape.toolkit.yaml` | Test fixture: sidecar for the above. |

The tests sit alongside existing ones in `tests/`. If a test file with overlapping concerns already exists (`tests/test_translators.py`, `tests/test_walker.py`), append the new cases there rather than creating a parallel file — the task that creates a file checks first.

---

## Task ordering rationale

Schema first (it's pure data, no Python uses it directly until validator instantiates). Walker second (translators depend on its record shape). Translators third. Then `_link_lib` (registers the new layouts). Then `new` (uses the new schema and shape). Then `check` (validates the new rules — must come after schema, walker, and templates are correct). Doctor advisory next. Migration command last (it's a separate codepath and can be developed without breaking anything else). Each task ends with a commit so the branch is bisectable.

---

### Task 1: Schema — add `spec.per_harness`

**Files:**
- Modify: `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json`
- Test: `tests/test_schema_per_harness.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_schema_per_harness.py`:

```python
"""spec.per_harness must accept arbitrary per-harness blocks.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

import json
from importlib.resources import files

import jsonschema


def _schema():
    text = (files("agent_toolkit_cli") / "_schemas" / "asset-frontmatter.v1alpha2.json").read_text()
    return json.loads(text)


def _base_skill_doc() -> dict:
    return {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "demo",
            "description": "Concise CLI label.",
            "lifecycle": "experimental",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["claude", "pi"],
        },
    }


def test_per_harness_accepts_pi_argument_hint():
    doc = _base_skill_doc()
    doc["spec"]["per_harness"] = {"pi": {"argument_hint": "<filename>"}}
    jsonschema.validate(doc, _schema())


def test_per_harness_accepts_unknown_harness_block():
    doc = _base_skill_doc()
    doc["spec"]["per_harness"] = {"future_harness": {"any_key": "any_value"}}
    jsonschema.validate(doc, _schema())


def test_per_harness_absent_is_valid():
    doc = _base_skill_doc()
    jsonschema.validate(doc, _schema())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schema_per_harness.py -v`
Expected: FAIL — `jsonschema.ValidationError: Additional properties are not allowed ('per_harness' was unexpected)` on the first two cases.

- [ ] **Step 3: Edit the schema**

Open `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json`. In the `spec` block's `properties` (currently ends with `requires`), add a `per_harness` property *before* the closing `}` of `properties`:

```json
        "per_harness": {
          "type": "object",
          "additionalProperties": { "type": "object", "additionalProperties": true },
          "propertyNames": { "enum": ["claude", "codex", "opencode", "gemini", "pi"] }
        },
```

The exact insertion point is between the existing `requires` block and the closing `}` of the `spec.properties` object. Order does not matter to the validator but keep it adjacent to `requires` for readability.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schema_per_harness.py -v`
Expected: PASS — all three cases.

Then run the full suite to confirm nothing else regressed:

Run: `uv run pytest -q`
Expected: PASS (914+ tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json tests/test_schema_per_harness.py
git commit -m "feat(schema): allow spec.per_harness on v1alpha2

Per-harness optional blocks (e.g. spec.per_harness.pi.argument_hint)
are now schema-valid. additionalProperties: true is intentional during
the build-out window; tightening is a follow-up.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
Issue: #150"
```

---

### Task 2: Walker — expose two descriptions on `AssetRecord`

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py` (`AssetRecord` dataclass, `load_asset_record` function)
- Test: `tests/test_walker_skill_shape.py` (new)

**Context for the implementer:** The current `AssetRecord` is a frozen dataclass with fields `asset`, `metadata`, `body_excerpt`, `requires`. No `description` attribute exists today — consumers read `record.metadata["description"]` (via `(metadata.get("metadata") or {}).get("description")` because of the v1alpha2 nesting). We are adding two new optional string fields without renaming anything; legacy callers continue to work.

- [ ] **Step 1: Write the failing test**

Create `tests/test_walker_skill_shape.py`:

```python
"""AssetRecord exposes harness_description (SKILL.md) and cli_description (sidecar).

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.walker import Asset, load_asset_record


@pytest.fixture
def new_shape_skill(tmp_path: Path) -> Asset:
    root = tmp_path
    skill_dir = root / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: demo\n"
        "description: Long, trigger-rich harness-facing description ending in a period.\n"
        "---\n"
        "\nbody\n"
    )
    (root / "skills" / "demo.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: demo\n"
        "  description: Concise CLI label.\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude, pi]\n"
    )
    return Asset(kind="skill", slug="demo", path=skill_dir / "SKILL.md")


@pytest.fixture
def legacy_inline_skill(tmp_path: Path) -> Asset:
    root = tmp_path
    skill_dir = root / "skills" / "legacy"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: legacy\n"
        "  description: Legacy combined description.\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
        "\nbody\n"
    )
    return Asset(kind="skill", slug="legacy", path=skill_dir / "SKILL.md")


def test_new_shape_exposes_both_descriptions(new_shape_skill: Asset):
    record = load_asset_record(new_shape_skill)
    assert record.harness_description == (
        "Long, trigger-rich harness-facing description ending in a period."
    )
    assert record.cli_description == "Concise CLI label."


def test_legacy_inline_skill_falls_back(legacy_inline_skill: Asset):
    record = load_asset_record(legacy_inline_skill)
    # Inline-only skills have no sidecar; the legacy description fills both
    # slots so consumers keep working during the tolerance window.
    assert record.harness_description == "Legacy combined description."
    assert record.cli_description == "Legacy combined description."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_walker_skill_shape.py -v`
Expected: FAIL — `AttributeError: 'AssetRecord' object has no attribute 'harness_description'`.

- [ ] **Step 3: Edit `walker.py` — extend `AssetRecord`**

In `src/agent_toolkit_cli/walker.py`, locate the `AssetRecord` dataclass (around line 305) and add the two fields:

```python
@dataclass(frozen=True)
class AssetRecord:
    asset: Asset
    metadata: dict
    body_excerpt: str
    requires: dict[str, list[str]]
    harness_description: str | None = None  # NEW: from SKILL.md top-level frontmatter
    cli_description: str | None = None      # NEW: from sidecar metadata.description
```

Default to `None` so any non-skill code path that constructs `AssetRecord` without these fields keeps working.

- [ ] **Step 4: Edit `walker.py` — populate the new fields in `load_asset_record`**

In `load_asset_record`, the `skill | agent | command` branch currently does:

```python
fm_path = frontmatter_path(asset.path, asset.kind)
metadata = extract_metadata(fm_path) or {}
```

For `kind == "skill"`, the resolved `fm_path` is the sidecar when present. We need both files. Replace the skill-handling logic with explicit two-file resolution:

```python
if asset.kind == "skill":
    # SKILL.md may carry top-level harness frontmatter (new shape) OR
    # toolkit v1alpha2 wrapper (legacy inline shape). The sidecar, if
    # present, carries the v1alpha2 wrapper.
    sidecar = _sidecar_path("skill", asset.slug, _toolkit_root_for(asset))
    skill_md_fm = extract_metadata(asset.path) or {}
    if sidecar.is_file():
        metadata = extract_metadata(sidecar) or {}
        # SKILL.md is harness-facing in the new shape.
        harness_description = skill_md_fm.get("description")
        cli_description = (metadata.get("metadata") or {}).get("description")
    else:
        # Legacy inline shape: the v1alpha2 wrapper is in SKILL.md itself.
        metadata = skill_md_fm
        legacy_desc = (metadata.get("metadata") or {}).get("description")
        harness_description = legacy_desc
        cli_description = legacy_desc
    # Body excerpt comes from SKILL.md's body regardless of where metadata lives.
    text = asset.path.read_text(encoding="utf-8").replace("\r\n", "\n")
    body = _strip_frontmatter(text) if metadata is skill_md_fm or not sidecar.is_file() else text
    body_excerpt = _first_paragraph(body, max_chars=400)
elif asset.kind in {"agent", "command"}:
    fm_path = frontmatter_path(asset.path, asset.kind)
    metadata = extract_metadata(fm_path) or {}
    # ... existing body logic unchanged
```

Add a helper `_toolkit_root_for(asset: Asset) -> Path` near `_sidecar_path` that walks up from `asset.path` three levels (matching the existing `frontmatter_path` heuristic: `<root>/skills/<slug>/SKILL.md` → `<root>`):

```python
def _toolkit_root_for(asset: Asset) -> Path:
    """Best-effort toolkit root for an asset path.

    For skills the path is <root>/skills/<slug>/SKILL.md, so the root is
    asset.path.parent.parent.parent. Mirrors the heuristic in
    `frontmatter_path` to avoid a separate root-resolution code path.
    """
    return asset.path.parent.parent.parent
```

At the end of `load_asset_record`, return the record with the new fields:

```python
return AssetRecord(
    asset=asset,
    metadata=metadata,
    body_excerpt=body_excerpt,
    requires=requires,
    harness_description=harness_description if asset.kind == "skill" else None,
    cli_description=cli_description if asset.kind == "skill" else None,
)
```

Wrap the `harness_description` / `cli_description` locals in `try/except UnboundLocalError` or initialize them to `None` at the top of the function — pick the cleaner option for the reviewer (init at top of function is preferred). Concretely add `harness_description: str | None = None; cli_description: str | None = None` immediately after the `metadata: dict; body_excerpt: str = ""` block.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_walker_skill_shape.py -v`
Expected: PASS — both cases.

Then run the full walker suite:

Run: `uv run pytest tests/ -k walker -v`
Expected: PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/walker.py tests/test_walker_skill_shape.py
git commit -m "feat(walker): expose harness_description and cli_description on AssetRecord

New-shape skills carry harness-facing description in SKILL.md top-level
frontmatter and CLI-facing description in <slug>.toolkit.yaml. Legacy
inline-shape skills fall back: both descriptions resolve to the
v1alpha2 metadata.description verbatim.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
Issue: #150"
```

---

### Task 3: Translators — reroute codex/opencode skill, add pi skill

**Files:**
- Modify: `src/agent_toolkit_cli/_translators.py`
- Create: `tests/test_translate_pi_skill.py`
- Modify: existing translator tests (likely in `tests/test_translators.py` or `tests/test_link_translate.py` — search first)

- [ ] **Step 1: Write the failing test for `_translate_pi_skill`**

Create `tests/test_translate_pi_skill.py`:

```python
"""_translate_pi_skill emits top-level name + description + optional argument-hint.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

import yaml

from agent_toolkit_cli._translators import _translate_pi_skill
from agent_toolkit_cli.walker import Asset, AssetRecord


def _record(*, harness_description: str, per_harness: dict | None = None) -> AssetRecord:
    metadata = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "demo",
            "description": "Concise CLI label.",
            "lifecycle": "experimental",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["pi"],
            **({"per_harness": per_harness} if per_harness else {}),
        },
    }
    return AssetRecord(
        asset=Asset(kind="skill", slug="demo", path=None),  # path unused by translators
        metadata=metadata,
        body_excerpt="",
        requires={},
        harness_description=harness_description,
        cli_description="Concise CLI label.",
    )


def _parse_frontmatter(out: bytes) -> dict:
    text = out.decode("utf-8")
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    return yaml.safe_load(text[4:end])


def test_emits_top_level_name_and_description():
    record = _record(harness_description="Long harness description.")
    out = _translate_pi_skill(record, body="body\n")
    fm = _parse_frontmatter(out)
    assert fm["name"] == "demo"
    assert fm["description"] == "Long harness description."


def test_lifts_argument_hint_from_per_harness_pi():
    record = _record(
        harness_description="Long harness description.",
        per_harness={"pi": {"argument_hint": "<filename>"}},
    )
    out = _translate_pi_skill(record, body="body\n")
    fm = _parse_frontmatter(out)
    assert fm["argument-hint"] == "<filename>"


def test_omits_argument_hint_when_absent():
    record = _record(harness_description="Long harness description.")
    out = _translate_pi_skill(record, body="body\n")
    fm = _parse_frontmatter(out)
    assert "argument-hint" not in fm


def test_includes_agent_toolkit_cli_wrapper_for_traceability():
    record = _record(harness_description="Long harness description.")
    out = _translate_pi_skill(record, body="body\n")
    fm = _parse_frontmatter(out)
    assert "agent_toolkit_cli" in fm
    assert fm["agent_toolkit_cli"]["apiVersion"] == "agent-toolkit/v1alpha2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_translate_pi_skill.py -v`
Expected: FAIL — `ImportError: cannot import name '_translate_pi_skill' from 'agent_toolkit_cli._translators'`.

- [ ] **Step 3: Implement `_translate_pi_skill` and update codex/opencode skill translators**

In `src/agent_toolkit_cli/_translators.py`, just below `_translate_opencode_skill`, add:

```python
def _translate_pi_skill(record: AssetRecord, body: str) -> bytes:
    """Pi skills require `description:` at the YAML top level (per the
    `pi demands` error `description is required`). Optionally accepts
    `argument-hint:` for arg-aware skills; that field is sourced from
    `spec.per_harness.pi.argument_hint` if present on the sidecar.

    Output mirrors `_translate_opencode_skill`: top-level `name`,
    `description`, optional `argument-hint`, plus the `agent_toolkit_cli`
    wrapper for round-trip traceability.
    """
    description = record.harness_description or _description(record)
    pi_extras = ((record.metadata.get("spec") or {}).get("per_harness") or {}).get("pi") or {}
    fm: dict = {
        "name": record.asset.slug,
        "description": description,
    }
    if "argument_hint" in pi_extras:
        fm["argument-hint"] = pi_extras["argument_hint"]
    fm["agent_toolkit_cli"] = _wrapper_block(record)
    return _render(fm, body)
```

The `description = record.harness_description or _description(record)` fallback covers the tolerance window: legacy inline skills have no top-level SKILL.md description, so we read from the v1alpha2 metadata block.

Update `_translate_codex_skill` and `_translate_opencode_skill` similarly — replace `_description(record)` (which reads from v1alpha2 metadata) with `record.harness_description or _description(record)`:

```python
def _translate_codex_skill(record: AssetRecord, body: str) -> bytes:
    """... (existing docstring unchanged) ..."""
    fm = {
        "description": record.harness_description or _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)


def _translate_opencode_skill(record: AssetRecord, body: str) -> bytes:
    """... (existing docstring unchanged) ..."""
    fm = {
        "name": record.asset.slug,  # was: _name(record) — slug is the cross-harness invariant
        "description": record.harness_description or _description(record),
        "agent_toolkit_cli": _wrapper_block(record),
    }
    return _render(fm, body)
```

Register the new pi-skill translator in the `TRANSLATORS` dict at the bottom of the file:

```python
TRANSLATORS: dict[tuple[str, str], Callable[[AssetRecord, str], bytes]] = {
    ("opencode", "agent"): _translate_opencode_agent,
    ("opencode", "command"): _translate_opencode_command,
    ("codex", "agent"): _translate_codex_agent,
    ("codex", "skill"): _translate_codex_skill,
    ("opencode", "skill"): _translate_opencode_skill,
    ("pi", "skill"): _translate_pi_skill,    # NEW
    ("gemini", "command"): _translate_gemini_command,
    ("gemini", "agent"): _translate_gemini_agent,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_translate_pi_skill.py -v`
Expected: PASS — all four cases.

- [ ] **Step 5: Update existing codex/opencode skill tests**

Run: `uv run pytest tests/ -k 'codex_skill or opencode_skill' -v`

If failures appear because existing fixtures construct `AssetRecord` without `harness_description`, those tests still pass thanks to the `or _description(record)` fallback. If any fail with "argument missing", add `harness_description="..."` to the fixture's `AssetRecord(...)` call. Make these edits minimally — do not rewrite the existing tests.

Then run the full test suite:

Run: `uv run pytest -q`
Expected: PASS (no regressions).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/_translators.py tests/test_translate_pi_skill.py tests/test_translators*.py
git commit -m "feat(translators): pi skill translator + new-shape source for codex/opencode

_translate_pi_skill is new — emits top-level name/description plus an
optional argument-hint lifted from spec.per_harness.pi.argument_hint.
Codex and opencode skill translators now read harness_description with
fallback to v1alpha2 metadata.description during the tolerance window.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
Issue: #150"
```

---

### Task 4: Link lib — register `(pi, skill)` and `(codex, skill)` as dir-with-file-symlink

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py` (`_translate_slot_layout`)
- Test: `tests/test_link_pi_skill.py` (new)

- [ ] **Step 1: Read current `_translate_slot_layout`**

Open `src/agent_toolkit_cli/commands/_link_lib.py` and find `_translate_slot_layout` (around line 135). The function returns `"dir-with-file-symlink"` for harnesses whose runtime expects a directory containing the SKILL.md (currently opencode). Codex and pi need the same treatment because they now have translators.

- [ ] **Step 2: Write the failing test**

Create `tests/test_link_pi_skill.py`:

```python
"""Pi skill links via dir-with-file-symlink, just like opencode skill.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from agent_toolkit_cli.commands._link_lib import _translate_slot_layout


def test_pi_skill_uses_dir_with_file_symlink():
    assert _translate_slot_layout("pi", "skill") == "dir-with-file-symlink"


def test_codex_skill_uses_dir_with_file_symlink():
    assert _translate_slot_layout("codex", "skill") == "dir-with-file-symlink"


def test_claude_skill_unchanged():
    # Claude skills are raw symlinks (no translator).
    assert _translate_slot_layout("claude", "skill") != "dir-with-file-symlink"


def test_gemini_skill_unchanged():
    # Gemini skills are raw symlinks (no translator).
    assert _translate_slot_layout("gemini", "skill") != "dir-with-file-symlink"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_link_pi_skill.py -v`
Expected: FAIL — pi and codex assertions fail (return something other than `dir-with-file-symlink`).

- [ ] **Step 4: Edit `_translate_slot_layout`**

Find the current logic — likely an `if (harness, kind) in {(...), (...)}` block returning `"dir-with-file-symlink"`. Add `("codex", "skill")` and `("pi", "skill")` to that set. Concrete edit:

Before:
```python
def _translate_slot_layout(harness: str, kind: str) -> str:
    if (harness, kind) in {("opencode", "skill")}:
        return "dir-with-file-symlink"
    # ...
```

After:
```python
def _translate_slot_layout(harness: str, kind: str) -> str:
    if (harness, kind) in {("opencode", "skill"), ("codex", "skill"), ("pi", "skill")}:
        return "dir-with-file-symlink"
    # ...
```

If the existing code uses a different structure (e.g. a dict lookup), match that structure rather than mechanically replacing.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_link_pi_skill.py -v`
Expected: PASS — all four cases.

Run the broader link suite to confirm no regressions:

Run: `uv run pytest tests/ -k link -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py tests/test_link_pi_skill.py
git commit -m "feat(link): pi and codex skills use dir-with-file-symlink layout

Both harnesses now have skill translators, so their slot needs to be
a real directory containing the translated SKILL.md symlink rather
than a raw symlink to the source.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
Issue: #150"
```

---

### Task 5: Scaffolder — `new skill` writes new-shape SKILL.md + sidecar; remove `--inline` for skill

**Files:**
- Modify: `src/agent_toolkit_cli/commands/new.py`
- Test: `tests/test_new_skill_shape.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_new_skill_shape.py`:

```python
"""`agent-toolkit new skill <slug>` writes a SKILL.md with harness frontmatter
plus a sidecar with CLI-facing description.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from agent_toolkit_cli.cli import cli


def test_new_skill_writes_skill_md_with_harness_frontmatter(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["new", "skill", "demo", "--toolkit-root", str(tmp_path)])
    assert result.exit_code == 0, result.output

    skill_md = tmp_path / "skills" / "demo" / "SKILL.md"
    assert skill_md.is_file()
    text = skill_md.read_text()
    assert text.startswith("---\n")
    # Parse the frontmatter — must have only name + description at top level
    end = text.find("\n---\n", 4)
    fm = yaml.safe_load(text[4:end])
    assert set(fm.keys()) == {"name", "description"}
    assert fm["name"] == "demo"
    assert fm["description"].endswith(".")  # period rule


def test_new_skill_writes_sidecar_with_cli_description(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(cli, ["new", "skill", "demo", "--toolkit-root", str(tmp_path)])
    assert result.exit_code == 0, result.output

    sidecar = tmp_path / "skills" / "demo.toolkit.yaml"
    assert sidecar.is_file()
    data = yaml.safe_load(sidecar.read_text())
    assert data["apiVersion"] == "agent-toolkit/v1alpha2"
    assert data["metadata"]["name"] == "demo"
    assert data["metadata"]["description"].endswith(".")


def test_new_skill_inline_rejected(tmp_path: Path):
    runner = CliRunner()
    result = runner.invoke(
        cli, ["new", "skill", "demo", "--inline", "--toolkit-root", str(tmp_path)]
    )
    assert result.exit_code == 2, result.output
    assert "sidecar" in result.output.lower() or "inline" in result.output.lower()


def test_new_mcp_inline_still_allowed(tmp_path: Path):
    # `--inline` is removed for skills only; mcp is unaffected.
    runner = CliRunner()
    result = runner.invoke(
        cli, ["new", "mcp", "demo", "--inline", "--toolkit-root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_new_skill_shape.py -v`
Expected: FAIL — current SKILL.md template has no frontmatter; sidecar has no CLI-facing description; `--inline skill` is accepted.

- [ ] **Step 3: Edit `commands/new.py` — templates**

In `src/agent_toolkit_cli/commands/new.py`:

(a) Replace `_BODY_TEMPLATE_NO_FRONTMATTER` (used for skill body when sidecar is in play) with a version that includes harness-facing frontmatter:

```python
_SKILL_BODY_TEMPLATE = """---
name: {slug}
description: TODO write the harness-loader-facing description ending in a period.
---

# {slug}

TODO body.
"""
```

Keep the original `_BODY_TEMPLATE_NO_FRONTMATTER` if it is still used by the mcp path; rename the existing constant to `_MCP_BODY_TEMPLATE_NO_FRONTMATTER_SKILL_LEGACY` only if needed — easier: keep the old constant intact for mcp and introduce `_SKILL_BODY_TEMPLATE` as a new name used only by the skill branch.

(b) The `_SIDECAR_TEMPLATE` currently emits a CLI-facing `metadata.description` — confirm by reading lines 41-55. If the description placeholder is something generic (e.g. `"TODO description."`), tighten the wording to `"TODO concise CLI label ending in a period."` so the period rule is self-documenting in the scaffold.

- [ ] **Step 4: Edit `commands/new.py` — `--inline` rejection for skill**

In the `new` function (around line 97), after the args are parsed:

```python
def new(ctx: click.Context, kind: str, slug: str, toolkit_root: Path | None, inline: bool) -> None:
    if inline and kind == "skill":
        raise click.UsageError(
            "Inline frontmatter is no longer supported for skills. "
            "Skills now use a two-file shape: SKILL.md (harness frontmatter) "
            "plus <slug>.toolkit.yaml (toolkit sidecar). See "
            "docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md."
        )
    # ... existing logic
```

`click.UsageError` exits with code 2 by default, matching the test.

(c) Where the skill body is written (around line 173), switch from `_BODY_TEMPLATE_NO_FRONTMATTER` to `_SKILL_BODY_TEMPLATE`:

```python
target.write_text(_SKILL_BODY_TEMPLATE.format(slug=slug))
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_new_skill_shape.py -v`
Expected: PASS — all four cases.

- [ ] **Step 6: Run the existing `new` tests to check for regressions**

Run: `uv run pytest tests/ -k 'new' -v`
Expected: PASS. If existing tests assert the old skill body shape, update them to match the new template (they will be `tests/test_cli_new.py` or similar — search). Update fixtures only; don't widen test scope.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/new.py tests/test_new_skill_shape.py
git commit -m "feat(new): scaffold skills with two-file shape; reject --inline skill

Generated SKILL.md now carries top-level name/description harness
frontmatter, separately from the sidecar's CLI-facing description.
\`--inline\` for skill exits 2 with a pointer to the design spec.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
Issue: #150"
```

---

### Task 6: Check — enforce new-shape rules

**Files:**
- Modify: `src/agent_toolkit_cli/commands/check.py` (or wherever skill-shape validation lands)
- Modify: `src/agent_toolkit_cli/schema.py` (`Validator.validate`) to emit cross-file rules
- Test: `tests/test_check_skill_shape.py` (new)

**Design choice locked in:** the cross-file rules live in `Validator.validate` rather than `check.py`'s top-level loop, because `Validator.validate(asset)` is already the per-asset entry point and other consumers (doctor) can reuse it.

- [ ] **Step 1: Write the failing test**

Create `tests/test_check_skill_shape.py`:

```python
"""`check` enforces SKILL.md frontmatter, both descriptions, period rule, name agreement.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.schema import Validator
from agent_toolkit_cli.walker import Asset


def _write_new_shape_skill(
    root: Path,
    slug: str = "demo",
    *,
    skill_md_fm: str | None = None,
    sidecar: str | None = None,
) -> Asset:
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    default_fm = (
        "---\n"
        f"name: {slug}\n"
        "description: Long harness-facing description ending in a period.\n"
        "---\n"
    )
    (skill_dir / "SKILL.md").write_text((skill_md_fm if skill_md_fm is not None else default_fm) + "\nbody\n")
    default_sidecar = (
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        f"  name: {slug}\n"
        "  description: Concise CLI label.\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
    )
    (root / "skills" / f"{slug}.toolkit.yaml").write_text(
        sidecar if sidecar is not None else default_sidecar
    )
    return Asset(kind="skill", slug=slug, path=skill_dir / "SKILL.md")


def test_new_shape_skill_validates(tmp_path: Path):
    asset = _write_new_shape_skill(tmp_path)
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    assert errors == []


def test_skill_md_missing_frontmatter_fails(tmp_path: Path):
    asset = _write_new_shape_skill(tmp_path, skill_md_fm="")
    # Overwrite to remove frontmatter entirely
    (tmp_path / "skills" / "demo" / "SKILL.md").write_text("no frontmatter here\n")
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    assert any("SKILL.md" in e and "frontmatter" in e for e in errors), errors


def test_harness_description_missing_period_fails(tmp_path: Path):
    fm = (
        "---\n"
        "name: demo\n"
        "description: No trailing period\n"
        "---\n"
    )
    asset = _write_new_shape_skill(tmp_path, skill_md_fm=fm)
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    assert any("description" in e and "period" in e.lower() for e in errors), errors


def test_name_disagreement_fails(tmp_path: Path):
    fm = (
        "---\n"
        "name: not-demo\n"
        "description: Long harness description.\n"
        "---\n"
    )
    asset = _write_new_shape_skill(tmp_path, skill_md_fm=fm)
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    assert any("name" in e.lower() for e in errors), errors


def test_missing_cli_description_fails(tmp_path: Path):
    bad_sidecar = (
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: demo\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
    )
    asset = _write_new_shape_skill(tmp_path, sidecar=bad_sidecar)
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    # Existing schema rule fires: metadata.description required.
    assert any("description" in e for e in errors), errors


def test_legacy_inline_skill_emits_advisory_not_error(tmp_path: Path):
    # No sidecar; SKILL.md carries v1alpha2 wrapper.
    skill_dir = tmp_path / "skills" / "legacy"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: legacy\n"
        "  description: Legacy description.\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
        "\nbody\n"
    )
    asset = Asset(kind="skill", slug="legacy", path=skill_dir / "SKILL.md")
    errors = Validator(toolkit_root=tmp_path).validate(asset)
    # During tolerance: no error. An advisory may be surfaced elsewhere (doctor).
    assert errors == [], errors
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_check_skill_shape.py -v`
Expected: most tests fail — the new validation rules don't exist yet.

- [ ] **Step 3: Edit `schema.py` — add skill-shape rules to `Validator.validate`**

In `src/agent_toolkit_cli/schema.py`, extend the `validate` method. After the existing schema validation and name-agreement block, add a skill-specific section:

```python
def validate(self, asset: Asset) -> list[str]:
    # ... existing code unchanged through name-mismatch check ...

    # Skill-shape rules (new shape only — legacy inline skills are tolerated
    # during the one-release window and surfaced via doctor advisory).
    if asset.kind == "skill":
        errors.extend(self._validate_skill_shape(asset, data))

    return errors


def _validate_skill_shape(self, asset: Asset, sidecar_data: dict) -> list[str]:
    """Cross-file skill-shape validation.

    - SKILL.md must have top-level name + description.
    - SKILL.md description must end with a period.
    - SKILL.md name must equal asset slug.
    - Sidecar metadata.description period rule is enforced by JSON Schema.

    Legacy inline skills (no sidecar; v1alpha2 wrapper inside SKILL.md) are
    detected by the absence of a sidecar file and return [] — they're tolerated
    during the one-release tolerance window. Doctor surfaces an advisory.
    """
    errors: list[str] = []
    sidecar = self.toolkit_root / "skills" / f"{asset.slug}.toolkit.yaml"
    if not sidecar.is_file():
        # Legacy inline shape — tolerated, doctor handles the advisory.
        return errors

    # New-shape skill: SKILL.md must have its own top-level frontmatter.
    from agent_toolkit_cli.walker import extract_frontmatter
    skill_md_fm = extract_frontmatter(asset.path)
    if not skill_md_fm:
        errors.append(
            f"{asset.path}: SKILL.md is missing top-level frontmatter "
            f"(required for sidecar-shape skills)"
        )
        return errors

    name = skill_md_fm.get("name")
    description = skill_md_fm.get("description")

    if not name:
        errors.append(f"{asset.path}: SKILL.md missing top-level `name`")
    elif name != asset.slug:
        errors.append(
            f"{asset.path}: SKILL.md name={name!r} does not match slug {asset.slug!r}"
        )

    if not description:
        errors.append(f"{asset.path}: SKILL.md missing top-level `description`")
    elif not description.endswith("."):
        errors.append(
            f"{asset.path}: SKILL.md description must end with a period"
        )

    # Confirm sidecar metadata.name agrees too (schema already enforces existence)
    sidecar_name = (sidecar_data.get("metadata") or {}).get("name")
    if sidecar_name and name and sidecar_name != name:
        errors.append(
            f"{asset.path}: SKILL.md name={name!r} != sidecar metadata.name={sidecar_name!r}"
        )

    return errors
```

If `extract_frontmatter` is not exported, expose it as a module-level function in `walker.py` (it likely already is; if not, add a thin `def extract_frontmatter(path: Path) -> dict | None: ...` wrapper).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_check_skill_shape.py -v`
Expected: PASS — all six cases.

- [ ] **Step 5: Run full check tests for regressions**

Run: `uv run pytest tests/ -k 'check or validate' -v`
Expected: PASS. If existing tests assert no errors on a legacy fixture, they should still pass thanks to the tolerance branch. If a test fails because a fixture now triggers a new error, decide: tighten the fixture (most likely correct) or relax the rule.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/schema.py tests/test_check_skill_shape.py
git commit -m "feat(check): enforce new-shape skill rules in Validator

Validator now applies cross-file rules to skills with a sidecar:
SKILL.md must have top-level name+description, description ends with
a period, names agree across both files. Legacy inline skills (no
sidecar) skip these checks — doctor surfaces the migration advisory.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
Issue: #150"
```

---

### Task 7: Doctor — `skill-shape` advisory module

**Files:**
- Create: `src/agent_toolkit_cli/doctor/skill_shape.py`
- Modify: `src/agent_toolkit_cli/doctor/__init__.py` (registration)
- Test: `tests/test_doctor_skill_shape.py` (new)

- [ ] **Step 1: Inspect an existing doctor module to match the conventions**

Read `src/agent_toolkit_cli/doctor/frontmatter.py` (a similar advisory module) to learn:
- What the `__init__.py` registry expects (likely a `class` or a `def diagnose(toolkit_root) -> Result` function).
- The `Result` shape from `doctor/result.py`.

Adopt the same shape. Don't invent a new pattern.

- [ ] **Step 2: Write the failing test**

Create `tests/test_doctor_skill_shape.py`:

```python
"""doctor.skill_shape reports advisory on legacy inline skills.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.doctor.skill_shape import diagnose


def test_new_shape_skill_is_clean(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Harness desc.\n---\nbody\n"
    )
    (tmp_path / "skills" / "demo.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: demo\n  description: CLI desc.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
    )
    result = diagnose(tmp_path)
    assert result.warnings == []
    assert result.errors == []


def test_legacy_inline_skill_warns(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "legacy"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: legacy\n  description: Legacy desc.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\nbody\n"
    )
    result = diagnose(tmp_path)
    assert any("legacy" in w.lower() and "migrate" in w.lower() for w in result.warnings), result.warnings


def test_orphaned_sidecar_errors(tmp_path: Path):
    # Sidecar present, but SKILL.md has no top-level frontmatter — drift.
    skill_dir = tmp_path / "skills" / "drift"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("no frontmatter\n")
    (tmp_path / "skills" / "drift.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: drift\n  description: x.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
    )
    result = diagnose(tmp_path)
    assert result.errors, result.errors
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_doctor_skill_shape.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_toolkit_cli.doctor.skill_shape'`.

- [ ] **Step 4: Implement `doctor/skill_shape.py`**

Create `src/agent_toolkit_cli/doctor/skill_shape.py`. Follow the pattern from `doctor/frontmatter.py`. Sketch:

```python
"""Skill-shape advisory: warns on legacy inline skills, errors on drift between SKILL.md and sidecar.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.doctor.result import Result
from agent_toolkit_cli.walker import extract_frontmatter


def diagnose(toolkit_root: Path) -> Result:
    skills_dir = toolkit_root / "skills"
    warnings: list[str] = []
    errors: list[str] = []
    if not skills_dir.is_dir():
        return Result(warnings=warnings, errors=errors)

    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        slug = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        sidecar = skills_dir / f"{slug}.toolkit.yaml"
        if not skill_md.is_file():
            continue  # not a skill, or malformed

        skill_md_fm = extract_frontmatter(skill_md) or {}
        has_sidecar = sidecar.is_file()
        is_legacy_inline = "apiVersion" in skill_md_fm and not has_sidecar

        if is_legacy_inline:
            warnings.append(
                f"skills/{slug}/SKILL.md uses legacy inline frontmatter — "
                f"migrate to sidecar shape (see docs/superpowers/specs/"
                f"2026-05-20-skill-sidecar-shape-design.md or run "
                f"`agent-toolkit migrate-skills`)"
            )
            continue

        if has_sidecar and ("apiVersion" in skill_md_fm):
            errors.append(
                f"skills/{slug}/: both sidecar and inline v1alpha2 frontmatter present "
                f"(remove apiVersion from SKILL.md)"
            )
            continue

        if has_sidecar and not skill_md_fm:
            errors.append(
                f"skills/{slug}/SKILL.md has sidecar but no top-level frontmatter"
            )
            continue

    return Result(warnings=warnings, errors=errors)
```

Match the actual `Result` field names from `doctor/result.py` — if they're named differently (e.g. `findings`, `severity`), adapt the test fixtures and the module body together to match what `result.py` defines.

- [ ] **Step 5: Register in `doctor/__init__.py`**

Open `src/agent_toolkit_cli/doctor/__init__.py`. Find where the other modules are imported and registered (e.g. an `_ADVISORIES = (...)` tuple). Add `skill_shape` alongside them, matching the existing pattern.

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_doctor_skill_shape.py -v`
Expected: PASS — all three cases.

- [ ] **Step 7: Run full doctor suite**

Run: `uv run pytest tests/ -k doctor -v`
Expected: PASS (no regressions). If an existing CLI-level `doctor` test asserts on the list of advisory names, update it to include `skill-shape` in the expected output.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit_cli/doctor/skill_shape.py src/agent_toolkit_cli/doctor/__init__.py tests/test_doctor_skill_shape.py
git commit -m "feat(doctor): add skill-shape advisory module

Warns on legacy inline skills (migration target), errors on drift
between SKILL.md and sidecar.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
Issue: #150"
```

---

### Task 8: `migrate-skills` subcommand

**Files:**
- Create: `src/agent_toolkit_cli/commands/migrate_skills.py`
- Modify: `src/agent_toolkit_cli/cli.py` (register the new subcommand)
- Create: `tests/test_migrate_skills.py`
- Create: `tests/fixtures/migrate_skills_input/skills/example/SKILL.md` (golden input)
- Create: `tests/fixtures/migrate_skills_expected/skills/example/SKILL.md` (golden expected SKILL.md)
- Create: `tests/fixtures/migrate_skills_expected/skills/example.toolkit.yaml` (golden expected sidecar)

- [ ] **Step 1: Create the golden-file fixtures**

`tests/fixtures/migrate_skills_input/skills/example/SKILL.md`:

```markdown
---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: example
  description: A combined description used by both harness and CLI today.
  lifecycle: experimental
  notes: |
    argument-hint: <filename>
    Other notes go here.
spec:
  origin: first-party
  vendored_via: none
  harnesses: [claude, pi]
---

# example

Body text.
```

`tests/fixtures/migrate_skills_expected/skills/example/SKILL.md`:

```markdown
---
name: example
description: A combined description used by both harness and CLI today.
---

# example

Body text.
```

`tests/fixtures/migrate_skills_expected/skills/example.toolkit.yaml`:

```yaml
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: example
  description: A combined description used by both harness and CLI today.
  lifecycle: experimental
  # TODO shorten — currently the same as SKILL.md description
  notes: |
    Other notes go here.
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
    - pi
  per_harness:
    pi:
      argument_hint: <filename>
```

(Exact key order and indentation in the expected sidecar must match what your template assembler produces — adjust the fixture or the assembler together until they agree. The test uses byte-equality on the expected files.)

- [ ] **Step 2: Write the failing test**

Create `tests/test_migrate_skills.py`:

```python
"""migrate-skills: dry-run golden file + idempotency.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import cli

FIXTURE_INPUT = Path(__file__).parent / "fixtures" / "migrate_skills_input"
FIXTURE_EXPECTED = Path(__file__).parent / "fixtures" / "migrate_skills_expected"


def _copy_input(dest: Path) -> Path:
    shutil.copytree(FIXTURE_INPUT, dest)
    return dest


def test_dry_run_does_not_modify_files(tmp_path: Path):
    repo = _copy_input(tmp_path / "repo")
    runner = CliRunner()
    result = runner.invoke(cli, ["migrate-skills", "--content-repo", str(repo), "--dry-run"])
    assert result.exit_code == 0
    # SKILL.md unchanged
    actual = (repo / "skills" / "example" / "SKILL.md").read_text()
    expected_input = (FIXTURE_INPUT / "skills" / "example" / "SKILL.md").read_text()
    assert actual == expected_input
    # No sidecar created
    assert not (repo / "skills" / "example.toolkit.yaml").exists()


def test_run_writes_new_shape(tmp_path: Path):
    repo = _copy_input(tmp_path / "repo")
    runner = CliRunner()
    result = runner.invoke(cli, ["migrate-skills", "--content-repo", str(repo)])
    assert result.exit_code == 0, result.output

    actual_skill_md = (repo / "skills" / "example" / "SKILL.md").read_text()
    expected_skill_md = (FIXTURE_EXPECTED / "skills" / "example" / "SKILL.md").read_text()
    assert actual_skill_md == expected_skill_md

    actual_sidecar = (repo / "skills" / "example.toolkit.yaml").read_text()
    expected_sidecar = (FIXTURE_EXPECTED / "skills" / "example.toolkit.yaml").read_text()
    assert actual_sidecar == expected_sidecar


def test_idempotent_second_run(tmp_path: Path):
    repo = _copy_input(tmp_path / "repo")
    runner = CliRunner()
    runner.invoke(cli, ["migrate-skills", "--content-repo", str(repo)])
    # Snapshot after first run
    first = {p: p.read_bytes() for p in repo.rglob("*.md") | set(repo.rglob("*.toolkit.yaml"))}
    # Second run
    result = runner.invoke(cli, ["migrate-skills", "--content-repo", str(repo)])
    assert result.exit_code == 0
    assert "no skills to migrate" in result.output.lower() or "0 migrated" in result.output.lower()
    second = {p: p.read_bytes() for p in repo.rglob("*.md") | set(repo.rglob("*.toolkit.yaml"))}
    assert first == second
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_migrate_skills.py -v`
Expected: FAIL — `migrate-skills` subcommand does not exist (`Error: No such command 'migrate-skills'`).

- [ ] **Step 4: Implement `commands/migrate_skills.py`**

Create `src/agent_toolkit_cli/commands/migrate_skills.py`:

```python
"""One-shot content-repo migration: inline-shape skills -> sidecar shape.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
"""
from __future__ import annotations

from pathlib import Path

import click
import yaml


@click.command("migrate-skills")
@click.option(
    "--content-repo",
    type=click.Path(file_okay=False, dir_okay=True, exists=True, path_type=Path),
    required=True,
    help="Path to the content repo (e.g. ~/GitHub/agent-toolkit).",
)
@click.option("--dry-run", is_flag=True, help="Print the plan without writing files.")
def migrate_skills(content_repo: Path, dry_run: bool) -> None:
    """Rewrite legacy inline-frontmatter skills into the new two-file shape."""
    skills_dir = content_repo / "skills"
    if not skills_dir.is_dir():
        raise click.UsageError(f"no skills/ directory under {content_repo}")

    migrated = 0
    skipped = 0
    for skill_dir in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        slug = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        sidecar = skills_dir / f"{slug}.toolkit.yaml"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---\n", 4)
        if end == -1:
            continue
        fm_yaml = text[4:end]
        body = text[end + 5 :]
        fm = yaml.safe_load(fm_yaml) or {}

        if "apiVersion" not in fm:
            # Already new-shape (or never had a wrapper). Skip.
            continue
        if sidecar.is_file():
            # Looks already migrated; skip.
            skipped += 1
            continue

        metadata = fm.get("metadata") or {}
        spec = fm.get("spec") or {}
        description = metadata.get("description", "")
        slug_from_fm = metadata.get("name", slug)

        # Detect pi argument-hint in notes
        notes = metadata.get("notes") or ""
        notes_lines = notes.splitlines()
        arg_hint: str | None = None
        remaining_notes_lines: list[str] = []
        for line in notes_lines:
            if arg_hint is None and line.lstrip().startswith("argument-hint:"):
                arg_hint = line.split(":", 1)[1].strip()
            else:
                remaining_notes_lines.append(line)
        cleaned_notes = "\n".join(remaining_notes_lines).strip()

        new_skill_md = (
            "---\n"
            f"name: {slug_from_fm}\n"
            f"description: {description}\n"
            "---\n"
            + body
        )
        new_sidecar = _render_sidecar(
            slug=slug_from_fm,
            description=description,
            lifecycle=metadata.get("lifecycle", "experimental"),
            notes=cleaned_notes,
            spec=spec,
            arg_hint=arg_hint,
        )

        click.echo(f"migrated skills/{slug}/ (added sidecar, rewrote SKILL.md frontmatter)")
        if not dry_run:
            skill_md.write_text(new_skill_md, encoding="utf-8")
            sidecar.write_text(new_sidecar, encoding="utf-8")
        migrated += 1

    suffix = " (dry-run)" if dry_run else ""
    if migrated == 0 and skipped == 0:
        click.echo(f"no skills to migrate{suffix}")
    else:
        click.echo(f"{migrated} migrated, {skipped} skipped{suffix}")


def _render_sidecar(
    *,
    slug: str,
    description: str,
    lifecycle: str,
    notes: str,
    spec: dict,
    arg_hint: str | None,
) -> str:
    """Render a sidecar via templated string assembly.

    We don't use yaml.safe_dump because it drops the `# TODO shorten` comment.
    The wrapper shape is small and known; the template is the source of truth.
    """
    lines: list[str] = []
    lines.append("apiVersion: agent-toolkit/v1alpha2")
    lines.append("metadata:")
    lines.append(f"  name: {slug}")
    lines.append(f"  description: {description}")
    lines.append(f"  lifecycle: {lifecycle}")
    lines.append("  # TODO shorten — currently the same as SKILL.md description")
    if notes:
        lines.append("  notes: |")
        for nline in notes.splitlines():
            lines.append(f"    {nline}")
    lines.append("spec:")
    lines.append(f"  origin: {spec.get('origin', 'first-party')}")
    lines.append(f"  vendored_via: {spec.get('vendored_via', 'none')}")
    lines.append("  harnesses:")
    for h in spec.get("harnesses", []):
        lines.append(f"    - {h}")
    if arg_hint is not None:
        lines.append("  per_harness:")
        lines.append("    pi:")
        lines.append(f"      argument_hint: {arg_hint}")
    return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Register the subcommand in `cli.py`**

In `src/agent_toolkit_cli/cli.py`, find where existing subcommands are registered (search for `add_command` or import statements that bring command functions into the group). Add:

```python
from agent_toolkit_cli.commands.migrate_skills import migrate_skills

cli.add_command(migrate_skills)
```

(adjust to match the project's actual registration pattern).

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_migrate_skills.py -v`
Expected: PASS — all three cases.

If the golden-file test fails on byte-equality, inspect the diff and adjust either the template assembler in `_render_sidecar` or the expected fixture file together so they match. Do this until equality holds. Spaces vs tabs and trailing newlines are common culprits.

- [ ] **Step 7: Confirm `--help` discoverability**

Run: `uv run agent-toolkit --help | grep migrate-skills`
Expected: a line listing `migrate-skills` with its short help.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit_cli/commands/migrate_skills.py src/agent_toolkit_cli/cli.py tests/test_migrate_skills.py tests/fixtures/migrate_skills_input tests/fixtures/migrate_skills_expected
git commit -m "feat(migrate-skills): one-shot content-repo migration command

Rewrites every legacy inline-frontmatter skill in <content-repo>/skills/
into the new sidecar shape. Uses templated string assembly so the
\`# TODO shorten\` comment in the emitted sidecar is preserved. The pi
\`argument-hint\` heuristic (first matching line in metadata.notes) is
lifted to spec.per_harness.pi.argument_hint.

Spec: docs/superpowers/specs/2026-05-20-skill-sidecar-shape-design.md
Issue: #150"
```

---

### Task 9: Full suite + harness empirical verification

**Files:** none (this task is verification, not implementation).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS, ≥ 920 tests (added ~20-30 cases across new files).

- [ ] **Step 2: Run lefthook pre-commit checks**

Run: `uv run lefthook run pre-commit` (or whatever the project uses; if there's a `lefthook.yml` with a `pre-push` hook, run that instead).
Expected: green.

- [ ] **Step 3: Empirical harness verifications**

For each of the three open verifications in the spec:

1. **Claude.** Create a fixture skill in the new shape at `/tmp/atk-fixture-claude/skills/probe/SKILL.md` plus sidecar. Symlink the SKILL.md into `~/.claude/skills/probe/SKILL.md`. Start `claude`, issue a trigger phrase, capture the transcript. Save to `assets/verification/150/claude-loader.log`.
2. **Gemini.** Same shape; symlink into the gemini home (`~/.gemini/skills/probe/SKILL.md` if applicable). Run `gemini`, trigger. Save to `assets/verification/150/gemini-loader.log`.
3. **Pi argument-hint.** Same shape with `spec.per_harness.pi.argument_hint: "<filename>"`. Run `agent-toolkit link --harness pi --content-repo /tmp/atk-fixture-claude`. Then `pi demands` (or whatever surfaces the hint). Save to `assets/verification/150/pi-arg-hint.log`.

If a harness is not installed locally, write a one-line note to `assets/verification/150/<harness>-deferred.txt` explaining which post-merge follow-up issue tracks it. Do not block the PR on missing harnesses (per spec).

- [ ] **Step 4: Commit any verification artifacts**

```bash
# Artifacts under assets/verification/ are gitignored by aj-workflow convention,
# but the empirical-verification notes go into the PR body, not the commit.
# This step is a no-op unless something changed.
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Task |
|---|---|
| Two-file shape (SKILL.md + sidecar) | Tasks 2, 5 |
| `spec.per_harness` block | Task 1 (schema), Task 3 (translator reads it) |
| Validation rules — sidecar mandatory, both descriptions, period, name agreement | Task 6 |
| Per-harness translator audit (claude/codex/opencode/gemini/pi) | Tasks 3, 4 |
| `_translate_slot_layout` extension | Task 4 |
| Translator implementation sketch (`_translate_pi_skill`) | Task 3 |
| Scaffolder updates + `--inline` rejection | Task 5 |
| Legacy tolerance window (warning advisory + fallback) | Tasks 2 (walker fallback), 6 (validator tolerance), 7 (doctor advisory) |
| Content repo migration command | Task 8 |
| Doctor `skill-shape` advisory | Task 7 |
| Empirical harness verifications | Task 9 |

All spec sections are covered.

**Placeholder scan:** no "TODO" or "implement later" in any task. Every code block contains the actual code to write.

**Type consistency:** `harness_description: str | None`, `cli_description: str | None` used in Tasks 2, 3, 6 with consistent naming. `_translate_pi_skill(record, body) -> bytes` matches the existing translator signature.

**Naming consistency:** `migrate-skills` (CLI), `migrate_skills` (Python module/function) — matches click convention used elsewhere in the codebase. `_render_sidecar` is a private helper, single use.

**Risk note:** Task 8 byte-equality on the golden sidecar fixture is brittle to YAML key order and whitespace. The plan explicitly tells the implementer to iterate the template and the fixture together until they match — this is the cheapest correct approach for a one-shot migration command.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-20-skill-sidecar-shape.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for this plan because the tasks are independent (each task touches a separate module with clear test boundaries).
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
