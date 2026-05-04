# MCP Adapters — Codex Proof + Full Wiring (CLI-PR-1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the harness-adapter framework end-to-end with **Codex** as the working proof, satisfy AC #1–#10 of the spec for Codex, and gracefully skip Claude/OpenCode/Pi until their adapter PRs (CLI-PR-2/3/4) land.

**Architecture:** New `harness_adapters/` package owning two `Protocol`s (`PluginFolderAdapter`, `ConfigFileAdapter`) plus a registry. New `_mcp_dispatch.py` owning `apply_link()`, the loud-write contract, and the atomic-write helper. `_link_lib.project_from_file`'s no-op MCP branch (Plan A) is replaced with a single `apply_link(...)` call. `commands/{diff,list,doctor,fix}` learn an MCP branch routed through the same adapter API. Schema is **replaced** v1alpha1 → v1alpha2 (no dual-validate window); fixture catalog migrates inside this PR; the content-repo catalog migration lands separately.

**Tech Stack:** Python 3.12+, Click, ruamel.yaml, jsonschema, **`tomlkit` (new dep)**, pytest. Codex round-trip via `tomlkit`.

**Out of scope (deferred to CLI-PR-2/3/4):**
- Claude / OpenCode / Pi adapter implementations.
- `--force` flag implementation (defined in this PR's `apply_link` signature; lit up in CLI-PR-2).
- `new mcp <slug>` complete authoring UX (we ship the scaffold function only).
- `ingest` MCP support.
- Catalog content-repo migration (its own PR; sequencing in spec § "Catalog migration sequencing").

---

## File Structure

**New package and modules:**

- `src/agent_toolkit/harness_adapters/__init__.py` — exports `get_adapter(harness)` registry.
- `src/agent_toolkit/harness_adapters/base.py` — `Scope`, `McpEntry`, `WriteAction`, `CannotInstall`, the two `Protocol`s, and the unimplemented-adapter sentinel `UnimplementedAdapter`.
- `src/agent_toolkit/harness_adapters/codex.py` — full `ConfigFileAdapter` implementation backed by `tomlkit`.
- `src/agent_toolkit/harness_adapters/claude.py` — placeholder raising in `__init__`; `get_adapter("claude")` returns `UnimplementedAdapter("claude")`.
- `src/agent_toolkit/harness_adapters/opencode.py` — same placeholder treatment.
- `src/agent_toolkit/harness_adapters/pi.py` — same placeholder treatment.
- `src/agent_toolkit/commands/_mcp_dispatch.py` — `apply_link()`, `_atomic_write_bytes()`, `_atomic_delete()`, the loud-print helpers, and `_build_mcp_entries()` (slug → `McpEntry` resolver).

**Schema files:**

- Create: `src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json` — full replacement schema (see Task 2 for content).
- Create: `schemas/asset-frontmatter.v1alpha2.json` (repo SSOT alongside the bundled package copy).
- Delete: `src/agent_toolkit/_schemas/asset-frontmatter.v1alpha1.json`.
- Delete: `schemas/asset-frontmatter.v1alpha1.json`.

**Modified files:**

- `pyproject.toml` — add `tomlkit>=0.13` to dependencies; bump `force-include` schema entry to v1alpha2.
- `src/agent_toolkit/schema.py:20` — load v1alpha2 schema; pass walker-derived kind into validator.
- `src/agent_toolkit/_repo_resolution.py:26` — bump `_SCHEMA` constant.
- `src/agent_toolkit/doctor/environment.py:14,18` — bump schema-presence check.
- `src/agent_toolkit/doctor/per_resource.py:46` — update "v1alpha1 valid" finding string to "v1alpha2 valid".
- `src/agent_toolkit/commands/new.py:24,79,95` — emit `apiVersion: agent-toolkit/v1alpha2` and add `mcp` branch.
- `src/agent_toolkit/ingest/types.py:46` — bump emitted `apiVersion`.
- `tests/conftest.py:12,32,34` — bump fixture text and schema path.
- `src/agent_toolkit/commands/_link_lib.py:212-223` — replace MCP no-op branch with adapter dispatch call.
- `src/agent_toolkit/commands/_list_json.py:160-179` — replace MCP "unsupported" overload with four-glyph status; add MCP-aware target-resolution.
- `src/agent_toolkit/commands/diff.py` (or new `_mcp_diff.py` helper) — extend to surface MCP would-writes via the adapter when the diff is on an MCP-capable harness.
- `src/agent_toolkit/commands/doctor.py:23,90-99` — add `mcps` group.
- New: `src/agent_toolkit/doctor/mcps.py` — drift/env/prereq/verify checks per allow-listed MCP.
- `src/agent_toolkit/commands/fix.py` — add MCP-reconcile path (preserves AGENTS.md region-regen behaviour).
- `src/agent_toolkit_tui/widgets/asset_grid.py:13-18` — extend `_GLYPH` map with the four MCP statuses; treat `installed-not-allowlisted` as non-interactive.
- `src/agent_toolkit_tui/state.py` — extend `CellStatus` literal with the four MCP states.

**Test files (new):**

- `tests/test_mcp_adapters_base.py` — Protocol shape, registry dispatch, `UnimplementedAdapter` skip-with-warning.
- `tests/test_mcp_adapters_codex.py` — Codex `read`/`upsert`/`remove`/`render`/`diff`/`entry_drift`/`list_installed`; full round-trip byte-equal test (AC #8) against a fixture `config.toml` carrying `[notice.*]`, `[tui.*]`, comments, and a hand-rolled MCP entry.
- `tests/test_mcp_dispatch.py` — `apply_link` orchestration: dry-run prints `would-<op>`, real run prints loud pre+post, atomic write, partial-failure isolation.
- `tests/test_doctor_mcps.py` — drift detection, env-var-missing warning, prereq-missing warning, verify gate behaviour.
- `tests/test_tui_mcp_integration.py` — TUI runner round-trip test exercising `link_plan` then `list_state` for one Codex MCP, asserting `linked-matches`.

**Test files (modified):**

- `tests/test_cli_link.py` — flip Plan-A "MCP install path for codex not yet implemented" tests to assert `[mcp_servers.context7]` lands in the target. Keep parallel "skipped" tests for Claude/OpenCode/Pi.
- `tests/test_cli_unlink.py` — same flip.
- `tests/test_list_json.py` — flip MCP `status="unsupported"` assertion to four-glyph status. Codex cells assert `linked-matches` after a link round-trip.
- `tests/test_cli_diff.py` — assert MCP would-writes appear in `diff` output for Codex.
- `tests/test_cli_list.py` — text-mode list shows four-glyph status for MCP rows; add Codex round-trip test.
- `tests/test_check.py` — bump fixture frontmatter to v1alpha2; add a v1alpha2-shaped MCP frontmatter test (with `spec.mcp` block).
- `tests/test_fix.py` — add MCP-reconcile test path; pin existing AGENTS.md region behaviour.
- `tests/test_validator.py`, `tests/test_validator_schema_path.py`, `tests/test_schema.py` — bump to v1alpha2.

---

## Task 0: Phase-0 spike — tomlkit round-trip on real Codex configs

**Files:**
- Create: `tests/_fixtures/codex_config_realistic.toml` (a representative `~/.codex/config.toml` with `[notice.model_migrations]`, `[tui.model_availability_nux]`, comments, blank lines, an existing `[mcp_servers.preexisting]` table).
- Create: `tests/test_tomlkit_roundtrip.py` (gate test).

This spike confirms `tomlkit` round-trips a realistic Codex config byte-equal under our `parse → render` cycle. If it fails, we either pin a working version or document the loss. **Do this before any adapter work.**

- [ ] **Step 1: Add `tomlkit` to `pyproject.toml` dependencies**

In `pyproject.toml`, edit the `[project]` `dependencies` list:

```toml
dependencies = [
    "jsonschema>=4.21",
    "pyyaml>=6.0",
    "click>=8.1",
    "ruamel.yaml>=0.18",
    "tomlkit>=0.13",
]
```

Run: `uv sync`. Expected: `tomlkit` installed, no other changes.

- [ ] **Step 2: Write the realistic fixture**

Create `tests/_fixtures/codex_config_realistic.toml`:

```toml
# Codex CLI configuration. Hand-edited.
model_provider = "openai"

[notice.model_migrations]
sonnet_4 = { migrated_at = "2026-04-01" }

# TUI tweaks.
[tui.model_availability_nux]
shown = true
last_seen_version = "0.42"

# A pre-existing hand-rolled MCP entry the user added before agent-toolkit.
[mcp_servers.preexisting]
command = "node"
args = ["./local-mcp.js"]
env = { LOG = "1" }
```

- [ ] **Step 3: Write the gate test**

Create `tests/test_tomlkit_roundtrip.py`:

```python
"""Phase-0 gate: tomlkit must round-trip a realistic Codex config byte-equal."""
from __future__ import annotations

from pathlib import Path

import tomlkit


_FIXTURE = Path(__file__).parent / "_fixtures" / "codex_config_realistic.toml"


def test_tomlkit_byte_equal_roundtrip():
    """Parse and re-dump must equal the source bytes verbatim."""
    src = _FIXTURE.read_bytes()
    doc = tomlkit.parse(src.decode("utf-8"))
    rendered = tomlkit.dumps(doc).encode("utf-8")
    assert rendered == src, (
        "tomlkit round-trip is NOT byte-equal — adapter design assumes it is.\n"
        f"Length src={len(src)} rendered={len(rendered)}.\n"
        "Investigate before continuing with Codex adapter."
    )
```

- [ ] **Step 4: Run the gate**

Run: `uv run pytest tests/test_tomlkit_roundtrip.py -v`
Expected: PASS.

If it FAILs:
1. Inspect the diff (`difflib.unified_diff(src.decode(), rendered.decode())`).
2. If churn is whitespace-only and trivial, accept and document in the test.
3. If churn is structural (comment positioning, key reordering), pin a known-good `tomlkit` version (try `tomlkit==0.12.5`, `0.13.0`, `0.13.1`) and update `pyproject.toml`.
4. If no version works, abort this plan and escalate — design assumes `tomlkit` round-trip is structural-equality safe.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/_fixtures/codex_config_realistic.toml tests/test_tomlkit_roundtrip.py
git commit -m "chore(deps): add tomlkit + phase-0 round-trip gate against codex config"
```

---

## Task 1: Add the v1alpha2 schema file (additive, before deleting v1alpha1)

**Files:**
- Create: `src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json`
- Create: `schemas/asset-frontmatter.v1alpha2.json` (repo-level SSOT copy)

We add v1alpha2 first, switch the loader to it next task, then delete v1alpha1 last. Until the loader switches, both files coexist on disk with no consumer of v1alpha2.

- [ ] **Step 1: Write the v1alpha2 schema**

Create `src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/ajanderson1/agent-toolkit/schemas/asset-frontmatter.v1alpha2.json",
  "title": "agent-toolkit asset frontmatter",
  "type": "object",
  "required": ["apiVersion", "metadata", "spec"],
  "properties": {
    "apiVersion": { "const": "agent-toolkit/v1alpha2" },
    "metadata": {
      "type": "object",
      "required": ["name", "description", "lifecycle"],
      "additionalProperties": false,
      "properties": {
        "name": { "type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$" },
        "description": { "type": "string", "pattern": "\\.$" },
        "kind": {
          "enum": ["skill", "agent", "command", "hook", "plugin", "mcp", "pi-extension"]
        },
        "keywords": {
          "type": "array",
          "items": { "type": "string" },
          "uniqueItems": true
        },
        "lifecycle": { "enum": ["experimental", "stable", "deprecated"] },
        "license": { "type": "string" },
        "notes": { "type": "string" }
      }
    },
    "spec": {
      "type": "object",
      "required": ["origin", "vendored_via", "harnesses"],
      "additionalProperties": false,
      "properties": {
        "origin": { "enum": ["first-party", "third-party"] },
        "vendored_via": { "enum": ["none", "submodule", "clone", "symlink"] },
        "upstream": { "type": "string", "format": "uri" },
        "fork": { "type": "string", "format": "uri" },
        "harnesses": {
          "type": "array",
          "minItems": 1,
          "uniqueItems": true,
          "items": { "enum": ["claude", "codex", "opencode", "pi"] }
        },
        "mcp": {
          "type": "object",
          "required": ["transport", "install_method"],
          "additionalProperties": false,
          "properties": {
            "transport":      { "enum": ["stdio", "http", "sse"] },
            "install_method": { "enum": ["npx", "uvx", "docker", "local", "remote"] },
            "command":        { "type": "string" },
            "env":            { "type": "array", "items": { "type": "string" }, "uniqueItems": true },
            "optional_env":   { "type": "array", "items": { "type": "string" }, "uniqueItems": true },
            "prerequisites":  { "type": "array", "items": { "type": "string" }, "uniqueItems": true },
            "verify":         { "type": "string" }
          }
        }
      },
      "allOf": [
        {
          "if": { "properties": { "origin": { "const": "third-party" } } },
          "then": { "required": ["upstream"] }
        },
        {
          "if": { "properties": { "vendored_via": { "const": "submodule" } } },
          "then": { "required": ["fork"] }
        }
      ]
    }
  },
  "allOf": [
    {
      "if": {
        "properties": { "metadata": { "properties": { "kind": { "const": "mcp" } }, "required": ["kind"] } },
        "required": ["metadata"]
      },
      "then": { "properties": { "spec": { "required": ["mcp"] } } }
    },
    {
      "if": {
        "properties": { "metadata": { "properties": { "kind": { "not": { "const": "mcp" } } } } }
      },
      "then": { "properties": { "spec": { "not": { "required": ["mcp"] } } } }
    }
  ]
}
```

Note: The conditional "spec.mcp required iff kind==mcp" uses `metadata.kind`. The walker-derived kind is cross-checked in the validator (Python code), not in this JSON schema — JSON Schema can't see `asset.kind`. The validator passes a discriminator into the data before validation; see Task 3.

- [ ] **Step 2: Mirror the schema to the repo-level SSOT path**

Create `schemas/asset-frontmatter.v1alpha2.json` with the **same content** as the package copy.

```bash
cp src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json schemas/asset-frontmatter.v1alpha2.json
```

Verify they match: `diff src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json schemas/asset-frontmatter.v1alpha2.json` → no output.

- [ ] **Step 3: Update `pyproject.toml` force-include**

In `pyproject.toml` find the `[tool.hatch.build.targets.wheel.force-include]` section. **Add** the v1alpha2 entry alongside the existing v1alpha1 entry (don't remove v1alpha1 yet; that happens at the end of Task 4):

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/agent_toolkit/_schemas/asset-frontmatter.v1alpha1.json" = "agent_toolkit/_schemas/asset-frontmatter.v1alpha1.json"
"src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json" = "agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json"
```

- [ ] **Step 4: Smoke-test schema is loadable**

Run:

```bash
uv run python -c "
import json
from importlib.resources import files
text = (files('agent_toolkit') / '_schemas' / 'asset-frontmatter.v1alpha2.json').read_text()
schema = json.loads(text)
print('apiVersion const:', schema['properties']['apiVersion']['const'])
print('mcp block:', 'mcp' in schema['properties']['spec']['properties'])
"
```

Expected output:

```
apiVersion const: agent-toolkit/v1alpha2
mcp block: True
```

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json schemas/asset-frontmatter.v1alpha2.json pyproject.toml
git commit -m "feat(schema): add v1alpha2 schema (parallel to v1alpha1)"
```

---

## Task 2: Switch the validator to v1alpha2 + cross-check walker-derived kind

**Files:**
- Modify: `src/agent_toolkit/schema.py` (loader + cross-check rule)
- Test: `tests/test_validator.py`, `tests/test_schema.py`, `tests/test_validator_schema_path.py`

The validator stops loading v1alpha1, loads v1alpha2 instead, and gains one extra rule: when frontmatter's `metadata.kind` is set, it must equal the walker-derived kind. If absent, the validator injects the walker-derived kind into the data dict before JSON-Schema validation so the conditional `spec.mcp required` rule fires correctly.

- [ ] **Step 1: Write failing tests**

Edit `tests/test_validator.py`. Replace the file with (start by reading what's there to keep helpers intact):

Read first: `tests/test_validator.py`. Then edit to assert against v1alpha2:

Replace any line containing `agent-toolkit/v1alpha1` with `agent-toolkit/v1alpha2`. Then **append** these new tests:

```python
def test_validator_loads_v1alpha2_schema(tmp_path):
    """The bundled schema is v1alpha2."""
    from agent_toolkit.schema import Validator

    v = Validator(toolkit_root=tmp_path)
    assert v.schema["properties"]["apiVersion"]["const"] == "agent-toolkit/v1alpha2"
    assert "mcp" in v.schema["properties"]["spec"]["properties"]


def test_validator_kind_mismatch_is_error(tmp_path):
    """If frontmatter declares metadata.kind, it must match walker-derived kind."""
    from agent_toolkit.schema import Validator
    from agent_toolkit.walker import Asset

    skills = tmp_path / "skills" / "alpha"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: Alpha.\n"
        "  lifecycle: stable\n"
        "  kind: agent\n"  # mismatch — walker derives 'skill'
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "---\n"
    )
    asset = Asset(kind="skill", slug="alpha", path=skills / "SKILL.md")
    v = Validator(toolkit_root=tmp_path)
    errors = v.validate(asset)
    assert any("kind" in e and "agent" in e and "skill" in e for e in errors), errors


