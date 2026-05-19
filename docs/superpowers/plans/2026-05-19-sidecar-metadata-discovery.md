# Sidecar metadata discovery — implementation plan (CLI side)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable submoduled / vendored upstream skills and MCPs to be ingested without modifying upstream content, by adding a sibling sidecar metadata form (`<slug>.toolkit.yaml`) alongside the existing inline-frontmatter form.

**Architecture:** Walker grows a three-step metadata resolution (sidecar probe → inline probe → mutex check) for skill and mcp kinds. Sidecar lives outside the asset directory; body discovered implicitly by name. Mutex violation (both forms for same slug) fails `check` with exit 2. `agent-toolkit-cli new skill <slug>` defaults to sidecar form. `doctor --fix` gains write-capable autofix for three new error classes. One in-place v1alpha2 schema relaxation makes `fork` optional under `vendored_via: submodule`.

**Tech Stack:** Python 3.11+, Click, PyYAML, jsonschema (validator), pytest. Two git repos: `agent-toolkit-cli` (this plan's target) and `agent-toolkit` (the content repo, handled via copy-paste operator prompts in the spec).

**Spec:** `docs/superpowers/specs/2026-05-19-sidecar-metadata-discovery-design.md`

**Repo scope:** All CLI changes land in `~/GitHub/projects/agent-toolkit-cli/`. Content-repo work (PR 2 = MCP migration; PR 4 = submoduled skill sidecars + docs) is delivered as copy-paste operator prompts at the end of the spec; not engineered through this plan.

**Sequencing across PRs:**

- **PR 1** (this plan, tasks 1–18): walker + check + new-command + schema relaxation + doctor scaffolding (read path only); migration helper script lands here too.
- **PR 2** (operator-run via spec prompt): atomic MCP migration in the content repo. Out of this plan's scope.
- **PR 3** (this plan, tasks 19–24): remove legacy MCP README-frontmatter code path; activate doctor autofix write logic; delete migration helper.
- **PR 4** (operator-run via spec prompt): submoduled skill sidecars + content-repo docs. Out of this plan's scope.

**Branches:** PR 1 lands on `feat/sidecar-metadata-discovery-pr1`. PR 3 lands on `feat/sidecar-metadata-discovery-pr3` cut from main after PR 2 merges in the content repo.

**Pre-flight (do once before Task 1):**

```bash
cd ~/GitHub/projects/agent-toolkit-cli
git checkout main && git pull --rebase
git checkout -b feat/sidecar-metadata-discovery-pr1
uv run pytest -q   # baseline: ~731 passed, 1 skipped
```

Expected baseline: all tests pass; lefthook gate green.

---

## PR 1 — Walker, check, new-command, schema, doctor scaffolding

### Task 1: Schema relaxation — drop `fork` requirement under `vendored_via: submodule`

**Files:**
- Modify: `~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha2.json` (content repo)
- Modify: `~/GitHub/projects/agent-toolkit-cli/src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json` (vendored)
- Test: relies on existing `tests/test_schema_vendor_parity.py`

The rule lives at `properties.spec.allOf[1]`. Both copies must remain byte-identical (the schema-vendor parity test enforces this).

- [ ] **Step 1: Read the current `spec.allOf` block from both schemas**

```bash
python3 -c "import json,pprint; s=json.load(open('/Users/ajanderson/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha2.json')); pprint.pp(s['properties']['spec']['allOf'])"
```

Expected output:
```python
[{'if': {'properties': {'origin': {'const': 'third-party'}}},
  'then': {'required': ['upstream']}},
 {'if': {'properties': {'vendored_via': {'const': 'submodule'}}},
  'then': {'required': ['fork']}}]
```

- [ ] **Step 2: Remove the second `allOf` entry from the content-repo schema**

Use Edit on `~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha2.json`. Find the block:

```json
        {
          "if": { "properties": { "vendored_via": { "const": "submodule" } } },
          "then": { "required": ["fork"] }
        }
```

Delete this object **and** the trailing comma on the previous `allOf` entry. The remaining `spec.allOf` should be:

```json
      "allOf": [
        {
          "if": { "properties": { "origin": { "const": "third-party" } } },
          "then": { "required": ["upstream"] }
        }
      ]
```

- [ ] **Step 3: Copy the modified schema to the vendored location**

```bash
cp ~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha2.json \
   ~/GitHub/projects/agent-toolkit-cli/src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json
```

- [ ] **Step 4: Verify byte-identity**

```bash
diff ~/GitHub/agent-toolkit/schemas/asset-frontmatter.v1alpha2.json \
     ~/GitHub/projects/agent-toolkit-cli/src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json
```

Expected: no output (files identical).

- [ ] **Step 5: Run the parity test**

```bash
cd ~/GitHub/projects/agent-toolkit-cli
uv run pytest tests/test_schema_vendor_parity.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full test suite to confirm no regressions**

```bash
uv run pytest -q
```

Expected: same 731 passed (no new failures from the schema change).

- [ ] **Step 7: Commit (CLI repo only; content-repo schema edit committed in PR 2 prompt)**

```bash
cd ~/GitHub/projects/agent-toolkit-cli
git add src/agent_toolkit_cli/_schemas/asset-frontmatter.v1alpha2.json
git commit -m "feat(schema): make spec.fork optional under vendored_via=submodule

Drops the allOf rule that mandated a fork for every submoduled asset.
Enables unpatched submodules to be described by toolkit metadata without
forcing a heavyweight fork-with-no-patches. The AGENTS.md submodule-fork
convention continues to recommend forking when patches exist; it just
stops being mandatory when there are no patches.

Additive change within v1alpha2 (removes a requirement, doesn't add one).
Refs: docs/superpowers/specs/2026-05-19-sidecar-metadata-discovery-design.md"
```

The content-repo schema edit (Step 2) is uncommitted at this point — it lands in PR 2's operator prompt. The CLI repo only commits the vendored copy.

---

### Task 2: Sidecar path helper

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py` (add helper)
- Test: `tests/test_walker_sidecar.py` (new)

Sidecars live at `<root>/<slug>.toolkit.yaml`. The helper computes this path from a kind, slug, and toolkit root.

- [ ] **Step 1: Write the failing test**

Create `tests/test_walker_sidecar.py`:

```python
"""Tests for sidecar metadata discovery (skill + mcp)."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.walker import _sidecar_path


class TestSidecarPath:
    def test_skill_sidecar_path(self, tmp_path: Path) -> None:
        result = _sidecar_path("skill", "deep-research", tmp_path)
        assert result == tmp_path / "skills" / "deep-research.toolkit.yaml"

    def test_mcp_sidecar_path(self, tmp_path: Path) -> None:
        result = _sidecar_path("mcp", "context7", tmp_path)
        assert result == tmp_path / "mcps" / "context7.toolkit.yaml"

    def test_unsupported_kind_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="sidecar not supported for kind"):
            _sidecar_path("agent", "foo", tmp_path)
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/test_walker_sidecar.py::TestSidecarPath -v
```

Expected: FAIL with `ImportError: cannot import name '_sidecar_path'`.

- [ ] **Step 3: Add the helper to walker.py**

In `src/agent_toolkit_cli/walker.py`, after the `_KIND_RULES` constant (around line 27), add:

```python
# Kinds for which sidecar metadata discovery is supported.
_SIDECAR_KINDS = frozenset({"skill", "mcp"})

# Per-kind root directory (matches _KIND_RULES but indexed for lookup).
_KIND_ROOT = {kind: root_name for kind, root_name, _ in _KIND_RULES}


def _sidecar_path(kind: str, slug: str, toolkit_root: Path) -> Path:
    """Return the sidecar path for a given kind + slug.

    Raises ValueError if the kind does not support sidecars.
    """
    if kind not in _SIDECAR_KINDS:
        raise ValueError(
            f"sidecar not supported for kind {kind!r} (only: {sorted(_SIDECAR_KINDS)})"
        )
    return toolkit_root / _KIND_ROOT[kind] / f"{slug}.toolkit.yaml"
```

- [ ] **Step 4: Run the test to verify pass**

```bash
uv run pytest tests/test_walker_sidecar.py::TestSidecarPath -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/walker.py tests/test_walker_sidecar.py
git commit -m "feat(walker): add _sidecar_path helper for skill + mcp sidecars"
```

---

### Task 3: Sidecar metadata reader

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py`
- Modify: `tests/test_walker_sidecar.py`

Sidecars are bare YAML files (no `---` markers). The reader parses them; returns `None` if missing or invalid YAML.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_walker_sidecar.py`:

```python
from agent_toolkit_cli.walker import read_sidecar


class TestReadSidecar:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        result = read_sidecar(tmp_path / "skills" / "missing.toolkit.yaml")
        assert result is None

    def test_valid_yaml_returns_dict(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "foo.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: foo\n"
            "spec:\n  origin: first-party\n"
        )
        result = read_sidecar(sidecar)
        assert result == {
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {"name": "foo"},
            "spec": {"origin": "first-party"},
        }

    def test_invalid_yaml_returns_none(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "broken.toolkit.yaml"
        sidecar.write_text("foo: [unclosed\n")
        result = read_sidecar(sidecar)
        assert result is None

    def test_yaml_not_a_dict_returns_none(self, tmp_path: Path) -> None:
        sidecar = tmp_path / "list.toolkit.yaml"
        sidecar.write_text("- just\n- a\n- list\n")
        result = read_sidecar(sidecar)
        assert result is None
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_walker_sidecar.py::TestReadSidecar -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add `read_sidecar` to walker.py**

After the `extract_frontmatter` function in `walker.py`, add:

```python
def read_sidecar(path: Path) -> dict | None:
    """Read a sidecar YAML file. Returns None if missing, unparseable, or not a dict."""
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        parsed = yaml.safe_load(text)
    except (OSError, yaml.YAMLError):
        return None
    return parsed if isinstance(parsed, dict) else None
```

- [ ] **Step 4: Verify pass**

```bash
uv run pytest tests/test_walker_sidecar.py::TestReadSidecar -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/walker.py tests/test_walker_sidecar.py
git commit -m "feat(walker): add read_sidecar() YAML loader"
```

---

### Task 4: Metadata resolution with mutex detection

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py`
- Modify: `tests/test_walker_sidecar.py`

The resolution function tries sidecar first, then inline. If both succeed for the same slug, it raises `BothMetadataLocationsExist`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_walker_sidecar.py`:

```python
from agent_toolkit_cli.walker import (
    BothMetadataLocationsExist,
    resolve_metadata,
)


def _make_skill_with_inline(root: Path, slug: str) -> Path:
    """Helper: create skills/<slug>/SKILL.md with inline frontmatter."""
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True)
    skill_path = skill_dir / "SKILL.md"
    skill_path.write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n  name: {slug}\n"
        "spec:\n  origin: first-party\n"
        "---\n\nbody\n"
    )
    return skill_path


