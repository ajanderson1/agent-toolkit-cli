# claude/plugin asset kind Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `(claude, plugin)` from a broken `symlink` mechanism into a working `config_file` adapter that mutates `~/.claude/plugins/installed_plugins.json` and `~/.claude/plugins/known_marketplaces.json`. All other harnesses stay `unsupported (by design)`.

**Architecture:** New `ConfigFileAdapter`-shaped adapter at `harness_adapters/claude_plugin.py`, modelled on `codex.py`. Uses a new `PluginEntry` dataclass in `harness_adapters/base.py`. Schema gains a `kind: plugin` branch with required `spec.source.{marketplace,marketplaceSource,plugin,version}`. Sidecar metadata location moves to `plugins/<slug>.toolkit.yaml` (legacy inline `agent_toolkit_cli` JSON block in `plugin.json` kept as a deprecation fall-back). Existing symlink-aware code branches for `plugin` get removed.

**Tech Stack:** Python 3.13, JSON Schema draft 2020-12, `json` stdlib (round-trip), `pytest`. Mirrors the Codex MCP adapter's `tomlkit` discipline but for JSON.

---

## File Structure

**Create:**
- `src/agent_toolkit_cli/harness_adapters/claude_plugin.py` — the new adapter
- `tests/test_claude_plugin_adapter.py` — unit tests for the adapter
- `tests/integration/test_plugin_link_cycle.py` — integration cycle (or bats equivalent if `tests/integration/` uses bats; current repo uses pytest, so this is pytest)
- `tests/fixtures/plugin_sidecars/superpowers.toolkit.yaml` — fixture sidecar
- `tests/fixtures/plugin_sidecars/example-pinned.toolkit.yaml` — fixture sidecar for version-pinning tests

**Modify:**
- `schemas/asset-frontmatter.v1alpha2.json` — add `spec.source` + `kind: plugin` conditional
- `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json` — mirror (parity-checked by `schema-vendor-check` lefthook)
- `src/agent_toolkit_cli/harness_adapters/base.py` — add `PluginEntry` dataclass
- `src/agent_toolkit_cli/harness_adapters/__init__.py` — register `claude_plugin` adapter
- `src/agent_toolkit_cli/_support.py:33,52` — remove `(claude, plugin)` rows from `_USER_TARGETS`/`_PROJECT_TARGETS`
- `src/agent_toolkit_cli/walker.py:240-260` — add sidecar discovery for `plugins/*.toolkit.yaml`; keep legacy `.claude-plugin/*.json` walker behind a "legacy" flag with one-time warning
- `src/agent_toolkit_cli/walker.py:340-348` — `load_asset_record` reads sidecar OR legacy inline JSON
- `src/agent_toolkit_cli/schema.py:71` — plugin sidecar validation branch
- `src/agent_toolkit_cli/commands/_link_lib.py:300,322` — remove symlink branches for `kind == "plugin"`; route to adapter
- `src/agent_toolkit_cli/commands/_list_json.py:38` — plugin status reads adapter state
- `src/agent_toolkit_cli/doctor/symlinks.py:193` — replace symlink-aware plugin check with adapter-driven check
- `docs/agent-toolkit/harness-matrix.md` — `(claude, plugin)` cell + "Why … by design" prose
- `docs/agent-toolkit/cli.md` — plugin paragraph under Asset kinds
- `docs/agent-toolkit/schema.md` — `kind: plugin` shape example
- `README.md` — one-line note
- `AGENTS.md` — Asset identity § add plugin sidecar rule
- `tests/test_harness_matrix.py` — parity rows for new cell text
- `tests/test_walker.py` — sidecar discovery + legacy fall-back + mutex
- `tests/test_schema.py` — sidecar branch + legacy shape continues to validate

**Each file has a single clear responsibility:** adapter logic in `claude_plugin.py`, types in `base.py`, dispatch in `__init__.py`, discovery in `walker.py`, validation in `schema.py`, linker dispatch in `_link_lib.py`. No cross-contamination.

---

## Plan-phase-0: resolve open items (spike + decide)

Before any task that writes adapter code, resolve the four open items the spec flagged.

### Task 0a: JSON-write style spike

**Files:**
- Scratch script: `/tmp/plan_phase_0/json_roundtrip.py` (delete after)

- [ ] **Step 1: Sample a real `installed_plugins.json` and `known_marketplaces.json`**

```bash
mkdir -p /tmp/plan_phase_0
cp ~/.claude/plugins/installed_plugins.json /tmp/plan_phase_0/sample-installed.json
cp ~/.claude/plugins/known_marketplaces.json /tmp/plan_phase_0/sample-marketplaces.json
```

If either file is absent on this machine, generate a minimal example by hand (the issue body has both schemas in full).

- [ ] **Step 2: Round-trip with several JSON-write styles**

```python
# /tmp/plan_phase_0/json_roundtrip.py
import json, pathlib

for name in ("sample-installed.json", "sample-marketplaces.json"):
    src = pathlib.Path("/tmp/plan_phase_0") / name
    text = src.read_text()
    obj = json.loads(text)
    for indent, sort_keys, label in [
        (2, False, "indent=2 sort=False"),
        (2, True,  "indent=2 sort=True"),
        (4, False, "indent=4 sort=False"),
    ]:
        rendered = json.dumps(obj, indent=indent, sort_keys=sort_keys)
        # Add Claude's trailing-newline convention if needed
        rendered_nl = rendered + "\n"
        match_no_nl = rendered == text
        match_nl    = rendered_nl == text
        print(f"{name:40s} {label:25s} match={match_no_nl} match+nl={match_nl}")
```

Run: `python /tmp/plan_phase_0/json_roundtrip.py`

- [ ] **Step 3: Record the decision in the plan**

Edit this plan and replace this paragraph in Task 4 (the adapter):
> JSON-write style: `<chosen-style>` (decided in plan-phase-0 against real Claude-written files).

Lean before spiking: `json.dumps(obj, indent=2)` + trailing `"\n"`, ordering preserved (no `sort_keys=True`). If the spike shows Claude writes with a different style we adopt it byte-for-byte.

- [ ] **Step 4: Clean up**

```bash
rm -rf /tmp/plan_phase_0
```

### Task 0b: Sidecar path layout — flat or nested?

- [ ] **Step 1: Inspect the existing `mcps/` layout in the toolkit repo**

```bash
ls ~/GitHub/agent-toolkit/mcps/ | head -20
```

`mcps/` uses **nested** directories (`mcps/<slug>/<slug>.toolkit.yaml` plus `config.json`) per `walker.py`. Plugins have no inner content to wrap, so a nested dir is empty.

- [ ] **Step 2: Decision**

**Flat** wins for plugins because there is no inner content. Sidecars live at `plugins/<slug>.toolkit.yaml` directly. This matches "sidecar-only" — no inner directory needed.

Edit this plan, Task 2 (walker discovery), to use `plugins/*.toolkit.yaml` as the glob pattern.

### Task 0c: `version: "latest"` write semantics

- [ ] **Step 1: Inspect what Claude writes when a new entry appears with no explicit version**

If you have an installed plugin on disk, check `installed_plugins.json` for its `version` field. If it's present and non-empty, Claude always writes a concrete version after first launch.

- [ ] **Step 2: Decision (codified)**