def test_validator_mcp_requires_spec_mcp(tmp_path):
    """An MCP without spec.mcp fails validation."""
    from agent_toolkit.schema import Validator
    from agent_toolkit.walker import Asset

    mcp_dir = tmp_path / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text("{}\n")
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: context7\n"
        "  description: c.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses: [codex]\n"
        "---\n"
    )
    asset = Asset(kind="mcp", slug="context7", path=mcp_dir / "config.json")
    v = Validator(toolkit_root=tmp_path)
    errors = v.validate(asset)
    assert any("mcp" in e.lower() for e in errors), errors


def test_validator_mcp_with_spec_mcp_passes(tmp_path):
    """An MCP with valid spec.mcp passes."""
    from agent_toolkit.schema import Validator
    from agent_toolkit.walker import Asset

    mcp_dir = tmp_path / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text("{}\n")
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: context7\n"
        "  description: c.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses: [codex]\n"
        "  mcp:\n"
        "    transport: stdio\n"
        "    install_method: npx\n"
        "---\n"
    )
    asset = Asset(kind="mcp", slug="context7", path=mcp_dir / "config.json")
    v = Validator(toolkit_root=tmp_path)
    errors = v.validate(asset)
    assert errors == [], errors


def test_validator_skill_with_spec_mcp_is_error(tmp_path):
    """spec.mcp on a non-MCP asset is forbidden."""
    from agent_toolkit.schema import Validator
    from agent_toolkit.walker import Asset

    skills = tmp_path / "skills" / "alpha"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: Alpha.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "  mcp:\n"
        "    transport: stdio\n"
        "    install_method: npx\n"
        "---\n"
    )
    asset = Asset(kind="skill", slug="alpha", path=skills / "SKILL.md")
    v = Validator(toolkit_root=tmp_path)
    errors = v.validate(asset)
    assert errors, "expected error for spec.mcp on a skill"
```

Edit `tests/test_validator_schema_path.py`. Replace `v1alpha1` → `v1alpha2` everywhere.

Edit `tests/test_schema.py`. Replace `v1alpha1` → `v1alpha2` everywhere.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_validator.py tests/test_validator_schema_path.py tests/test_schema.py -v`
Expected: FAIL — validator still loads v1alpha1.

- [ ] **Step 3: Update `Validator` to load v1alpha2 and cross-check kind**

Replace `src/agent_toolkit/schema.py` entirely:

```python
"""Validate asset frontmatter against the v1alpha2 JSON schema + cross-asset rules."""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import jsonschema
import yaml

from agent_toolkit.walker import Asset, extract_frontmatter, frontmatter_path


class Validator:
    def __init__(self, toolkit_root: Path):
        self.toolkit_root = toolkit_root
        # Schema is the contract the CLI enforces; it ships with the CLI.
        # The toolkit repo holds the SSOT for humans, but the validator's runtime
        # source of truth is the bundled copy in the agent_toolkit package.
        schema_text = (files("agent_toolkit") / "_schemas" / "asset-frontmatter.v1alpha2.json").read_text()
        self.schema = json.loads(schema_text)

    def validate(self, asset: Asset) -> list[str]:
        data = self._load_metadata(asset)
        errors: list[str] = []
        if data is None:
            return [f"{asset.path}: no frontmatter / metadata block found"]

        # Cross-check declared metadata.kind against walker-derived kind.
        declared_kind = ((data.get("metadata") or {}).get("kind"))
        if declared_kind is not None and declared_kind != asset.kind:
            errors.append(
                f"{asset.path}: metadata.kind={declared_kind!r} but walker derived {asset.kind!r}"
            )
            # Skip JSON-Schema validation for the mismatched-kind case so
            # the conditional spec.mcp rule doesn't fire spuriously.
            return errors

        # Inject walker-derived kind so the JSON-Schema conditional
        # ("spec.mcp required iff metadata.kind == mcp") fires regardless
        # of whether frontmatter declared metadata.kind.
        data_for_schema = dict(data)
        meta_for_schema = dict(data_for_schema.get("metadata") or {})
        meta_for_schema.setdefault("kind", asset.kind)
        data_for_schema["metadata"] = meta_for_schema

        try:
            jsonschema.validate(data_for_schema, self.schema)
        except jsonschema.ValidationError as e:
            errors.append(f"{asset.path}: schema: {e.message}")

        # Cross-asset rule: metadata.name must equal asset.slug
        name = (data.get("metadata") or {}).get("name")
        if name and name != asset.slug:
            errors.append(
                f"{asset.path}: slug mismatch — metadata.name={name!r} but path slug is {asset.slug!r}"
            )
        return errors

    def _load_metadata(self, asset: Asset) -> dict | None:
        if asset.kind in {"skill", "agent", "command"}:
            return extract_frontmatter(asset.path)
        if asset.kind in {"hook", "pi-extension"}:
            return yaml.safe_load(asset.path.read_text())
        if asset.kind == "mcp":
            fm_path = frontmatter_path(asset.path, asset.kind)
            if not fm_path.is_file():
                return None
            return extract_frontmatter(fm_path)
        if asset.kind == "plugin":
            doc = json.loads(asset.path.read_text())
            return doc.get("agent_toolkit")
        return None
```

- [ ] **Step 4: Update `_repo_resolution.py`, `doctor/environment.py`, `doctor/per_resource.py`**

In `src/agent_toolkit/_repo_resolution.py:26`, replace:

```python
_SCHEMA = "schemas/asset-frontmatter.v1alpha2.json"
```

In `src/agent_toolkit/doctor/environment.py:14,18`, replace:

```python
    schema = toolkit_root / "schemas" / "asset-frontmatter.v1alpha2.json"
    if not schema.exists():
        failures.append(f"schema missing at {schema}")
    else:
        findings.append("schema present at schemas/asset-frontmatter.v1alpha2.json")
```

In `src/agent_toolkit/doctor/per_resource.py:46`, replace the `[OK] frontmatter v1alpha1 valid` literal with `[OK]   frontmatter   v1alpha2 valid`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_validator.py tests/test_validator_schema_path.py tests/test_schema.py -v`
Expected: PASS for those files. Other tests (`test_check.py`, `test_cli_*`) will fail — they expect v1alpha1 fixtures. Task 3 fixes those.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit/schema.py src/agent_toolkit/_repo_resolution.py src/agent_toolkit/doctor/environment.py src/agent_toolkit/doctor/per_resource.py tests/test_validator.py tests/test_validator_schema_path.py tests/test_schema.py
git commit -m "feat(schema): load v1alpha2; cross-check walker-derived kind; require spec.mcp for mcps"
```

---

## Task 3: Migrate fixture catalog and `new`/`ingest` to v1alpha2; delete v1alpha1

**Files:**
- Modify: `tests/conftest.py:12,32,34` — fixture text + schema path.
- Modify: `tests/test_walker.py` — fixture text (any v1alpha1 strings → v1alpha2).
- Modify: `tests/test_cli_link.py`, `tests/test_cli_unlink.py`, `tests/test_cli_list.py`, `tests/test_cli_diff.py`, `tests/test_check.py`, `tests/test_doctor_*.py`, `tests/test_link_lib.py`, `tests/test_list_json.py`, `tests/test_pi_extension.py`, `tests/test_inventory.py`, `tests/test_fix.py`, `tests/test_check_conventions_drift.py` — bump every fixture string `agent-toolkit/v1alpha1` → `agent-toolkit/v1alpha2`.
- Modify: `src/agent_toolkit/commands/new.py` — emit v1alpha2; add `mcp` branch.
- Modify: `src/agent_toolkit/ingest/types.py:46` — emit v1alpha2.
- Delete: `src/agent_toolkit/_schemas/asset-frontmatter.v1alpha1.json`.
- Delete: `schemas/asset-frontmatter.v1alpha1.json`.
- Modify: `pyproject.toml` — drop the v1alpha1 force-include line.

This is a mechanical sweep. After this task, no `agent-toolkit/v1alpha1` string remains in the codebase or fixtures.

- [ ] **Step 1: Mass-replace v1alpha1 fixture strings**

Run from the repo root:

```bash
grep -rln 'agent-toolkit/v1alpha1' src tests
```

Read each match. For each file, replace `agent-toolkit/v1alpha1` with `agent-toolkit/v1alpha2`.

If the file is `src/agent_toolkit/commands/new.py`, also handle the `mcp` branch — see Step 2.

If the file is `src/agent_toolkit/ingest/types.py`, change `"apiVersion": "agent-toolkit/v1alpha1"` to `"apiVersion": "agent-toolkit/v1alpha2"` at line 46.

If the file is `tests/conftest.py`, update **two** things:
- Line ~12 `apiVersion: agent-toolkit/v1alpha1` in `SKILL_FRONTMATTER` → `agent-toolkit/v1alpha2`.
- Lines 32-34 schema path: change `asset-frontmatter.v1alpha1.json` → `asset-frontmatter.v1alpha2.json` (both the source-side path on line 32 and the destination-side filename on line 34).

- [ ] **Step 2: Update `commands/new.py` to emit v1alpha2 and add an `mcp` branch**

Read `src/agent_toolkit/commands/new.py` first. Then edit:

In `_KIND_LAYOUT` (line ~12), change the `mcp` entry to use `config.json` (matching walker reality, not `mcp.json`):

```python
_KIND_LAYOUT = {
    "skill": ("skills/{slug}/SKILL.md", "markdown"),
    "agent": ("agents/{slug}.md", "markdown"),
    "command": ("commands/{slug}.md", "markdown"),
    "hook": ("hooks/{slug}.meta.yaml", "yaml"),
    "mcp": ("mcps/{slug}/README.md", "mcp"),
    "plugin": ("plugins/{slug}/marketplace.json", "json"),
    "pi-extension": ("extensions/{slug}/extension.meta.yaml", "yaml"),
}
```

In `_FRONTMATTER_TEMPLATE` (line ~23), bump apiVersion to `v1alpha2`. The new template:

```python
_FRONTMATTER_TEMPLATE = """---
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: TODO write one sentence ending with a period.
  lifecycle: experimental
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
---

# {slug}

TODO body.
"""
```

In the YAML branch (line ~78), bump:

```python
        target.write_text(
            f"apiVersion: agent-toolkit/v1alpha2\n"
            ...
```

In the JSON branch (line ~95), bump apiVersion in the dict.

Add a new `mcp` branch **before** the markdown/yaml/json fork. Insert just before `if fmt == "markdown":`:

```python
    if fmt == "mcp":
        # Two files: README.md (frontmatter) and config.json (inner MCP config).
        target.write_text(
            "---\n"
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n"
            f"  name: {slug}\n"
            "  description: TODO write one sentence ending with a period.\n"
            "  lifecycle: experimental\n"
            "spec:\n"
            "  origin: third-party\n"
            "  vendored_via: none\n"
            "  upstream: https://TODO\n"
            "  harnesses:\n"
            "    - codex\n"
            "  mcp:\n"
            "    transport: stdio\n"
            "    install_method: npx\n"
            "---\n\n"
            f"# {slug}\n\n"
            "TODO body.\n"
        )
        # Sibling config.json carrying the inner MCP server config.
        config_path = target.parent / "config.json"
        config_path.write_text(
            json.dumps(
                {"type": "stdio", "command": "npx", "args": ["-y", f"@TODO/{slug}"]},
                indent=2,
            ) + "\n"
        )
        rel = target.relative_to(root)
        click.echo(f"created {rel}")
        click.echo(f"created {config_path.relative_to(root)}")
        summary(f"Created {rel}. Edit it, then run 'agent-toolkit check' to validate.")
        return
```

Then in the existing JSON branch, change `kind == "plugin"` test logic to check for the file format directly (the code already does — verify by reading). The existing structure stays intact for non-mcp kinds.

- [ ] **Step 3: Update `tests/test_new.py`**