def _make_skill_with_sidecar(root: Path, slug: str) -> Path:
    """Helper: create skills/<slug>/SKILL.md (body only) + skills/<slug>.toolkit.yaml."""
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("body\n")
    sidecar = root / "skills" / f"{slug}.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n  name: {slug}\n"
        "spec:\n  origin: third-party\n"
    )
    return sidecar


class TestResolveMetadata:
    def test_sidecar_only(self, tmp_path: Path) -> None:
        _make_skill_with_sidecar(tmp_path, "foo")
        metadata, source = resolve_metadata("skill", "foo", tmp_path)
        assert metadata is not None
        assert metadata["metadata"]["name"] == "foo"
        assert source.name == "foo.toolkit.yaml"

    def test_inline_only(self, tmp_path: Path) -> None:
        _make_skill_with_inline(tmp_path, "bar")
        metadata, source = resolve_metadata("skill", "bar", tmp_path)
        assert metadata is not None
        assert metadata["metadata"]["name"] == "bar"
        assert source.name == "SKILL.md"

    def test_both_raises_mutex(self, tmp_path: Path) -> None:
        _make_skill_with_inline(tmp_path, "dup")
        # Now also add a sidecar at skills/dup.toolkit.yaml
        sidecar = tmp_path / "skills" / "dup.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: dup\n"
            "spec:\n  origin: third-party\n"
        )
        with pytest.raises(BothMetadataLocationsExist) as exc:
            resolve_metadata("skill", "dup", tmp_path)
        assert exc.value.slug == "dup"
        assert exc.value.kind == "skill"
        assert exc.value.sidecar_path.name == "dup.toolkit.yaml"
        assert exc.value.inline_path.name == "SKILL.md"

    def test_neither_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "skills" / "empty").mkdir(parents=True)
        (tmp_path / "skills" / "empty" / "SKILL.md").write_text("just a body\n")
        metadata, source = resolve_metadata("skill", "empty", tmp_path)
        assert metadata is None
        assert source is None
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_walker_sidecar.py::TestResolveMetadata -v
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Add the mutex error class and resolver to walker.py**

After `read_sidecar` in `walker.py`, add:

```python
class BothMetadataLocationsExist(Exception):
    """Raised when both sidecar AND inline frontmatter exist for the same slug."""

    def __init__(self, kind: str, slug: str, sidecar_path: Path, inline_path: Path) -> None:
        self.kind = kind
        self.slug = slug
        self.sidecar_path = sidecar_path
        self.inline_path = inline_path
        super().__init__(
            f"{kind}/{slug}: both {sidecar_path} and {inline_path} exist. Delete one."
        )


def _inline_body_path(kind: str, slug: str, toolkit_root: Path) -> Path:
    """Return the file that carries inline frontmatter for sidecar-supporting kinds."""
    if kind == "skill":
        return toolkit_root / "skills" / slug / "SKILL.md"
    if kind == "mcp":
        return toolkit_root / "mcps" / slug / "README.md"
    raise ValueError(f"inline body path not defined for kind {kind!r}")


def resolve_metadata(
    kind: str,
    slug: str,
    toolkit_root: Path,
) -> tuple[dict | None, Path | None]:
    """Resolve asset metadata for a sidecar-supporting kind.

    Returns (metadata_dict, source_path) on success; (None, None) if neither
    location exists. Raises BothMetadataLocationsExist if both exist.
    """
    if kind not in _SIDECAR_KINDS:
        raise ValueError(f"resolve_metadata called for non-sidecar kind {kind!r}")
    sidecar = _sidecar_path(kind, slug, toolkit_root)
    inline_path = _inline_body_path(kind, slug, toolkit_root)
    sidecar_meta = read_sidecar(sidecar)
    inline_meta = extract_frontmatter(inline_path) if inline_path.is_file() else None
    if sidecar_meta is not None and inline_meta is not None:
        raise BothMetadataLocationsExist(kind, slug, sidecar, inline_path)
    if sidecar_meta is not None:
        return sidecar_meta, sidecar
    if inline_meta is not None:
        return inline_meta, inline_path
    return None, None
```

- [ ] **Step 4: Verify pass**

```bash
uv run pytest tests/test_walker_sidecar.py::TestResolveMetadata -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/walker.py tests/test_walker_sidecar.py
git commit -m "feat(walker): resolve_metadata() with sidecar/inline mutex"
```

---

### Task 5: Wire sidecar resolution into discover_assets

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py`
- Modify: `tests/test_walker_sidecar.py`

The existing walker walks `_KIND_RULES`. For skill and mcp, we add a second pass that walks `*.toolkit.yaml` files to surface sidecar-described assets that have no inline-frontmatter trigger.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_walker_sidecar.py`:

```python
from agent_toolkit_cli.walker import Asset, discover_assets


class TestDiscoverAssetsSidecar:
    def test_sidecar_skill_is_discovered(self, tmp_path: Path) -> None:
        _make_skill_with_sidecar(tmp_path, "deep-research")
        assets = discover_assets(tmp_path)
        slugs = {a.slug for a in assets if a.kind == "skill"}
        assert "deep-research" in slugs

    def test_inline_skill_still_discovered(self, tmp_path: Path) -> None:
        _make_skill_with_inline(tmp_path, "agent-toolkit")
        assets = discover_assets(tmp_path)
        slugs = {a.slug for a in assets if a.kind == "skill"}
        assert "agent-toolkit" in slugs

    def test_orphan_sidecar_not_discovered(self, tmp_path: Path) -> None:
        # Sidecar exists but body directory does not — should NOT yield an Asset
        # (this gets surfaced by check, not walker).
        (tmp_path / "skills").mkdir()
        sidecar = tmp_path / "skills" / "orphan.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: orphan\n"
            "spec:\n  origin: third-party\n"
        )
        assets = discover_assets(tmp_path)
        slugs = {a.slug for a in assets if a.kind == "skill"}
        assert "orphan" not in slugs

    def test_sidecar_for_submoduled_body(self, tmp_path: Path) -> None:
        """The point of the whole feature: sidecar outside submodule path."""
        skill_dir = tmp_path / "skills" / "vendored"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("upstream body, no frontmatter\n")
        # Pretend this directory is submoduled
        (tmp_path / ".gitmodules").write_text(
            '[submodule "skills/vendored"]\n'
            "    path = skills/vendored\n"
            "    url = https://example.com/upstream.git\n"
        )
        # Sidecar lives OUTSIDE the submoduled directory
        sidecar = tmp_path / "skills" / "vendored.toolkit.yaml"
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            "metadata:\n  name: vendored\n"
            "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        )
        assets = discover_assets(tmp_path)
        slugs = {a.slug for a in assets if a.kind == "skill"}
        assert "vendored" in slugs
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_walker_sidecar.py::TestDiscoverAssetsSidecar -v
```

Expected: 4 FAIL (sidecar-described assets not yet discovered).

- [ ] **Step 3: Modify `discover_assets` to yield sidecar-described skills + MCPs**

In `walker.py`, inside `discover_assets()`, after the existing `for kind, root_name, pattern in _KIND_RULES:` loop completes, add a second pass:

```python
    # Second pass: yield sidecar-described skills and mcps. The body directory
    # for each must exist (sidecars without a body are surfaced by `check`,
    # not yielded as Assets here).
    for kind in _SIDECAR_KINDS:
        root_name = _KIND_ROOT[kind]
        root = toolkit_root / root_name
        if not root.exists():
            continue
        for sidecar in sorted(root.glob("*.toolkit.yaml")):
            slug = sidecar.name[: -len(".toolkit.yaml")]
            body_dir = root / slug
            if not body_dir.is_dir():
                # Orphan sidecar — surfaced by check, not yielded as Asset
                continue
            # Determine the asset's primary file (for the Asset.path field —
            # callers use this with frontmatter_path() to find metadata).
            if kind == "skill":
                primary = body_dir / "SKILL.md"
            else:  # mcp
                primary = body_dir / "config.json"
            if not primary.is_file():
                continue
            # Skip if inline frontmatter ALSO exists at primary — the mutex
            # case. We don't raise here; check.py raises with a better message.
            # The walker just skips, so duplicate Assets aren't yielded.
            if extract_frontmatter(primary) is not None:
                continue
            assets.append(Asset(kind=kind, slug=slug, path=primary))
```

- [ ] **Step 4: Update `frontmatter_path` to honor sidecars**

In `walker.py`, replace the existing `frontmatter_path` function with:

```python
def frontmatter_path(asset_path: Path, kind: str) -> Path:
    """Return the file carrying the asset's YAML frontmatter.

    Resolution order:
      1. For kinds in _SIDECAR_KINDS, check for a sibling <slug>.toolkit.yaml.
      2. For MCPs, fall back to the sibling README.md (legacy path).
      3. Otherwise, frontmatter lives in asset_path itself.
    """
    if kind in _SIDECAR_KINDS:
        slug = asset_path.parent.name
        toolkit_root_candidate = asset_path.parent.parent.parent
        sidecar = toolkit_root_candidate / _KIND_ROOT[kind] / f"{slug}.toolkit.yaml"
        if sidecar.is_file():
            return sidecar
    if kind == "mcp":
        return asset_path.parent / "README.md"
    return asset_path
```