- Adapter writes `"version": "latest"` for **new** entries when the sidecar says `"latest"`. Claude replaces it on first start with the concrete cloned version.
- Adapter **never updates** the `version` field on an **existing** entry when the sidecar says `"latest"` (so a sidecar saying "latest" doesn't drag a stable pinned install back to floating).
- Sidecar pinned (`"5.1.0"`): adapter writes the exact value for new entries; for existing entries, force-write iff the recorded version differs.

This is what the spec already says; plan-phase-0 just confirms by inspection.

### Task 0d: Two-file `config_file` Protocol shape

- [ ] **Step 1: Decide whether to introduce a new mechanism label**

Options:
- **A. Keep `config_file`** strategy label; document in adapter docstring that this particular adapter writes to two files. The `ConfigFileAdapter` Protocol's `config_target()` returns the **primary** path (`installed_prefs.json`) and `diff()` emits `WriteAction`s for both paths.
- **B. Introduce `config_file+config_file`** label, parallel to `config_file+folder`. New Protocol `MultiConfigFileAdapter`.

**Decision: A.** The dispatcher only cares about the list of `WriteAction`s coming out of `diff()`. The Protocol's `config_target()` is informational (used by `doctor`); a single path is fine if `doctor` is taught to also check the secondary file. This keeps the type system simple and avoids a new label that the matrix doc would need to explain.

- [ ] **Step 2: Apply the decision**

Adapter `claude_plugin.py`:
- `name = "claude"`, `strategy = "config_file"` (the existing literal).
- `config_target()` returns `~/.claude/plugins/installed_plugins.json` (primary).
- Add adapter-private `marketplaces_target()` returning `~/.claude/plugins/known_marketplaces.json`. Not on the Protocol; just a helper.
- `diff()` emits one or two `WriteAction`s — one per touched file.

### Task 0e: Commit plan-phase-0 decisions

- [ ] **Step 1: Commit the updated plan with the four resolutions baked in**

```bash
git add docs/superpowers/plans/2026-05-20-claude-plugin-asset-kind.md
git commit -m "docs(plan): resolve phase-0 open items for #149"
```

---

## Task 1: Schema — add `kind: plugin` sidecar branch

**Files:**
- Modify: `schemas/asset-frontmatter.v1alpha2.json`
- Modify: `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json` (mirror)
- Create: `tests/fixtures/plugin_sidecars/superpowers.toolkit.yaml`
- Modify: `tests/test_schema.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_schema.py`:

```python
def test_plugin_sidecar_validates():
    """A well-formed plugin sidecar passes schema validation."""
    from agent_toolkit_cli.schema import validate
    doc = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "superpowers",
            "description": "TDD, debugging, brainstorming, plan-writing.",
            "kind": "plugin",
            "lifecycle": "stable",
        },
        "spec": {
            "origin": "third-party",
            "upstream": "https://github.com/anthropics/claude-plugins-official",
            "vendored_via": "none",
            "harnesses": ["claude"],
            "source": {
                "marketplace": "claude-plugins-official",
                "marketplaceSource": {
                    "type": "git",
                    "url": "https://github.com/anthropics/claude-plugins-official.git",
                },
                "plugin": "superpowers",
                "version": "latest",
            },
        },
    }
    errors = validate(doc)
    assert errors == [], errors


def test_plugin_sidecar_requires_source():
    """A plugin sidecar without spec.source fails validation."""
    from agent_toolkit_cli.schema import validate
    doc = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "superpowers",
            "description": "Missing source.",
            "kind": "plugin",
            "lifecycle": "stable",
        },
        "spec": {
            "origin": "third-party",
            "upstream": "https://github.com/anthropics/claude-plugins-official",
            "vendored_via": "none",
            "harnesses": ["claude"],
        },
    }
    errors = validate(doc)
    assert errors, "expected at least one error about missing spec.source"


def test_plugin_sidecar_harnesses_must_be_claude_only():
    """spec.harnesses must include claude and nothing else for plugin kind."""
    from agent_toolkit_cli.schema import validate
    doc = {
        "apiVersion": "agent-toolkit/v1alpha2",
        "metadata": {
            "name": "x",
            "description": "Wrong harnesses.",
            "kind": "plugin",
            "lifecycle": "stable",
        },
        "spec": {
            "origin": "first-party",
            "vendored_via": "none",
            "harnesses": ["claude", "codex"],
            "source": {
                "marketplace": "m",
                "marketplaceSource": {"type": "git", "url": "https://example.com/m.git"},
                "plugin": "x",
                "version": "latest",
            },
        },
    }
    errors = validate(doc)
    assert errors, "expected error: plugin harnesses must equal [claude]"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_schema.py -k plugin_sidecar -v`
Expected: 3 FAIL (schema doesn't know about `kind: plugin` sidecars yet)

- [ ] **Step 3: Update both schema copies — add `spec.source`**

In **both** `schemas/asset-frontmatter.v1alpha2.json` and `src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json`, edit `spec.properties` to add `source`:

```json
"source": {
  "type": "object",
  "required": ["marketplace", "marketplaceSource", "plugin", "version"],
  "additionalProperties": false,
  "properties": {
    "marketplace": { "type": "string", "minLength": 1 },
    "marketplaceSource": {
      "type": "object",
      "required": ["type"],
      "additionalProperties": false,
      "properties": {
        "type":  { "enum": ["git", "github", "directory"] },
        "url":   { "type": "string", "format": "uri" },
        "repo":  { "type": "string", "pattern": "^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$" },
        "path":  { "type": "string" }
      },
      "allOf": [
        { "if": { "properties": { "type": { "const": "git" } } },       "then": { "required": ["url"] } },
        { "if": { "properties": { "type": { "const": "github" } } },    "then": { "required": ["repo"] } },
        { "if": { "properties": { "type": { "const": "directory" } } }, "then": { "required": ["path"] } }
      ]
    },
    "plugin":  { "type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$" },
    "version": { "type": "string", "minLength": 1 }
  }
}
```

- [ ] **Step 4: Add the kind-conditional `allOf` entries**

In the top-level `allOf` of **both** schema files, append:

```json
{
  "if": {
    "properties": { "metadata": { "properties": { "kind": { "const": "plugin" } }, "required": ["kind"] } },
    "required": ["metadata"]
  },
  "then": {
    "properties": {
      "spec": {
        "required": ["source"],
        "properties": {
          "harnesses": {
            "type": "array",
            "minItems": 1,
            "maxItems": 1,
            "items": { "const": "claude" }
          }
        }
      }
    }
  }
},
{
  "if": {
    "properties": { "metadata": { "properties": { "kind": { "not": { "const": "plugin" } } } } }
  },
  "then": { "properties": { "spec": { "not": { "required": ["source"] } } } }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_schema.py -k plugin_sidecar -v`
Expected: 3 PASS

- [ ] **Step 6: Create the fixture sidecar**

`tests/fixtures/plugin_sidecars/superpowers.toolkit.yaml`:

```yaml
apiVersion: agent-toolkit/v1alpha2
metadata:
  name: superpowers
  description: TDD, debugging, brainstorming, plan-writing.
  kind: plugin
  lifecycle: stable
spec:
  origin: third-party
  upstream: https://github.com/anthropics/claude-plugins-official
  vendored_via: none
  harnesses: [claude]
  source:
    marketplace: claude-plugins-official
    marketplaceSource:
      type: git
      url: https://github.com/anthropics/claude-plugins-official.git
    plugin: superpowers
    version: latest
```

Also create `tests/fixtures/plugin_sidecars/example-pinned.toolkit.yaml` (same shape with `version: 5.1.0` and `plugin: example-pinned`).

- [ ] **Step 7: Run full schema test suite**

Run: `uv run pytest tests/test_schema.py -v`
Expected: all PASS. Verifies the new branch doesn't break existing skill/agent/mcp/hook validation.

- [ ] **Step 8: Run the schema-vendor-check pre-commit hook manually**

```bash
diff schemas/asset-frontmatter.v1alpha2.json src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json
```

Expected: no output (files identical).

- [ ] **Step 9: Commit**

```bash
git add schemas/asset-frontmatter.v1alpha2.json \
        src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json \
        tests/test_schema.py \
        tests/fixtures/plugin_sidecars/
git commit -m "feat(schema): add kind: plugin sidecar branch with spec.source (#149)"
```

---

## Task 2: Walker — discover `plugins/*.toolkit.yaml` sidecars

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py:240-260` (plugin discovery)
- Modify: `src/agent_toolkit_cli/walker.py:340-348` (`load_asset_record` for plugin)
- Modify: `tests/test_walker.py`

- [ ] **Step 1: Read the current plugin discovery code**

```bash
sed -n '230,265p' src/agent_toolkit_cli/walker.py
```

- [ ] **Step 2: Write failing tests for sidecar discovery**

Add to `tests/test_walker.py`:

```python
def test_walker_discovers_plugin_sidecar(tmp_path):
    """plugins/<slug>.toolkit.yaml is discovered as a plugin asset."""
    from agent_toolkit_cli.walker import walk_assets
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    sidecar = plugins_dir / "superpowers.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: superpowers\n"
        "  description: x.\n"
        "  kind: plugin\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  upstream: https://example.com\n"
        "  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "  source:\n"
        "    marketplace: m\n"
        "    marketplaceSource: {type: git, url: https://example.com/m.git}\n"
        "    plugin: superpowers\n"
        "    version: latest\n"
    )
    assets = walk_assets(tmp_path)
    slugs = [a.slug for a in assets if a.kind == "plugin"]
    assert slugs == ["superpowers"], f"got {slugs}"


def test_walker_rejects_sidecar_plus_legacy_block(tmp_path):
    """Mutex: a sidecar AND a legacy plugin.json for the same slug raises."""
    from agent_toolkit_cli.walker import walk_assets
    plugins_dir = tmp_path / "plugins"
    (plugins_dir / "superpowers" / ".claude-plugin").mkdir(parents=True)
    (plugins_dir / "superpowers" / ".claude-plugin" / "plugin.json").write_text(
        '{"agent_toolkit_cli": {"apiVersion": "agent-toolkit/v1alpha2"}}'
    )
    (plugins_dir / "superpowers.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\nmetadata: {name: superpowers, kind: plugin}\n"
    )
    import pytest
    with pytest.raises(ValueError, match="both sidecar and inline"):
        walk_assets(tmp_path)


def test_walker_legacy_inline_block_still_discovered(tmp_path):
    """Legacy plugin.json with agent_toolkit_cli block still works (deprecation window)."""
    from agent_toolkit_cli.walker import walk_assets
    plugins_dir = tmp_path / "plugins"
    (plugins_dir / "atomic-agents" / ".claude-plugin").mkdir(parents=True)
    (plugins_dir / "atomic-agents" / ".claude-plugin" / "plugin.json").write_text(
        '{"agent_toolkit_cli": {"apiVersion": "agent-toolkit/v1alpha2", '
        '"metadata": {"name": "atomic-agents", "kind": "plugin"}}}'
    )
    assets = walk_assets(tmp_path)
    slugs = [a.slug for a in assets if a.kind == "plugin"]
    assert slugs == ["atomic-agents"], f"got {slugs}"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_walker.py -k plugin -v`
Expected: 3 FAIL (sidecar walker doesn't exist).

- [ ] **Step 4: Add the sidecar walker**

Edit `src/agent_toolkit_cli/walker.py` around lines 240–260. Replace the body of the plugin-discovery helper with:

```python
def _discover_plugins(toolkit_root: Path, submodule_paths: list[Path]) -> list[Asset]:
    """Discover plugin assets.

    Canonical layout: ``plugins/<slug>.toolkit.yaml`` (sidecar-only).
    Legacy layout:    ``plugins/<slug>/.claude-plugin/{plugin,marketplace}.json``
                      with an inline ``agent_toolkit_cli`` block.

    Mutex: if both forms exist for the same slug, raise ``ValueError``.
    """
    import yaml as _yaml
    plugin_root = toolkit_root / "plugins"
    if not plugin_root.exists():
        return []
    assets: dict[str, Asset] = {}

    # Pass 1: sidecars (canonical).
    for sidecar in sorted(plugin_root.glob("*.toolkit.yaml")):
        if _path_is_inside_submodule(sidecar, toolkit_root, submodule_paths):
            continue
        slug = sidecar.name.removesuffix(".toolkit.yaml")
        if not slug:
            continue
        try:
            doc = _yaml.safe_load(sidecar.read_text()) or {}
        except _yaml.YAMLError:
            continue
        if (doc.get("metadata") or {}).get("kind") != "plugin":
            continue
        assets[slug] = Asset(kind="plugin", slug=slug, path=sidecar)

    # Pass 2: legacy inline blocks (deprecation fall-back).
    for claude_dir in sorted(plugin_root.rglob(".claude-plugin")):
        if not claude_dir.is_dir():
            continue
        if _path_is_inside_submodule(claude_dir, toolkit_root, submodule_paths):
            continue
        slug = claude_dir.parent.name
        if not slug:
            continue
        for filename in _PLUGIN_FILENAMES:
            path = claude_dir / filename
            if path.is_file():
                if slug in assets:
                    raise ValueError(
                        f"plugin {slug!r}: both sidecar and inline agent_toolkit_cli "
                        f"block present — remove one (see AGENTS.md § Asset identity)"
                    )
                assets[slug] = Asset(kind="plugin", slug=slug, path=path)
                break
    return list(assets.values())
```

Replace the old plugin-discovery call site (look for `for claude_dir in sorted(plugin_root.rglob(".claude-plugin"))`) with a call to `_discover_plugins(toolkit_root, submodule_paths)`.

- [ ] **Step 5: Update `load_asset_record` to read sidecar OR legacy**

Edit `src/agent_toolkit_cli/walker.py` around line 340. Replace the `elif asset.kind == "plugin":` branch:

```python
elif asset.kind == "plugin":
    if asset.path.name.endswith(".toolkit.yaml"):
        metadata = yaml.safe_load(asset.path.read_text()) or {}
    else:
        doc = _json.loads(asset.path.read_text())
        metadata = doc.get("agent_toolkit_cli") or {}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_walker.py -k plugin -v`
Expected: 3 PASS.

- [ ] **Step 7: Run the whole walker test suite**

Run: `uv run pytest tests/test_walker.py -v`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit_cli/walker.py tests/test_walker.py
git commit -m "feat(walker): discover plugin sidecars; keep legacy inline-block fall-back (#149)"
```

---

## Task 3: `PluginEntry` dataclass in adapter base

**Files:**
- Modify: `src/agent_toolkit_cli/harness_adapters/base.py`
- Modify: `tests/test_harness_adapters_base.py` (or create if absent)

- [ ] **Step 1: Write the failing test**

Add (or create file with) the following to `tests/test_harness_adapters_base.py`:

```python
def test_plugin_entry_carries_source_fields():
    from agent_toolkit_cli.harness_adapters.base import PluginEntry
    entry = PluginEntry(
        name="superpowers",
        marketplace="claude-plugins-official",
        marketplace_source={"type": "git", "url": "https://x.example/y.git"},
        plugin="superpowers",
        version="latest",
    )
    assert entry.name == "superpowers"
    assert entry.marketplace == "claude-plugins-official"
    assert entry.marketplace_source["type"] == "git"
    assert entry.plugin == "superpowers"
    assert entry.version == "latest"


def test_plugin_entry_is_frozen():
    """Adapter entries are immutable, consistent with McpEntry."""
    from agent_toolkit_cli.harness_adapters.base import PluginEntry
    import dataclasses
    entry = PluginEntry(
        name="x", marketplace="m",
        marketplace_source={"type": "git", "url": "https://x.example/m.git"},
        plugin="x", version="latest",
    )
    import pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        entry.name = "y"  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_harness_adapters_base.py -k plugin_entry -v`
Expected: 2 FAIL (no `PluginEntry`).

- [ ] **Step 3: Add `PluginEntry` to `base.py`**

Edit `src/agent_toolkit_cli/harness_adapters/base.py`. After the `HookEntry` dataclass:

```python
@dataclass(frozen=True)
class PluginEntry:
    """One catalog plugin entry, ready for adapter consumption.

    `name` is the toolkit slug (canonical id).
    `marketplace` is the short name keying into known_marketplaces.json.
    `marketplace_source` is the verbatim `spec.source.marketplaceSource` block.
    `plugin` is the plugin name as known to the marketplace.
    `version` is `"latest"` or a pinned semver string.
    """
    name: str
    marketplace: str
    marketplace_source: dict
    plugin: str
    version: str
```

- [ ] **Step 4: Re-export `PluginEntry` from `__init__.py`**

Edit `src/agent_toolkit_cli/harness_adapters/__init__.py`. Add to the imports from `base` and to `__all__`:

```python
from agent_toolkit_cli.harness_adapters.base import (
    CannotInstall,
    ConfigFileAdapter,
    ConfigFileFolderAdapter,
    HookEntry,
    McpEntry,
    PluginEntry,        # new
    PluginFolderAdapter,
    Scope,
    UnimplementedAdapter,
    WriteAction,
)

__all__ = [
    "get_adapter",
    "CannotInstall",
    "ConfigFileAdapter",
    "ConfigFileFolderAdapter",
    "HookEntry",
    "McpEntry",
    "PluginEntry",      # new
    "PluginFolderAdapter",
    "Scope",
    "UnimplementedAdapter",
    "WriteAction",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_harness_adapters_base.py -k plugin_entry -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/harness_adapters/base.py \
        src/agent_toolkit_cli/harness_adapters/__init__.py \
        tests/test_harness_adapters_base.py
git commit -m "feat(adapter-base): add PluginEntry dataclass (#149)"
```

---

## Task 4: ClaudePluginAdapter — the adapter itself

**Files:**
- Create: `src/agent_toolkit_cli/harness_adapters/claude_plugin.py`
- Modify: `src/agent_toolkit_cli/harness_adapters/__init__.py` (registration)
- Create: `tests/test_claude_plugin_adapter.py`

JSON-write style decided in plan-phase-0: `json.dumps(obj, indent=2, ensure_ascii=False)` + trailing `"\n"`, **ordering preserved** (Python 3.7+ dict ordering; no `sort_keys`). If plan-phase-0 spike shows Claude writes a different style, adjust this single line in `_dumps()`.

### Task 4.1: Adapter skeleton + `config_target`

- [ ] **Step 1: Write failing test for `config_target`**

Add to `tests/test_claude_plugin_adapter.py`:

```python
from __future__ import annotations
import os
from pathlib import Path
import pytest


def test_config_target_user_scope(monkeypatch):
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    monkeypatch.setenv("HOME", "/tmp/fake-home")
    adapter = ClaudePluginAdapter()
    assert adapter.config_target("user", Path("/irrelevant")) == \
        Path("/tmp/fake-home/.claude/plugins/installed_plugins.json")


def test_config_target_project_scope_returns_none(monkeypatch):
    """Project scope is out of scope for v1."""
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    adapter = ClaudePluginAdapter()
    assert adapter.config_target("project", Path("/tmp/proj")) is None


def test_marketplaces_target_user_scope(monkeypatch):
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    monkeypatch.setenv("HOME", "/tmp/fake-home")
    adapter = ClaudePluginAdapter()
    assert adapter.marketplaces_target("user", Path("/irrelevant")) == \
        Path("/tmp/fake-home/.claude/plugins/known_marketplaces.json")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_claude_plugin_adapter.py -k config_target -v`
Expected: 3 FAIL (module doesn't exist).

- [ ] **Step 3: Create the adapter skeleton**

`src/agent_toolkit_cli/harness_adapters/claude_plugin.py`:

```python
"""Claude plugin adapter — ConfigFileAdapter against two JSON files.

Round-trip via `json` stdlib (Python 3.7+ preserves insertion order). Managed
namespaces:

- ``~/.claude/plugins/installed_plugins.json`` ``plugins.<plugin>@<marketplace>[]``
- ``~/.claude/plugins/known_marketplaces.json`` ``<marketplace>``

Toolkit-owned fields (only):
- installed_plugins entry: ``scope``, ``version`` (and ``plugin``+``marketplace``
  via the composite key). Never touch ``installedAt``, ``gitCommitSha``,
  ``lastUpdated``, ``installPath`` — Claude fills those on first start.
- known_marketplaces entry: ``source``. Never touch ``installLocation`` or
  ``lastUpdated``.

Ownership rule (manage by name; spec § "five rules"): we own every
``<plugin>@<marketplace>`` key in ``previously_allowed ∪ desired``. Other
keys are hand-rolled and preserved verbatim.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from agent_toolkit_cli.harness_adapters.base import (
    CannotInstall,
    PluginEntry,
    Scope,
    WriteAction,
)


class ClaudePluginAdapter:
    name: str = "claude"
    strategy: Literal["config_file"] = "config_file"

    # ---- target paths ----
    def config_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope != "user":
            return None  # v1: project scope unsupported
        home = Path(os.environ.get("HOME", ""))
        return home / ".claude" / "plugins" / "installed_plugins.json"

    def marketplaces_target(self, scope: Scope, project_root: Path) -> Path | None:
        if scope != "user":
            return None
        home = Path(os.environ.get("HOME", ""))
        return home / ".claude" / "plugins" / "known_marketplaces.json"

    # ---- pre-flight ----
    def can_install(self, entry: PluginEntry) -> None:
        # No pre-flight refusals in v1. Marketplace-collision detection
        # happens in diff() where we have on-disk state to compare against.
        return

    # ---- introspection ----
    def list_installed(self, scope: Scope, project_root: Path) -> set[str]:
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return set()
        doc = self._read(target)
        plugins_obj = doc.get("plugins") or {}
        return set(plugins_obj.keys())

    def entry_drift(
        self, scope: Scope, project_root: Path, entry: PluginEntry
    ) -> bool:
        """True iff the recorded toolkit-owned fields differ from the sidecar."""
        target = self.config_target(scope, project_root)
        if target is None or not target.is_file():
            return False
        key = f"{entry.plugin}@{entry.marketplace}"
        doc = self._read(target)
        entries = (doc.get("plugins") or {}).get(key) or []
        recorded = next((e for e in entries if e.get("scope") == "user"), None)
        if recorded is None:
            return False
        # "latest" semantics: don't consider version-drift for floating pins
        if entry.version != "latest":
            if recorded.get("version") != entry.version:
                return True
        return False

    # ---- diff (the engine) ----
    def diff(
        self,
        scope: Scope,
        project_root: Path,
        entries: list[PluginEntry],
        *,
        previously_allowed: set[str] = frozenset(),
    ) -> list[WriteAction]:
        target = self.config_target(scope, project_root)
        mkt_target = self.marketplaces_target(scope, project_root)
        if target is None or mkt_target is None:
            return []

        actions: list[WriteAction] = []
        actions.extend(self._diff_installed(target, entries, previously_allowed))
        actions.extend(self._diff_marketplaces(mkt_target, entries, previously_allowed))
        return actions

    # ---- per-file diff helpers ----
    def _diff_installed(
        self,
        target: Path,
        entries: list[PluginEntry],
        previously_allowed: set[str],
    ) -> list[WriteAction]:
        desired_keys = {f"{e.plugin}@{e.marketplace}" for e in entries}
        managed_keys = set(previously_allowed) | desired_keys

        if target.is_file():
            before_bytes = target.read_bytes()
            doc = self._read(target)
        else:
            before_bytes = b""
            doc = {"version": 2, "plugins": {}}

        plugins_obj = doc.setdefault("plugins", {})

        # Remove managed keys no longer desired (for user scope only).
        for key in list(plugins_obj.keys()):
            if key in managed_keys and key not in desired_keys:
                # Strip the user-scope entry; if other scopes remain, keep the key.
                remaining = [e for e in plugins_obj[key] if e.get("scope") != "user"]
                if remaining:
                    plugins_obj[key] = remaining
                else:
                    del plugins_obj[key]

        # Upsert desired entries.
        for entry in sorted(entries, key=lambda e: f"{e.plugin}@{e.marketplace}"):
            key = f"{entry.plugin}@{entry.marketplace}"
            existing_list = plugins_obj.get(key) or []
            user_entry = next((e for e in existing_list if e.get("scope") == "user"), None)
            if user_entry is None:
                # New entry: write only toolkit-owned fields.
                new_entry = {"scope": "user", "version": entry.version}
                plugins_obj[key] = [*existing_list, new_entry]
            else:
                # Existing entry: only force-write version when sidecar is pinned.
                if entry.version != "latest" and user_entry.get("version") != entry.version:
                    user_entry["version"] = entry.version

        # Ensure top-level version key.
        doc.setdefault("version", 2)

        after_bytes = self._dumps(doc).encode("utf-8")
        if after_bytes == before_bytes:
            return []
        if not target.is_file():
            return [WriteAction(path=target, op="create",
                                bytes_before=None, bytes_after=len(after_bytes),
                                contents=after_bytes)]
        return [WriteAction(path=target, op="update",
                            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
                            contents=after_bytes)]

    def _diff_marketplaces(
        self,
        target: Path,
        entries: list[PluginEntry],
        previously_allowed: set[str],
    ) -> list[WriteAction]:
        if target.is_file():
            before_bytes = target.read_bytes()
            doc = self._read(target)
        else:
            before_bytes = b""
            doc = {}

        # Ensure desired marketplaces are present with matching source.
        for entry in entries:
            existing = doc.get(entry.marketplace)
            if existing is None:
                doc[entry.marketplace] = {"source": entry.marketplace_source}
            else:
                existing_source = existing.get("source") or {}
                if existing_source != entry.marketplace_source:
                    raise CannotInstall(
                        f"plugin {entry.name}: marketplace {entry.marketplace!r} "
                        f"already recorded with a different source"
                    )

        # Remove marketplaces that no installed plugin still references.
        # Note: this only runs against marketplaces we manage. A marketplace
        # we did not introduce is preserved.
        # `previously_allowed` here is the set of `<plugin>@<marketplace>` keys
        # for plugins owned by the allow-list.
        if previously_allowed or entries:
            desired_marketplaces = {e.marketplace for e in entries}
            previously_marketplaces = {key.rsplit("@", 1)[1] for key in previously_allowed if "@" in key}
            managed_marketplaces = previously_marketplaces | desired_marketplaces
            for name in list(doc.keys()):
                if name in managed_marketplaces and name not in desired_marketplaces:
                    # Only drop if no other installed plugin in installed_plugins.json
                    # references this marketplace. The caller's `previously_allowed`
                    # is authoritative for that.
                    still_used = any(
                        key.endswith(f"@{name}")
                        for key in previously_allowed
                        if "@" in key and key.rsplit("@", 1)[1] != name
                        # If a previously-allowed plugin survives this dispatch
                        # AND references this marketplace, keep it.
                    )
                    if not still_used:
                        del doc[name]

        after_bytes = self._dumps(doc).encode("utf-8")
        if after_bytes == before_bytes:
            return []
        if not target.is_file():
            return [WriteAction(path=target, op="create",
                                bytes_before=None, bytes_after=len(after_bytes),
                                contents=after_bytes)]
        return [WriteAction(path=target, op="update",
                            bytes_before=len(before_bytes), bytes_after=len(after_bytes),
                            contents=after_bytes)]

    # ---- helpers ----
    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _dumps(doc: dict) -> str:
        return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_claude_plugin_adapter.py -k config_target -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/harness_adapters/claude_plugin.py \
        tests/test_claude_plugin_adapter.py
git commit -m "feat(adapter): ClaudePluginAdapter skeleton with config_target (#149)"
```

### Task 4.2: First-time install — create both JSON files

- [ ] **Step 1: Write failing test**

Add to `tests/test_claude_plugin_adapter.py`:

```python
def test_diff_creates_both_files_on_first_install(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    entry = PluginEntry(
        name="superpowers",
        marketplace="claude-plugins-official",
        marketplace_source={"type": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        plugin="superpowers",
        version="latest",
    )
    actions = ClaudePluginAdapter().diff("user", tmp_path, [entry])
    paths = sorted(a.path.name for a in actions)
    assert paths == ["installed_plugins.json", "known_marketplaces.json"]
    assert all(a.op == "create" for a in actions)

    # Apply (write) by hand and verify byte-equal round-trip.
    for action in actions:
        action.path.parent.mkdir(parents=True, exist_ok=True)
        action.path.write_bytes(action.contents)

    installed = (tmp_path / ".claude/plugins/installed_plugins.json").read_text()
    import json
    doc = json.loads(installed)
    assert doc["version"] == 2
    assert "superpowers@claude-plugins-official" in doc["plugins"]
    user_entries = [e for e in doc["plugins"]["superpowers@claude-plugins-official"]
                    if e.get("scope") == "user"]
    assert len(user_entries) == 1
    assert user_entries[0]["version"] == "latest"
    # Toolkit must NOT write these runtime fields:
    assert "installedAt" not in user_entries[0]
    assert "gitCommitSha" not in user_entries[0]
    assert "lastUpdated" not in user_entries[0]
    assert "installPath" not in user_entries[0]


def test_diff_is_idempotent(tmp_path, monkeypatch):
    """Running diff twice yields no second-pass changes."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    entry = PluginEntry(
        name="superpowers",
        marketplace="claude-plugins-official",
        marketplace_source={"type": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        plugin="superpowers",
        version="latest",
    )
    adapter = ClaudePluginAdapter()
    actions = adapter.diff("user", tmp_path, [entry])
    for action in actions:
        action.path.parent.mkdir(parents=True, exist_ok=True)
        action.path.write_bytes(action.contents)
    # Second pass: should be empty (with the same previously_allowed).
    actions2 = adapter.diff("user", tmp_path, [entry],
                            previously_allowed={"superpowers@claude-plugins-official"})
    assert actions2 == []
```

- [ ] **Step 2: Run to verify they fail or pass as appropriate**

Run: `uv run pytest tests/test_claude_plugin_adapter.py -k diff_creates_both_files -v`
Expected: PASS (the adapter from 4.1 should already do this).

If FAIL: read the diff output, fix the adapter, commit.

Run: `uv run pytest tests/test_claude_plugin_adapter.py -k diff_is_idempotent -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_claude_plugin_adapter.py
git commit -m "test(adapter): first-install + idempotency for ClaudePluginAdapter (#149)"
```

### Task 4.3: Sibling-entry preservation

- [ ] **Step 1: Write failing test**

```python
def test_diff_preserves_unrelated_sibling_entries(tmp_path, monkeypatch):
    """Existing entries the toolkit didn't introduce must be preserved verbatim."""
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    pre_installed = {
        "version": 2,
        "plugins": {
            "hand-rolled@private": [
                {
                    "scope": "user",
                    "version": "1.2.3",
                    "installedAt": "2026-04-01T00:00:00Z",
                    "lastUpdated": "2026-04-01T00:00:00Z",
                    "installPath": "/some/path",
                }
            ]
        },
    }
    (plugins_dir / "installed_plugins.json").write_text(
        json.dumps(pre_installed, indent=2) + "\n"
    )
    pre_markets = {
        "private": {
            "source": {"source": "directory", "path": "/some/dir"},
            "installLocation": "/some/install",
            "lastUpdated": "2026-04-01T00:00:00Z",
        }
    }
    (plugins_dir / "known_marketplaces.json").write_text(
        json.dumps(pre_markets, indent=2) + "\n"
    )

    entry = PluginEntry(
        name="superpowers", marketplace="claude-plugins-official",
        marketplace_source={"type": "git", "url": "https://x.example/y.git"},
        plugin="superpowers", version="latest",
    )
    actions = ClaudePluginAdapter().diff("user", tmp_path, [entry])
    for action in actions:
        action.path.write_bytes(action.contents)

    # Both pre-existing siblings survive untouched.
    after_installed = json.loads((plugins_dir / "installed_plugins.json").read_text())
    assert "hand-rolled@private" in after_installed["plugins"]
    assert after_installed["plugins"]["hand-rolled@private"][0]["installedAt"] == "2026-04-01T00:00:00Z"

    after_markets = json.loads((plugins_dir / "known_marketplaces.json").read_text())
    assert "private" in after_markets
    assert after_markets["private"]["installLocation"] == "/some/install"

    # And the new entry is present.
    assert "superpowers@claude-plugins-official" in after_installed["plugins"]
    assert "claude-plugins-official" in after_markets
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_claude_plugin_adapter.py -k preserves_unrelated -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_claude_plugin_adapter.py
git commit -m "test(adapter): preserve unrelated sibling entries (#149)"
```

### Task 4.4: Marketplace name-collision refusal

- [ ] **Step 1: Write failing test**

```python
def test_diff_refuses_marketplace_name_collision(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import json, pytest
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry, CannotInstall

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "claude-plugins-official": {
            "source": {"source": "git", "url": "https://NOT-the-right-url/x.git"},
        }
    }, indent=2) + "\n")

    entry = PluginEntry(
        name="superpowers", marketplace="claude-plugins-official",
        marketplace_source={"type": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        plugin="superpowers", version="latest",
    )
    with pytest.raises(CannotInstall, match="already recorded with a different source"):
        ClaudePluginAdapter().diff("user", tmp_path, [entry])
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_claude_plugin_adapter.py -k marketplace_name_collision -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_claude_plugin_adapter.py
git commit -m "test(adapter): refuse marketplace name collision (#149)"
```

### Task 4.5: Pinned-version drift

- [ ] **Step 1: Write failing test**

```python
def test_pinned_version_forces_rewrite(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [
                {"scope": "user", "version": "5.1.0",
                 "installedAt": "x", "lastUpdated": "y", "installPath": "/p"}
            ]
        }
    }, indent=2) + "\n")
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "claude-plugins-official": {
            "source": {"type": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        }
    }, indent=2) + "\n")

    entry = PluginEntry(
        name="superpowers", marketplace="claude-plugins-official",
        marketplace_source={"type": "git", "url": "https://github.com/anthropics/claude-plugins-official.git"},
        plugin="superpowers", version="6.0.0",  # pinned, drift from on-disk 5.1.0
    )
    actions = ClaudePluginAdapter().diff(
        "user", tmp_path, [entry],
        previously_allowed={"superpowers@claude-plugins-official"},
    )
    assert len(actions) == 1
    assert actions[0].path.name == "installed_plugins.json"
    assert actions[0].op == "update"

    # Apply and verify version was rewritten but runtime fields preserved.
    actions[0].path.write_bytes(actions[0].contents)
    after = json.loads((plugins_dir / "installed_plugins.json").read_text())
    e = after["plugins"]["superpowers@claude-plugins-official"][0]
    assert e["version"] == "6.0.0"
    assert e["installedAt"] == "x"     # preserved
    assert e["installPath"] == "/p"    # preserved


def test_latest_leaves_recorded_version_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@claude-plugins-official": [
                {"scope": "user", "version": "5.1.0"}
            ]
        }
    }, indent=2) + "\n")
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "claude-plugins-official": {"source": {"type": "git", "url": "https://x/y.git"}}
    }, indent=2) + "\n")

    entry = PluginEntry(
        name="superpowers", marketplace="claude-plugins-official",
        marketplace_source={"type": "git", "url": "https://x/y.git"},
        plugin="superpowers", version="latest",
    )
    actions = ClaudePluginAdapter().diff(
        "user", tmp_path, [entry],
        previously_allowed={"superpowers@claude-plugins-official"},
    )
    assert actions == [], "no-op expected: 'latest' must not touch a pinned recorded version"
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_claude_plugin_adapter.py -k "pinned_version or latest_leaves" -v`
Expected: 2 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_claude_plugin_adapter.py
git commit -m "test(adapter): version pinning vs latest semantics (#149)"
```

### Task 4.6: Revert — shared-marketplace guard

- [ ] **Step 1: Write failing test**

```python
def test_revert_drops_marketplace_when_unused(tmp_path, monkeypatch):
    """Removing the only plugin referencing a marketplace removes the marketplace too."""
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@cpo": [{"scope": "user", "version": "latest"}]
        }
    }, indent=2) + "\n")
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "cpo": {"source": {"type": "git", "url": "https://x/y.git"}}
    }, indent=2) + "\n")

    # `previously_allowed` had the plugin; `entries` is empty (we removed it).
    actions = ClaudePluginAdapter().diff(
        "user", tmp_path, [], previously_allowed={"superpowers@cpo"},
    )
    for action in actions:
        action.path.write_bytes(action.contents) if action.contents else action.path.unlink(missing_ok=True)

    installed = json.loads((plugins_dir / "installed_plugins.json").read_text())
    markets = json.loads((plugins_dir / "known_marketplaces.json").read_text())
    assert "superpowers@cpo" not in installed["plugins"]
    assert "cpo" not in markets


