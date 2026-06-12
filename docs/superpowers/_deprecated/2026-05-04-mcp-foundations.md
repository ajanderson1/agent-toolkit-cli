# MCP Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make MCPs first-class citizens of the allow-list and the discovery layer, without yet writing any harness MCP configs. Unblocks the per-harness adapter work that follows.

**Architecture:** Three contained code changes — fix walker's MCP discovery to match the catalog convention (`config.json`, not `mcp.json`); add a `mcps` section to the YAML allow-list and route `kind=mcp` through it; relax the four `mcps are not yet scope-routed` guards in link/unlink and route through the same code path as other kinds, but stop short of writing harness configs (a clear "no-op for now" message is emitted at the projection step). Inventory and `list` learn to surface MCPs alongside other kinds.

**Tech Stack:** Python 3.11+, Click, ruamel.yaml, pytest, jsonschema. No new dependencies.

**Out of scope (deferred to Plan B and later):**
- Per-harness MCP write strategy (plugin folder vs config file).
- Schema bump to v1alpha2 / `metadata.kind`.
- Reading or writing `~/.claude.json`, `~/.codex/config.toml`, `opencode.json`, etc.
- TUI MCP section.

---

## File Structure

**Files this plan modifies:**

- `src/agent_toolkit_cli/walker.py` — fix `_KIND_RULES` for `mcp`: use `config.json` not `mcp.json`. Update `load_asset_record` to read frontmatter from sibling `README.md` instead of from `config.json`. Update `_slug_for` (already correct for `mcp`, but verify).
- `src/agent_toolkit_cli/_allowlist.py` — add `"mcps"` to `SECTIONS`, add `"mcp": "mcps"` to `_KIND_TO_SECTION`, drop the `ValueError` for `kind == "mcp"`.
- `src/agent_toolkit_cli/schema.py` — `_load_metadata` for `kind == "mcp"` reads the sibling README.md frontmatter (matching the new walker behaviour), not the `config.json`'s `agent_toolkit_cli` key.
- `src/agent_toolkit_cli/commands/_link_lib.py` — extend `KINDS_FOR_PROJECTION` with `"mcp"`. Add a no-op branch in `project_from_file` for `kind == "mcp"`: emits a single "MCP install path for <harness> not yet implemented; allow-list updated only" message per (harness, scope, kind=mcp) and increments no link-counters. No symlinks created.
- `src/agent_toolkit_cli/commands/link.py` — remove the two `kind == "mcp"` guard blocks (lines 197–204 and 437–442). MCP requests now flow into the regular per-asset / plan paths.
- `src/agent_toolkit_cli/commands/unlink.py` — remove the two `kind == "mcp"` guard blocks (lines 192–198 and 292–296). Same treatment as link.
- `src/agent_toolkit_cli/commands/list.py` — drop the MCP short-circuit at lines 203–208. MCPs appear in the inventory like any other kind, with install state read via the same path.
- `src/agent_toolkit_cli/commands/_list_json.py` — change `ALL_KINDS` to include `"mcp"`. Drop the `if asset.kind == "mcp": continue` skip in `_build_inventory` (line 128). MCP cells emit `status="unsupported"` per harness for now (since no adapter writes anywhere); `allowlisted` reflects the new YAML section.
- `src/agent_toolkit_cli/commands/_yaml_edit.py` — no code change needed (the writer is section-agnostic; once `_allowlist.SECTIONS` includes `"mcps"`, `add_slug`/`remove_slug`/`write_snapshot` accept it automatically). Verify by test.

**Tests touched:**

- `tests/test_allowlist.py` — flip the `mcp` semantics: was "kind=mcp raises", now "kind=mcp routes to mcps section". Add tests for the new section in `read_allowlist`.
- `tests/test_walker.py` (new file) — assert that `mcps/<slug>/config.json` is discovered, frontmatter is read from sibling README.md, and slug equals the directory name.
- `tests/test_cli_link.py` — replace the "mcps are not yet scope-routed" tests with new tests asserting the YAML mutation succeeds and the "no-op for now" message appears at projection.
- `tests/test_cli_unlink.py` — same structural change as link.
- `tests/test_cli_list.py` — assert MCPs appear in the inventory output with correct allow-listed state.
- `tests/test_list_json.py` — assert `kind=mcp` cells appear in the JSON output with `status="unsupported"` and correct `allowlisted` field.
- `tests/test_link_lib.py` — pin the new no-op behaviour for `kind=mcp` in `project_from_file`.

**No new files** except `tests/test_walker.py` (currently the walker has no dedicated test file).

---

## Task 1: Add `mcps` to the allow-list section list