Read it first. Bump any v1alpha1 strings to v1alpha2. Add a test for the new `mcp` branch:

```python
def test_new_mcp_writes_readme_and_config(tmp_path):
    from click.testing import CliRunner
    from agent_toolkit.cli import main

    (tmp_path / "schemas").mkdir()
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (tmp_path / ".agent-toolkit-source").write_text("")

    runner = CliRunner()
    result = runner.invoke(
        main, ["new", "mcp", "fake-mcp", "--toolkit-repo", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    readme = tmp_path / "mcps" / "fake-mcp" / "README.md"
    config = tmp_path / "mcps" / "fake-mcp" / "config.json"
    assert readme.is_file()
    assert config.is_file()
    assert "agent-toolkit/v1alpha2" in readme.read_text()
    assert "spec:" in readme.read_text() and "mcp:" in readme.read_text()
    assert '"command": "npx"' in config.read_text()
```

- [ ] **Step 4: Run all tests, expect green for fixture-bump tests**

Run: `uv run pytest tests/test_validator.py tests/test_check.py tests/test_walker.py tests/test_link_lib.py tests/test_new.py tests/test_inventory.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS for all tests except possibly tests that exercise CLI workflows whose stdout assertions reference Plan-A's "MCP install path for X not yet implemented" message — those are addressed in Tasks 7 and 9.

If anything else fails, the failure is missed v1alpha1 strings — re-run `grep -rln agent-toolkit/v1alpha1 src tests` and fix.

- [ ] **Step 6: Delete v1alpha1 schema files and force-include line**

```bash
rm src/agent_toolkit/_schemas/asset-frontmatter.v1alpha1.json
rm schemas/asset-frontmatter.v1alpha1.json
```

In `pyproject.toml`, delete the v1alpha1 line:

```toml
[tool.hatch.build.targets.wheel.force-include]
"src/agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json" = "agent_toolkit/_schemas/asset-frontmatter.v1alpha2.json"
```

- [ ] **Step 7: Confirm no v1alpha1 references remain**

Run:

```bash
grep -rn 'agent-toolkit/v1alpha1\|asset-frontmatter.v1alpha1' src tests pyproject.toml
```

Expected: no output.

- [ ] **Step 8: Run the full suite again**

Run: `uv run pytest -q`
Expected: PASS for all v1alpha2-migrated tests. CLI-link/unlink tests that pin Plan-A's "no-op" line are still pending; fix in later tasks.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(schema): migrate fixtures + new + ingest to v1alpha2; delete v1alpha1"
```

---

## Task 4: Adapter package skeleton — types, Protocols, registry

**Files:**
- Create: `src/agent_toolkit/harness_adapters/__init__.py`
- Create: `src/agent_toolkit/harness_adapters/base.py`
- Create: `src/agent_toolkit/harness_adapters/codex.py` (stub raising `NotImplementedError`)
- Create: `src/agent_toolkit/harness_adapters/claude.py` (UnimplementedAdapter)
- Create: `src/agent_toolkit/harness_adapters/opencode.py` (UnimplementedAdapter)
- Create: `src/agent_toolkit/harness_adapters/pi.py` (UnimplementedAdapter)
- Create: `tests/test_mcp_adapters_base.py`

This task lays out the package shape but ships only types, the registry, and the `UnimplementedAdapter` stub. Codex's full implementation lands in Task 5.

- [ ] **Step 1: Write failing test for the registry**

Create `tests/test_mcp_adapters_base.py`:

```python
"""Adapter registry + base types tests."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_get_adapter_returns_codex_adapter():
    from agent_toolkit.harness_adapters import get_adapter

    a = get_adapter("codex")
    assert a.name == "codex"
    assert a.strategy == "config_file"


def test_get_adapter_unknown_harness_raises():
    from agent_toolkit.harness_adapters import get_adapter

    with pytest.raises(ValueError, match="unknown harness"):
        get_adapter("nonexistent")


def test_get_adapter_returns_unimplemented_for_pending_harnesses():
    """Claude/OpenCode/Pi return UnimplementedAdapter until their PRs land."""
    from agent_toolkit.harness_adapters import get_adapter
    from agent_toolkit.harness_adapters.base import UnimplementedAdapter

    for h in ("claude", "opencode", "pi"):
        a = get_adapter(h)
        assert isinstance(a, UnimplementedAdapter), f"{h} should be UnimplementedAdapter"
        assert a.name == h


def test_unimplemented_adapter_skip_message():
    """UnimplementedAdapter exposes a stable message for the loud-skip path."""
    from agent_toolkit.harness_adapters.base import UnimplementedAdapter

    a = UnimplementedAdapter("claude")
    assert "claude" in a.skip_message()
    assert "not yet" in a.skip_message().lower() or "no MCP adapter" in a.skip_message()


def test_mcp_entry_dataclass_is_frozen():
    """McpEntry must be hashable (frozen) for set membership in callers."""
    from agent_toolkit.harness_adapters.base import McpEntry

    e1 = McpEntry(name="x", inner_config={"a": 1}, mcp_spec={"transport": "stdio"})
    with pytest.raises((AttributeError, Exception)):
        e1.name = "y"  # frozen


def test_write_action_carries_contents_for_writes():
    """WriteAction for create/update carries `contents` bytes; delete has None."""
    from agent_toolkit.harness_adapters.base import WriteAction

    a = WriteAction(
        path=Path("/tmp/x"), op="create", bytes_before=None, bytes_after=10,
        contents=b"hello world",
    )
    assert a.contents == b"hello world"

    d = WriteAction(
        path=Path("/tmp/x"), op="delete", bytes_before=10, bytes_after=None,
        contents=None,
    )
    assert d.contents is None


def test_cannot_install_is_exception():
    """CannotInstall is a regular exception."""
    from agent_toolkit.harness_adapters.base import CannotInstall

    with pytest.raises(CannotInstall, match="bad-mcp"):
        raise CannotInstall("bad-mcp: transport http unsupported")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_mcp_adapters_base.py -v`
Expected: FAIL — `agent_toolkit.harness_adapters` does not exist.

- [ ] **Step 3: Write `harness_adapters/base.py`**

Create `src/agent_toolkit/harness_adapters/base.py`:

```python
"""Base types and Protocols for harness MCP adapters.

Two strategy Protocols (PluginFolderAdapter, ConfigFileAdapter) plus a common
base. Adapters implement exactly one strategy.

See docs/superpowers/specs/2026-05-04-mcp-adapters-design.md § "Two Protocols"
for the rationale.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import IO, Literal, Protocol, runtime_checkable


Scope = Literal["user", "project"]


@dataclass(frozen=True)
class McpEntry:
    """One catalog MCP entry, ready for adapter consumption.

    `name` is the toolkit-repo directory name (the canonical id).
    `inner_config` is the verbatim parsed `mcps/<name>/config.json`.
    `mcp_spec` is the `spec.mcp` block from the sibling README.md frontmatter.
    """
    name: str
    inner_config: dict
    mcp_spec: dict


@dataclass(frozen=True)
class WriteAction:
    """Describes a single filesystem mutation produced by an adapter.

    Carries `contents` (rendered desired bytes) so the dispatcher can write
    atomically without re-rendering. None on `delete` (nothing to write).
    """
    path: Path
    op: Literal["create", "update", "delete", "unchanged"]
    bytes_before: int | None
    bytes_after: int | None
    contents: bytes | None


class CannotInstall(Exception):
    """Pre-flight refusal raised by adapter.can_install().

    Caller catches and skips the offending entry, proceeding with siblings.
    Matches the existing exception-raising pattern in the codebase
    (e.g. _yaml_edit.add_slug → ValueError, walker → yaml.YAMLError).
    """


@runtime_checkable
class PluginFolderAdapter(Protocol):
    """Strategy: own a folder outright (e.g. ~/.claude/plugins/agent-toolkit/)."""

    name: str
    strategy: Literal["plugin_folder"]

    def can_install(self, entry: McpEntry) -> None: ...
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]: ...
    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool: ...
    def plugin_target(self, scope: Scope, project_root: Path) -> Path: ...
    def render(self, entries: list[McpEntry]) -> dict[Path, bytes]: ...
    def diff(
        self, scope: Scope, project_root: Path, entries: list[McpEntry],
    ) -> list[WriteAction]: ...


@runtime_checkable
class ConfigFileAdapter(Protocol):
    """Strategy: surgically mutate a single named config file (round-trip)."""

    name: str
    strategy: Literal["config_file"]

    def can_install(self, entry: McpEntry) -> None: ...
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]: ...
    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool: ...
    def config_target(self, scope: Scope, project_root: Path) -> Path: ...
    def diff(
        self, scope: Scope, project_root: Path, entries: list[McpEntry],
    ) -> list[WriteAction]: ...


class UnimplementedAdapter:
    """Returned by `get_adapter()` for harnesses whose adapter has not landed.

    Loud-skip semantics: callers detect this via `isinstance(...,
    UnimplementedAdapter)` and print `skip_message()` before continuing.
    Currently used for claude/opencode/pi until CLI-PR-2/3/4 ship.
    """
    name: str
    strategy: Literal["unimplemented"] = "unimplemented"

    def __init__(self, name: str) -> None:
        self.name = name

    def skip_message(self) -> str:
        return f"no MCP adapter for harness {self.name} yet — skipping"
```

- [ ] **Step 4: Write each per-harness module stub**

Create `src/agent_toolkit/harness_adapters/codex.py`:

```python
"""Codex MCP adapter — ConfigFileAdapter against ~/.codex/config.toml.

Round-trip via tomlkit. Managed namespace: `[mcp_servers.<name>]` tables.
"""
from __future__ import annotations

# Implementation lands in Task 5. This stub keeps the import path stable.

class CodexAdapter:
    name = "codex"
    strategy = "config_file"

    def __init__(self) -> None:
        raise NotImplementedError(
            "CodexAdapter is implemented in plan task 5; do not instantiate yet"
        )
```

Create `src/agent_toolkit/harness_adapters/claude.py`:

```python
"""Claude MCP adapter — placeholder until CLI-PR-2 ships."""
# Intentionally empty. get_adapter("claude") returns UnimplementedAdapter.
```

Create `src/agent_toolkit/harness_adapters/opencode.py`:

```python
"""OpenCode MCP adapter — placeholder until CLI-PR-3 ships."""
# Intentionally empty. get_adapter("opencode") returns UnimplementedAdapter.
```

Create `src/agent_toolkit/harness_adapters/pi.py`:

```python
"""Pi MCP adapter — placeholder until CLI-PR-4 ships."""
# Intentionally empty. get_adapter("pi") returns UnimplementedAdapter.
```

- [ ] **Step 5: Write the registry in `__init__.py`**

Create `src/agent_toolkit/harness_adapters/__init__.py`:

```python
"""Registry: get_adapter(harness) → adapter instance.

Single entry point above the package; CLI commands and the TUI runner do not
import individual adapter modules.
"""
from __future__ import annotations

from agent_toolkit.harness_adapters.base import (
    CannotInstall,
    ConfigFileAdapter,
    McpEntry,
    PluginFolderAdapter,
    Scope,
    UnimplementedAdapter,
    WriteAction,
)


_KNOWN_HARNESSES: tuple[str, ...] = ("claude", "codex", "opencode", "pi")


def get_adapter(harness: str):
    """Return the adapter for `harness`.

    Raises ValueError on unknown harness names.
    Returns UnimplementedAdapter for known-but-pending harnesses.
    """
    if harness not in _KNOWN_HARNESSES:
        raise ValueError(f"unknown harness {harness!r}")
    if harness == "codex":
        # Lazy import so the dependency on tomlkit (and any future codex deps)
        # only loads when the codex adapter is actually requested.
        from agent_toolkit.harness_adapters.codex import CodexAdapter
        return CodexAdapter()
    return UnimplementedAdapter(harness)


__all__ = [
    "get_adapter",
    "McpEntry",
    "WriteAction",
    "CannotInstall",
    "Scope",
    "PluginFolderAdapter",
    "ConfigFileAdapter",
    "UnimplementedAdapter",
]
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_mcp_adapters_base.py -v`
Expected: most tests PASS, but `test_get_adapter_returns_codex_adapter` will FAIL because `CodexAdapter.__init__` raises `NotImplementedError`.

That's expected at this point (Task 5 implements Codex). Mark this test xfail temporarily:

In `tests/test_mcp_adapters_base.py`, add `@pytest.mark.xfail(reason="codex adapter implemented in task 5", strict=True)` above `test_get_adapter_returns_codex_adapter`.

Re-run: `uv run pytest tests/test_mcp_adapters_base.py -v`
Expected: PASS (with the xfail marked).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit/harness_adapters tests/test_mcp_adapters_base.py
git commit -m "feat(adapters): scaffold harness_adapters package + base Protocols + registry"
```

---

## Task 5: Codex adapter — full implementation

**Files:**
- Modify: `src/agent_toolkit/harness_adapters/codex.py` (replace stub)
- Test: `tests/test_mcp_adapters_codex.py`

The Codex adapter implements `ConfigFileAdapter`. It mutates `[mcp_servers.<name>]` tables in `~/.codex/config.toml` (user) or `<project>/.codex/config.toml` (project, only if dir exists). Round-trip via `tomlkit`. Refuses MCPs with `transport != "stdio"`.

- [ ] **Step 1: Write the failing test suite**

Create `tests/test_mcp_adapters_codex.py`:

```python
"""Codex adapter — ConfigFileAdapter against ~/.codex/config.toml."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def _make_entry(name: str = "context7", *, transport: str = "stdio",
                command: str = "npx", args: list[str] | None = None,
                env: dict[str, str] | None = None) -> "McpEntry":
    from agent_toolkit.harness_adapters.base import McpEntry

    inner: dict = {"command": command}
    if args is not None:
        inner["args"] = args
    if env is not None:
        inner["env"] = env
    return McpEntry(
        name=name,
        inner_config=inner,
        mcp_spec={"transport": transport, "install_method": "npx"},
    )


def test_codex_adapter_basic_attrs():
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    a = CodexAdapter()
    assert a.name == "codex"
    assert a.strategy == "config_file"


def test_codex_user_config_target(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexAdapter()
    assert a.config_target("user", tmp_path) == tmp_path / ".codex" / "config.toml"


def test_codex_project_config_target_requires_dir(tmp_path):
    """Project target only set when .codex/ exists in project_root."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    proj = tmp_path / "p"
    proj.mkdir()
    a = CodexAdapter()
    # No .codex/ → no target
    assert a.config_target("project", proj) is None
    # Create .codex/ → target appears
    (proj / ".codex").mkdir()
    assert a.config_target("project", proj) == proj / ".codex" / "config.toml"