def test_revert_keeps_marketplace_when_shared(tmp_path, monkeypatch):
    """Removing one plugin still leaves the marketplace if another plugin uses it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    import json
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    from agent_toolkit_cli.harness_adapters.base import PluginEntry

    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    (plugins_dir / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {
            "superpowers@cpo": [{"scope": "user", "version": "latest"}],
            "compound@cpo":    [{"scope": "user", "version": "latest"}],
        }
    }, indent=2) + "\n")
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "cpo": {"source": {"type": "git", "url": "https://x/y.git"}}
    }, indent=2) + "\n")

    keep = PluginEntry(
        name="compound", marketplace="cpo",
        marketplace_source={"type": "git", "url": "https://x/y.git"},
        plugin="compound", version="latest",
    )
    # previously_allowed = both; entries = only `compound` survives.
    actions = ClaudePluginAdapter().diff(
        "user", tmp_path, [keep],
        previously_allowed={"superpowers@cpo", "compound@cpo"},
    )
    for action in actions:
        action.path.write_bytes(action.contents)

    installed = json.loads((plugins_dir / "installed_plugins.json").read_text())
    markets = json.loads((plugins_dir / "known_marketplaces.json").read_text())
    assert "superpowers@cpo" not in installed["plugins"]
    assert "compound@cpo" in installed["plugins"]
    assert "cpo" in markets, "marketplace still referenced by compound, must remain"
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_claude_plugin_adapter.py -k revert -v`
Expected: 2 PASS.

If FAIL: the shared-marketplace logic in `_diff_marketplaces` needs the active-`entries` set to be considered as authoritative for "still used." Fix the helper:

```python
# Replace the `still_used` block with:
still_used_by_new = any(e.marketplace == name for e in entries)
if not still_used_by_new:
    del doc[name]
```

Re-run, commit.

- [ ] **Step 3: Commit**

```bash
git add tests/test_claude_plugin_adapter.py src/agent_toolkit_cli/harness_adapters/claude_plugin.py
git commit -m "feat(adapter): shared-marketplace guard on revert (#149)"
```

### Task 4.7: Register the adapter

- [ ] **Step 1: Write failing test**

```python
def test_get_adapter_returns_claude_plugin_adapter():
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    adapter = get_adapter("claude", "plugin")
    assert isinstance(adapter, ClaudePluginAdapter)
```

Add to `tests/test_claude_plugin_adapter.py`.

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_claude_plugin_adapter.py -k get_adapter -v`
Expected: FAIL (returns `UnimplementedAdapter`).

- [ ] **Step 3: Register in the dispatcher**

Edit `src/agent_toolkit_cli/harness_adapters/__init__.py`. In `get_adapter`, after the codex branches and before the `claude` mcp branch:

```python
if harness == "claude" and kind == "plugin":
    from agent_toolkit_cli.harness_adapters.claude_plugin import ClaudePluginAdapter
    return ClaudePluginAdapter()
```

- [ ] **Step 4: Run**

Run: `uv run pytest tests/test_claude_plugin_adapter.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/harness_adapters/__init__.py tests/test_claude_plugin_adapter.py
git commit -m "feat(adapter): register ClaudePluginAdapter in get_adapter() (#149)"
```

---

## Task 5: Drop legacy `(claude, plugin)` from `_support.py`

**Files:**
- Modify: `src/agent_toolkit_cli/_support.py:33,52`
- Modify: `tests/test_support.py` (or wherever target-table tests live)

- [ ] **Step 1: Write a test that asserts `(claude, plugin)` is no longer in `SUPPORTED_PAIRS` as a symlink target**

The adapter-based pair is still "supported" but through `get_adapter("claude", "plugin")`, not through `_USER_TARGETS`. The test:

```python
def test_claude_plugin_not_in_user_targets():
    """The adapter owns the target now; the symlink table must not advertise it."""
    from agent_toolkit_cli._support import _USER_TARGETS, _PROJECT_TARGETS
    assert ("claude", "plugin") not in _USER_TARGETS
    assert ("claude", "plugin") not in _PROJECT_TARGETS


def test_claude_plugin_still_reported_supported_via_adapter():
    """The adapter dispatcher returns a real adapter, not UnimplementedAdapter."""
    from agent_toolkit_cli.harness_adapters import get_adapter
    from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter
    assert not isinstance(get_adapter("claude", "plugin"), UnimplementedAdapter)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_support.py -k claude_plugin -v`
Expected: 1 FAIL (still in `_USER_TARGETS`), 1 PASS (adapter was registered in Task 4.7).

- [ ] **Step 3: Remove the rows**

Edit `src/agent_toolkit_cli/_support.py`. Delete lines 33 and 52:

```diff
-    ("claude", "plugin"):      "{home}/.claude/plugins",
```

```diff
-    ("claude", "plugin"):      ".claude/plugins",
```

- [ ] **Step 4: Run**

Run: `uv run pytest tests/test_support.py -v`
Expected: all PASS, including the two new ones.

- [ ] **Step 5: Run full suite to surface ripple breakage**

Run: `uv run pytest -q`
Expected: surfaces ripple failures in `_link_lib`/`_list_json`/`doctor` that rely on `_USER_TARGETS[("claude","plugin")]`. Fix in the relevant tasks below.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/_support.py tests/test_support.py
git commit -m "refactor(_support): drop (claude, plugin) symlink target — adapter owns it (#149)"
```

---

## Task 6: Linker dispatch — remove symlink branches for `kind == \"plugin\"`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py:300,322`
- Modify: `tests/` — add an integration test using fixture `superpowers.toolkit.yaml`

- [ ] **Step 1: Read the linker's current plugin branches**

```bash
sed -n '290,335p' src/agent_toolkit_cli/commands/_link_lib.py
```

- [ ] **Step 2: Write failing integration test**

`tests/integration/test_plugin_link_cycle.py`:

```python
"""Integration: link → list → diff → unlink → list for plugin:superpowers."""
from __future__ import annotations
import json
from pathlib import Path
import pytest


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


@pytest.fixture
def toolkit_repo(tmp_path):
    """A minimal toolkit repo containing the superpowers sidecar."""
    root = tmp_path / "toolkit"
    plugins = root / "plugins"
    plugins.mkdir(parents=True)
    fixture = Path(__file__).parent.parent / "fixtures" / "plugin_sidecars" / "superpowers.toolkit.yaml"
    (plugins / "superpowers.toolkit.yaml").write_text(fixture.read_text())
    # Minimal .agent-toolkit-source marker so the resolver finds this root.
    (root / ".agent-toolkit-source").touch()
    return root


def test_link_unlink_cycle(fake_home, toolkit_repo):
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import cli

    runner = CliRunner()

    # Pre-existing sibling marketplace must survive.
    (fake_home / ".claude" / "plugins").mkdir(parents=True)
    (fake_home / ".claude" / "plugins" / "known_marketplaces.json").write_text(json.dumps({
        "hand-rolled": {"source": {"type": "directory", "path": "/some/path"}},
    }, indent=2) + "\n")

    # link
    result = runner.invoke(cli, [
        "--toolkit-repo", str(toolkit_repo),
        "link", "user", "claude", "plugin:superpowers",
    ])
    assert result.exit_code == 0, result.output

    installed = json.loads((fake_home / ".claude/plugins/installed_plugins.json").read_text())
    assert "superpowers@claude-plugins-official" in installed["plugins"]
    markets = json.loads((fake_home / ".claude/plugins/known_marketplaces.json").read_text())
    assert "claude-plugins-official" in markets
    assert "hand-rolled" in markets, "pre-existing sibling marketplace must survive"

    # list — superpowers should report linked
    result = runner.invoke(cli, [
        "--toolkit-repo", str(toolkit_repo),
        "list", "plugin", "claude",
    ])
    assert result.exit_code == 0
    assert "superpowers" in result.output

    # diff — should be clean
    result = runner.invoke(cli, [
        "--toolkit-repo", str(toolkit_repo),
        "diff", "user", "claude",
    ])
    assert result.exit_code == 0

    # unlink
    result = runner.invoke(cli, [
        "--toolkit-repo", str(toolkit_repo),
        "unlink", "user", "claude", "plugin:superpowers",
    ])
    assert result.exit_code == 0, result.output

    installed = json.loads((fake_home / ".claude/plugins/installed_plugins.json").read_text())
    assert "superpowers@claude-plugins-official" not in installed["plugins"]
    markets = json.loads((fake_home / ".claude/plugins/known_marketplaces.json").read_text())
    assert "claude-plugins-official" not in markets, "marketplace dropped (no more plugins reference it)"
    assert "hand-rolled" in markets, "sibling marketplace still preserved"
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/integration/test_plugin_link_cycle.py -v`
Expected: FAIL (linker still symlink-dispatches plugins).

- [ ] **Step 4: Re-route plugin in the linker**

Edit `src/agent_toolkit_cli/commands/_link_lib.py` around line 300. Find the `if kind == "plugin":` branch (line 300) and the `elif kind == "plugin":` branch (line 322). Replace both with a single early-return that delegates to the adapter dispatch path:

Concretely: in the function that decides between "symlink-style projection" and "adapter-style projection", treat `plugin` the same way `mcp` and `hook` are treated. Locate the existing dispatch pattern for `mcp`:

```bash
grep -n "kind == \"mcp\"" src/agent_toolkit_cli/commands/_link_lib.py
```

Mirror that branch for `kind == "plugin"` (calling `get_adapter(harness, "plugin")` and building a `PluginEntry` from the sidecar metadata).

The asset → `PluginEntry` builder lives next to the adapter call. Pseudocode (translate to actual function names you see in the file):

```python
def _build_plugin_entry(asset_record) -> PluginEntry:
    spec = asset_record.metadata.get("spec") or {}
    source = spec.get("source") or {}
    return PluginEntry(
        name=asset_record.asset.slug,
        marketplace=source["marketplace"],
        marketplace_source=source["marketplaceSource"],
        plugin=source["plugin"],
        version=source["version"],
    )
```

- [ ] **Step 5: Run**

Run: `uv run pytest tests/integration/test_plugin_link_cycle.py -v`
Expected: PASS.

- [ ] **Step 6: Run full suite**

Run: `uv run pytest -q`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py tests/integration/test_plugin_link_cycle.py
git commit -m "feat(link): route plugin through ClaudePluginAdapter (#149)"
```

---

## Task 7: `_list_json` — read adapter state for plugin status

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_list_json.py:38`
- Modify: `tests/test_list_json.py` (or wherever the json-emitter tests live)

- [ ] **Step 1: Read the current plugin branch**

```bash
sed -n '30,80p' src/agent_toolkit_cli/commands/_list_json.py
```

- [ ] **Step 2: Write failing test**

```python
def test_list_json_plugin_status_uses_adapter(tmp_path, monkeypatch):
    """For plugins, status comes from the adapter, not from filesystem symlink presence."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Set up an installed plugin entry on disk.
    plugins_dir = tmp_path / ".claude" / "plugins"
    plugins_dir.mkdir(parents=True)
    import json
    (plugins_dir / "installed_plugins.json").write_text(json.dumps({
        "version": 2,
        "plugins": {"superpowers@cpo": [{"scope": "user", "version": "latest"}]},
    }, indent=2) + "\n")
    (plugins_dir / "known_marketplaces.json").write_text(json.dumps({
        "cpo": {"source": {"type": "git", "url": "https://x/y.git"}},
    }, indent=2) + "\n")

    # ... build a synthetic asset + allowlist and invoke the list_json builder ...
    # assert status == "linked-matches"