- [ ] **Step 5: Update `extract_frontmatter` to also handle bare YAML sidecars**

Sidecars don't have `---` delimiters. Either teach `extract_frontmatter` to accept both forms, or branch in callers. The simpler path: callers ask via path suffix.

Add this helper right after `read_sidecar`:

```python
def extract_metadata(path: Path) -> dict | None:
    """Read metadata from either an inline-frontmatter file or a bare-YAML sidecar.

    Discriminates by filename: *.toolkit.yaml → bare YAML; everything else →
    inline frontmatter between --- markers.
    """
    if path.name.endswith(".toolkit.yaml"):
        return read_sidecar(path)
    return extract_frontmatter(path)
```

- [ ] **Step 6: Verify all tests pass**

```bash
uv run pytest tests/test_walker_sidecar.py -v
uv run pytest -q  # full suite
```

Expected: `test_walker_sidecar.py` all green; full suite still 731 + new tests.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/walker.py tests/test_walker_sidecar.py
git commit -m "feat(walker): discover sidecar-described skills and mcps"
```

---

### Task 6: Update callers to use extract_metadata

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py` — inside `discover_assets`, the call site that reads frontmatter from MCP READMEs.
- Modify: any other callers of `extract_frontmatter` that operate on assets — search for them.

This task replaces direct `extract_frontmatter(path)` calls with `extract_metadata(path)` so the same code works for both forms.

- [ ] **Step 1: Find all callers**

```bash
cd ~/GitHub/projects/agent-toolkit-cli
grep -rn "extract_frontmatter\|extract_metadata" src/ tests/ | grep -v test_walker_sidecar.py
```

Expected: a handful of call sites in `walker.py`, `commands/check.py`, `commands/ingest.py`, possibly `doctor/frontmatter.py`. Note each.

- [ ] **Step 2: For each non-test caller, swap to `extract_metadata`**

Each caller that does `from agent_toolkit_cli.walker import extract_frontmatter` and calls `extract_frontmatter(path)` on a path that *might* be a sidecar should now do:

```python
from agent_toolkit_cli.walker import extract_metadata
# ...
metadata = extract_metadata(frontmatter_path(asset.path, asset.kind))
```

`frontmatter_path` (updated in Task 5) returns the sidecar path when one exists, so `extract_metadata` will read it correctly. Inline-frontmatter callers keep working unchanged.

- [ ] **Step 3: Run the full test suite**

```bash
uv run pytest -q
```

Expected: 731+ passed. Any regression here means a caller still uses `extract_frontmatter` on a path that's now a sidecar — fix and re-run.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_cli/
git commit -m "refactor: callers use extract_metadata() to support both metadata forms"
```

---

### Task 7: Sidecar mutex check in `agent-toolkit-cli check`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/check.py`
- Test: `tests/test_check_mutex.py` (new)

The walker already silently skips the mutex case. We want `check --exit-code` to fail loudly with a clear message.

- [ ] **Step 1: Write the failing test**

Create `tests/test_check_mutex.py`:

```python
"""Tests for the mutex-violation check (sidecar + inline both present)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _setup_mutex_violation(toolkit_root: Path) -> None:
    """Create skills/foo/ with BOTH inline frontmatter AND a sidecar."""
    skill_dir = toolkit_root / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: inline.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    sidecar = toolkit_root / "skills" / "foo.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: sidecar.\n  lifecycle: experimental\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
    )


def test_check_fails_on_mutex_violation(tmp_path: Path) -> None:
    _setup_mutex_violation(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(tmp_path),
         "check", "--exit-code"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "MutexViolation" in result.stdout + result.stderr
    assert "skills/foo" in result.stdout + result.stderr
    assert "foo.toolkit.yaml" in result.stdout + result.stderr
    assert "SKILL.md" in result.stdout + result.stderr
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_check_mutex.py -v
```

Expected: FAIL (mutex violation not detected today; check returns 0).

- [ ] **Step 3: Add mutex detection to check.py**

In `src/agent_toolkit_cli/commands/check.py`, find the `check` Click command function. Before the asset-validation loop, add a mutex pass:

```python
def _detect_mutex_violations(toolkit_root: Path) -> list[str]:
    """Return error messages for any (kind, slug) with both sidecar AND inline."""
    from agent_toolkit_cli.walker import (
        _SIDECAR_KINDS,
        _KIND_ROOT,
        read_sidecar,
        extract_frontmatter,
        _inline_body_path,
    )
    errors: list[str] = []
    for kind in _SIDECAR_KINDS:
        root = toolkit_root / _KIND_ROOT[kind]
        if not root.exists():
            continue
        for sidecar in sorted(root.glob("*.toolkit.yaml")):
            slug = sidecar.name[: -len(".toolkit.yaml")]
            if read_sidecar(sidecar) is None:
                continue
            inline = _inline_body_path(kind, slug, toolkit_root)
            if inline.is_file() and extract_frontmatter(inline) is not None:
                errors.append(
                    f"MutexViolation: {kind}/{slug}: both "
                    f"{sidecar.relative_to(toolkit_root)} and "
                    f"{inline.relative_to(toolkit_root)} exist. "
                    f"Delete one, or run `agent-toolkit-cli doctor --fix`."
                )
    return errors
```

Then, in the existing `check` command function, near the top of the validation flow:

```python
    # Mutex check — fail fast before per-asset schema validation
    mutex_errors = _detect_mutex_violations(toolkit_root)
    if mutex_errors:
        for msg in mutex_errors:
            click.echo(msg, err=True)
        if exit_code:
            sys.exit(2)
```

Make sure `import sys` is at the top of `check.py` (it likely already is; if not, add it).

- [ ] **Step 4: Verify pass**

```bash
uv run pytest tests/test_check_mutex.py -v
```

Expected: PASS.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```

Expected: still 731+. No regression on real assets (this repo has no mutex violations today).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/check.py tests/test_check_mutex.py
git commit -m "feat(check): detect sidecar/inline mutex violations; exit 2"
```

---

### Task 8: `new skill <slug>` defaults to sidecar form

**Files:**
- Modify: `src/agent_toolkit_cli/commands/new.py`
- Test: `tests/test_new_command_sidecar.py` (new)

Today `agent-toolkit-cli new skill foo` creates `skills/foo/SKILL.md` with inline frontmatter. Going forward, the default creates two files (body + sidecar). `--inline` opts back to the old shape.

- [ ] **Step 1: Write the failing test**

Create `tests/test_new_command_sidecar.py`:

```python
"""Tests for the `new` command's sidecar-default behavior."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def _run_new(toolkit_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(toolkit_root),
         "new", *args],
        capture_output=True,
        text=True,
    )


class TestNewSkillSidecar:
    def test_new_skill_creates_sidecar_by_default(self, tmp_path: Path) -> None:
        result = _run_new(tmp_path, "skill", "foo")
        assert result.returncode == 0, result.stderr
        sidecar = tmp_path / "skills" / "foo.toolkit.yaml"
        body = tmp_path / "skills" / "foo" / "SKILL.md"
        assert sidecar.exists()
        assert body.exists()
        # Body should NOT have inline frontmatter
        body_text = body.read_text()
        assert not body_text.startswith("---\n")
        # Sidecar should be valid YAML with the expected shape
        meta = yaml.safe_load(sidecar.read_text())
        assert meta["apiVersion"] == "agent-toolkit/v1alpha2"
        assert meta["metadata"]["name"] == "foo"

    def test_new_skill_inline_flag_uses_inline_form(self, tmp_path: Path) -> None:
        result = _run_new(tmp_path, "skill", "bar", "--inline")
        assert result.returncode == 0, result.stderr
        sidecar = tmp_path / "skills" / "bar.toolkit.yaml"
        body = tmp_path / "skills" / "bar" / "SKILL.md"
        assert not sidecar.exists()
        assert body.exists()
        assert body.read_text().startswith("---\n")
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_new_command_sidecar.py -v
```

Expected: FAIL (no sidecar created today).

- [ ] **Step 3: Add `--inline` flag and sidecar template to `new.py`**

In `src/agent_toolkit_cli/commands/new.py`:

1. Near the top of the file, add the sidecar template constants:

```python
_SIDECAR_TEMPLATE = """apiVersion: agent-toolkit/v1alpha2
metadata:
  name: {slug}
  description: TODO write one sentence ending with a period.
  lifecycle: experimental
spec:
  origin: first-party
  vendored_via: none
  harnesses:
    - claude
"""

_BODY_TEMPLATE_NO_FRONTMATTER = """# {slug}

TODO body.
"""
```

2. Add `--inline` to the Click command decorator:

```python
@click.option(
    "--inline",
    is_flag=True,
    default=False,
    help="(skill/mcp only) Use inline frontmatter in the body file instead of a sidecar.",
)
```

3. In the command body, branch on kind + `--inline`:

```python
def new(kind: str, slug: str, inline: bool, toolkit_root: Path) -> None:
    # ... existing slug validation ...

    sidecar_kinds = {"skill", "mcp"}
    use_sidecar = kind in sidecar_kinds and not inline

    rel_template, fmt = _KIND_LAYOUT[kind]
    target = toolkit_root / rel_template.format(slug=slug)
    target.parent.mkdir(parents=True, exist_ok=True)

    if use_sidecar:
        # Write body without frontmatter
        target.write_text(_BODY_TEMPLATE_NO_FRONTMATTER.format(slug=slug))
        # Write sidecar — reuse _KIND_ROOT from walker.py (Task 2)
        from agent_toolkit_cli.walker import _KIND_ROOT
        sidecar = toolkit_root / _KIND_ROOT[kind] / f"{slug}.toolkit.yaml"
        sidecar.write_text(_SIDECAR_TEMPLATE.format(slug=slug))
        click.echo(f"Created {target.relative_to(toolkit_root)}")
        click.echo(f"Created {sidecar.relative_to(toolkit_root)}")
    else:
        # Existing inline-frontmatter path
        # ... existing code unchanged ...
```

- [ ] **Step 4: Verify pass**