def test_codex_can_install_accepts_stdio():
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    a = CodexAdapter()
    a.can_install(_make_entry(transport="stdio"))  # no exception


def test_codex_can_install_refuses_http():
    from agent_toolkit.harness_adapters.codex import CodexAdapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    a = CodexAdapter()
    with pytest.raises(CannotInstall, match="stdio"):
        a.can_install(_make_entry(transport="http"))


def test_codex_diff_creates_file_when_missing(monkeypatch, tmp_path):
    """No config.toml on disk → one create-action with rendered bytes."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    a = CodexAdapter()
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    actions = a.diff("user", tmp_path, [entry])
    assert len(actions) == 1
    act = actions[0]
    assert act.path == target
    assert act.op == "create"
    assert act.bytes_before is None
    assert act.bytes_after is not None
    assert b"[mcp_servers.context7]" in act.contents
    assert b'command = "npx"' in act.contents
    assert b'args = ["-y", "@upstash/context7-mcp"]' in act.contents


def test_codex_diff_updates_existing_file(monkeypatch, tmp_path):
    """Adding a new MCP to a file with existing content yields one update-action."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    target.write_text(
        "# Pre-existing.\n"
        "model_provider = \"openai\"\n"
        "\n"
        "[notice.x]\n"
        "y = 1\n"
    )
    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    actions = a.diff("user", tmp_path, [entry])
    assert len(actions) == 1
    act = actions[0]
    assert act.op == "update"
    assert act.bytes_before == len(target.read_bytes())
    # Pre-existing tables preserved.
    assert b"[notice.x]" in act.contents
    assert b'model_provider = "openai"' in act.contents
    assert b"[mcp_servers.context7]" in act.contents


def test_codex_diff_unchanged_when_aligned(monkeypatch, tmp_path):
    """If on-disk already matches the desired render, diff returns []."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()

    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    # First call: create. Apply by writing the rendered contents.
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    # Second call: should be empty.
    actions2 = a.diff("user", tmp_path, [entry])
    assert actions2 == []


def test_codex_unlink_removes_one_entry_preserving_siblings(monkeypatch, tmp_path):
    """unlink() = re-render with entry absent. Siblings remain byte-equal."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    target.write_text(
        "# Hand-rolled by user.\n"
        "model_provider = \"openai\"\n"
        "\n"
        "[mcp_servers.preexisting]\n"
        "command = \"node\"\n"
        "args = [\"./local-mcp.js\"]\n"
    )
    before = target.read_bytes()

    a = CodexAdapter()
    # Allow-list contains only context7 (newly link it).
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [link_act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(link_act.contents)
    after_link = target.read_bytes()
    assert b"[mcp_servers.context7]" in after_link
    assert b"[mcp_servers.preexisting]" in after_link  # AC #3: untouched

    # Now allow-list is empty (unlink). Diff with [] should produce one
    # update removing context7 only, preserving preexisting.
    actions = a.diff("user", tmp_path, [])
    assert len(actions) == 1
    act = actions[0]
    assert b"[mcp_servers.context7]" not in act.contents
    assert b"[mcp_servers.preexisting]" in act.contents


def test_codex_link_unlink_round_trip_byte_equal(monkeypatch, tmp_path):
    """AC #8: source with comments + unknown sections + hand-rolled MCP →
    link an unrelated MCP → unlink it → byte-equal to source.
    """
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    src = (
        b"# Codex config.\n"
        b"model_provider = \"openai\"\n"
        b"\n"
        b"[notice.model_migrations]\n"
        b"sonnet_4 = { migrated_at = \"2026-04-01\" }\n"
        b"\n"
        b"[tui.model_availability_nux]\n"
        b"shown = true\n"
        b"\n"
        b"[mcp_servers.preexisting]\n"
        b"command = \"node\"\n"
        b"args = [\"./local-mcp.js\"]\n"
    )
    target.write_bytes(src)

    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])

    # Link
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    # Unlink (allow-list now contains only the preexisting hand-rolled, which
    # this adapter doesn't manage — pass [] for managed entries).
    actions = a.diff("user", tmp_path, [])
    assert len(actions) == 1
    target.write_bytes(actions[0].contents)

    after = target.read_bytes()
    assert after == src, (
        "Round-trip is NOT byte-equal — adapter design assumes it is.\n"
        f"Length src={len(src)} after={len(after)}.\n"
    )


def test_codex_list_installed_returns_managed_entry_names(monkeypatch, tmp_path):
    """list_installed enumerates [mcp_servers.X] tables present in the file."""
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    target.write_text(
        "[mcp_servers.context7]\n"
        "command = \"npx\"\n"
        "\n"
        "[mcp_servers.preexisting]\n"
        "command = \"node\"\n"
    )
    a = CodexAdapter()
    assert a.list_installed("user", tmp_path) == {"context7", "preexisting"}