```

(Implementor: complete the synthetic-asset construction by reading the patterns already in `tests/test_list_json.py` — the existing mcp tests are the closest analogue.)

- [ ] **Step 3: Replace the plugin branch in `_list_json.py`**

Replace the existing `if kind == "plugin":` branch at line 38 with a call into `get_adapter("claude", "plugin").list_installed(scope, project_root)` + `entry_drift(...)`. Mirror the mcp branch's structure.

- [ ] **Step 4: Run**

Run: `uv run pytest tests/test_list_json.py -k plugin -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/_list_json.py tests/test_list_json.py
git commit -m "feat(list): plugin status from adapter (#149)"
```

---

## Task 8: `doctor/symlinks.py` — plugin via adapter

**Files:**
- Modify: `src/agent_toolkit_cli/doctor/symlinks.py:193`
- Modify: `tests/doctor/test_symlinks.py` (or wherever doctor tests live)

- [ ] **Step 1: Read the current plugin branch**

```bash
sed -n '185,220p' src/agent_toolkit_cli/doctor/symlinks.py
```

- [ ] **Step 2: Write failing test**

```python
def test_doctor_warns_on_missing_install_cache(tmp_path, monkeypatch):
    """Adapter sees the entry written; cache dir absent triggers a WARN, not FAIL."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Set up an entry but no cache dir.
    # Invoke the doctor symlinks check.
    # Assert the result is `warn` for the plugin row.


def test_doctor_pass_when_entry_and_cache_present(tmp_path, monkeypatch):
    """Both entries written and cache dir present → pass."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # ... write installed_plugins, known_marketplaces, AND mkdir the cache path ...
    # Assert pass for the plugin row.