```bash
uv run pytest tests/test_new_command_sidecar.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -q
```

Expected: 731+ passed.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/new.py tests/test_new_command_sidecar.py
git commit -m "feat(new): default to sidecar form for skill+mcp; --inline opts back"
```

---

### Task 9: Doctor — OrphanBody advisory group

**Files:**
- Create: `src/agent_toolkit_cli/doctor/orphans.py`
- Modify: `src/agent_toolkit_cli/commands/doctor.py`
- Test: `tests/test_doctor_orphans.py` (new)

When a body directory exists with no metadata anywhere (no inline frontmatter, no sidecar), the slug is silently skipped by the walker. Today that's invisible; post-migration, it's the most likely "I forgot to write a sidecar" mistake. The OrphanBody group surfaces it as advisory in `doctor` (not a `check` failure).

- [ ] **Step 1: Write the failing test**

Create `tests/test_doctor_orphans.py`:

```python
"""Tests for the doctor 'orphans' group — orphan body directories."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.doctor.orphans import diagnose_orphans
from agent_toolkit_cli.doctor.result import Status


def _make_orphan_body(root: Path, slug: str) -> None:
    """skills/<slug>/SKILL.md exists, but no inline FM and no sidecar."""
    skill_dir = root / "skills" / slug
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# Orphan\n\nNo metadata anywhere.\n")


def test_orphan_body_is_advisory(tmp_path: Path) -> None:
    _make_orphan_body(tmp_path, "lonely")
    result = diagnose_orphans(tmp_path)
    assert result.status == Status.ADVISORY
    assert any("lonely" in finding for finding in result.findings)


def test_no_orphans_passes(tmp_path: Path) -> None:
    # skills/foo/ with inline frontmatter — not an orphan
    skill_dir = tmp_path / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: x.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    result = diagnose_orphans(tmp_path)
    assert result.status == Status.PASS
    assert result.findings == []
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_doctor_orphans.py -v
```

Expected: FAIL with ImportError.

- [ ] **Step 3: Look at an existing doctor group for the GroupResult/Status shape**

```bash
cat src/agent_toolkit_cli/doctor/result.py
cat src/agent_toolkit_cli/doctor/submodules.py | head -40
```

Confirm: `GroupResult` has `summary`, `findings`, `status` fields; `Status` is an enum with `PASS`, `WARN`, `FAIL` (and possibly `ADVISORY` — if not, add it).

- [ ] **Step 4: Add `ADVISORY` to Status if missing**

If `Status` doesn't have `ADVISORY`, add it to `src/agent_toolkit_cli/doctor/result.py`:

```python
class Status(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    ADVISORY = "advisory"   # informational; never blocks check
```

- [ ] **Step 5: Create `src/agent_toolkit_cli/doctor/orphans.py`**

```python
"""Doctor group: orphan body directories (no metadata anywhere)."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.doctor.result import GroupResult, Status
from agent_toolkit_cli.walker import (
    _SIDECAR_KINDS,
    _KIND_ROOT,
    _inline_body_path,
    extract_frontmatter,
    read_sidecar,
    _sidecar_path,
)


def diagnose_orphans(toolkit_root: Path) -> GroupResult:
    findings: list[str] = []
    for kind in _SIDECAR_KINDS:
        root = toolkit_root / _KIND_ROOT[kind]
        if not root.exists():
            continue
        for body_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            slug = body_dir.name
            inline = _inline_body_path(kind, slug, toolkit_root)
            sidecar = _sidecar_path(kind, slug, toolkit_root)
            has_inline = inline.is_file() and extract_frontmatter(inline) is not None
            has_sidecar = read_sidecar(sidecar) is not None
            if not has_inline and not has_sidecar:
                findings.append(
                    f"Orphan body: {body_dir.relative_to(toolkit_root)} "
                    f"has no metadata. Add inline frontmatter or {sidecar.name}."
                )
    return GroupResult(
        summary=f"{len(findings)} orphan body director{'y' if len(findings)==1 else 'ies'} found",
        findings=findings,
        status=Status.ADVISORY if findings else Status.PASS,
    )
```

- [ ] **Step 6: Wire `orphans` into the doctor command**

In `src/agent_toolkit_cli/commands/doctor.py`, add to the imports:

```python
from agent_toolkit_cli.doctor import orphans as g_orphans
```

Add `"orphans"` to the `_GROUPS` tuple. Add a case to the group dispatcher (search for how other groups are dispatched and follow the same pattern; usually a dict mapping group-name → diagnose function).

- [ ] **Step 7: Verify the unit test passes**

```bash
uv run pytest tests/test_doctor_orphans.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Run full suite**

```bash
uv run pytest -q
```

Expected: 731+ passed; no new failures.

- [ ] **Step 9: Commit**

```bash
git add src/agent_toolkit_cli/doctor/orphans.py src/agent_toolkit_cli/doctor/result.py src/agent_toolkit_cli/commands/doctor.py tests/test_doctor_orphans.py
git commit -m "feat(doctor): orphan-body advisory group"
```

---

### Task 10: Doctor — autofix scaffolding (dry-run only in PR 1)

**Files:**
- Create: `src/agent_toolkit_cli/doctor/autofix.py`
- Modify: `src/agent_toolkit_cli/commands/doctor.py` — add `--fix`, `--dry-run`, `--yes` flags
- Test: `tests/test_doctor_autofix_dryrun.py` (new)

PR 1 ships the scaffolding only: `doctor --fix --dry-run` lists what would change but writes nothing. The actual write logic activates in PR 3 (after the content-repo MCP migration runs).

- [ ] **Step 1: Write the failing test**

Create `tests/test_doctor_autofix_dryrun.py`:

```python
"""Tests for doctor --fix --dry-run (PR 1: no writes happen)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _mutex_violation(toolkit_root: Path) -> None:
    skill_dir = toolkit_root / "skills" / "dup"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: dup\n  description: inline.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    (toolkit_root / "skills" / "dup.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: dup\n  description: sidecar.\n  lifecycle: experimental\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
    )


def test_dry_run_reports_but_writes_nothing(tmp_path: Path) -> None:
    _mutex_violation(tmp_path)
    sidecar = tmp_path / "skills" / "dup.toolkit.yaml"
    body = tmp_path / "skills" / "dup" / "SKILL.md"
    sidecar_before = sidecar.read_text()
    body_before = body.read_text()

    result = subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(tmp_path),
         "doctor", "--fix", "--dry-run", "--yes"],
        capture_output=True, text=True,
    )
    # dry-run never errors out (it's diagnostic)
    assert "Would " in result.stdout
    assert "dup" in result.stdout
    # Crucially: nothing changed on disk
    assert sidecar.read_text() == sidecar_before
    assert body.read_text() == body_before
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_doctor_autofix_dryrun.py -v
```

Expected: FAIL (no `--fix` flag yet).

- [ ] **Step 3: Create `src/agent_toolkit_cli/doctor/autofix.py`**

```python
"""Doctor autofix — mechanical resolutions for sidecar/inline mutex etc.

PR 1: dry-run scaffolding only. Actual write logic activates in PR 3.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_toolkit_cli.walker import (
    _SIDECAR_KINDS,
    _KIND_ROOT,
    _inline_body_path,
    extract_frontmatter,
    read_sidecar,
    _sidecar_path,
)


@dataclass(frozen=True)
class Fixable:
    """Describes one mechanically-resolvable issue."""
    kind: str
    slug: str
    issue: str       # "mutex" | "orphan-body"
    action: str      # human-readable "would do X"
    target_path: Path


def find_fixables(toolkit_root: Path) -> list[Fixable]:
    """Walk the repo and produce the list of mechanically-fixable issues."""
    fixables: list[Fixable] = []
    submodule_paths = _submodule_paths(toolkit_root)
    for kind in _SIDECAR_KINDS:
        root = toolkit_root / _KIND_ROOT[kind]
        if not root.exists():
            continue
        for sidecar in sorted(root.glob("*.toolkit.yaml")):
            slug = sidecar.name[: -len(".toolkit.yaml")]
            if read_sidecar(sidecar) is None:
                continue
            inline = _inline_body_path(kind, slug, toolkit_root)
            if inline.is_file() and extract_frontmatter(inline) is not None:
                # Mutex violation: prefer sidecar. If body is under a submodule
                # path, we can't safely strip its frontmatter; refuse to autofix
                # that case (operator must intervene).
                if _path_under(inline, submodule_paths):
                    fixables.append(Fixable(
                        kind=kind, slug=slug, issue="mutex",
                        action=(
                            f"Refuse autofix: {inline.relative_to(toolkit_root)} "
                            f"is inside a submodule; cannot strip its frontmatter."
                        ),
                        target_path=inline,
                    ))
                else:
                    fixables.append(Fixable(
                        kind=kind, slug=slug, issue="mutex",
                        action=(
                            f"Would strip inline frontmatter from "
                            f"{inline.relative_to(toolkit_root)} "
                            f"(sidecar wins)."
                        ),
                        target_path=inline,
                    ))
    return fixables


def apply_fixable(item: Fixable) -> None:
    """Apply a fix. PR 1: not implemented — raises NotImplementedError."""
    raise NotImplementedError(
        "Autofix writes activate in PR 3. Run `doctor --fix --dry-run` for now."
    )


def _submodule_paths(toolkit_root: Path) -> list[Path]:
    import configparser
    gm = toolkit_root / ".gitmodules"
    if not gm.exists():
        return []
    parser = configparser.ConfigParser()
    parser.read(gm)
    paths: list[Path] = []
    for sect in parser.sections():
        rel = parser[sect].get("path")
        if rel:
            paths.append((toolkit_root / rel).resolve())
    return paths


def _path_under(path: Path, submodule_paths: list[Path]) -> bool:
    rp = path.resolve()
    for sm in submodule_paths:
        try:
            rp.relative_to(sm)
            return True
        except ValueError:
            continue
    return False
```

- [ ] **Step 4: Wire `--fix`, `--dry-run`, `--yes` into doctor**

In `src/agent_toolkit_cli/commands/doctor.py`:

1. Import:
```python
from agent_toolkit_cli.doctor.autofix import find_fixables
```

2. Add three options:
```python
@click.option("--fix", is_flag=True, help="Apply mechanical autofixes (writes!).")
@click.option("--dry-run", is_flag=True, help="With --fix: show what would change; do not write.")
@click.option("--yes", is_flag=True, help="With --fix: no prompts; favour sidecar on mutex.")
```

3. At the end of the existing doctor command body, before returning:
```python
    if fix:
        click.echo(header("Autofix"))
        fixables = find_fixables(toolkit_root)
        if not fixables:
            click.echo("Nothing to fix.")
        else:
            for item in fixables:
                click.echo(f"  [{item.kind}/{item.slug}] {item.action}")
            if not dry_run:
                click.echo(
                    "\nPR 1 ships dry-run only. Apply path activates in PR 3.",
                    err=True,
                )
                # In PR 3, this is where the per-item apply_fixable() loop lives.
```

- [ ] **Step 5: Verify pass**

```bash
uv run pytest tests/test_doctor_autofix_dryrun.py -v
```

Expected: PASS.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -q
```

Expected: 731+ passed.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/doctor/autofix.py src/agent_toolkit_cli/commands/doctor.py tests/test_doctor_autofix_dryrun.py
git commit -m "feat(doctor): --fix --dry-run scaffolding; write path lands in PR 3"
```

---

### Task 11: Migration helper — `agent-toolkit-cli migrate-mcps-to-sidecar`

**Files:**
- Create: `src/agent_toolkit_cli/commands/migrate_mcps_to_sidecar.py`
- Modify: `src/agent_toolkit_cli/__init__.py` (or wherever Click commands are registered) to add the new command
- Test: `tests/test_migrate_mcps.py` (new)

This is a one-shot script the operator runs from the content repo (per the PR 2 prompt in the spec). It moves the `agent_toolkit_cli` frontmatter block from each `mcps/<slug>/README.md` to a sidebar `mcps/<slug>/<slug>.toolkit.yaml`, then strips the frontmatter from the README. It is removed in PR 3.

- [ ] **Step 1: Write the failing test**

Create `tests/test_migrate_mcps.py`:

```python
"""Tests for the migrate-mcps-to-sidecar one-shot script."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def _make_mcp_with_readme_frontmatter(root: Path, slug: str) -> None:
    mcp_dir = root / "mcps" / slug
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type": "stdio", "command": "npx"}')
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n  name: {slug}\n  description: An MCP.\n"
        "  kind: mcp\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  harnesses: [claude]\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n    command: npx\n"
        f"  upstream: https://github.com/example/{slug}\n"
        "---\n\n"
        f"# {slug}\n\nDocumentation prose.\n"
    )


def _run_migrate(toolkit_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(toolkit_root),
         "migrate-mcps-to-sidecar", *extra],
        capture_output=True, text=True,
    )


class TestMigrateMcps:
    def test_emits_sidecar_and_strips_readme(self, tmp_path: Path) -> None:
        _make_mcp_with_readme_frontmatter(tmp_path, "context7")
        result = _run_migrate(tmp_path)
        assert result.returncode == 0, result.stderr
        sidecar = tmp_path / "mcps" / "context7.toolkit.yaml"
        readme = tmp_path / "mcps" / "context7" / "README.md"
        assert sidecar.exists()
        meta = yaml.safe_load(sidecar.read_text())
        assert meta["metadata"]["name"] == "context7"
        assert "transport" in meta["spec"]["mcp"]
        # README should no longer have frontmatter
        readme_text = readme.read_text()
        assert not readme_text.startswith("---\n")
        assert readme_text.startswith("# context7")

    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        _make_mcp_with_readme_frontmatter(tmp_path, "context7")
        readme_before = (tmp_path / "mcps" / "context7" / "README.md").read_text()
        result = _run_migrate(tmp_path, "--dry-run")
        assert result.returncode == 0, result.stderr
        sidecar = tmp_path / "mcps" / "context7.toolkit.yaml"
        readme_after = (tmp_path / "mcps" / "context7" / "README.md").read_text()
        assert not sidecar.exists()
        assert readme_after == readme_before
        assert "Would write" in result.stdout

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running twice should not change anything the second time."""
        _make_mcp_with_readme_frontmatter(tmp_path, "context7")
        _run_migrate(tmp_path)
        readme_text = (tmp_path / "mcps" / "context7" / "README.md").read_text()
        sidecar_text = (tmp_path / "mcps" / "context7.toolkit.yaml").read_text()
        result = _run_migrate(tmp_path)
        assert result.returncode == 0
        assert (tmp_path / "mcps" / "context7" / "README.md").read_text() == readme_text
        assert (tmp_path / "mcps" / "context7.toolkit.yaml").read_text() == sidecar_text
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_migrate_mcps.py -v
```