def test_codex_list_installed_missing_file_returns_empty(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    a = CodexAdapter()
    assert a.list_installed("user", tmp_path) == set()


def test_codex_entry_drift_false_when_aligned(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    assert a.entry_drift("user", tmp_path, entry) is False


def test_codex_entry_drift_true_after_hand_edit(monkeypatch, tmp_path):
    from agent_toolkit.harness_adapters.codex import CodexAdapter

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".codex" / "config.toml"
    target.parent.mkdir()
    a = CodexAdapter()
    entry = _make_entry(args=["-y", "@upstash/context7-mcp"])
    [act] = a.diff("user", tmp_path, [entry])
    target.write_bytes(act.contents)

    # User hand-edits the args array inside the managed entry.
    text = target.read_text().replace(
        '["-y", "@upstash/context7-mcp"]', '["-y", "@upstash/context7-mcp", "--debug"]'
    )
    target.write_text(text)

    assert a.entry_drift("user", tmp_path, entry) is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_mcp_adapters_codex.py -v`
Expected: FAIL — `CodexAdapter.__init__` raises `NotImplementedError`.

- [ ] **Step 3: Implement `CodexAdapter`**

Replace `src/agent_toolkit/harness_adapters/codex.py` entirely:

```python
"""Codex MCP adapter — ConfigFileAdapter against ~/.codex/config.toml.

Round-trip via tomlkit. Managed namespace: `[mcp_servers.<name>]` tables.
The adapter manages only the entries whose names appear in the allow-list;
sibling tables (notice/tui/whatever) are preserved byte-equal by tomlkit.

Refuses MCPs with `transport != "stdio"` — Codex MCP support is stdio-only.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import tomlkit
from tomlkit import TOMLDocument, table
from tomlkit.items import Table

from agent_toolkit.harness_adapters.base import (
    CannotInstall,
    McpEntry,
    Scope,
    WriteAction,
)


class CodexAdapter:
    name: str = "codex"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope == "user":
            home = Path(os.environ.get("HOME", ""))
            return home / ".codex" / "config.toml"
        # project: only if .codex/ exists
        codex_dir = project_root / ".codex"
        if not codex_dir.is_dir():
            return None
        return codex_dir / "config.toml"

    # ---- pre-flight ----
    def can_install(self, entry: McpEntry) -> None:
        transport = (entry.mcp_spec or {}).get("transport")
        if transport != "stdio":
            raise CannotInstall(
                f"{entry.name}: codex MCP support is stdio-only "
                f"(spec.mcp.transport={transport!r})"
            )

    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        servers = doc.get("mcp_servers")
        if not isinstance(servers, Table) and not isinstance(servers, dict):
            return set()
        return set(servers.keys())

    def entry_drift(self, scope: Scope, project_root: Path, entry: McpEntry) -> bool:
        """True iff the on-disk single entry differs from its template render.

        Implemented by rendering this single entry to a one-table doc, parsing
        the on-disk entry to a one-table doc, and comparing rendered bytes.
        """
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False  # no file → no drift question (caller handles via list_installed)
        doc = self._read(target)
        on_disk_table = doc.get("mcp_servers", {}).get(entry.name) if doc.get("mcp_servers") else None
        if on_disk_table is None:
            return False  # not installed → drift undefined; caller checks list_installed
        on_disk_doc = TOMLDocument()
        on_disk_servers = table()
        on_disk_servers.append(entry.name, on_disk_table)
        on_disk_doc.append("mcp_servers", on_disk_servers)
        on_disk_bytes = tomlkit.dumps(on_disk_doc).encode("utf-8")

        template_doc = TOMLDocument()
        template_servers = table()
        self._build_entry_table(template_servers, entry)
        template_doc.append("mcp_servers", template_servers)
        template_bytes = tomlkit.dumps(template_doc).encode("utf-8")

        return on_disk_bytes != template_bytes

    # ---- diff (the engine) ----
    def diff(
        self, scope: Scope, project_root: Path, entries: list[McpEntry],
    ) -> list[WriteAction]:
        target = self.config_target(scope, project_root)
        if target is None:
            return []  # no target dir; caller treats as no-op for this scope
        desired_names = {e.name for e in entries}

        if not target.is_file():
            # Render fresh from empty doc.
            new_doc = TOMLDocument()
            self._merge_entries(new_doc, entries, managed_names=set(), desired_names=desired_names)
            rendered = tomlkit.dumps(new_doc).encode("utf-8")
            return [WriteAction(
                path=target, op="create",
                bytes_before=None, bytes_after=len(rendered),
                contents=rendered,
            )]

        before_bytes = target.read_bytes()
        doc = self._read(target)
        managed_names = self._managed_names(doc, allowed=desired_names | self._existing_managed(doc, allowed_only=True))
        # Note: managed_names == every mcp_servers.* table we OWN, which by
        # spec is "every name in the allow-list". A name on disk we don't own
        # (hand-rolled, never allow-listed) is preserved.
        # _managed_names treats a name as ours iff it appears in `allowed`.
        # We therefore OWN: desired_names ∪ (existing entries we previously managed).
        # Since "previously managed" isn't tracked outside the allow-list, we treat
        # only desired_names as managed for upserts and removals.

        self._merge_entries(doc, entries, managed_names=desired_names, desired_names=desired_names)

        after_bytes = tomlkit.dumps(doc).encode("utf-8")
        if after_bytes == before_bytes:
            return []
        return [WriteAction(
            path=target, op="update",
            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
            contents=after_bytes,
        )]

    # ---- helpers ----
    @staticmethod
    def _read(path: Path) -> TOMLDocument:
        return tomlkit.parse(path.read_text(encoding="utf-8"))

    @staticmethod
    def _existing_managed(doc: TOMLDocument, *, allowed_only: bool) -> set[str]:
        servers = doc.get("mcp_servers")
        if servers is None:
            return set()
        return set(servers.keys())

    @staticmethod
    def _managed_names(doc: TOMLDocument, *, allowed: set[str]) -> set[str]:
        servers = doc.get("mcp_servers")
        if servers is None:
            return set()
        return {n for n in servers.keys() if n in allowed}

    def _merge_entries(
        self,
        doc: TOMLDocument,
        entries: list[McpEntry],
        *,
        managed_names: set[str],
        desired_names: set[str],
    ) -> None:
        """Mutate `doc` so its `[mcp_servers.X]` tables match the desired state.

        Removes managed entries no longer in `desired_names`, upserts entries
        in `entries`. Untouched: any `[mcp_servers.Y]` not in `managed_names`
        (= hand-rolled).
        """
        if "mcp_servers" not in doc:
            doc["mcp_servers"] = table()
        servers = doc["mcp_servers"]

        # Remove managed entries no longer desired.
        on_disk = list(servers.keys())
        for name in on_disk:
            if name in managed_names and name not in desired_names:
                del servers[name]

        # Upsert each desired entry.
        for entry in sorted(entries, key=lambda e: e.name):
            new_table = table()
            self._build_entry_table(new_table, entry)
            # Replace whole table so render is deterministic; tomlkit preserves
            # surrounding whitespace at the document level.
            servers[entry.name] = new_table

    @staticmethod
    def _build_entry_table(t: Table, entry: McpEntry) -> None:
        """Populate `t` with the inner-config translated to Codex shape."""
        cfg = entry.inner_config or {}
        # type: stdio is implicit in Codex; omit it.
        cmd = cfg.get("command")
        if cmd is None:
            raise CannotInstall(
                f"{entry.name}: inner_config.command missing — required for Codex"
            )
        t["command"] = cmd
        if "args" in cfg and cfg["args"]:
            t["args"] = list(cfg["args"])
        if "env" in cfg and cfg["env"]:
            env_dict = cfg["env"]
            if not isinstance(env_dict, dict):
                raise CannotInstall(
                    f"{entry.name}: inner_config.env must be a dict, got {type(env_dict).__name__}"
                )
            t["env"] = {str(k): str(v) for k, v in env_dict.items()}
```

- [ ] **Step 4: Remove the xfail marker from Task 4**

In `tests/test_mcp_adapters_base.py`, delete the `@pytest.mark.xfail(...)` line above `test_get_adapter_returns_codex_adapter`.

- [ ] **Step 5: Run all adapter tests**

Run: `uv run pytest tests/test_mcp_adapters_base.py tests/test_mcp_adapters_codex.py -v`
Expected: PASS for all tests.

If `test_codex_link_unlink_round_trip_byte_equal` FAILs:
- This is the AC #8 gate. Investigate the diff. Common causes:
  - tomlkit re-rendering an inline table without preserving its delimiter style.
  - Whitespace between top-level tables changing.
- If structural, document the limitation and adjust the test fixture (e.g. require a blank line before `[mcp_servers.preexisting]` in the source). If too lossy, escalate.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit/harness_adapters/codex.py tests/test_mcp_adapters_codex.py tests/test_mcp_adapters_base.py
git commit -m "feat(adapters): codex ConfigFileAdapter — tomlkit round-trip, AC#1-3,8"
```

---

## Task 6: Dispatcher — `apply_link`, atomic write, loud-print contract, `_build_mcp_entries`

**Files:**
- Create: `src/agent_toolkit/commands/_mcp_dispatch.py`
- Test: `tests/test_mcp_dispatch.py`

The dispatcher is the only code that **writes**. Adapters render bytes; the dispatcher writes bytes atomically and emits the loud-print lines.

- [ ] **Step 1: Write failing tests**

Create `tests/test_mcp_dispatch.py`:

```python
"""Dispatcher: apply_link orchestration, atomic write, loud-print contract."""
from __future__ import annotations

import io
import os
from pathlib import Path

import pytest


def _seed_mcp(toolkit_root: Path, slug: str = "context7", *,
              transport: str = "stdio", command: str = "npx",
              args: list[str] | None = None) -> None:
    mcp_dir = toolkit_root / "mcps" / slug
    mcp_dir.mkdir(parents=True, exist_ok=True)
    inner = {"type": transport, "command": command}
    if args:
        inner["args"] = args
    import json
    (mcp_dir / "config.json").write_text(json.dumps(inner) + "\n")
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        f"  name: {slug}\n"
        f"  description: {slug} mcp.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses:\n"
        "    - codex\n"
        "  mcp:\n"
        f"    transport: {transport}\n"
        "    install_method: npx\n"
        "---\n"
    )


def test_build_mcp_entries_resolves_slug_to_mcpentry(tmp_path):
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    assert len(entries) == 1
    e = entries[0]
    assert e.name == "context7"
    assert e.inner_config["command"] == "npx"
    assert e.mcp_spec["transport"] == "stdio"


def test_build_mcp_entries_skips_unknown_slug(tmp_path):
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries

    _seed_mcp(tmp_path, "context7")
    entries = _build_mcp_entries(tmp_path, ["context7", "does-not-exist"])
    assert len(entries) == 1
    assert entries[0].name == "context7"


def test_apply_link_dry_run_prints_would_op_no_write(monkeypatch, tmp_path):
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    target = tmp_path / ".codex" / "config.toml"

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")

    buf = io.StringIO()
    actions = apply_link(
        a, scope="user", project_root=tmp_path, entries=entries,
        dry_run=True, stdout=buf,
    )
    out = buf.getvalue()
    assert "would-create" in out
    assert str(target) in out
    assert not target.exists()
    assert len(actions) == 1
    assert actions[0].op == "create"


def test_apply_link_real_run_writes_atomically_and_prints_loud(monkeypatch, tmp_path):
    """Real run: writes bytes, prints `→ creating ...` then `✓ created ...`."""
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    target = tmp_path / ".codex" / "config.toml"

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")

    buf = io.StringIO()
    actions = apply_link(
        a, scope="user", project_root=tmp_path, entries=entries,
        dry_run=False, stdout=buf,
    )
    out = buf.getvalue()
    assert "→ creating" in out
    assert "✓ created" in out
    assert str(target) in out
    assert target.is_file()
    text = target.read_text()
    assert "[mcp_servers.context7]" in text
    assert len(actions) == 1
    assert actions[0].op == "create"


def test_apply_link_update_prints_byte_delta(monkeypatch, tmp_path):
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    target = tmp_path / ".codex" / "config.toml"
    target.write_text("model_provider = \"openai\"\n")

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")

    buf = io.StringIO()
    apply_link(a, scope="user", project_root=tmp_path, entries=entries,
               dry_run=False, stdout=buf)
    out = buf.getvalue()
    assert "→ updating" in out
    assert "✓ updated" in out
    # Print includes byte delta `(NB → MB)`.
    assert "→" in out


def test_apply_link_unchanged_prints_nothing(monkeypatch, tmp_path):
    """When already in sync, no pre/post print, no write."""
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()
    target = tmp_path / ".codex" / "config.toml"

    _seed_mcp(tmp_path, "context7", args=["-y", "@upstash/context7-mcp"])
    entries = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")

    # First run: create.
    buf1 = io.StringIO()
    apply_link(a, scope="user", project_root=tmp_path, entries=entries,
               dry_run=False, stdout=buf1)
    mtime_before = target.stat().st_mtime_ns

    # Second run: should be no-op.
    buf2 = io.StringIO()
    actions = apply_link(a, scope="user", project_root=tmp_path, entries=entries,
                         dry_run=False, stdout=buf2)
    assert buf2.getvalue() == ""
    assert actions == []
    assert target.stat().st_mtime_ns == mtime_before


def test_apply_link_raises_on_cannot_install(monkeypatch, tmp_path):
    """Adapter.can_install raising CannotInstall propagates up; caller (link.py)
    is responsible for catching to skip just the offending entry."""
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter
    from agent_toolkit.harness_adapters.base import CannotInstall

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".codex").mkdir()

    _seed_mcp(tmp_path, "bad-mcp", transport="http")
    entries = _build_mcp_entries(tmp_path, ["bad-mcp"])
    a = get_adapter("codex")

    buf = io.StringIO()
    with pytest.raises(CannotInstall, match="stdio"):
        apply_link(a, scope="user", project_root=tmp_path, entries=entries,
                   dry_run=False, stdout=buf)


def test_atomic_write_uses_same_directory_temp_file(monkeypatch, tmp_path):
    """Atomic-write helper writes to a temp file in target.parent then replaces."""
    from agent_toolkit.commands._mcp_dispatch import _atomic_write_bytes

    target = tmp_path / "out.toml"
    payload = b"hello\n"
    _atomic_write_bytes(target, payload)
    assert target.read_bytes() == payload
    # No temp file left behind.
    leftovers = [p for p in tmp_path.iterdir() if p.name != "out.toml"]
    assert leftovers == [], leftovers
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_mcp_dispatch.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement the dispatcher**

Create `src/agent_toolkit/commands/_mcp_dispatch.py`:

```python
"""Dispatcher: orchestrates adapter.diff() output into atomic writes + prints.

Single writer-of-truth for MCP adapter actions. CLI commands (link/unlink/fix)
flow through `apply_link`; the dispatcher handles dry-run, atomic writes, and
the loud-print contract.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import IO, Iterable

from agent_toolkit.harness_adapters.base import (
    CannotInstall,
    McpEntry,
    Scope,
    UnimplementedAdapter,
    WriteAction,
)
from agent_toolkit.walker import extract_frontmatter


def _build_mcp_entries(toolkit_root: Path, slugs: Iterable[str]) -> list[McpEntry]:
    """Resolve a list of slugs to McpEntry instances.

    Skips slugs whose `mcps/<slug>/{config.json, README.md}` are not both present.
    """
    entries: list[McpEntry] = []
    for slug in slugs:
        mcp_dir = toolkit_root / "mcps" / slug
        config_path = mcp_dir / "config.json"
        readme_path = mcp_dir / "README.md"
        if not config_path.is_file() or not readme_path.is_file():
            continue
        inner = json.loads(config_path.read_text())
        fm = extract_frontmatter(readme_path) or {}
        mcp_spec = ((fm.get("spec") or {}).get("mcp")) or {}
        entries.append(McpEntry(name=slug, inner_config=inner, mcp_spec=mcp_spec))
    return entries


def apply_link(
    adapter,
    *,
    scope: Scope,
    project_root: Path,
    entries: list[McpEntry],
    dry_run: bool,
    stdout: IO[str],
    force: bool = False,  # CLI-PR-2 wires this for Claude; ignored here.
) -> list[WriteAction]:
    """Reconcile adapter state to the desired entry set.

    Both `link` and `unlink` reduce to this single call; they differ only in
    how the allow-list YAML is mutated *before* the dispatch.

    For each entry, calls `adapter.can_install(entry)` first; CannotInstall
    propagates to the caller.

    In dry-run mode, prints `would-<op>: <path>` per non-`unchanged` action and
    makes no filesystem mutation.

    In real-run mode, writes bytes atomically and prints the op-specialised
    loud-print pair.
    """
    if isinstance(adapter, UnimplementedAdapter):
        # Should not be called for unimplemented adapters; the caller checks
        # first. If it slips through, no-op silently — the caller already
        # printed the skip message.
        return []

    # Pre-flight every entry. CannotInstall raises here; caller decides
    # whether to swallow per-entry or fail the batch.
    for entry in entries:
        adapter.can_install(entry)

    actions = adapter.diff(scope, project_root, entries)

    if dry_run:
        for act in actions:
            if act.op == "unchanged":
                continue
            print(f"would-{act.op}: {act.path}", file=stdout)
        return actions

    for act in actions:
        if act.op == "unchanged":
            continue
        _print_pre(act, stdout)
        _execute_action(act)
        _print_post(act, stdout)
    return actions


def _execute_action(act: WriteAction) -> None:
    if act.op in {"create", "update"}:
        if act.contents is None:
            raise RuntimeError(f"{act.op} action missing contents: {act.path}")
        _atomic_write_bytes(act.path, act.contents)
    elif act.op == "delete":
        try:
            act.path.unlink()
        except FileNotFoundError:
            pass
    elif act.op == "unchanged":
        return
    else:
        raise RuntimeError(f"unknown action op: {act.op}")


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomic write: same-directory temp file + os.replace.

    Same-directory staging guarantees atomicity across filesystems.
    Creates parent dirs if missing.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _print_pre(act: WriteAction, stdout: IO[str]) -> None:
    if act.op == "create":
        print(f"→ creating {act.path}", file=stdout)
    elif act.op == "update":
        print(f"→ updating {act.path}", file=stdout)
    elif act.op == "delete":
        print(f"→ deleting {act.path}", file=stdout)


def _print_post(act: WriteAction, stdout: IO[str]) -> None:
    if act.op == "create":
        print(f"✓ created {act.path} ({act.bytes_after}B)", file=stdout)
    elif act.op == "update":
        print(
            f"✓ updated {act.path} ({act.bytes_before}B → {act.bytes_after}B)",
            file=stdout,
        )
    elif act.op == "delete":
        print(f"✓ deleted {act.path} (was {act.bytes_before}B)", file=stdout)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_mcp_dispatch.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit/commands/_mcp_dispatch.py tests/test_mcp_dispatch.py
git commit -m "feat(mcp): dispatcher — apply_link, atomic write, loud-print contract"
```

---

## Task 7: Wire `_link_lib.project_from_file` to dispatch via `apply_link`

**Files:**
- Modify: `src/agent_toolkit/commands/_link_lib.py:212-223` (replace Plan-A no-op branch)
- Modify: `tests/test_link_lib.py` (replace Plan-A no-op test with adapter-dispatch tests)
- Modify: `tests/test_cli_link.py`, `tests/test_cli_unlink.py` (update assertions)

The Plan-A no-op site at `_link_lib.py:212-223` becomes the only spot where MCP dispatch is invoked. Both `link` (per-asset, --all, --plan) and `unlink` flow through `project_from_file`, so this single edit lights up MCPs across all four entry points.

For Codex (the working adapter), the no-op message becomes a real adapter call.
For Claude/OpenCode/Pi (UnimplementedAdapter), we print a loud skip and continue.

- [ ] **Step 1: Update Plan-A test in `test_link_lib.py`**

Read `tests/test_link_lib.py`. Find the `test_project_from_file_mcp_emits_no_op_message` test (was added in Plan A, Task 3). Replace it with this pair:

```python
def test_project_from_file_codex_mcp_dispatches_to_adapter(tmp_path, monkeypatch, capsys):
    """Codex + allow-listed MCP → adapter writes target file."""
    import io

    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".codex").mkdir(parents=True)

    toolkit_root = tmp_path / "toolkit"
    mcp_dir = toolkit_root / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: context7\n"
        "  description: c.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses:\n"
        "    - codex\n"
        "  mcp:\n"
        "    transport: stdio\n"
        "    install_method: npx\n"
        "---\n"
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    allowlist.write_text("mcps:\n  - context7\n")

    counters = LinkCounters()
    buf = io.StringIO()
    project_from_file(
        scope="user", harness="codex", toolkit_root=toolkit_root,
        project_root=project_root, allowlist_path=allowlist,
        dry_run=False, counters=counters, stdout=buf,
    )

    out = buf.getvalue()
    assert "→ creating" in out
    assert "✓ created" in out
    target = tmp_path / "home" / ".codex" / "config.toml"
    assert target.is_file()
    assert "[mcp_servers.context7]" in target.read_text()


def test_project_from_file_claude_mcp_skips_loudly(tmp_path, monkeypatch):
    """Claude + allow-listed MCP → loud skip, exit 0, no file written."""
    import io

    from agent_toolkit.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "home" / ".claude").mkdir(parents=True)

    toolkit_root = tmp_path / "toolkit"
    mcp_dir = toolkit_root / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: context7\n"
        "  description: c.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses:\n"
        "    - claude\n"
        "  mcp:\n"
        "    transport: stdio\n"
        "    install_method: npx\n"
        "---\n"
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    allowlist.write_text("mcps:\n  - context7\n")

    counters = LinkCounters()
    buf = io.StringIO()
    project_from_file(
        scope="user", harness="claude", toolkit_root=toolkit_root,
        project_root=project_root, allowlist_path=allowlist,
        dry_run=False, counters=counters, stdout=buf,
    )

    out = buf.getvalue()
    assert "no MCP adapter for harness claude yet — skipping" in out
    # Counters not bumped.
    assert counters.created == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_link_lib.py -v -k mcp`
Expected: FAIL — `_link_lib` still emits the Plan-A no-op message.

- [ ] **Step 3: Replace the Plan-A MCP branch in `_link_lib.project_from_file`**

In `src/agent_toolkit/commands/_link_lib.py`, at lines 211-223 the current branch is the Plan-A no-op:

```python
        if kind == "mcp":
            section = kind_to_section(kind)
            mcp_allowed_slugs = list(allowed.get(section, []))
            if not mcp_allowed_slugs:
                continue
            slugs_csv = ", ".join(mcp_allowed_slugs)
            print(
                f"MCP install path for {harness} not yet implemented; "
                f"allow-list updated only ({slugs_csv}).",
                file=stdout,
            )
            continue
```

Replace it with:

```python
        if kind == "mcp":
            section = kind_to_section(kind)
            mcp_allowed_slugs = list(allowed.get(section, []))
            if not mcp_allowed_slugs:
                continue
            from agent_toolkit.commands._mcp_dispatch import (
                _build_mcp_entries, apply_link,
            )
            from agent_toolkit.harness_adapters import get_adapter
            from agent_toolkit.harness_adapters.base import (
                CannotInstall, UnimplementedAdapter,
            )

            adapter = get_adapter(harness)
            if isinstance(adapter, UnimplementedAdapter):
                print(adapter.skip_message(), file=stdout)
                continue

            entries = _build_mcp_entries(toolkit_root, mcp_allowed_slugs)
            try:
                apply_link(
                    adapter, scope=scope, project_root=project_root,
                    entries=entries, dry_run=dry_run, stdout=stdout,
                )
            except CannotInstall as exc:
                # Per-entry refusal: print a warning and continue.
                # Future: split entries to skip only the offending one.
                print(f"warning: {exc}", file=stdout)
                continue
            continue