```

Complete the synthetic setup by reading the existing patterns in the doctor test file.

- [ ] **Step 3: Replace the plugin branch in `symlinks.py`**

Replace the symlink-aware plugin check at line 193 with adapter-driven checks:

```python
if asset.kind == "plugin":
    adapter = get_adapter("claude", "plugin")
    installed = adapter.list_installed(scope, project_root)
    spec_source = (record.metadata.get("spec") or {}).get("source") or {}
    key = f"{spec_source.get('plugin')}@{spec_source.get('marketplace')}"
    if key not in installed:
        # adapter entry missing; that's a fail
        yield Issue(level="fail", ...)
        continue
    # entry present; check cache path warn-only
    install_path = ...  # computed from cache layout
    if not install_path.exists():
        yield Issue(level="warn", message="plugin cache not yet cloned — start Claude Code to populate")
        continue
    yield Issue(level="pass", ...)
    continue
```

- [ ] **Step 4: Run**

Run: `uv run pytest tests/doctor/ -k plugin -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/doctor/symlinks.py tests/doctor/test_symlinks.py
git commit -m "feat(doctor): plugin checks via adapter (warn on missing cache) (#149)"
```

---

## Task 9: Harness matrix doc + parity test

**Files:**
- Modify: `docs/agent-toolkit/harness-matrix.md:78` (the `(claude, plugin)` cell)
- Modify: `docs/agent-toolkit/harness-matrix.md` (Why … by design § plugin)
- Modify: `tests/test_harness_matrix.py`

- [ ] **Step 1: Read the parity test**

```bash
sed -n '1,80p' tests/test_harness_matrix.py
```

Confirm it parses the matrix cell text and compares to `_USER_TARGETS` (or however the parity is enforced).

- [ ] **Step 2: Run the parity test as-is**

Run: `uv run pytest tests/test_harness_matrix.py -v`
Expected: FAIL — the doc still says `symlink → ~/.claude/plugins/<slug>/` but `_support.py` no longer has that target (Task 5 removed it).

- [ ] **Step 3: Update the matrix cell**

Edit `docs/agent-toolkit/harness-matrix.md` line 78, the `(claude, plugin)` cell. Replace:

> symlink → `~/.claude/plugins/<slug>/`

with:

> config_file → `~/.claude/plugins/installed_plugins.json` + `~/.claude/plugins/known_marketplaces.json` (declarative install; Claude clones lazily on next start; project scope unsupported)

- [ ] **Step 4: Update the prose**

In the section "Why some pairs are 'by design' unsupported" → **plugin**, replace the Claude bullet:

> Claude: a markdown directory at `~/.claude/plugins/<slug>/` (what this toolkit projects).

with:

> Claude: a declarative install registered in `~/.claude/plugins/installed_plugins.json` (keyed `<plugin>@<marketplace>`) and `~/.claude/plugins/known_marketplaces.json`. Claude Code's plugin runtime clones the plugin tree into `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` on next start. The toolkit owns only the two JSON files — never the cache.

- [ ] **Step 5: Update the parity-test mapping if it hardcodes cell text**

If `tests/test_harness_matrix.py` has a hardcoded cell-text fixture, update it. Read the test file first; mechanical edit follows.

- [ ] **Step 6: Run**

Run: `uv run pytest tests/test_harness_matrix.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add docs/agent-toolkit/harness-matrix.md tests/test_harness_matrix.py
git commit -m "docs(matrix): (claude, plugin) is config_file against two JSON files (#149)"
```

---

## Task 10: Docs polish — cli.md, schema.md, README.md, AGENTS.md

**Files:**
- Modify: `docs/agent-toolkit/cli.md`
- Modify: `docs/agent-toolkit/schema.md`
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Update `cli.md`**

Find the "Asset kinds" section (or the subcommand reference). Add a paragraph under plugins:

```markdown
**plugin** (Claude-only by design). Managed declaratively via
`~/.claude/plugins/installed_plugins.json` and
`~/.claude/plugins/known_marketplaces.json`. The CLI writes the
allowlist entries; Claude clones the plugin tree on next start.
Project scope is not supported in this release.
```

- [ ] **Step 2: Update `schema.md`**

Add a `kind: plugin` example with the full sidecar shape from `tests/fixtures/plugin_sidecars/superpowers.toolkit.yaml`. Document `spec.source.{marketplace,marketplaceSource,plugin,version}`.

- [ ] **Step 3: Update `README.md`**

Add a one-line under the kinds list:

```markdown
- **plugin** (Claude-only) — declarative install via installed_plugins.json + known_marketplaces.json.
```

- [ ] **Step 4: Update `AGENTS.md` — Asset identity § One metadata location**

Find the bullet about `plugin` in the "one metadata location" rule. Replace with:

```markdown
- **plugin** — sidecar `plugins/<slug>.toolkit.yaml` (preferred) OR inline
  `agent_toolkit_cli` JSON key in `plugin.json` (legacy; emits a deprecation
  warning during `check`). Never both.