Expected: FAIL (command doesn't exist).

- [ ] **Step 3: Create the migration script**

Create `src/agent_toolkit_cli/commands/migrate_mcps_to_sidecar.py`:

```python
"""One-shot migration: move MCP frontmatter from README.md to sidecar."""
from __future__ import annotations

from pathlib import Path

import click
import yaml

from agent_toolkit_cli._repo_resolution import RepoNotFoundError, resolve_toolkit_root
from agent_toolkit_cli._ui import header, summary
from agent_toolkit_cli.walker import extract_frontmatter


@click.command(
    name="migrate-mcps-to-sidecar",
    short_help="One-shot: move MCP frontmatter from README.md to sidecar files.",
)
@click.option("--toolkit-repo", "toolkit_root", default=None,
              type=click.Path(file_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Report what would change; write nothing.")
def migrate_mcps_to_sidecar(toolkit_root: Path | None, dry_run: bool) -> None:
    try:
        root = resolve_toolkit_root(toolkit_root)
    except RepoNotFoundError as e:
        raise click.ClickException(str(e))

    click.echo(header("Migrate MCP metadata to sidecars"))
    mcps_dir = root / "mcps"
    if not mcps_dir.is_dir():
        click.echo("No mcps/ directory found.")
        return

    moved = 0
    skipped = 0
    for mcp_dir in sorted(p for p in mcps_dir.iterdir() if p.is_dir()):
        slug = mcp_dir.name
        readme = mcp_dir / "README.md"
        sidecar = mcps_dir / f"{slug}.toolkit.yaml"

        if sidecar.exists() and not readme.is_file():
            skipped += 1
            continue
        if not readme.is_file():
            skipped += 1
            continue
        fm = extract_frontmatter(readme)
        if fm is None:
            # README has no toolkit frontmatter — nothing to migrate
            skipped += 1
            continue
        if sidecar.exists():
            # Sidecar already exists AND README has frontmatter — mutex case.
            # Let `check` flag it; don't migrate over an existing sidecar.
            skipped += 1
            continue

        # Strip frontmatter from README
        text = readme.read_text(encoding="utf-8").replace("\r\n", "\n")
        # The frontmatter is everything from "---\n" to "\n---\n" inclusive
        end = text.find("\n---\n", 4)
        if end == -1:
            skipped += 1
            continue
        new_readme = text[end + len("\n---\n") :].lstrip("\n")

        # Emit sidecar
        sidecar_yaml = yaml.safe_dump(fm, sort_keys=False, default_flow_style=False)

        if dry_run:
            click.echo(f"  Would write {sidecar.relative_to(root)}")
            click.echo(f"  Would strip frontmatter from {readme.relative_to(root)}")
        else:
            sidecar.write_text(sidecar_yaml, encoding="utf-8")
            readme.write_text(new_readme, encoding="utf-8")
            click.echo(f"  Wrote {sidecar.relative_to(root)}")
            click.echo(f"  Stripped frontmatter from {readme.relative_to(root)}")
        moved += 1

    click.echo(summary(f"Migrated {moved} MCP(s); skipped {skipped}."))
```

- [ ] **Step 4: Register the command**

Find where other commands are registered (e.g. `src/agent_toolkit_cli/__init__.py` or `src/agent_toolkit_cli/__main__.py`). Add:

```python
from agent_toolkit_cli.commands.migrate_mcps_to_sidecar import migrate_mcps_to_sidecar
# ...
cli.add_command(migrate_mcps_to_sidecar)
```

- [ ] **Step 5: Verify pass**

```bash
uv run pytest tests/test_migrate_mcps.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -q
```

Expected: 731+ passed.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/migrate_mcps_to_sidecar.py src/agent_toolkit_cli/ tests/test_migrate_mcps.py
git commit -m "feat: add migrate-mcps-to-sidecar one-shot script (removed in PR 3)"
```

---

### Task 12: Integration test — sidecar-described skill links identically to inline

**Files:**
- Create: `tests/test_link_sidecar_parity.py`

End-to-end check that the link output for a sidecar-described skill is byte-identical to the link output for the same skill described inline.

- [ ] **Step 1: Write the test**

Create `tests/test_link_sidecar_parity.py`:

```python
"""Integration: sidecar-described skill projects identically to inline."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def _setup_with_inline(root: Path) -> None:
    skill_dir = root / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: Test skill.\n  lifecycle: stable\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nBody text.\n"
    )


def _setup_with_sidecar(root: Path) -> None:
    skill_dir = root / "skills" / "foo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("Body text.\n")
    (root / "skills" / "foo.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: foo\n  description: Test skill.\n  lifecycle: stable\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
    )


def test_inventory_lists_sidecar_skill(tmp_path: Path) -> None:
    _setup_with_sidecar(tmp_path)
    result = subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(tmp_path),
         "inventory", "skill"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "foo" in result.stdout


def test_inventory_output_identical_inline_vs_sidecar(tmp_path: Path) -> None:
    inline_root = tmp_path / "inline"
    sidecar_root = tmp_path / "sidecar"
    inline_root.mkdir()
    sidecar_root.mkdir()
    _setup_with_inline(inline_root)
    _setup_with_sidecar(sidecar_root)

    def _inv(root: Path) -> str:
        out = subprocess.run(
            [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(root),
             "inventory", "skill"],
            capture_output=True, text=True,
        )
        # Strip absolute paths so the comparison is portable
        return out.stdout.replace(str(root), "<ROOT>")

    inline_out = _inv(inline_root)
    sidecar_out = _inv(sidecar_root)
    # The two should be identical except for the LOCATION line, which legitimately
    # differs (one is SKILL.md, the other is foo.toolkit.yaml).
    inline_filtered = "\n".join(
        line for line in inline_out.splitlines() if not line.startswith("LOCATION")
    )
    sidecar_filtered = "\n".join(
        line for line in sidecar_out.splitlines() if not line.startswith("LOCATION")
    )
    assert inline_filtered == sidecar_filtered
```

- [ ] **Step 2: Run the test**

```bash
uv run pytest tests/test_link_sidecar_parity.py -v
```

Expected: PASS. If failing, the inventory output likely differs in unexpected ways — investigate and either widen the filter or fix the actual divergence.

- [ ] **Step 3: Commit**

```bash
git add tests/test_link_sidecar_parity.py
git commit -m "test: integration parity between inline and sidecar discovery"
```

---

### Task 13: AGENTS.md updates (CLI repo)

**Files:**
- Modify: `AGENTS.md` (CLI repo)

Update three invariant sections to reflect the new reality.

- [ ] **Step 1: Read the current asset-identity section**

```bash
cd ~/GitHub/projects/agent-toolkit-cli
grep -n "metadata in exactly one place\|One asset, one metadata\|Sidecar" AGENTS.md
```

If the wording doesn't exist yet in the CLI repo's AGENTS.md, look for the "Asset identity" or "Invariants" section and add it. If the rule is in `agent-toolkit/AGENTS.md` instead (the content repo), this task's edits live in the **content repo** and ship via PR 4 — skip this CLI-repo task.

- [ ] **Step 2: Add or update the "Asset identity" invariant**

Insert under the Invariants section (replace any contradicting prior wording):

```markdown
### Asset identity

- **Slug equality** — `metadata.name` MUST equal the on-disk slug.
- **One asset, one metadata location.** Every asset carries metadata in
  exactly one place:
  - **skill** — sidecar `skills/<slug>.toolkit.yaml` (preferred) OR inline
    frontmatter in `skills/<slug>/SKILL.md` (legacy). Never both.
  - **mcp** — sidecar `mcps/<slug>.toolkit.yaml` (post-PR-3, the only form).
  - **agent**, **command** — inline frontmatter in `<slug>.md`.
  - **hook**, **pi-extension** — dedicated `.meta.yaml` sidecar.
  - **plugin** — inline `agent_toolkit_cli` JSON key in `plugin.json`.
- **Mutex rule** — if both sidecar AND inline metadata exist for the same
  slug, `agent-toolkit-cli check` exits 2. Lefthook pre-commit blocks the
  commit until one is removed.
```

- [ ] **Step 3: Run check on the CLI repo's own assets (if any)**

```bash
uv run pytest -q
```

Expected: still 731+ passed.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md
git commit -m "docs(AGENTS): document sidecar/inline mutex; clarify per-kind locations"
```

---

### Task 14: CLI documentation — `docs/agent-toolkit/cli.md`

**Files:**
- Modify: `docs/agent-toolkit/cli.md`

Add a "Sidecar metadata" section; document the new `--inline` flag on `new`; document `--fix`, `--dry-run`, `--yes` on `doctor`.

- [ ] **Step 1: Add the "Sidecar metadata" section**

Append (or insert at a logical position) to `docs/agent-toolkit/cli.md`:

```markdown
## Sidecar metadata

Skill and MCP assets can declare their toolkit metadata in one of two
locations:

- **Sidecar (preferred for new assets):** A sibling YAML file named
  `<slug>.toolkit.yaml`, living next to the asset directory:

  ```
  skills/
    deep-research/                  ← body (may be a submodule)
      SKILL.md
    deep-research.toolkit.yaml      ← sidecar (this repo)
  ```

- **Inline (legacy):** YAML frontmatter at the top of the body file
  (`SKILL.md` for skills; `README.md` for pre-migration MCPs).

The sidecar form exists so that **submoduled or vendored upstream content
can be ingested without modifying upstream files**. The body stays exactly
as upstream published it; the toolkit's `apiVersion`/`metadata`/`spec`
block lives in the sidecar.

### Choosing a form

- **Use sidecar** for any asset whose body is third-party (submoduled,
  cloned from upstream, or vendored verbatim).
- **Use inline** when authoring a self-contained first-party skill that
  doesn't need to track an upstream — fewer files, full colocation.
- New assets default to sidecar via `agent-toolkit-cli new`. Pass
  `--inline` to opt back to single-file authoring.

### Mutex rule

Both sidecar and inline metadata for the same slug is an error.
`agent-toolkit-cli check` exits 2; the lefthook gate blocks the commit.
The fix:

```
agent-toolkit-cli doctor --fix --dry-run    # show what would change
agent-toolkit-cli doctor --fix --yes        # apply: favour sidecar
```

The `--yes` mode always prefers the sidecar (consistent with the
sidecar-as-preferred-form policy). Without `--yes`, doctor prompts
per finding.
```

- [ ] **Step 2: Update the `new` subcommand doc**

Find the `new` command section. Update the synopsis and add an example:

```markdown
### `new <kind> <slug> [--inline]`

Scaffold a new asset. For `skill` and `mcp`, the default creates two
files: a body without frontmatter, and a `<slug>.toolkit.yaml` sidecar.
Pass `--inline` to create a single file with inline frontmatter instead.

For `agent`, `command`, `hook`, `plugin`, and `pi-extension`, the
existing single-file shape is used regardless of the `--inline` flag.
```

- [ ] **Step 3: Update the `doctor` subcommand doc**

Find the `doctor` section. Add:

```markdown
### `doctor --fix [--dry-run] [--yes]`

Apply mechanical autofixes for sidecar-related issues:

- **Mutex violation** (both sidecar AND inline for same slug) — favour
  sidecar by default; strip inline frontmatter from the body file. Refuses
  to edit files inside submodule paths.
- **Orphan sidecar** (sidecar exists, body directory does not) — refuses
  to autofix; surfaces the path so the operator can decide.
- **Orphan body** (body exists with no metadata anywhere) — emits a stub
  `<slug>.toolkit.yaml` for the operator to complete.

`--dry-run` reports what would change without writing. `--yes` no-prompts.

In PR 1, only `--dry-run` is functional; the actual write path activates
in PR 3 (after MCP migration is complete in the content repo).
```

- [ ] **Step 4: Commit**

```bash
git add docs/agent-toolkit/cli.md
git commit -m "docs(cli): add 'Sidecar metadata' section; document new --inline + doctor --fix"
```

---

### Task 15: Harness-matrix one-line clarification

**Files:**
- Modify: `docs/agent-toolkit/harness-matrix.md`

The matrix is about projection mechanisms (Kind × Harness). Sidecars are a metadata-discovery concern that doesn't affect the matrix cells. Add one clarifying sentence so readers don't get confused.

- [ ] **Step 1: Edit the matrix doc**

In `docs/agent-toolkit/harness-matrix.md`, after the §1 mechanisms list, add:

```markdown
### Sidecar metadata vs projection mechanisms

The mechanisms above describe how an asset is **projected** into a harness
(symlink, translate, config_file, etc.). The asset's **metadata location**
(inline frontmatter vs sidecar `<slug>.toolkit.yaml`) is an orthogonal
concern handled at discovery time — see `cli.md` "Sidecar metadata."
The matrix cells are identical regardless of where the metadata lives.
```

- [ ] **Step 2: Run the parity test to ensure no matrix cells were disturbed**

```bash
uv run pytest tests/test_harness_matrix.py -v
```

Expected: 13 passed.

- [ ] **Step 3: Commit**

```bash
git add docs/agent-toolkit/harness-matrix.md
git commit -m "docs(matrix): clarify sidecar metadata is orthogonal to projection mechanisms"
```

---

### Task 16: Final pre-PR full-suite + lefthook gate

- [ ] **Step 1: Run the full pytest suite**

```bash
cd ~/GitHub/projects/agent-toolkit-cli
uv run pytest -q
```

Expected: all green; new tests + 731 existing.

- [ ] **Step 2: Run the lefthook pre-commit gate manually**

```bash
lefthook run pre-commit
```

Expected: all hooks green.

- [ ] **Step 3: Review the full branch diff**

```bash
git log --oneline main..HEAD
git diff main..HEAD --stat
```

Expected:
- ~13 commits (Tasks 1–15)
- Modified: `walker.py`, `commands/check.py`, `commands/new.py`, `commands/doctor.py`, schema vendored copy, AGENTS.md, several docs.
- Created: `doctor/orphans.py`, `doctor/autofix.py`, `commands/migrate_mcps_to_sidecar.py`, several test files.

- [ ] **Step 4: No commit — proceed to PR open in Task 17**

---

### Task 17: Open PR 1

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feat/sidecar-metadata-discovery-pr1
```

- [ ] **Step 2: Open the PR via gh**

```bash
gh pr create --title "feat(sidecar): metadata discovery for skill + mcp (PR 1 of 2)" --body "$(cat <<'EOF'
## Summary

PR 1 of 2 implementing sidecar metadata discovery per
`docs/superpowers/specs/2026-05-19-sidecar-metadata-discovery-design.md`.

Enables submoduled and vendored upstream skills/MCPs to be ingested without
modifying upstream content, by adding a sibling `<slug>.toolkit.yaml`
metadata location alongside the existing inline-frontmatter form.

## Changes

- Walker: sidecar discovery for skill + mcp; mutex detection.
- `check`: exits 2 on mutex violation.
- `new`: defaults to sidecar form for skill/mcp; `--inline` opts back.
- `doctor`: adds `orphans` advisory group; `--fix --dry-run` scaffolding (write path lands in PR 3).
- Schema: in-place relaxation — `fork` is now optional under `vendored_via: submodule`.
- New one-shot helper: `agent-toolkit-cli migrate-mcps-to-sidecar` (removed in PR 3 after content-repo migration runs).

## Test plan

- [x] All new unit tests pass.
- [x] Existing 731 tests pass.
- [x] Schema vendor parity test passes.
- [x] Harness matrix parity test passes.
- [x] Manual: `agent-toolkit-cli new skill demo` creates two files; `--inline` creates one.
- [x] Manual: artificially creating a mutex violation in a tmp dir, `check --exit-code` exits 2 with a clear message.

## What's not in this PR

- Content-repo MCP migration (PR 2 — operator-run via spec prompt).
- Removing legacy MCP README-frontmatter path (PR 3).
- Activating doctor autofix write logic (PR 3).
- Submoduled-skill sidecars + content-repo docs (PR 4 — operator-run).

## Spec

`docs/superpowers/specs/2026-05-19-sidecar-metadata-discovery-design.md`
EOF
)"
```

- [ ] **Step 3: Return the PR URL**

The `gh pr create` command outputs the URL. Note it for the user; they will review and merge before content-repo work proceeds.

---

## PR 3 — Remove legacy MCP README path; activate doctor autofix writes

> **Prerequisite:** PR 1 merged into `main`. Content-repo PR 2 has run (MCPs migrated to sidecars). The content repo no longer has any `agent_toolkit_cli:` frontmatter inside `mcps/<slug>/README.md`.

### Task 18: Branch from latest main

- [ ] **Step 1: Update local main and branch**

```bash
cd ~/GitHub/projects/agent-toolkit-cli
git checkout main && git pull --rebase
git checkout -b feat/sidecar-metadata-discovery-pr3
uv run pytest -q
```

Expected: 731+ tests pass; baseline green.

- [ ] **Step 2: Verify content-repo migration ran**

```bash
ls ~/GitHub/agent-toolkit/mcps/*.toolkit.yaml | wc -l
grep -l "apiVersion: agent-toolkit" ~/GitHub/agent-toolkit/mcps/*/README.md 2>/dev/null | wc -l
```

Expected: 17 sidecar files; 0 READMEs still carrying frontmatter.

If the second count is non-zero, **stop** — the content-repo migration is incomplete. Re-run PR 2's prompt before continuing.

---

### Task 19: Remove MCP README-frontmatter path from walker

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py`
- Test: `tests/test_walker_mcp_legacy_removed.py` (new)

After this, `frontmatter_path("mcps/foo/config.json", "mcp")` returns the sidecar path; the README is never consulted.

- [ ] **Step 1: Write the regression test**

Create `tests/test_walker_mcp_legacy_removed.py`:

```python
"""Regression: MCP README-frontmatter is no longer parsed for toolkit metadata."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.walker import discover_assets


def test_mcp_with_only_readme_frontmatter_is_not_discovered(tmp_path: Path) -> None:
    """After PR 3, a stale README-with-frontmatter MCP shows up as orphan, not asset."""
    mcp_dir = tmp_path / "mcps" / "ghost"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"x"}')
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: ghost\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n    command: x\n"
        "---\n# ghost\n"
    )
    assets = discover_assets(tmp_path)
    slugs = {a.slug for a in assets if a.kind == "mcp"}
    assert "ghost" not in slugs