```

- [ ] **Step 4: Run unit tests**

Run: `uv run pytest tests/test_link_lib.py -v`
Expected: PASS for the new tests.

- [ ] **Step 5: Update `tests/test_cli_link.py` and `tests/test_cli_unlink.py`**

These pin Plan-A's "MCP install path for X not yet implemented" message. Find each occurrence:

```bash
grep -n "MCP install path" tests/test_cli_link.py tests/test_cli_unlink.py
```

For tests asserting the Plan-A message under harness=codex (or any harness), choose:
- For codex: assert that `"→ creating"` and `"[mcp_servers."` appear (real install).
- For claude/opencode/pi: assert `"no MCP adapter for harness <h> yet — skipping"`.

Read each test, then update its assertions accordingly. Keep the `mcps:` YAML mutation assertions — those remain valid.

If any test was harness-agnostic, split it into two: one for codex (working), one for claude (skip).

- [ ] **Step 6: Run the full CLI test suite**

Run: `uv run pytest tests/test_cli_link.py tests/test_cli_unlink.py -v -k mcp`
Expected: PASS.

Then: `uv run pytest -q`
Expected: PASS overall.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit/commands/_link_lib.py tests/test_link_lib.py tests/test_cli_link.py tests/test_cli_unlink.py
git commit -m "feat(mcp): wire link/unlink through harness adapter via apply_link"
```

---

## Task 8: Wire `diff` to surface MCP would-writes

**Files:**
- Modify: `src/agent_toolkit/commands/diff.py` (no change needed — `diff` is already an alias for `link --dry-run`)
- Test: `tests/test_cli_diff.py` — add MCP-specific assertions.

`commands/diff.py` is `link --dry-run`. With Task 7, `link --dry-run` already calls `apply_link(..., dry_run=True, ...)` which prints `would-<op>: <path>`. No code change in `diff.py` is needed — only verification that the output reads naturally.

The spec proposes a richer per-action format:

```
codex / user / mcp:
  ~ ~/.codex/config.toml (4521B → 4612B)
    +mcp_servers.context7
```

That's a "nice to have" but the AC #5 only requires "shows would-be changes per file, no writes". The current `would-<op>: <path>` line is sufficient for AC. We ship the simpler format and note the richer format as follow-up.

- [ ] **Step 1: Add a CLI test for MCP diff**

Read `tests/test_cli_diff.py`. Append:

```python
def test_diff_mcp_codex_shows_would_create(tmp_path, monkeypatch):
    """diff for an allow-listed MCP on codex prints would-create and writes nothing."""
    from click.testing import CliRunner
    from agent_toolkit.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    (toolkit / "schemas").mkdir(parents=True)
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["diff", "user", "codex",
         "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert result.exit_code == 0, result.output
    assert "would-create" in result.output
    target = home / ".codex" / "config.toml"
    assert not target.exists()
```

Place a `from pathlib import Path` import at the top of the file if not already present.

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_cli_diff.py -v -k mcp`
Expected: PASS (Task 7 already wired the dispatch via `link --dry-run`).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli_diff.py
git commit -m "test(diff): pin MCP would-create output for codex"
```

---

## Task 9: Replace `list`'s MCP "unsupported" overload with four-glyph status

**Files:**
- Modify: `src/agent_toolkit/commands/_list_json.py:160-179` (replace MCP branch)
- Modify: `src/agent_toolkit_tui/state.py` (extend `CellStatus` literal)
- Modify: `src/agent_toolkit_tui/widgets/asset_grid.py:13-18,116-249` (extend glyph map + interactivity rule)
- Modify: `tests/test_list_json.py` (update assertions)
- Modify: `tests/test_cli_list.py` (update assertions if any)

The four MCP statuses replace the Plan-A `"unsupported"` stand-in:

| Status | Glyph | Meaning |
|---|---|---|
| `linked-matches` | `[x]` | allow-listed AND installed AND no drift |
| `linked-drifted` | `[~]` | allow-listed AND installed AND drift |
| `unlinked-allowlisted` | `[ ]` | allow-listed AND not installed |
| `installed-not-allowlisted` | `[!]` | not allow-listed AND present in harness namespace |

Cells where the harness has no adapter (UnimplementedAdapter) keep `"unsupported"` — that's accurate.

- [ ] **Step 1: Write failing test**

In `tests/test_list_json.py`, find `test_list_json_includes_mcps` (added in Plan A). Replace it with this richer test (which also covers the four new statuses):

```python
def test_list_json_mcp_codex_linked_matches_after_link(tmp_path, monkeypatch):
    """After linking, the codex cell reports linked-matches with the target path."""
    import json
    from click.testing import CliRunner
    from agent_toolkit.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    (toolkit / "schemas").mkdir(parents=True)
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    # Before link: status should be unlinked-allowlisted.
    r1 = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    data1 = json.loads(r1.output)
    [mcp1] = [a for a in data1["assets"] if a["kind"] == "mcp"]
    user_codex_1 = next(c for c in mcp1["cells"]
                        if c["harness"] == "codex" and c["scope"] == "user")
    # YAML user allow-list is empty (project allow-list has it). user scope:
    # status should be unlinked-allowlisted iff allowlisted, else null/skip.
    # In this test, only project allow-lists context7, so user-scope cell is
    # not allowlisted nor installed.
    assert user_codex_1["status"] in {"unlinked-allowlisted", "unsupported"}

    # Link to user scope (so we can verify linked-matches there).
    rl = runner.invoke(
        main,
        ["link", "user", "codex", "mcp:context7",
         "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert rl.exit_code == 0, rl.output

    # After link: codex/user cell is linked-matches.
    r2 = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    data2 = json.loads(r2.output)
    [mcp2] = [a for a in data2["assets"] if a["kind"] == "mcp"]
    user_codex_2 = next(c for c in mcp2["cells"]
                        if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex_2["status"] == "linked-matches"
    target = home / ".codex" / "config.toml"
    assert user_codex_2["target"] == str(target)


def test_list_json_mcp_unlinked_allowlisted(tmp_path, monkeypatch):
    """Allow-listed but not installed → unlinked-allowlisted."""
    import json
    from click.testing import CliRunner
    from agent_toolkit.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    toolkit = tmp_path / "toolkit"
    (toolkit / "schemas").mkdir(parents=True)
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    r = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    data = json.loads(r.output)
    [mcp] = [a for a in data["assets"] if a["kind"] == "mcp"]
    user_codex = next(c for c in mcp["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "unlinked-allowlisted"
    assert user_codex["target"] is None


def test_list_json_mcp_installed_not_allowlisted(tmp_path, monkeypatch):
    """Hand-rolled entry in codex config but absent from allow-list → installed-not-allowlisted."""
    import json
    from click.testing import CliRunner
    from agent_toolkit.cli import main

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    target = home / ".codex" / "config.toml"
    target.write_text(
        "[mcp_servers.context7]\ncommand = \"node\"\nargs = [\"hand-rolled.js\"]\n"
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    (toolkit / "schemas").mkdir(parents=True)
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()

    runner = CliRunner()
    r = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    data = json.loads(r.output)
    [mcp] = [a for a in data["assets"] if a["kind"] == "mcp"]
    user_codex = next(c for c in mcp["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "installed-not-allowlisted"
    assert user_codex["target"] == str(target)


def test_list_json_mcp_claude_unsupported(tmp_path, monkeypatch):
    """Cells for harnesses with UnimplementedAdapter still report 'unsupported'."""
    import json
    from click.testing import CliRunner
    from agent_toolkit.cli import main

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    (toolkit / "schemas").mkdir(parents=True)
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    r = runner.invoke(
        main,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    data = json.loads(r.output)
    [mcp] = [a for a in data["assets"] if a["kind"] == "mcp"]
    user_claude = next(c for c in mcp["cells"]
                       if c["harness"] == "claude" and c["scope"] == "user")
    assert user_claude["status"] == "unsupported"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_list_json.py -v -k mcp`
Expected: FAIL — current code emits status=unsupported uniformly for MCPs.

- [ ] **Step 3: Replace the MCP branch in `_build_inventory`**

In `src/agent_toolkit/commands/_list_json.py`, find the MCP branch around lines 160-179. Replace it with adapter-aware status:

```python
            if asset.kind == "mcp":
                # Status comes from the per-harness adapter when available.
                # Cells for UnimplementedAdapter harnesses keep "unsupported".
                from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries  # noqa: PLC0415
                from agent_toolkit.harness_adapters import get_adapter  # noqa: PLC0415
                from agent_toolkit.harness_adapters.base import UnimplementedAdapter  # noqa: PLC0415

                adapter = get_adapter(h)
                if isinstance(adapter, UnimplementedAdapter):
                    cells.append({
                        "harness": h, "scope": "user",
                        "status": "unsupported", "target": None,
                        "allowlisted": user_allowlisted,
                    })
                    cells.append({
                        "harness": h, "scope": "project",
                        "status": "unsupported", "target": None,
                        "allowlisted": proj_allowlisted,
                    })
                    continue

                # Build the McpEntry for this slug once; pass to adapter.
                [entry] = _build_mcp_entries(toolkit_root, [asset.slug]) or [None]
                if entry is None:
                    cells.append({
                        "harness": h, "scope": "user",
                        "status": "unsupported", "target": None,
                        "allowlisted": user_allowlisted,
                    })
                    cells.append({
                        "harness": h, "scope": "project",
                        "status": "unsupported", "target": None,
                        "allowlisted": proj_allowlisted,
                    })
                    continue

                for scope, allowlisted in (
                    ("user", user_allowlisted),
                    ("project", proj_allowlisted),
                ):
                    installed_names = adapter.list_installed(scope, project_root)
                    is_installed = entry.name in installed_names
                    if not allowlisted:
                        if is_installed:
                            target_path = adapter.config_target(scope, project_root)
                            cells.append({
                                "harness": h, "scope": scope,
                                "status": "installed-not-allowlisted",
                                "target": str(target_path) if target_path else None,
                                "allowlisted": False,
                            })
                        else:
                            cells.append({
                                "harness": h, "scope": scope,
                                "status": "unsupported", "target": None,
                                "allowlisted": False,
                            })
                        continue
                    if not is_installed:
                        cells.append({
                            "harness": h, "scope": scope,
                            "status": "unlinked-allowlisted", "target": None,
                            "allowlisted": True,
                        })
                        continue
                    drifted = adapter.entry_drift(scope, project_root, entry)
                    target_path = adapter.config_target(scope, project_root)
                    cells.append({
                        "harness": h, "scope": scope,
                        "status": "linked-drifted" if drifted else "linked-matches",
                        "target": str(target_path) if target_path else None,
                        "allowlisted": True,
                    })
                continue
```

Notes:
- The status for "harness declares MCP support but adapter is unimplemented and slug is not allowlisted on either scope" is `unsupported`. This collapses into the same UI affordance as Plan-A and is semantically correct.
- `config_target` may return `None` (Codex project scope without `.codex/`); we handle that.

- [ ] **Step 4: Update TUI `state.py` literal**

In `src/agent_toolkit_tui/state.py`, replace:

```python
CellStatus = Literal["linked", "unlinked", "unsupported", "broken"]
```

with:

```python
CellStatus = Literal[
    "linked", "unlinked", "unsupported", "broken",
    "linked-matches", "linked-drifted", "unlinked-allowlisted", "installed-not-allowlisted",
]
```

- [ ] **Step 5: Update `asset_grid.py` glyph map and interactivity rule**

In `src/agent_toolkit_tui/widgets/asset_grid.py`, replace the `_GLYPH` dict:

```python
_GLYPH = {
    "linked":                     "☑",
    "unlinked":                   "☐",
    "unsupported":                "──",
    "broken":                     "⚠ ",
    # MCP four-glyph statuses:
    "linked-matches":             "☑",
    "linked-drifted":             "≁",
    "unlinked-allowlisted":       "☐",
    "installed-not-allowlisted":  "!",
}
```

Then update the interactivity rule. Read `asset_grid.py` lines 110-260 and find every check of `cell.status == "unsupported"` (line 116, 131, 174, etc.). For each, extend the predicate to:

```python
status_noninteractive = cell.status in {"unsupported", "installed-not-allowlisted"}
```

Specifically, update lines that look like:

```python
if cell is None or cell.status == "unsupported":
```

to:

```python
if cell is None or cell.status in {"unsupported", "installed-not-allowlisted"}:
```

There are three such sites in the current file (lines 116, 131, 174). Update all three.

For the toggle logic at lines 240-248, the predicates need to be widened similarly: linked-* and unlinked-* states behave like the two-state `linked`/`unlinked` for toggling. Specifically:

```python
                if op == "link" and cell.status in {"linked", "linked-matches"}:
                    continue
                if op == "unlink" and cell.status in {
                    "unlinked", "unsupported", "unlinked-allowlisted", "installed-not-allowlisted"
                }:
                    continue
```