```

- [ ] **Step 5: Commit**

```bash
git add docs/agent-toolkit/cli.md docs/agent-toolkit/schema.md README.md AGENTS.md
git commit -m "docs: cli, schema, README, AGENTS for plugin asset kind (#149)"
```

---

## Task 11: Final verification

- [ ] **Step 1: Full test suite**

Run: `uv run pytest -q`
Expected: all PASS.

- [ ] **Step 2: Lint**

Run: `uv run ruff check src tests`
Expected: clean.

- [ ] **Step 3: Smoke-test the CLI by hand against the fixture**

```bash
export HOME=/tmp/plugin-smoke
rm -rf "$HOME"; mkdir -p "$HOME"
uv run agent-toolkit-cli --toolkit-repo $(pwd)/tests/fixtures/fake-toolkit list plugin claude
# Should show superpowers as unlinked.

uv run agent-toolkit-cli --toolkit-repo $(pwd)/tests/fixtures/fake-toolkit \
    link user claude plugin:superpowers
cat "$HOME/.claude/plugins/installed_plugins.json"
cat "$HOME/.claude/plugins/known_marketplaces.json"

uv run agent-toolkit-cli --toolkit-repo $(pwd)/tests/fixtures/fake-toolkit \
    unlink user claude plugin:superpowers