**Files:**
- Modify: `src/agent_toolkit_cli/_allowlist.py`
- Test: `tests/test_allowlist.py`

- [ ] **Step 1: Update the failing test that pins old behaviour, add new tests**

Replace `tests/test_allowlist.py:27-29` (the `test_kind_to_section_mcp_raises` test) and lines 36-38 (`test_sections_constant_matches_routing`) with:

```python
def test_kind_to_section_mcp():
    assert kind_to_section("mcp") == "mcps"


def test_sections_constant_matches_routing():
    assert set(SECTIONS) == {"skills", "agents", "commands", "hooks", "plugins", "mcps"}


def test_section_to_kind_mcps():
    assert section_to_kind("mcps") == "mcp"


def test_read_allowlist_mcps_section(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text(
        "skills:\n"
        "  - alpha\n"
        "mcps:\n"
        "  - context7\n"
        "  - playwright\n"
    )
    result = read_allowlist(f)
    assert result["skills"] == ["alpha"]
    assert result["mcps"] == ["context7", "playwright"]
```

Also update `tests/test_allowlist.py:32-34` (`test_section_to_kind_inverse`) to include `"mcp"` in the loop:

```python
def test_section_to_kind_inverse():
    for kind in ("skill", "agent", "command", "hook", "plugin", "mcp"):
        assert section_to_kind(kind_to_section(kind)) == kind
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_allowlist.py -v`
Expected: FAIL — `kind_to_section("mcp")` raises `ValueError`, `SECTIONS` does not include `"mcps"`.

- [ ] **Step 3: Make the change in `_allowlist.py`**

Edit `src/agent_toolkit_cli/_allowlist.py`:

Replace the `SECTIONS` tuple (line 15):

```python
SECTIONS: tuple[str, ...] = ("skills", "agents", "commands", "hooks", "plugins", "mcps")
```

Replace `_KIND_TO_SECTION` (lines 17-23):

```python
_KIND_TO_SECTION: dict[str, str] = {
    "skill":   "skills",
    "agent":   "agents",
    "command": "commands",
    "hook":    "hooks",
    "plugin":  "plugins",
    "mcp":     "mcps",
}
```

Delete the `mcp` guard in `kind_to_section` (lines 33-36):

```python
def kind_to_section(kind: str) -> str:
    """Map an asset kind to its allow-list section name.

    Raises ValueError for any unknown kind.
    """
    if kind not in _KIND_TO_SECTION:
        raise ValueError(f"unknown asset kind: {kind!r}")
    return _KIND_TO_SECTION[kind]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_allowlist.py -v`
Expected: PASS — all tests in test_allowlist.py.