def test_mcp_with_sidecar_is_discovered(tmp_path: Path) -> None:
    mcp_dir = tmp_path / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"x"}')
    (mcp_dir / "README.md").write_text("# context7\n\nNo frontmatter, just docs.\n")
    (tmp_path / "mcps" / "context7.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n    command: x\n"
    )
    assets = discover_assets(tmp_path)
    slugs = {a.slug for a in assets if a.kind == "mcp"}
    assert "context7" in slugs
```

- [ ] **Step 2: Run to verify the first test FAILS today**

```bash
uv run pytest tests/test_walker_mcp_legacy_removed.py::test_mcp_with_only_readme_frontmatter_is_not_discovered -v
```

Expected: FAIL (today's walker still discovers MCPs via README frontmatter).

- [ ] **Step 3: Remove the legacy path from `frontmatter_path`**

In `src/agent_toolkit_cli/walker.py`, update `frontmatter_path`:

```python
def frontmatter_path(asset_path: Path, kind: str) -> Path:
    """Return the file carrying the asset's YAML frontmatter.

    Skills and MCPs use sidecar metadata at `<root>/<slug>.toolkit.yaml`.
    All other kinds use inline frontmatter in `asset_path` itself.
    """
    if kind in _SIDECAR_KINDS:
        slug = asset_path.parent.name
        toolkit_root_candidate = asset_path.parent.parent.parent
        return toolkit_root_candidate / _KIND_ROOT[kind] / f"{slug}.toolkit.yaml"
    return asset_path
```

The MCP README fallback is gone.

- [ ] **Step 4: Update `discover_assets` first pass**

The first pass (`for kind, root_name, pattern in _KIND_RULES`) currently discovers MCPs via `config.json` and reads their frontmatter from README.md. With the legacy path removed, MCPs only enter via the second (sidecar) pass. Remove the MCP entry from `_KIND_RULES`:

```python
_KIND_RULES = (
    ("skill", "skills", "SKILL.md"),
    ("agent", "agents", "*.md"),
    ("command", "commands", "*.md"),
    ("hook", "hooks", "*.meta.yaml"),
    # mcp is now sidecar-only — discovered in the second pass via *.toolkit.yaml
    ("pi-extension", "extensions", "extension.meta.yaml"),
)
```

Skills remain in `_KIND_RULES` so that inline-frontmatter skills (the legacy path, still supported) are still discovered.

- [ ] **Step 5: Verify both tests pass**

```bash
uv run pytest tests/test_walker_mcp_legacy_removed.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -q
```

Expected: all green. If any existing MCP-related test breaks, it's because the test was using the README-frontmatter fixture pattern — update the fixture to use a sidecar.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/walker.py tests/test_walker_mcp_legacy_removed.py
git commit -m "feat(walker): remove MCP README-frontmatter legacy path

MCPs are now sidecar-only. The frontmatter_path() special case for MCPs
is gone; the first-pass _KIND_RULES no longer triggers on mcps/<slug>/config.json
since metadata never lives in the README. Sidecar (second pass) is the
only discovery path for MCPs."
```

---

### Task 20: Activate doctor autofix writes

**Files:**
- Modify: `src/agent_toolkit_cli/doctor/autofix.py`
- Modify: `src/agent_toolkit_cli/commands/doctor.py`
- Test: `tests/test_doctor_autofix.py` (new)

PR 1 shipped `apply_fixable()` raising `NotImplementedError`. PR 3 fills it in.

- [ ] **Step 1: Write the failing test**

Create `tests/test_doctor_autofix.py`:

```python
"""Tests for doctor --fix write path (PR 3)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


def _mutex_first_party(toolkit_root: Path) -> tuple[Path, Path]:
    """First-party mutex: body not in submodule."""
    skill_dir = toolkit_root / "skills" / "dup"
    skill_dir.mkdir(parents=True)
    body = skill_dir / "SKILL.md"
    body.write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: dup\n  description: inline.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    sidecar = toolkit_root / "skills" / "dup.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: dup\n  description: sidecar.\n  lifecycle: experimental\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n"
    )
    return sidecar, body


def _mutex_in_submodule(toolkit_root: Path) -> tuple[Path, Path]:
    """Mutex where the inline body is inside a submodule path."""
    skill_dir = toolkit_root / "skills" / "vendored"
    skill_dir.mkdir(parents=True)
    body = skill_dir / "SKILL.md"
    body.write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: vendored\n  description: upstream.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
        "---\n\nbody\n"
    )
    (toolkit_root / ".gitmodules").write_text(
        '[submodule "skills/vendored"]\n  path = skills/vendored\n  url = x\n'
    )
    sidecar = toolkit_root / "skills" / "vendored.toolkit.yaml"
    sidecar.write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: vendored\n  description: sidecar.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: submodule\n"
        "  upstream: https://example.com\n  harnesses: [claude]\n"
    )
    return sidecar, body


def _run_fix(toolkit_root: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(toolkit_root),
         "doctor", "--fix", "--yes", *extra],
        capture_output=True, text=True,
    )


def test_first_party_mutex_strips_inline_keeps_sidecar(tmp_path: Path) -> None:
    sidecar, body = _mutex_first_party(tmp_path)
    sidecar_before = sidecar.read_text()
    _run_fix(tmp_path)
    # Sidecar unchanged; body's frontmatter stripped
    assert sidecar.read_text() == sidecar_before
    body_after = body.read_text()
    assert not body_after.startswith("---\n")
    assert "body" in body_after


def test_submoduled_body_mutex_refuses(tmp_path: Path) -> None:
    sidecar, body = _mutex_in_submodule(tmp_path)
    body_before = body.read_text()
    result = _run_fix(tmp_path)
    # Body inside submodule must NOT be modified
    assert body.read_text() == body_before
    assert "Refuse" in result.stdout or "Refuse" in result.stderr


def test_dry_run_still_writes_nothing(tmp_path: Path) -> None:
    sidecar, body = _mutex_first_party(tmp_path)
    body_before = body.read_text()
    subprocess.run(
        [sys.executable, "-m", "agent_toolkit_cli", "--toolkit-repo", str(tmp_path),
         "doctor", "--fix", "--dry-run", "--yes"],
        capture_output=True, text=True,
    )
    assert body.read_text() == body_before
```

- [ ] **Step 2: Run to verify fail**

```bash
uv run pytest tests/test_doctor_autofix.py -v
```

Expected: FAIL (autofix raises NotImplementedError).

- [ ] **Step 3: Implement `apply_fixable` in autofix.py**

Replace the stub in `src/agent_toolkit_cli/doctor/autofix.py`:

```python
def apply_fixable(item: Fixable) -> None:
    """Apply a mechanical autofix."""
    if item.issue == "mutex":
        path = item.target_path
        # Defense in depth: never edit files in submodule paths
        from agent_toolkit_cli.walker import _read_submodule_paths
        toolkit_root = _find_toolkit_root(path)
        submods = _read_submodule_paths(toolkit_root)
        if _path_under(path, submods):
            return  # already reported as "Refuse" in the action string
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        if not text.startswith("---\n"):
            return
        end = text.find("\n---\n", 4)
        if end == -1:
            return
        stripped = text[end + len("\n---\n") :].lstrip("\n")
        path.write_text(stripped, encoding="utf-8")
        return
    if item.issue == "orphan-body":
        # Emit a stub sidecar
        slug = item.slug
        kind = item.kind
        toolkit_root = _find_toolkit_root(item.target_path)
        sidecar = toolkit_root / _KIND_ROOT[kind] / f"{slug}.toolkit.yaml"
        # Try to extract a description from the body's first H1 or paragraph
        body = item.target_path
        description = "TODO write one sentence ending with a period."
        if body.is_file():
            for line in body.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("# "):
                    description = line[2:].rstrip(".") + "."
                    break
                if line and not line.startswith("#"):
                    description = line.rstrip(".") + "."
                    break
        sidecar.write_text(
            "apiVersion: agent-toolkit/v1alpha2\n"
            f"metadata:\n  name: {slug}\n  description: {description}\n"
            "  lifecycle: experimental\n"
            "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses: [claude]\n",
            encoding="utf-8",
        )


def _find_toolkit_root(path: Path) -> Path:
    """Walk up from a path to find the toolkit root (parent containing skills/, mcps/)."""
    for ancestor in path.resolve().parents:
        if (ancestor / "skills").is_dir() or (ancestor / "mcps").is_dir():
            return ancestor
    raise RuntimeError(f"could not find toolkit root above {path}")
```

Add `from agent_toolkit_cli.walker import _KIND_ROOT` to the imports.

- [ ] **Step 4: Wire autofix application into the doctor command**

In `src/agent_toolkit_cli/commands/doctor.py`, replace the placeholder `"Apply path activates in PR 3"` echo with the real loop:

```python
    if fix:
        click.echo(header("Autofix"))
        fixables = find_fixables(toolkit_root)
        if not fixables:
            click.echo("Nothing to fix.")
        else:
            for item in fixables:
                click.echo(f"  [{item.kind}/{item.slug}] {item.action}")
                if dry_run:
                    continue
                if not yes:
                    if not click.confirm(f"    Apply this fix?", default=True):
                        continue
                try:
                    apply_fixable(item)
                except NotImplementedError as e:
                    click.echo(f"    Skipped: {e}", err=True)
```

Add `from agent_toolkit_cli.doctor.autofix import apply_fixable` to imports.

- [ ] **Step 5: Verify tests pass**

```bash
uv run pytest tests/test_doctor_autofix.py -v
uv run pytest tests/test_doctor_autofix_dryrun.py -v
```

Expected: all green.

- [ ] **Step 6: Run full suite**

```bash
uv run pytest -q
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/doctor/autofix.py src/agent_toolkit_cli/commands/doctor.py tests/test_doctor_autofix.py
git commit -m "feat(doctor): activate --fix write path; never edit files in submodules"
```

---

### Task 21: Delete the migration script

**Files:**
- Delete: `src/agent_toolkit_cli/commands/migrate_mcps_to_sidecar.py`
- Delete: `tests/test_migrate_mcps.py`
- Modify: wherever the command was registered (remove the registration)

- [ ] **Step 1: Delete the files**

```bash
rm src/agent_toolkit_cli/commands/migrate_mcps_to_sidecar.py
rm tests/test_migrate_mcps.py
```

- [ ] **Step 2: Remove the registration**

```bash
grep -rn "migrate_mcps_to_sidecar\|migrate-mcps-to-sidecar" src/
```

Remove the matching import and `cli.add_command(...)` line from wherever it was added in Task 11.

- [ ] **Step 3: Run full suite**

```bash
uv run pytest -q
```

Expected: all green.

- [ ] **Step 4: Confirm the command is gone**

```bash
uv run agent-toolkit-cli --help | grep migrate
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove migrate-mcps-to-sidecar one-shot script (migration complete)"
```

---

### Task 22: Update cli.md to reflect doctor full activation

**Files:**
- Modify: `docs/agent-toolkit/cli.md`

Remove the "PR 1 ships dry-run only" caveat now that the write path is live.

- [ ] **Step 1: Edit cli.md**

Find the paragraph in the `doctor --fix` section that says:

> In PR 1, only `--dry-run` is functional; the actual write path activates in PR 3 (after MCP migration is complete in the content repo).

Replace with:

> `--dry-run` reports what would change without writing. `--yes` no-prompts and always favours the sidecar on mutex violations. Without `--yes`, doctor prompts per finding.

- [ ] **Step 2: Commit**

```bash
git add docs/agent-toolkit/cli.md
git commit -m "docs(cli): remove PR-1 caveat — doctor --fix write path now live"
```

---

### Task 23: Final pre-PR full-suite + lefthook gate

- [ ] **Step 1: Run the full pytest suite**

```bash
uv run pytest -q
```

Expected: all green.

- [ ] **Step 2: Run the lefthook gate manually**

```bash
lefthook run pre-commit
```

Expected: all green.

- [ ] **Step 3: Review the branch diff**

```bash
git log --oneline main..HEAD
git diff main..HEAD --stat
```

Expected: ~5 commits removing the legacy MCP path, activating autofix writes, deleting the migration script, and updating the doc.

---

### Task 24: Open PR 3

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feat/sidecar-metadata-discovery-pr3
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --title "feat(sidecar): remove legacy MCP path + activate doctor --fix writes (PR 3 of 2)" --body "$(cat <<'EOF'
## Summary

PR 3 of 2 (final CLI-side PR) for sidecar metadata discovery.
**Requires:** PR 1 merged AND content-repo PR 2 (MCP migration) complete.

## Changes

- Walker: remove the MCP README-frontmatter legacy path. MCPs are now
  sidecar-only.
- `doctor --fix`: activate the write path (was dry-run-only in PR 1).
  - Mutex violation → strip inline frontmatter; favour sidecar.
  - Refuses to edit files inside submodule paths.
  - Orphan body → emit stub sidecar.
- Delete the one-shot `migrate-mcps-to-sidecar` helper (migration done).
- Documentation: remove PR 1 caveat from `cli.md`.

## Test plan

- [x] All new write-path autofix tests pass.
- [x] Regression test confirms MCP README-frontmatter is no longer parsed.
- [x] Existing tests pass.
- [x] Schema vendor parity passes.

## Spec

`docs/superpowers/specs/2026-05-19-sidecar-metadata-discovery-design.md`
EOF
)"
```

- [ ] **Step 3: Report the PR URL to the user**

End state: both CLI-side PRs open. PR 2 and PR 4 are operator-run via the prompts in the spec.

---

## Self-review (run after writing this plan)

This is the writer's own check; not a separate task.

### Spec coverage

Walking the spec section by section:

- **Schema relaxation** → Task 1 ✓
- **Walker sidecar discovery** → Tasks 2, 3, 4, 5, 6 ✓
- **Mutex `check` rule** → Task 7 ✓
- **`new` defaults to sidecar** → Task 8 ✓
- **OrphanBody doctor advisory** → Task 9 ✓
- **Doctor `--fix` scaffolding** → Task 10 (PR 1) ✓
- **Migration helper script** → Task 11 (PR 1); removed Task 21 (PR 3) ✓
- **AGENTS.md updates (CLI repo)** → Task 13 ✓
- **CLI docs** → Tasks 14, 15 ✓
- **Remove legacy MCP path** → Task 19 (PR 3) ✓
- **Activate doctor writes** → Task 20 (PR 3) ✓
- **Acceptance criteria — `new` defaults to sidecar; `--inline` opts back** → Task 8 + 14 ✓
- **Acceptance criteria — `check --exit-code` remains 0** → Task 7 (and verified in pre-PR full-suite tasks 16, 23) ✓
- **Risk mitigation — autofix never edits submoduled files** → Task 10 (scaffolding) + Task 20 (write path) — explicit submodule guard with regression test in `test_submoduled_body_mutex_refuses` ✓

Content-side PR 2 + PR 4 deliverables (operator prompts) are in the spec, not this plan. Per the conversation, that's correct scope.

### Placeholder scan

Searched for: TBD, TODO, "implement later", "fill in details", "Add appropriate", "Write tests for the above". No matches in task bodies (only "TODO" mentions are inside template strings the user is meant to edit, which is intentional and the template's whole point).

### Type consistency

Checked names across tasks:
- `_sidecar_path` defined Task 2, used Tasks 5, 7, 9, 10 ✓
- `read_sidecar` defined Task 3, used Tasks 4, 7, 9, 10 ✓
- `resolve_metadata` defined Task 4, used (not used elsewhere — kept as a public API helper for future callers; documented in Task 4) ✓
- `extract_metadata` defined Task 5, used Task 6 ✓
- `BothMetadataLocationsExist` defined Task 4, referenced in Task 7's design narrative (not raised directly — check.py builds its own messages via `_detect_mutex_violations`; acceptable since the test asserts on message format, not exception class) ✓
- `_inline_body_path` defined Task 4, used Tasks 7, 9, 10 ✓
- `Fixable` dataclass defined Task 10, used Task 20 ✓
- `apply_fixable` stub Task 10 raising NotImplementedError; real impl Task 20; signature `(item: Fixable) -> None` consistent ✓
- `_KIND_ROOT_FOR_NEW` introduced Task 8 — note: shadows the `_KIND_ROOT` from Task 2. Resolve: use `_KIND_ROOT` (already defined in Task 2) instead of introducing a second table. Fix needed.

Fix the duplicate in Task 8 inline:

The Task 8 step 3 code shows `_KIND_ROOT_FOR_NEW`. Replace usage with `_KIND_ROOT` (defined in Task 2). The lookup table at the bottom of Task 8 step 3 is unnecessary — remove the line `_KIND_ROOT_FOR_NEW = {"skill": "skills", "mcp": "mcps"}` and use `_KIND_ROOT[kind]` directly in the `new.py` write block. Save the operator a confusing duplicate.