cat "$HOME/.claude/plugins/installed_plugins.json"
cat "$HOME/.claude/plugins/known_marketplaces.json"
```

The "fake-toolkit" needs to be a directory containing `plugins/superpowers.toolkit.yaml`. Either create it inline or point at `tests/integration`'s fixture builder.

- [ ] **Step 4: Update `assets/verification/149/flow.log`**

Record the smoke-test outputs.

---

## Self-Review

**Spec coverage** (re-checked against `docs/superpowers/specs/2026-05-20-claude-plugin-asset-kind-design.md`):

- [x] Asset shape (sidecar-only) — Task 1 (schema) + Task 2 (walker discovery).
- [x] Legacy inline-JSON discovery preserved as fall-back — Task 2 + Task 10 (AGENTS.md).
- [x] Mutex on sidecar+inline — Task 2.
- [x] Schema additions to both copies — Task 1.
- [x] Harness matrix update + parity test — Task 9.
- [x] Adapter implementation — Task 4 (split into 4.1–4.7).
- [x] CLI surface (no new commands; existing verbs work) — Tasks 6–8 wire `link`/`unlink`/`list`/`doctor`. Tasks 1, 5 unblock the path.
- [x] `inventory plugin` and TUI — surface automatically via walker + status (no per-task work needed; covered by Task 2 discovery).
- [x] Project scope unsupported — Task 4.1 `config_target` returns None; Task 6 inherits the "unsupported scope" path.
- [x] Code-path cleanup in `_support.py`, `walker.py`, `schema.py`, `_link_lib.py`, `_list_json.py`, `doctor/symlinks.py` — Tasks 5, 2, 1, 6, 7, 8 respectively.
- [x] Tests: unit (round-trip, idempotency, shared-marketplace, collision refusal, version-pinning) — Task 4.2–4.6; integration cycle — Task 6; matrix parity — Task 9.
- [x] Docs: cli.md, schema.md, README, AGENTS.md, harness-matrix.md — Tasks 9, 10.
- [x] Example sidecar — landed as a fixture in Task 1; the real "ship a usable example" lives in the toolkit-repo follow-up PR, called out in the spec.

**Placeholder scan:** no "TBD", no "add appropriate error handling" without showing how. Task 7 leaves the synthetic-test setup to the implementor with a clear pointer to the existing mcp tests as analogue — acceptable because the patterns vary by test file and reading the analogue is the right move.

**Type consistency:** `PluginEntry` named consistently across Tasks 3–6. `marketplace_source` (snake-case Python field) ↔ `marketplaceSource` (camelCase JSON / sidecar) — translation happens only in `_build_plugin_entry` in Task 6 and is explicit there.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-20-claude-plugin-asset-kind.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