Then run: `uv run pytest -q`
Expected: some failures elsewhere (test_cli_link, test_cli_unlink expect the "mcps are not yet scope-routed" message). These are addressed in Task 4. Note the failure count.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_allowlist.py tests/test_allowlist.py
git commit -m "feat(allowlist): route kind=mcp to mcps section, remove guard"
```

---

## Task 2: Fix walker MCP discovery to match catalog convention

**Files:**
- Modify: `src/agent_toolkit_cli/walker.py:24` and `src/agent_toolkit_cli/walker.py:115-135`
- Modify: `src/agent_toolkit_cli/schema.py:45-47`
- Create: `tests/test_walker.py`

The catalog at `~/GitHub/agent-toolkit/mcps/<name>/` uses `config.json` (the inner MCP server config, no `mcpServers` wrapper) plus a sibling `README.md` carrying frontmatter (`name`, `description`, `lifecycle`, etc.). The current walker looks for `mcp.json` and tries to read frontmatter from it as JSON with an `agent_toolkit_cli` key — neither matches reality, so MCP discovery silently produces zero results.

This task aligns the walker with the catalog: discover via `config.json`, read metadata from sibling `README.md` frontmatter (same shape as skills/agents/commands).

- [ ] **Step 1: Create the failing test**

Create `tests/test_walker.py`:

```python
"""Tests for src/agent_toolkit_cli/walker.py — discovery and metadata loading."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.walker import discover_assets, load_asset_record


def _write_mcp(toolkit_root: Path, slug: str, *, harnesses: list[str]) -> None:
    mcp_dir = toolkit_root / "mcps" / slug
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (mcp_dir / "config.json").write_text(
        '{"type": "stdio", "command": "npx", "args": ["-y", "fake"]}\n'
    )
    harness_lines = "\n".join(f"    - {h}" for h in harnesses)
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n"
        f"  name: {slug}\n"
        f"  description: {slug} mcp.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses:\n"
        f"{harness_lines}\n"
        "---\n\n"
        f"# {slug}\n\n"
        f"Body for {slug}.\n"
    )


def test_discover_mcp_uses_config_json(tmp_path):
    _write_mcp(tmp_path, "context7", harnesses=["claude", "codex"])
    assets = discover_assets(tmp_path)
    mcps = [a for a in assets if a.kind == "mcp"]
    assert len(mcps) == 1
    assert mcps[0].slug == "context7"
    assert mcps[0].path.name == "config.json"


def test_load_asset_record_mcp_reads_readme_frontmatter(tmp_path):
    _write_mcp(tmp_path, "context7", harnesses=["claude"])
    [asset] = [a for a in discover_assets(tmp_path) if a.kind == "mcp"]
    record = load_asset_record(asset)
    assert record.metadata["metadata"]["name"] == "context7"
    assert record.metadata["spec"]["harnesses"] == ["claude"]


def test_discover_mcp_skips_directory_without_readme(tmp_path):
    """A config.json without sibling README.md is still discovered (no metadata loss)
    but record metadata is empty. This pins the contract: discovery is structural,
    metadata read is best-effort."""
    mcp_dir = tmp_path / "mcps" / "orphan"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text("{}\n")
    [asset] = [a for a in discover_assets(tmp_path) if a.kind == "mcp"]
    record = load_asset_record(asset)
    assert record.metadata == {}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_walker.py -v`
Expected: FAIL — `test_discover_mcp_uses_config_json` finds zero mcps because `_KIND_RULES` looks for `mcp.json`.

- [ ] **Step 3: Update `_KIND_RULES` in walker.py**

In `src/agent_toolkit_cli/walker.py`, replace line 24:

```python
    ("mcp", "mcps", "config.json"),
```

(was: `("mcp", "mcps", "mcp.json"),`)

- [ ] **Step 4: Update `load_asset_record` to read MCP metadata from sibling README.md**

In `src/agent_toolkit_cli/walker.py`, replace the body of `load_asset_record` (lines 115-135). Replace the existing function with:

```python
def load_asset_record(asset: Asset) -> AssetRecord:
    """Load full metadata and a body excerpt for an asset."""
    import json as _json

    metadata: dict
    body_excerpt: str = ""

    if asset.kind in {"skill", "agent", "command"}:
        text = asset.path.read_text(encoding="utf-8").replace("\r\n", "\n")
        metadata = extract_frontmatter(asset.path) or {}
        body = _strip_frontmatter(text)
        body_excerpt = _first_paragraph(body, max_chars=400)
    elif asset.kind == "hook":
        metadata = yaml.safe_load(asset.path.read_text()) or {}
    elif asset.kind == "mcp":
        readme = asset.path.parent / "README.md"
        if readme.is_file():
            text = readme.read_text(encoding="utf-8").replace("\r\n", "\n")
            metadata = extract_frontmatter(readme) or {}
            body = _strip_frontmatter(text)
            body_excerpt = _first_paragraph(body, max_chars=400)
        else:
            metadata = {}
    elif asset.kind == "plugin":
        doc = _json.loads(asset.path.read_text())
        metadata = doc.get("agent_toolkit_cli") or {}
    else:
        metadata = {}

    return AssetRecord(asset=asset, metadata=metadata, body_excerpt=body_excerpt)
```

- [ ] **Step 5: Update `Validator._load_metadata` for MCPs**

In `src/agent_toolkit_cli/schema.py`, replace lines 40-48 (the whole `_load_metadata` method):

```python
    def _load_metadata(self, asset: Asset) -> dict | None:
        if asset.kind in {"skill", "agent", "command"}:
            return extract_frontmatter(asset.path)
        if asset.kind == "hook":
            return yaml.safe_load(asset.path.read_text())
        if asset.kind == "mcp":
            readme = asset.path.parent / "README.md"
            if not readme.is_file():
                return None
            return extract_frontmatter(readme)
        if asset.kind == "plugin":
            doc = json.loads(asset.path.read_text())
            return doc.get("agent_toolkit_cli")
        return None
```

- [ ] **Step 6: Run walker + schema tests**

Run: `uv run pytest tests/test_walker.py tests/test_check.py -v`
Expected: PASS for `tests/test_walker.py`; `tests/test_check.py` likely still passes (it does not exercise MCPs by default — confirm).

If `test_check.py` fails because it had MCP fixtures using `mcp.json`, fix the fixture filenames there. Otherwise no change.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/walker.py src/agent_toolkit_cli/schema.py tests/test_walker.py
git commit -m "fix(walker): discover MCPs via config.json + sibling README.md frontmatter"
```

---

## Task 3: Add `mcp` to `KINDS_FOR_PROJECTION` with explicit no-op branch

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py`
- Test: `tests/test_link_lib.py`

The projection algorithm needs to recognise `mcp` as a kind that is allow-list-managed but produces no symlinks. Until per-harness adapters land (Plan B+), the projection step for MCPs is a no-op that emits a single informational line so the user understands why nothing happened on disk.

- [ ] **Step 1: Write failing test**

Append to `tests/test_link_lib.py`:

```python
def test_project_from_file_mcp_emits_no_op_message(tmp_path, monkeypatch, capsys):
    """When the allow-list contains MCPs, the projection step emits a clear
    'install path not yet implemented' line and creates no symlinks."""
    import io
    from pathlib import Path

    from agent_toolkit_cli.commands._link_lib import LinkCounters, project_from_file

    # Seed a toolkit with one MCP
    toolkit_root = tmp_path / "toolkit"
    mcp_dir = toolkit_root / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n"
        "  name: context7\n"
        "  description: c7.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses:\n"
        "    - claude\n"
        "---\n"
    )

    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist = project_root / ".agent-toolkit.yaml"
    allowlist.write_text("mcps:\n  - context7\n")

    counters = LinkCounters()
    buf = io.StringIO()
    project_from_file(
        scope="project",
        harness="claude",
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist,
        dry_run=False,
        counters=counters,
        stdout=buf,
    )

    out = buf.getvalue()
    assert "MCP install path for claude not yet implemented" in out
    assert "context7" in out
    # No symlinks created, no counters bumped
    assert counters.created == 0
    assert counters.updated == 0
    assert counters.removed == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_link_lib.py::test_project_from_file_mcp_emits_no_op_message -v`
Expected: FAIL — currently `mcp` is not in `KINDS_FOR_PROJECTION`, so nothing is emitted.

- [ ] **Step 3: Add `mcp` to `KINDS_FOR_PROJECTION`**

In `src/agent_toolkit_cli/commands/_link_lib.py`, replace line 98:

```python
KINDS_FOR_PROJECTION: tuple[str, ...] = ("skill", "agent", "command", "hook", "plugin", "mcp")
```

- [ ] **Step 4: Add MCP no-op branch in `project_from_file`**

In `src/agent_toolkit_cli/commands/_link_lib.py`, modify the `project_from_file` function (lines 171-223). Insert a special-case branch at the top of the per-kind loop:

Replace lines 189-223 (the `for kind in KINDS_FOR_PROJECTION:` block) with:

```python
    for kind in KINDS_FOR_PROJECTION:
        if kind == "mcp":
            section = kind_to_section(kind)
            allowed_slugs = list(allowed.get(section, []))
            if not allowed_slugs:
                continue
            slugs_csv = ", ".join(allowed_slugs)
            print(
                f"MCP install path for {harness} not yet implemented; "
                f"allow-list updated only ({slugs_csv}).",
                file=stdout,
            )
            continue
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if target_dir is None:
            continue
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
        section = kind_to_section(kind)
        allowed_slugs = set(allowed.get(section, []))
        discovered_slugs: set[str] = set()
        for asset in by_kind[kind]:
            discovered_slugs.add(asset.slug)
            if asset.slug in allowed_slugs:
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
                )
            else:
                _prune_if_into_repo(
                    target_dir / asset.slug, toolkit_root, dry_run, counters, stdout,
                )
        # Sweep orphan symlinks (slug in target dir but no asset in repo)
        if target_dir.is_dir():
            for entry in target_dir.iterdir():
                if not entry.is_symlink():
                    continue
                if entry.name in discovered_slugs:
                    continue
                _prune_if_into_repo(entry, toolkit_root, dry_run, counters, stdout)
```

Also update `by_kind` initialisation (line 184) to omit `mcp` (mcp uses `allowed` directly, not the by_kind bucket):

```python
    by_kind: dict[str, list[Asset]] = {
        k: [] for k in KINDS_FOR_PROJECTION if k != "mcp"
    }
    for asset in discover_assets(toolkit_root):
        if asset.kind in by_kind:
            by_kind[asset.kind].append(asset)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_link_lib.py -v`
Expected: PASS — all link_lib tests including the new one.

Then: `uv run pytest tests/test_link_lib.py tests/test_allowlist.py tests/test_walker.py -v`
Expected: PASS — all three test files.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py tests/test_link_lib.py
git commit -m "feat(link): allow-list mcps now project as a documented no-op"
```

---

## Task 4: Remove the four `mcps are not yet scope-routed` guards in link/unlink

**Files:**
- Modify: `src/agent_toolkit_cli/commands/link.py:197-204` and `:437-442`
- Modify: `src/agent_toolkit_cli/commands/unlink.py:192-198` and `:292-296`
- Test: `tests/test_cli_link.py`, `tests/test_cli_unlink.py`

These guards now actively prevent the new code path from running. With Tasks 1–3 in place, removing them lets `link/unlink user|project <harness> mcp:context7` flow through the same logic as other kinds — the YAML mutation succeeds and the projection step emits the no-op message.

- [ ] **Step 1: Find existing tests that pin the old guard**

Run: `grep -n "mcps are not yet scope-routed" tests/`
Expected output:

```
tests/test_cli_link.py:294:    assert "mcps are not yet scope-routed" in combined
```

(There may be more in `test_cli_unlink.py`; double-check with `grep -rn "mcps are not yet" tests/`.)

- [ ] **Step 2: Update the failing test in `test_cli_link.py`**

Locate the test around line 294 (search for `mcps are not yet`). It pins behaviour for `agent-toolkit link user claude mcp:something`. Replace its assertions with the new expectation: the YAML is mutated, the no-op message appears, exit is 0.

Read the test first to see its setup, then replace the assertion. The exact replacement depends on the surrounding test structure, but the shape is:

```python
    # ... existing setup writing a toolkit with an MCP ...
    result = runner.invoke(
        cli, ["link", "project", "claude", "mcp:context7",
              "--toolkit-repo", str(toolkit_root),
              "--project", str(project_root)],
    )
    assert result.exit_code == 0, result.output
    assert "MCP install path for claude not yet implemented" in result.output
    # YAML allow-list has been mutated
    text = (project_root / ".agent-toolkit.yaml").read_text()
    assert "context7" in text
```

(If the existing test uses `runner.invoke(cli, [...])` on a fixture toolkit that doesn't have an `mcps/context7/` directory, you must seed it. Use the helper from `tests/test_walker.py` Step 1 — copy the `_write_mcp` helper inline or import it.)

- [ ] **Step 3: Add a parallel test in `tests/test_cli_unlink.py`**

If `tests/test_cli_unlink.py` doesn't already have an MCP guard test, add this test (place it next to the other per-asset tests):

```python
def test_unlink_mcp_removes_from_allowlist(tmp_path, monkeypatch):
    """Unlink mcp:slug removes it from the allow-list and prints the no-op message."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import cli

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["unlink", "project", "claude", "mcp:context7",
         "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert result.exit_code == 0, result.output
    text = (project / ".agent-toolkit.yaml").read_text()
    assert "context7" not in text
```

- [ ] **Step 4: Run the new tests to confirm they fail**

Run: `uv run pytest tests/test_cli_link.py tests/test_cli_unlink.py -v -k "mcp"`
Expected: FAIL — the four guards still trigger and emit the old error.

- [ ] **Step 5: Remove the four guard blocks**

Edit `src/agent_toolkit_cli/commands/link.py`. Delete lines 197-204 (the entire `if kind == "mcp":` block in `_do_per_asset`):

```python
    # 1. mcp guard
    if kind == "mcp":
        click.echo(
            "mcps are not yet scope-routed — edit the harness's mcp.json directly",
            err=True,
        )
        ctx.exit(2)
        return
```

Renumber the trailing comment from `# 2. resolve asset` to `# 1. resolve asset` if you want, but not required.

Then delete lines 437-442 (the `if kind == "mcp":` block in `_do_plan_entry`):

```python
    # mcp guard
    if kind == "mcp":
        error_lines.append(
            "mcps are not yet scope-routed — edit the harness's mcp.json directly"
        )
        return False
```

Edit `src/agent_toolkit_cli/commands/unlink.py`. Delete lines 192-198 (the `if kind == "mcp":` block in `_do_per_asset`):

```python
    if kind == "mcp":
        click.echo(
            "mcps are not yet scope-routed — edit the harness's mcp.json directly",
            err=True,
        )
        ctx.exit(2)
        return
```

Then delete lines 292-296 (the `if kind == "mcp":` block in `_do_plan_entry`):

```python
    if kind == "mcp":
        error_lines.append(
            "mcps are not yet scope-routed — edit the harness's mcp.json directly"
        )
        return False
```

- [ ] **Step 6: Run the full test suite**

Run: `uv run pytest -q`
Expected: PASS. All previously-failing CLI tests now pass.

If any test still fails, read the failure carefully — it likely depends on the old behaviour and needs an update similar to Step 2 / 3.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/link.py src/agent_toolkit_cli/commands/unlink.py tests/test_cli_link.py tests/test_cli_unlink.py
git commit -m "feat(cli): drop mcp scope-routed guard, route through allow-list"
```

---

## Task 5: Surface MCPs in `list` and `_list-json` output

**Files:**
- Modify: `src/agent_toolkit_cli/commands/list.py:18-19`, `:202-208`
- Modify: `src/agent_toolkit_cli/commands/_list_json.py:22`, `:128-129`
- Test: `tests/test_cli_list.py`, `tests/test_list_json.py`

`list --format=json` and the human-readable `list` both currently skip MCPs entirely. Now that MCPs are allow-list-managed, they should appear with the same status structure as other kinds. Install state for any (harness, scope, mcp) is `unsupported` until the per-harness adapters land — that's accurate and informative.

- [ ] **Step 1: Add the failing test in `test_list_json.py`**

Append to `tests/test_list_json.py`:

```python
def test_list_json_includes_mcps(tmp_path, monkeypatch):
    """MCPs appear as kind=mcp entries in JSON output with status=unsupported per cell."""
    import json
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import cli

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["list", "--format", "json", "--toolkit-repo", str(toolkit),
         "--project", str(project)],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    mcps = [a for a in data["assets"] if a["kind"] == "mcp"]
    assert len(mcps) == 1
    assert mcps[0]["slug"] == "context7"
    # All cells should be unsupported (no adapter yet) but allowlisted on project
    project_claude = next(
        c for c in mcps[0]["cells"]
        if c["harness"] == "claude" and c["scope"] == "project"
    )
    assert project_claude["status"] == "unsupported"
    assert project_claude["allowlisted"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_list_json.py::test_list_json_includes_mcps -v`
Expected: FAIL — `_build_inventory` skips `kind == "mcp"`.

- [ ] **Step 3: Update `_list_json.py`**

In `src/agent_toolkit_cli/commands/_list_json.py` line 22, replace `ALL_KINDS`:

```python
ALL_KINDS = ("skill", "agent", "command", "hook", "plugin", "mcp")
```

In `_build_inventory` (around line 128), delete the skip:

```python
        if asset.kind == "mcp":
            continue
```

In the per-cell loop in `_build_inventory` (around lines 162-175), MCPs need to emit `status=unsupported` because no adapter writes anywhere. Replace the inner cell-building block with a kind-aware version:

Locate the block:

```python
            if h not in declared:
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
            expected_src = _expected_source(asset.path, asset.kind)
            for scope, allowlisted in (
                ("user", user_allowlisted),
                ("project", proj_allowlisted),
            ):
                status, target = _cell_status(
                    h, asset.kind, asset.slug, scope, expected_src,
                    toolkit_root_resolved, project_root,
                )
                cells.append({
                    "harness": h, "scope": scope,
                    "status": status, "target": target,
                    "allowlisted": allowlisted,
                })
```

Replace with:

```python
            if h not in declared:
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
            if asset.kind == "mcp":
                # MCPs have no symlink path yet — adapter work lands in a follow-up.
                # Report status=unsupported but preserve the allowlisted bit so
                # `list` can still show users which MCPs they've selected.
                for scope, allowlisted in (
                    ("user", user_allowlisted),
                    ("project", proj_allowlisted),
                ):
                    cells.append({
                        "harness": h, "scope": scope,
                        "status": "unsupported", "target": None,
                        "allowlisted": allowlisted,
                    })
                continue
            expected_src = _expected_source(asset.path, asset.kind)
            for scope, allowlisted in (
                ("user", user_allowlisted),
                ("project", proj_allowlisted),
            ):
                status, target = _cell_status(
                    h, asset.kind, asset.slug, scope, expected_src,
                    toolkit_root_resolved, project_root,
                )
                cells.append({
                    "harness": h, "scope": scope,
                    "status": status, "target": target,
                    "allowlisted": allowlisted,
                })
```

- [ ] **Step 4: Run the JSON test**

Run: `uv run pytest tests/test_list_json.py -v`
Expected: PASS — all tests including the new one.

- [ ] **Step 5: Update text-mode `list` to surface MCPs**

In `src/agent_toolkit_cli/commands/list.py`, delete the MCP short-circuit (lines 202-208):

```python
    # MCP short-circuit: MCPs aren't symlink-managed.
    if kind_filter == "mcp":
        _ui.header("Asset inventory (filter: kind=mcp):")
        _ui.summary(
            "MCPs are configured via the harness's mcp.json, not symlinks — not shown here."
        )
        return
```

Add `"mcp": "MCPs"` to `_KIND_TITLE` (around line 22-28):

```python
_KIND_TITLE: dict[str, str] = {
    "skill": "SKILLS",
    "agent": "AGENTS",
    "command": "COMMANDS",
    "hook": "HOOKS",
    "plugin": "PLUGINS",
    "mcp": "MCPs",
}
```

Add `"mcp"` to the kinds iterated in the text-mode loop. The current loop iterates `KINDS_FOR_PROJECTION` (line 218); after Task 3 that already includes `"mcp"`. So the text-mode list should now produce an MCPs section automatically — verify after the next step.

But the text-mode install state computation (`_install_state`, lines 37-71) computes "✓" via symlink existence — for MCPs that always returns "—" (no symlink). That's accurate. No change needed.

- [ ] **Step 6: Add a text-mode test in `test_cli_list.py`**

Append to `tests/test_cli_list.py`:

```python
def test_list_text_includes_mcps(tmp_path, monkeypatch):
    """Text-mode list shows an MCPs section with allow-listed MCPs."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import cli

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n---\n"
    )

    project = tmp_path / "project"
    project.mkdir()
    (project / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["list", "--toolkit-repo", str(toolkit), "--project", str(project)],
    )
    assert result.exit_code == 0, result.output
    assert "MCPs (1)" in result.output
    assert "context7" in result.output
```

- [ ] **Step 7: Run the text-mode test**

Run: `uv run pytest tests/test_cli_list.py -v -k mcp`
Expected: PASS.

- [ ] **Step 8: Run the full suite to catch regressions**

Run: `uv run pytest -q`
Expected: PASS. All tests green.

- [ ] **Step 9: Commit**

```bash
git add src/agent_toolkit_cli/commands/list.py src/agent_toolkit_cli/commands/_list_json.py tests/test_cli_list.py tests/test_list_json.py
git commit -m "feat(list): surface MCPs in list/JSON output with status=unsupported"
```

---

## Task 6: Verify schema validation accepts existing catalog MCPs

**Files:**
- Test: `tests/test_check.py` (verify, augment if needed)

The repo's `check` command runs the validator over the toolkit catalog. Tasks 1–5 changed the walker's MCP discovery. We need to confirm the existing schema accepts the catalog's actual MCP frontmatter (which it should — the schema is harness-agnostic).

- [ ] **Step 1: Smoke-test `check` against a real toolkit clone**

Run: `uv run agent-toolkit --toolkit-repo ~/GitHub/agent-toolkit check --exit-code`
Expected: exit 0 (or pre-existing failures unrelated to MCPs). If MCPs cause new failures, the cause is one of:

  (a) The catalog's `README.md` doesn't have v1alpha1 frontmatter — check with `head -20 ~/GitHub/agent-toolkit/mcps/context7/README.md`. If the frontmatter is the older flat shape (`name: ..., description: ..., status: ...`) rather than the structured shape (`apiVersion: ..., metadata: {...}, spec: {...}`), this is expected catalog drift. Document but DO NOT change the catalog as part of this plan — that's a separate migration.

  (b) The schema rejects something legitimate. Likely fix is in the catalog frontmatter, not the schema.

If (a) is the case, add a known-skipped marker to `tests/test_check.py` to flag this for a follow-up — do not block this plan on catalog migration.

- [ ] **Step 2: Add a regression test for MCP discovery + validation**

Append to `tests/test_check.py`:

```python
def test_check_accepts_v1alpha1_mcp(tmp_path, monkeypatch):
    """Validator accepts a catalog MCP with structured v1alpha1 frontmatter."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import cli

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("AGENT_TOOLKIT_REPO", raising=False)

    toolkit = tmp_path / "toolkit"
    toolkit.mkdir()
    (toolkit / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text('{"type":"stdio","command":"npx"}\n')
    (mcp_dir / "README.md").write_text(
        "---\napiVersion: agent-toolkit/v1alpha1\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - claude\n---\n"
    )

    runner = CliRunner()
    result = runner.invoke(
        cli, ["check", "--exit-code", "--toolkit-repo", str(toolkit)],
    )
    assert result.exit_code == 0, result.output
```

- [ ] **Step 3: Run the test**

Run: `uv run pytest tests/test_check.py::test_check_accepts_v1alpha1_mcp -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/test_check.py
git commit -m "test(check): pin validator behavior for v1alpha1-shaped MCP frontmatter"
```

---

## Task 7: Final sweep + documentation update

**Files:**
- Modify: `docs/agent-toolkit/cli.md` (add MCP usage examples)
- Modify: `README.md` (small note about MCP foundations)

- [ ] **Step 1: Run the full test suite one more time**

Run: `uv run pytest -q && bats tests/bats`
Expected: PASS for both.

- [ ] **Step 2: Smoke-test the CLI against a synthetic toolkit**

```bash
mkdir -p /tmp/agent-toolkit-smoke/toolkit/mcps/context7
echo "" > /tmp/agent-toolkit-smoke/toolkit/.agent-toolkit-source
cat > /tmp/agent-toolkit-smoke/toolkit/mcps/context7/config.json <<'EOF'
{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp@latest"]}
EOF
cat > /tmp/agent-toolkit-smoke/toolkit/mcps/context7/README.md <<'EOF'
---
apiVersion: agent-toolkit/v1alpha1
metadata:
  name: context7
  description: Up-to-date documentation MCP.
  lifecycle: stable
spec:
  origin: third-party
  vendored_via: none
  upstream: https://github.com/upstash/context7-mcp
  harnesses:
    - claude
    - codex
    - opencode
    - pi
---

# context7
EOF
mkdir -p /tmp/agent-toolkit-smoke/project
uv run agent-toolkit \
  --toolkit-repo /tmp/agent-toolkit-smoke/toolkit \
  link project claude mcp:context7 \
  --project /tmp/agent-toolkit-smoke/project
```

Expected output includes:
- A success-y line about adding to allow-list.
- The line: `MCP install path for claude not yet implemented; allow-list updated only (context7).`

Verify the YAML was written:

```bash
cat /tmp/agent-toolkit-smoke/project/.agent-toolkit.yaml
```

Expected: contains `mcps:` section with `- context7`.

Then unlink:

```bash
uv run agent-toolkit \
  --toolkit-repo /tmp/agent-toolkit-smoke/toolkit \
  unlink project claude mcp:context7 \
  --project /tmp/agent-toolkit-smoke/project
cat /tmp/agent-toolkit-smoke/project/.agent-toolkit.yaml
```

Expected: `context7` no longer in the file.

- [ ] **Step 3: Update `docs/agent-toolkit/cli.md`**

Find the section in `docs/agent-toolkit/cli.md` describing `link`/`unlink` arguments. After the existing kind list, add a paragraph:

```markdown
### MCPs

`mcp:<name>` is recognised the same as other kinds (`skill:`, `agent:`, etc.). The
allow-list YAML is updated under the `mcps:` section; the projection step emits a
`MCP install path for <harness> not yet implemented` line because per-harness MCP
adapters are not yet implemented. Per-harness MCP installation lands in a follow-up
plan; for now, MCPs are first-class allow-list citizens but produce no symlinks or
config edits.
```

- [ ] **Step 4: Update `README.md`**

Find the "Commands" or features section in `README.md`. If there's a one-line claim about supported asset kinds, update it to include MCPs with a note:

```markdown
- **MCPs** are recognised in the allow-list (`mcps:` section) and surfaced in
  `list`/`inventory`. Per-harness MCP installation arrives in a follow-up.
```

- [ ] **Step 5: Final commit**

```bash
git add docs/agent-toolkit/cli.md README.md
git commit -m "docs: MCP foundations — allow-list section, projection no-op"
```

- [ ] **Step 6: Verify clean state**

Run:

```bash
uv run pytest -q
bats tests/bats
git status
```

Expected: tests green, working tree clean.

---

## Plan Self-Review Checklist

The following spec requirements from `docs/superpowers/specs/2026-05-04-mcp-management-design.md` are addressed in this plan:

- [x] Walker discovers MCPs (Task 2)
- [x] Allow-list has `mcps` section (Task 1)
- [x] `link`/`unlink` accept `mcp:<slug>` (Task 4, builds on Task 1)
- [x] `list` surfaces MCPs (Task 5)
- [x] Validator handles MCP README frontmatter (Task 2 step 5)

Spec requirements **deferred to Plan B (and beyond)**:

- Schema bump to v1alpha2 with `metadata.kind` discriminator
- `harness_adapters/` package and the `HarnessMCPAdapter` Protocol
- Plugin-folder vs config-file strategy decision per (harness, scope)
- Round-trip parsers (`tomlkit`, JSONC) for harness configs
- `doctor` MCP group (drift, env-var presence, prerequisites, `verify:`)
- `fix` reconciliation for MCPs
- TUI MCPs section
- `--force` opt-out for live `~/.claude.json`
- Atomic write helper

Plan A is a self-contained foundation: every task produces working, tested software, and the deferred work is naturally additive (no rework expected).

**Type/name consistency check:**
- `KINDS_FOR_PROJECTION` — same name in `_link_lib.py` and consumers (`link.py`, `list.py`).
- `kind == "mcp"` (singular) — matches `Asset.kind` convention.
- `"mcps"` (plural) — matches the YAML section name and directory name in the catalog.
- The function `kind_to_section("mcp")` returns `"mcps"` — verified in Task 1's tests.
- `_KIND_TITLE["mcp"] = "MCPs"` (Task 5) — display only, no consumer dependency.

No placeholders. Every step contains actual code or commands.