Read the actual file before making this change to keep diffs minimal. Treat `linked-drifted` as "linkable but mark as needs reconcile" — i.e. allow link toggle on it; the dispatch will be a no-op if already in sync (which it isn't, by definition of drift) and a write otherwise.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_list_json.py tests/test_tui -v`
Expected: PASS for the new MCP-status tests; existing TUI tests should pass (the literal widening is additive).

If `test_asset_grid_glyphs.py` fails due to the new literals, update its expected glyph table to include the four new entries.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit/commands/_list_json.py src/agent_toolkit_tui/state.py src/agent_toolkit_tui/widgets/asset_grid.py tests/test_list_json.py tests/test_tui
git commit -m "feat(list): replace MCP unsupported overload with four-glyph status (linked-matches/drifted/unlinked-allowlisted/installed-not-allowlisted)"
```

---

## Task 10: `doctor` MCP group — drift, env-var presence, prerequisites, verify gate

**Files:**
- Create: `src/agent_toolkit/doctor/mcps.py`
- Modify: `src/agent_toolkit/commands/doctor.py:23,90-99` (register the group)
- Test: `tests/test_doctor_mcps.py`

The `mcps` group reports:
- **Drift**: `adapter.entry_drift(scope, project_root, entry) == True` for any allow-listed MCP → finding.
- **Env vars**: `spec.mcp.env` lists required vars; check `os.environ` for each → warn-only on missing.
- **Prerequisites**: `spec.mcp.prerequisites` lists CLI tools; `shutil.which(tool)` → warn on missing.
- **Verify**: `spec.mcp.verify` is a shell string. Only run if the user passed `--verify`. Default off (verify can run arbitrary shell).

This group reads-only — no writes.

- [ ] **Step 1: Write failing tests**

Create `tests/test_doctor_mcps.py`:

```python
"""Doctor mcps group: drift, env, prereq, verify."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def _seed_codex_with_mcp(home: Path, target_text: str) -> None:
    (home / ".codex").mkdir(parents=True, exist_ok=True)
    (home / ".codex" / "config.toml").write_text(target_text)


def _seed_toolkit_mcp(toolkit_root: Path, *, env: list[str] | None = None,
                      prerequisites: list[str] | None = None,
                      verify: str | None = None) -> None:
    mcp_dir = toolkit_root / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    extra = ""
    if env:
        items = "\n".join(f"      - {e}" for e in env)
        extra += f"    env:\n{items}\n"
    if prerequisites:
        items = "\n".join(f"      - {p}" for p in prerequisites)
        extra += f"    prerequisites:\n{items}\n"
    if verify:
        extra += f"    verify: {verify!r}\n"
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n"
        f"{extra}---\n"
    )


def test_doctor_mcps_ok_when_no_drift(monkeypatch, tmp_path):
    from agent_toolkit.doctor.mcps import run
    from agent_toolkit.doctor.result import Status

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_mcp(tmp_path)
    # Pre-populate the codex config with the canonical render.
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit.harness_adapters import get_adapter
    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir(parents=True, exist_ok=True)
    (home / ".codex" / "config.toml").write_bytes(act.contents)

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.OK


def test_doctor_mcps_warn_on_drift(monkeypatch, tmp_path):
    from agent_toolkit.doctor.mcps import run
    from agent_toolkit.doctor.result import Status

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_mcp(tmp_path)

    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit.harness_adapters import get_adapter
    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir(parents=True, exist_ok=True)
    target = home / ".codex" / "config.toml"
    target.write_bytes(act.contents)
    # Hand-edit to force drift.
    text = target.read_text().replace(
        '"@upstash/context7-mcp"', '"@upstash/context7-mcp", "--debug"'
    )
    target.write_text(text)

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status in {Status.WARN, Status.FAIL}
    assert any("drift" in f.lower() for f in result.findings)


def test_doctor_mcps_warn_on_missing_env(monkeypatch, tmp_path):
    from agent_toolkit.doctor.mcps import run
    from agent_toolkit.doctor.result import Status

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("CONTEXT7_API_KEY", raising=False)
    home = tmp_path / "home"
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_mcp(tmp_path, env=["CONTEXT7_API_KEY"])

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.WARN
    assert any("CONTEXT7_API_KEY" in f for f in result.findings)


def test_doctor_mcps_ok_when_env_present(monkeypatch, tmp_path):
    from agent_toolkit.doctor.mcps import run
    from agent_toolkit.doctor.result import Status

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("CONTEXT7_API_KEY", "x")
    home = tmp_path / "home"
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_mcp(tmp_path, env=["CONTEXT7_API_KEY"])

    # Pre-populate codex with canonical content (no drift).
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit.harness_adapters import get_adapter
    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir(parents=True, exist_ok=True)
    (home / ".codex" / "config.toml").write_bytes(act.contents)

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.OK


def test_doctor_mcps_warn_on_missing_prereq(monkeypatch, tmp_path):
    from agent_toolkit.doctor.mcps import run
    from agent_toolkit.doctor.result import Status

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_mcp(tmp_path, prerequisites=["definitelynotacommand_xyz"])

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.WARN
    assert any("definitelynotacommand_xyz" in f for f in result.findings)


def test_doctor_mcps_skips_unimplemented_harness(monkeypatch, tmp_path):
    """harness=claude → group reports OK with a 'no adapter' note (no writes attempted)."""
    from agent_toolkit.doctor.mcps import run
    from agent_toolkit.doctor.result import Status

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_mcp(tmp_path)

    result = run(toolkit_root=tmp_path, harness="claude", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.OK
    assert any("no MCP adapter" in f for f in result.findings)
```

- [ ] **Step 2: Implement `doctor/mcps.py`**

Create `src/agent_toolkit/doctor/mcps.py`:

```python
"""Doctor: mcps group — drift, env-var presence, prerequisites, optional verify."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from agent_toolkit._allowlist import read_allowlist
from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries
from agent_toolkit.doctor.result import GroupResult, Status
from agent_toolkit.harness_adapters import get_adapter
from agent_toolkit.harness_adapters.base import UnimplementedAdapter


def run(
    toolkit_root: Path,
    *,
    harness: str,
    scope: str,
    project_root: Path,
    run_verify: bool = False,
) -> GroupResult:
    """For each allow-listed MCP under (harness, scope):
       - structural drift (call adapter.entry_drift; True = drift finding)
       - env var presence in current shell (warn-only on missing required env)
       - prerequisites on PATH (warn on missing)
       - optional verify command (only with run_verify=True)
    """
    adapter = get_adapter(harness)
    findings: list[str] = []
    warnings: list[str] = []
    failures: list[str] = []

    if isinstance(adapter, UnimplementedAdapter):
        findings.append(f"no MCP adapter for harness {harness} yet — skipped")
        return GroupResult(
            name="mcps",
            status=Status.OK,
            summary=f"no adapter for {harness} yet",
            findings=findings,
        )

    if scope == "user":
        allowlist_path = Path(os.environ.get("HOME", "")) / ".agent-toolkit.yaml"
    else:
        allowlist_path = project_root / ".agent-toolkit.yaml"
    allowed = read_allowlist(allowlist_path).get("mcps", [])
    if not allowed:
        findings.append(f"no allow-listed MCPs for {harness}/{scope}")
        return GroupResult(
            name="mcps", status=Status.OK,
            summary="no MCPs allow-listed",
            findings=findings,
        )

    entries = _build_mcp_entries(toolkit_root, allowed)
    for entry in entries:
        installed_names = adapter.list_installed(scope, project_root)
        if entry.name not in installed_names:
            findings.append(f"{entry.name}: allow-listed but not installed (run `agent-toolkit link`)")
            continue
        if adapter.entry_drift(scope, project_root, entry):
            warnings.append(f"{entry.name}: drift — installed entry differs from template")
        else:
            findings.append(f"{entry.name}: installed and matches template")

        # env-var presence
        for var in (entry.mcp_spec or {}).get("env") or []:
            if not os.environ.get(var):
                warnings.append(f"{entry.name}: required env {var!s} not set")

        # prerequisites on PATH
        for tool in (entry.mcp_spec or {}).get("prerequisites") or []:
            if shutil.which(tool) is None:
                warnings.append(f"{entry.name}: prerequisite {tool!s} not on PATH")

        # verify gate (opt-in)
        verify = (entry.mcp_spec or {}).get("verify")
        if verify and run_verify:
            import subprocess
            proc = subprocess.run(verify, shell=True, capture_output=True, text=True)
            if proc.returncode == 0:
                findings.append(f"{entry.name}: verify exited 0")
            else:
                warnings.append(
                    f"{entry.name}: verify exited {proc.returncode}: {proc.stderr.strip()[:200]}"
                )

    if failures:
        status = Status.FAIL
    elif warnings:
        status = Status.WARN
    else:
        status = Status.OK
    return GroupResult(
        name="mcps",
        status=status,
        summary=f"{len(entries)} MCPs checked, {len(warnings)} warnings, {len(failures)} failures",
        findings=findings + warnings + failures,
    )
```

- [ ] **Step 3: Register the `mcps` group in `commands/doctor.py`**

In `src/agent_toolkit/commands/doctor.py`, edit `_GROUPS` (line 23):

```python
_GROUPS = (
    "environment", "symlink-integrity", "conventions", "submodule-health",
    "frontmatter", "duplicates", "harness-homes", "allowlist-audit", "mcps",
)
```

In `_run_global` (line 90-99), append the runner:

```python
def _run_global(root: Path, *, harness: str, group_name: str | None) -> list[GroupResult]:
    from agent_toolkit.doctor import mcps as g_mcps  # noqa: PLC0415
    runners: list[tuple[str, callable]] = [
        ("environment", lambda: g_environment.run(root)),
        ("symlink-integrity", lambda: g_symlinks.run(root, harness=harness)),
        ("conventions", lambda: g_conventions.run(root, harness=harness)),
        ("submodule-health", lambda: g_submodules.run(root)),
        ("frontmatter", lambda: g_frontmatter.run(root)),
        ("duplicates", lambda: g_duplicates.run(root)),
        ("harness-homes", lambda: g_harness_homes.run()),
        ("allowlist-audit", lambda: g_allowlist_audit.run(root, project_root=Path.cwd())),
        ("mcps", lambda: g_mcps.run(root, harness=harness, scope="user", project_root=Path.cwd())),
    ]
    if group_name:
        runners = [(n, fn) for (n, fn) in runners if n == group_name]
    return [fn() for (_n, fn) in runners]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_doctor_mcps.py tests/test_doctor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit/doctor/mcps.py src/agent_toolkit/commands/doctor.py tests/test_doctor_mcps.py
git commit -m "feat(doctor): add mcps group — drift, env, prereq, verify"
```

---

## Task 11: `fix` — MCP reconcile path

**Files:**
- Modify: `src/agent_toolkit/commands/fix.py`
- Test: `tests/test_fix.py`

The current `fix` regenerates AGENTS.md auto-regions. Per spec, `fix` also reconciles MCP drift to canonical form. Approach: keep the existing region-regen behaviour as the default; add a new `--mcps` flag (or run by default if `--only` is unset) that invokes the dispatch reconcile path for every allow-listed MCP under `(harness, scope)`.

To avoid a UX regression, run **both** by default: regenerate AGENTS.md regions **and** reconcile MCPs. Tests pin both behaviours.

- [ ] **Step 1: Write failing test**

Append to `tests/test_fix.py`:

```python
def test_fix_reconciles_mcp_drift(tmp_path, monkeypatch):
    """fix reconciles drifted codex MCP entries to canonical form."""
    from click.testing import CliRunner
    from agent_toolkit.cli import main
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit.harness_adapters import get_adapter

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    # Seed toolkit + AGENTS.md (so existing fix path doesn't fail).
    _seed_repo(tmp_path)  # from test_fix.py existing helper
    mcp_dir = tmp_path / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    # Install via adapter then drift.
    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir(parents=True, exist_ok=True)
    target = home / ".codex" / "config.toml"
    target.write_bytes(act.contents)
    text = target.read_text().replace(
        '"@upstash/context7-mcp"', '"@upstash/context7-mcp", "--debug"'
    )
    target.write_text(text)
    assert a.entry_drift("user", tmp_path, entry) is True

    runner = CliRunner()
    result = runner.invoke(
        main, ["fix", "--toolkit-repo", str(tmp_path), "--harness", "codex", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    # After fix, no drift.
    assert a.entry_drift("user", tmp_path, entry) is False


def test_fix_skips_unimplemented_harness(tmp_path, monkeypatch):
    """fix --harness claude prints skip and does not error."""
    from click.testing import CliRunner
    from agent_toolkit.cli import main

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    home = tmp_path / "home"
    home.mkdir()
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    _seed_repo(tmp_path)
    mcp_dir = tmp_path / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["fix", "--toolkit-repo", str(tmp_path), "--harness", "claude", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    assert "no MCP adapter for harness claude yet" in result.output
```

Note: `_seed_repo` is the existing helper in `test_fix.py` from Plan A — bump its frontmatter strings to v1alpha2 in Task 3 if not already done.

- [ ] **Step 2: Add `--harness` and `--scope` flags + MCP-reconcile path to `fix.py`**

Edit `src/agent_toolkit/commands/fix.py`. Read it first. Then modify:

Add `--harness` and `--scope` options; after the existing region-regen block, add a reconcile pass:

```python
@click.option("--harness", type=click.Choice(["claude", "codex", "opencode", "pi"]), default="codex",
              help="Harness for MCP reconcile (default: codex).")
@click.option("--scope", type=click.Choice(["user", "project"]), default="user",
              help="Scope for MCP reconcile (default: user).")
@click.option("--mcps-only", is_flag=True, default=False,
              help="Skip AGENTS.md region regen; reconcile MCPs only.")
@click.pass_context
def fix(ctx, toolkit_root, only, to_stdout, harness, scope, mcps_only):
    ...
```

Then in the body, **before** the `header(...)` call:

```python
def fix(ctx, toolkit_root, only, to_stdout, harness, scope, mcps_only):
    # ... existing toolkit_root resolution unchanged ...

    if not mcps_only:
        # Existing AGENTS.md region regen (unchanged from Plan A).
        ... existing block ...

    # MCP reconcile pass: only if not --to-stdout (which is region-only).
    if not to_stdout:
        _reconcile_mcps(toolkit_root, harness=harness, scope=scope, project_root=Path.cwd())
```

Add the `_reconcile_mcps` helper at the bottom of the file:

```python
def _reconcile_mcps(toolkit_root: Path, *, harness: str, scope: str,
                    project_root: Path) -> None:
    """For each allow-listed MCP, run apply_link to bring on-disk → canonical."""
    import sys
    from agent_toolkit._allowlist import read_allowlist
    from agent_toolkit.commands._mcp_dispatch import _build_mcp_entries, apply_link
    from agent_toolkit.harness_adapters import get_adapter
    from agent_toolkit.harness_adapters.base import CannotInstall, UnimplementedAdapter

    if scope == "user":
        allowlist_path = Path(os.environ.get("HOME", "")) / ".agent-toolkit.yaml"
    else:
        allowlist_path = project_root / ".agent-toolkit.yaml"
    if not allowlist_path.is_file():
        return
    allowed = read_allowlist(allowlist_path).get("mcps", [])
    if not allowed:
        return

    adapter = get_adapter(harness)
    if isinstance(adapter, UnimplementedAdapter):
        click.echo(adapter.skip_message())
        return

    entries = _build_mcp_entries(toolkit_root, allowed)

    # Diff-first to preserve mtime when nothing changed.
    actions = adapter.diff(scope, project_root, entries)
    nontrivial = [a for a in actions if a.op != "unchanged"]
    if not nontrivial:
        return

    try:
        apply_link(
            adapter, scope=scope, project_root=project_root,
            entries=entries, dry_run=False, stdout=sys.stdout,
        )
    except CannotInstall as exc:
        click.echo(f"warning: {exc}", err=True)
```

Add `import os` at the top of `fix.py` if not present.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/test_fix.py -v`
Expected: PASS for all tests in this file.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit/commands/fix.py tests/test_fix.py
git commit -m "feat(fix): reconcile MCP drift via apply_link (preserves AGENTS.md region regen)"
```

---

## Task 12: TUI integration test — round-trip via runner.link_plan

**Files:**
- Create: `tests/test_tui_mcp_integration.py`

This test satisfies AC #10: TUI reads via `_list_json` and writes via `runner.link_plan`/`unlink_plan`. No adapter imports inside the TUI package.

- [ ] **Step 1: Write the integration test**

Create `tests/test_tui_mcp_integration.py`:

```python
"""TUI integration test: link_plan → list_state shows linked-matches.

Exercises the full CLI subprocess + adapter pipeline to verify the TUI's
write path doesn't bypass the adapter (AC #10).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def tui_env(tmp_path, monkeypatch):
    if shutil.which("agent-toolkit") is None:
        pytest.skip("agent-toolkit CLI not on PATH; run `uv sync` then `uv run pip install -e .`")

    home = tmp_path / "home"
    home.mkdir()
    (home / ".codex").mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    (toolkit / "schemas").mkdir(parents=True)
    src_schema = Path(__file__).parent.parent / "schemas" / "asset-frontmatter.v1alpha2.json"
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(src_schema.read_text())
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    return {"home": home, "toolkit": toolkit, "project": project}


def test_tui_runner_link_plan_then_list_state_codex(tui_env, monkeypatch):
    """runner.link_plan(scope=user, harness=codex, mcp:context7) → list_state shows linked-matches."""
    from agent_toolkit_tui.runner import CLIRunner

    monkeypatch.chdir(tui_env["project"])
    runner = CLIRunner(tui_env["toolkit"])

    # Allow-list and link via plan.
    plan = runner.link_plan(
        scope="user", harness="codex", entries=[("mcp", "context7")],
    )
    assert plan.failed == 0, plan.errors
    assert plan.ok == 1

    # Re-read state; codex/user cell for context7 is linked-matches.
    state = runner.list_state()
    mcps = [a for a in state["assets"] if a["kind"] == "mcp"]
    assert len(mcps) == 1
    user_codex = next(c for c in mcps[0]["cells"]
                      if c["harness"] == "codex" and c["scope"] == "user")
    assert user_codex["status"] == "linked-matches"

    # Unlink round-trip.
    plan2 = runner.unlink_plan(
        scope="user", harness="codex", entries=[("mcp", "context7")],
    )
    assert plan2.failed == 0, plan2.errors

    state2 = runner.list_state()
    mcps2 = [a for a in state2["assets"] if a["kind"] == "mcp"]
    user_codex2 = next(c for c in mcps2[0]["cells"]
                       if c["harness"] == "codex" and c["scope"] == "user")
    # After unlink: not allow-listed, not installed → unsupported (per Task 9 rules)
    # OR `unlinked-allowlisted` if allow-listed remained. The plan removes it.
    assert user_codex2["status"] in {"unsupported", "unlinked-allowlisted"}


def test_tui_package_does_not_import_adapters():
    """TUI must not import any harness_adapter module directly."""
    import importlib
    import pkgutil

    import agent_toolkit_tui  # noqa: F401
    forbidden = "agent_toolkit.harness_adapters"
    for finder, name, ispkg in pkgutil.walk_packages(
        path=Path(agent_toolkit_tui.__file__).parent.__fspath__(),
        prefix="agent_toolkit_tui.",
    ):
        mod = importlib.import_module(name)
        src = Path(mod.__file__ or "").read_text() if mod.__file__ else ""
        assert forbidden not in src, (
            f"{name} imports {forbidden} — TUI must go through CLIRunner only"
        )
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_tui_mcp_integration.py -v`

Expected: PASS for `test_tui_runner_link_plan_then_list_state_codex` (skipped if `agent-toolkit` not on PATH — install with `uv pip install -e .` first). PASS for `test_tui_package_does_not_import_adapters`.

If skipped, verify install:

```bash
uv pip install -e .
uv run pytest tests/test_tui_mcp_integration.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/test_tui_mcp_integration.py
git commit -m "test(tui): integration round-trip codex MCP via CLIRunner (AC#10)"
```

---

## Task 13: Smoke-test against a real toolkit checkout

**Files:** None modified. This is a manual smoke that verifies the v1alpha2 catalog interop.

- [ ] **Step 1: Verify schema/catalog readiness**

Run:

```bash
ls ~/GitHub/agent-toolkit/mcps/ | head -5
head -20 ~/GitHub/agent-toolkit/mcps/context7/README.md 2>/dev/null || echo "no context7 mcp"
```

If the catalog has not yet been migrated to v1alpha2, the smoke will fail at `check`. **That's expected** until the catalog PR lands. Skip Step 2 in that case and document.

If the catalog **has** been migrated (the catalog PR landed before this CLI PR per spec sequencing), proceed.

- [ ] **Step 2: Smoke `check` against the real catalog**

Run:

```bash
uv run agent-toolkit --toolkit-repo ~/GitHub/agent-toolkit check --exit-code
```

Expected: exit 0.

If FAIL, the catalog and CLI are out of sync. Verify the catalog has v1alpha2 frontmatter:

```bash
grep -l 'agent-toolkit/v1alpha1' ~/GitHub/agent-toolkit/mcps/*/README.md | head -5
```

If non-empty, the catalog is stale; coordinate with the catalog PR.

- [ ] **Step 3: Smoke link / list / diff / fix against a synthetic project**

```bash
mkdir -p /tmp/agent-toolkit-mcp-smoke/project
cd /tmp/agent-toolkit-mcp-smoke/project

# Clean any prior smoke.
rm -f ~/.agent-toolkit.yaml.bak
[ -f ~/.agent-toolkit.yaml ] && cp ~/.agent-toolkit.yaml ~/.agent-toolkit.yaml.bak
[ -f ~/.codex/config.toml ] && cp ~/.codex/config.toml ~/.codex/config.toml.bak

uv run agent-toolkit link user codex mcp:context7
uv run agent-toolkit list --format json | python -c "
import sys, json
data = json.load(sys.stdin)
for a in data['assets']:
    if a['kind'] == 'mcp' and a['slug'] == 'context7':
        for c in a['cells']:
            if c['harness'] == 'codex' and c['scope'] == 'user':
                print('STATUS:', c['status'], 'TARGET:', c['target'])
"
```

Expected output: `STATUS: linked-matches TARGET: /Users/<you>/.codex/config.toml`

```bash
uv run agent-toolkit diff user codex
```

Expected: no `would-create` for context7 (already linked, in sync).

```bash
uv run agent-toolkit unlink user codex mcp:context7
grep mcp_servers.context7 ~/.codex/config.toml || echo "(removed)"
```

Expected: `(removed)`.

- [ ] **Step 4: Restore backups**

```bash
[ -f ~/.agent-toolkit.yaml.bak ] && mv ~/.agent-toolkit.yaml.bak ~/.agent-toolkit.yaml
[ -f ~/.codex/config.toml.bak ] && mv ~/.codex/config.toml.bak ~/.codex/config.toml
```

- [ ] **Step 5: Commit (no changes; just confirm clean working tree)**

```bash
git status
```

Expected: clean tree (the smoke is read-only on the repo).

---

## Task 14: Documentation update

**Files:**
- Modify: `docs/agent-toolkit/cli.md` (extend MCP section with adapter status)
- Modify: `README.md` (note Codex adapter shipped, others pending)

- [ ] **Step 1: Read current docs to find the MCP section**

```bash
grep -n "MCP\|mcp" docs/agent-toolkit/cli.md README.md | head -20
```

- [ ] **Step 2: Update `docs/agent-toolkit/cli.md`**

Replace the Plan-A MCP paragraph (search for "MCP install path for"). The new paragraph:

```markdown
### MCPs

`mcp:<name>` is recognised the same as other kinds. The allow-list YAML is
updated under the `mcps:` section, then the harness adapter writes the
appropriate config:

| Harness | Status (this release) | Target |
|---|---|---|
| `codex` | ✓ implemented | `~/.codex/config.toml` (user), `<project>/.codex/config.toml` (project, only if `.codex/` exists) |
| `claude`, `opencode`, `pi` | not yet — `link`/`unlink` print a loud skip message | — |

For `codex`, `link` mutates `[mcp_servers.<name>]` tables via a round-trip
`tomlkit` parse, preserving every other section, comment, and key order. The
adapter refuses MCPs whose `spec.mcp.transport` is not `stdio`.

The four-glyph status appears in `list`:

| Glyph | Meaning |
|---|---|
| `[x]` (`linked-matches`) | allow-listed, installed, no drift |
| `[~]` (`linked-drifted`) | allow-listed, installed, structural drift |
| `[ ]` (`unlinked-allowlisted`) | allow-listed, not installed (run `link`) |
| `[!]` (`installed-not-allowlisted`) | hand-rolled — never touched by this CLI |

`agent-toolkit doctor --group mcps --harness codex` reports drift, missing
required env vars, missing prerequisites on `$PATH`, and (with `--verify`)
runs the optional verify command.

`agent-toolkit fix --harness codex --scope user` reconciles drift.
```

- [ ] **Step 3: Update `README.md`**

Find the MCP note (added in Plan A). Replace with:

```markdown
- **MCPs** (Codex shipped; Claude / OpenCode / Pi pending follow-up PRs).
  `link mcp:<name>` writes `[mcp_servers.<name>]` to `~/.codex/config.toml`
  via a round-trip parser; sibling sections and comments are preserved.
  The four-glyph status `[x] [~] [ ] [!]` appears in `list`.
```

- [ ] **Step 4: Commit**

```bash
git add docs/agent-toolkit/cli.md README.md
git commit -m "docs(mcp): document adapter status, four-glyph list, doctor/fix"
```

---

## Task 15: Final sweep + green tests

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS for all tests.

If any fixture-bump tests still fail, re-run:

```bash
grep -rln 'agent-toolkit/v1alpha1\|asset-frontmatter.v1alpha1' src tests
```

Expected: no output. Fix any stragglers.

- [ ] **Step 2: Lint and type-check (if available)**

```bash
uv run ruff check src tests 2>/dev/null || echo "ruff not configured"
uv run mypy src 2>/dev/null || echo "mypy not configured"
```

If either tool is configured for the repo and reports issues, fix them. Otherwise skip.

- [ ] **Step 3: Final commit if any tweaks**

```bash
git status
```

If clean, no commit. If dirty, commit with a focused message.

---

## Plan Self-Review Checklist

The following spec requirements from `docs/superpowers/specs/2026-05-04-mcp-adapters-design.md` are addressed:

- [x] Schema bump v1alpha1 → v1alpha2 (full replacement) — Tasks 1–3.
- [x] Adapter package layout (`harness_adapters/`) — Tasks 4–5.
- [x] Two Protocols (`PluginFolderAdapter`, `ConfigFileAdapter`) — Task 4.
- [x] `McpEntry`, `WriteAction`, `CannotInstall`, `Scope` types — Task 4.
- [x] Codex adapter (`tomlkit`, refuses `transport != stdio`) — Task 5.
- [x] `apply_link` dispatcher + atomic write + loud-print contract — Task 6.
- [x] `_link_lib.project_from_file` MCP branch replaced with adapter dispatch — Task 7.
- [x] `link` / `unlink` use the same dispatch (allow-list mutation differs) — Task 7.
- [x] `--dry-run` prints `would-<op>: <path>` — Task 6 + 8.
- [x] `--force` flag declared in `apply_link` signature; lit up in CLI-PR-2 — Task 6 (signature only).
- [x] `diff` surfaces MCP would-writes — Task 8.
- [x] `list` four-glyph status — Task 9.
- [x] `installed-not-allowlisted` (`[!]`) detection — Task 9.
- [x] `entry_drift` per-entry semantics for `list` and `doctor` — Task 5 + 10.
- [x] `doctor --group mcps` (drift, env, prereq, verify) — Task 10.
- [x] `fix` MCP reconcile — Task 11.
- [x] TUI integration (no adapter imports) — Task 9 (state literal) + Task 12 (test).
- [x] `new mcp <slug>` scaffold function — Task 3 step 2.
- [x] Claude / OpenCode / Pi loud-skip via `UnimplementedAdapter` — Task 4.

**AC coverage from spec § Acceptance criteria (Codex satisfies #1–#8):**

- AC #1 (`link` installs without secrets): Task 7. Codex adapter writes `[mcp_servers.<name>]`; secret env-vars are emitted as keys, not values.
- AC #2 (re-run byte-identical): Task 5 (`test_codex_diff_unchanged_when_aligned`).
- AC #3 (unlink leaves siblings byte-equal): Task 5 (`test_codex_unlink_removes_one_entry_preserving_siblings`).
- AC #4 (`list` four-glyph): Task 9.
- AC #5 (`diff` shows would-be changes, no writes): Task 8.
- AC #6 (`doctor` reports drift + warns env/prereq): Task 10.
- AC #7 (`fix` reconciles drift): Task 11.
- AC #8 (round-trip byte-equal): Task 5 (`test_codex_link_unlink_round_trip_byte_equal`).
- AC #9 (v1alpha2 schema, no v1alpha1 leftover): Task 3 (`grep` confirms zero matches).
- AC #10 (TUI uses `_list_json` reads + `runner.link_plan` writes; no adapter imports): Task 12.

**Type/name consistency check:**
- `McpEntry` (singular) — Task 4 base.py; consumed by `_build_mcp_entries` (Task 6), `apply_link` (Task 6), `CodexAdapter.diff` (Task 5), `doctor.mcps.run` (Task 10).
- `WriteAction` — Task 4; produced by `adapter.diff()`, consumed by `apply_link` and tests.
- `CannotInstall` — Task 4; raised by `CodexAdapter.can_install` (Task 5), caught in `_link_lib` (Task 7) and `fix._reconcile_mcps` (Task 11).
- `apply_link` — Task 6; called from `_link_lib.project_from_file` (Task 7), `fix._reconcile_mcps` (Task 11), and tested directly in `test_mcp_dispatch.py` (Task 6).
- `get_adapter(harness)` — Task 4; called from `_link_lib` (Task 7), `_list_json` (Task 9), `doctor/mcps` (Task 10), `fix` (Task 11).
- `_build_mcp_entries(toolkit_root, slugs)` — Task 6; called from `_link_lib` (Task 7), `_list_json` (Task 9), `doctor/mcps` (Task 10), `fix` (Task 11).
- `UnimplementedAdapter.skip_message()` — Task 4; printed in `_link_lib` (Task 7), `doctor/mcps` (Task 10), `fix` (Task 11).
- Status literals in CLI JSON match the TUI's `CellStatus`: `linked-matches`, `linked-drifted`, `unlinked-allowlisted`, `installed-not-allowlisted` (Tasks 9 in both directions).
- `config_target(scope, project_root)` returns `Path | None` (None when project scope's `.codex/` doesn't exist) — handled in Task 5 (`CodexAdapter`) and Task 9 (`_list_json` MCP branch).

**No placeholders.** Every step carries actual code/commands. The single "TBD" earmark — `_render_*` helpers — is a no-op: this plan does not introduce them.

**Bite-sized:** Each task averages 5–10 small steps; each step is 2–5 minutes of editing or one targeted test run.

**TDD:** Every code task starts with a failing test (Task 0–12). The dispatch (Task 6) and Codex adapter (Task 5) drive their implementations test-first.

**Frequent commits:** 16 commits (one per task ×15 + Task 0), each with a single coherent purpose.
