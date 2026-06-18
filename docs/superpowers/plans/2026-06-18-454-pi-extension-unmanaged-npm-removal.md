# Pi Extension Unmanaged npm Disambiguation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `pi-extension add npm:<package>` as the managed npm flow, while making unmanaged npm Pi extensions visible, clearly labeled, and non-removable with exact manual removal advice.

**Architecture:** Extend Pi extension inventory records with managed-state and config-location metadata, then route CLI/TUI behavior through that single model. Managed npm remains lock-backed. Unmanaged npm remains read-only observed settings state. Public CLI/TUI terminology uses `library`, not `store-owned`, for source-backed rows.

**Tech Stack:** Python 3.12+, Click, Textual `DataTable`, pytest/pytest-asyncio, existing `agent_toolkit_cli` Pi extension modules.

---

## Implementation Units

- Modify `src/agent_toolkit_cli/pi_extension_inventory.py`: expose npm managed state and per-scope settings locations.
- Keep `src/agent_toolkit_cli/pi_extension_add.py` npm behavior intact; add/adjust tests to lock it as supported.
- Modify `src/agent_toolkit_cli/pi_extension_ops.py`: refuse unmanaged npm uninstall with exact advice while preserving managed npm behavior.
- Modify `src/agent_toolkit_cli/commands/pi_extension/remove_cmd.py`, `list_cmd.py`, and `status_cmd.py`: surface unmanaged warnings and managed labels.
- Modify `src/agent_toolkit_tui/pi_extension_state.py` and `src/agent_toolkit_tui/widgets/pi_grid.py`: render managed/unmanaged npm state and block/warn on unmanaged toggles.
- Update docs where Pi extension origin terminology leaks `store-owned` to user-facing copy.
- Add/extend CLI and TUI tests listed below.

## Task 1: Extend inventory with npm managed-state metadata

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_inventory.py`
- Modify: `tests/test_cli/test_pi_extension_inventory.py`

- [ ] **Step 1: Write failing inventory tests**

Add tests covering:

```python
def test_npm_from_lock_and_settings_is_managed(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    lock = tmp_path / ".agent-toolkit" / "pi-extensions-lock.json"
    lock.parent.mkdir(parents=True)
    lock.write_text(json.dumps({
        "version": 1,
        "skills": {
            "pi-recap": {"source": "npm:pi-recap", "sourceType": "npm"}
        },
    }) + "\n")
    _seed_packages(tmp_path / ".pi" / "agent" / "settings.json", "npm:pi-recap")

    rec = {r.slug: r for r in build_inventory(home=tmp_path)}["pi-recap"]

    assert rec.origin == "npm"
    assert rec.managed is True
    assert rec.global_loaded is True
    assert rec.global_package_spec == "npm:pi-recap"
    assert rec.global_config_path == tmp_path / ".pi" / "agent" / "settings.json"


def test_npm_from_settings_without_lock_is_unmanaged(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_packages(tmp_path / ".pi" / "agent" / "settings.json", "npm:pi-title-renamer")

    rec = {r.slug: r for r in build_inventory(home=tmp_path)}["pi-title-renamer"]

    assert rec.origin == "npm"
    assert rec.managed is False
    assert rec.global_loaded is True
    assert rec.global_package_spec == "npm:pi-title-renamer"
    assert rec.global_config_path == tmp_path / ".pi" / "agent" / "settings.json"
```

Run:

```bash
uv run pytest tests/test_cli/test_pi_extension_inventory.py -q
```

Expected: FAIL because `InventoryRecord` lacks `managed`, `global_package_spec`, and `global_config_path`.

- [ ] **Step 2: Add inventory fields**

Extend `InventoryRecord`:

```python
@dataclass
class InventoryRecord:
    slug: str
    origin: Origin
    source: str
    global_loaded: bool = False
    project_loaded: bool = False
    pinned_sha: str | None = None
    managed: bool = False
    global_package_spec: str | None = None
    project_package_spec: str | None = None
    global_config_path: Path | None = None
    project_config_path: Path | None = None
```

Set `managed=True` for lock-backed npm entries. In the packages pass, fill package spec and config path for each scope using `_pi_settings.settings_path(...)`. Do not let an unmanaged packages row overwrite a library-backed row. For npm rows, `managed` is true when a matching npm lock row exists for that slug/source identity.

- [ ] **Step 3: Run inventory tests**

Run:

```bash
uv run pytest tests/test_cli/test_pi_extension_inventory.py -q
```

Expected: PASS.

## Task 2: Lock current managed npm add behavior as supported

**Files:**
- Modify: `tests/test_cli/test_pi_extension_add.py`
- Modify: docs only if they accidentally describe `add npm:` as deprecated.

- [ ] **Step 1: Add/adjust tests proving npm add remains supported**

Ensure coverage asserts:

```python
def test_add_npm_source_creates_managed_lock_row(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    slug = pi_extension_add.add(source="npm:@tifan/pi-recap", slug=None, env=None)

    assert slug == "@tifan/pi-recap"
    lock = read_lock(tmp_path / ".agent-toolkit" / "pi-extensions-lock.json")
    entry = lock.skills["@tifan/pi-recap"]
    assert entry.source == "npm:@tifan/pi-recap"
    assert entry.source_type == "npm"
```

Run:

```bash
uv run pytest tests/test_cli/test_pi_extension_add.py -q
```

Expected: PASS. If existing tests already cover this, update names/comments only; do not change implementation.

- [ ] **Step 2: Confirm docs do not deprecate add npm**

Search:

```bash
rg -n "retire|deprecated|reject.*npm|add npm" README.md docs src tests
```

Expected: no docs claim `pi-extension add npm:<package>` is retired or rejected. Existing command examples may remain.

## Task 3: Refuse unmanaged npm uninstall with exact advice

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_ops.py`
- Modify: `tests/test_cli/test_pi_extension_ops.py`

- [ ] **Step 1: Write failing unmanaged uninstall tests**

Seed `~/.pi/agent/settings.json` with `"npm:pi-title-renamer"` and no lock row. Assert:

```python
with pytest.raises(pi_extension_install.InstallError) as excinfo:
    pi_extension_ops.uninstall(slug="pi-title-renamer", scope="global", home=tmp_path)

message = str(excinfo.value)
assert "unmanaged npm package" in message
assert "will not remove packages it did not add" in message
assert str(tmp_path / ".pi" / "agent" / "settings.json") in message
assert 'remove "npm:pi-title-renamer" from packages[]' in message
```

Also add a project-scope variant that seeds `<project>/.pi/settings.json` and asserts that project path appears.

Run:

```bash
uv run pytest tests/test_cli/test_pi_extension_ops.py -q
```

Expected: FAIL because current uninstall falls through to library symlink planning or generic errors.

- [ ] **Step 2: Add helper to find unmanaged npm rows**

Create a focused helper in `pi_extension_ops.py` or a new small module:

```python
def unmanaged_npm_advice(
    slug: str,
    *,
    scope: Scope,
    home: Path | None,
    project: Path | None,
    action: Literal["remove", "uninstall"],
) -> str | None:
    path = _pi_settings.settings_path(scope=scope, home=home, project=project)
    for spec in _pi_settings.read_packages(scope=scope, home=home, project=project):
        if spec.startswith("npm:") and _pi_settings.npm_identity(spec) == _pi_settings.npm_identity(slug):
            if action == "remove":
                return (
                    f"{slug} is not managed by agent-toolkit.\n"
                    f"Found unmanaged npm package in {path}.\n"
                    "agent-toolkit-cli will not remove packages it did not add.\n"
                    f"To remove it manually, remove \"{spec}\" from packages[]."
                )
            return (
                f"{slug} is an unmanaged npm package in Pi settings.\n"
                "agent-toolkit-cli will not remove packages it did not add.\n"
                f"To remove it manually, edit {path} and remove \"{spec}\" from packages[]."
            )
    return None
```

If `_npm_identity` is private, promote it to `npm_identity` with tests preserving current behavior.

- [ ] **Step 3: Use helper in uninstall**

In `pi_extension_ops.uninstall`, when no managed entry exists, check the selected scope for unmanaged npm advice before library-extension symlink planning. Raise `InstallError(advice)` when found. Keep existing managed npm uninstall unchanged.

- [ ] **Step 4: Run ops tests**

Run:

```bash
uv run pytest tests/test_cli/test_pi_extension_ops.py -q
```

Expected: PASS.

## Task 4: Refuse unmanaged npm remove with exact CLI advice

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/remove_cmd.py`
- Modify: `tests/test_cli/test_cli_pi_extension_lifecycle.py`

- [ ] **Step 1: Write failing CLI remove tests**

Use `CliRunner` or existing CLI fixture to seed global settings with unmanaged `npm:pi-title-renamer` and no lock row. Assert:

```python
result = runner.invoke(cli, ["pi-extension", "remove", "pi-title-renamer"])

assert result.exit_code != 0
assert "not managed by agent-toolkit" in result.output
assert "will not remove packages it did not add" in result.output
assert ".pi/agent/settings.json" in result.output
assert 'remove "npm:pi-title-renamer" from packages[]' in result.output
```

Add project-first coverage: if current directory has `<project>/.pi/settings.json` containing the package, `remove` should report the project settings path before global.

Run:

```bash
uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -q
```

Expected: FAIL because current `remove` says only `not in the global library`.

- [ ] **Step 2: Use unmanaged advice in remove command**

In `remove_cmd`, when no global lock entry exists, check both Pi settings scopes before generic fallback:

1. if current directory has project Pi settings (`<project>/.pi/settings.json`), check project packages first and report that project file when matched;
2. check global packages at `~/.pi/agent/settings.json` and report that global file when matched;
3. only then fall back to `not in the global library`.

Use `action="remove"` so the message starts with `not managed by agent-toolkit` and then gives unmanaged package path/advice.

- [ ] **Step 3: Run lifecycle tests**

Run:

```bash
uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -q
```

Expected: PASS.

## Task 5: Render managed/unmanaged state in CLI list/status

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/list_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/pi_extension/status_cmd.py`
- Modify: `tests/test_cli/test_cli_pi_extension_list.py`
- Modify: `tests/test_cli/test_pi_extension_list_table.py`

- [ ] **Step 1: Write failing list/status tests**

Add JSON list coverage:

```python
rows = json.loads(result.output)
row = next(r for r in rows if r["slug"] == "pi-title-renamer")
assert row["origin"] == "npm"
assert row["managed"] is False
assert row["globalConfigPath"].endswith(".pi/agent/settings.json")
assert row["globalPackageSpec"] == "npm:pi-title-renamer"
```

Add table/status text coverage that expects `npm unmanaged` for unmanaged package rows, `npm managed` for lock-backed npm rows, and `library` for source-backed rows. Assert no CLI table/status output contains `store-owned`.

Run:

```bash
uv run pytest tests/test_cli/test_cli_pi_extension_list.py tests/test_cli/test_pi_extension_list_table.py -q
```

Expected: FAIL because current output has only `origin=npm` and may expose internal source-backed terminology.

- [ ] **Step 2: Extend JSON output**

In `list_cmd`, add fields:

```python
"managed": r.managed,
"globalPackageSpec": r.global_package_spec,
"projectPackageSpec": r.project_package_spec,
"globalConfigPath": str(r.global_config_path) if r.global_config_path else None,
"projectConfigPath": str(r.project_config_path) if r.project_config_path else None,
```

For source-backed rows, prefer a user-facing/display field with `library`. Preserve raw `origin` only if compatibility needs it.

- [ ] **Step 3: Extend visible labels**

Render source-backed lock rows as `library`, and npm origin as `npm managed` or `npm unmanaged` in list/status output. Do not expose `store-owned` in CLI text. If internal code keeps the `store-owned` enum for compatibility, map it at every output boundary.

- [ ] **Step 4: Run list/status tests**

Run:

```bash
uv run pytest tests/test_cli/test_cli_pi_extension_list.py tests/test_cli/test_pi_extension_list_table.py -q
```

Expected: PASS.

## Task 6: Update TUI state and PiGrid behavior

**Files:**
- Modify: `src/agent_toolkit_tui/pi_extension_state.py`
- Modify: `src/agent_toolkit_tui/widgets/pi_grid.py`
- Modify: `tests/test_tui/test_pi_grid.py`
- Modify: `tests/test_tui/test_pi_apply_roundtrip.py`

- [ ] **Step 1: Write failing TUI tests**

Add a helper row for unmanaged npm:

```python
def _unmanaged_npm_row(slug: str) -> PiExtensionRow:
    cell = PiCell(global_loaded=True, project_loaded=False, origin="npm", managed=False)
    return PiExtensionRow(
        slug=slug,
        origin="npm",
        source=f"npm:{slug}",
        global_cell=cell,
        project_cell=cell,
        managed=False,
        global_config_path="/tmp/home/.pi/agent/settings.json",
        global_package_spec=f"npm:{slug}",
    )
```

Test that pressing space on the scope column does not queue pending entries for unmanaged npm, or shows a warning and leaves pending empty.

Test info body includes:

- `unmanaged npm package`;
- `will not remove packages it did not add`;
- config path;
- exact `remove "npm:pi-title-renamer" from packages[]` advice.

Run:

```bash
uv run pytest tests/test_tui/test_pi_grid.py tests/test_tui/test_pi_apply_roundtrip.py -q
```

Expected: FAIL because npm rows are currently all toggleable and copy says managed via install.

- [ ] **Step 2: Extend TUI row/cell state**

In `pi_extension_state.py`, carry inventory metadata into `PiExtensionRow`/`PiCell` as appropriate:

```python
managed: bool = True
global_package_spec: str | None = None
project_package_spec: str | None = None
global_config_path: str | None = None
project_config_path: str | None = None
```

Default `managed=True` preserves existing test helpers unless they explicitly set unmanaged.

- [ ] **Step 3: Block or warn on unmanaged npm toggles**

In `PiGrid._toggle_at`, when `row.origin == "npm" and not row.managed`, do not queue a pending entry. Either silently no-op like untracked rows or notify; notification is preferred because issue asks for a warning.

- [ ] **Step 4: Update origin/info copy**

Render origin as `npm managed` or `npm unmanaged`. In `_info_body`, unmanaged npm should return manual removal advice for active scope:

```python
return (
    "[dim]Unmanaged npm package.[/]\n\n"
    "agent-toolkit-cli will not remove packages it did not add.\n"
    f"To remove it manually, edit {path} and remove \"{spec}\" from packages[]."
)
```

Choose `{path}` and `{spec}` from `row.global_config_path` / `row.global_package_spec` in global scope and from `row.project_config_path` / `row.project_package_spec` in project scope. Managed npm copy should continue to describe pending install/uninstall through packages[].

- [ ] **Step 5: Run TUI tests**

Run:

```bash
uv run pytest tests/test_tui/test_pi_grid.py tests/test_tui/test_pi_apply_roundtrip.py -q
```

Expected: PASS.

## Task 7: Targeted verification and docs update

**Files:**
- Modify: `README.md` and/or `docs/asset-types/pi-extensions.md` if stale origin terminology exists.
- Modify: any tests affected by new managed/unmanaged output.

- [ ] **Step 1: Run targeted test set**

Run:

```bash
uv run pytest \
  tests/test_cli/test_pi_extension_add.py \
  tests/test_cli/test_pi_extension_ops.py \
  tests/test_cli/test_pi_extension_inventory.py \
  tests/test_cli/test_cli_pi_extension_list.py \
  tests/test_cli/test_pi_extension_list_table.py \
  tests/test_cli/test_cli_pi_extension_lifecycle.py \
  tests/test_tui/test_pi_grid.py \
  tests/test_tui/test_pi_apply_roundtrip.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full suite if targeted tests pass**

Run:

```bash
uv run pytest -q
```

Expected: PASS.

- [ ] **Step 3: Manual CLI smoke check**

With temp `HOME` and temp project root, run:

```bash
HOME="$tmp_home" uv run agent-toolkit-cli pi-extension add npm:pi-title-renamer
HOME="$tmp_home" uv run agent-toolkit-cli pi-extension install -g pi-title-renamer
HOME="$tmp_home" uv run agent-toolkit-cli pi-extension list --json
HOME="$tmp_home" uv run agent-toolkit-cli pi-extension uninstall -g pi-title-renamer
HOME="$tmp_home" uv run agent-toolkit-cli pi-extension remove pi-title-renamer
```

Expected:

- `add npm:` succeeds and writes managed lock row.
- `install -g` writes managed settings entry.
- `list --json` shows `managed: true` for managed row.
- `uninstall -g` removes managed package entry.
- `remove` removes managed lock row.

Then seed unmanaged settings manually and run:

```bash
python - <<'PY'
import json, pathlib, os
p = pathlib.Path(os.environ["HOME"]) / ".pi" / "agent" / "settings.json"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"packages": ["npm:pi-title-renamer"]}, indent=2) + "\n")
PY
HOME="$tmp_home" uv run agent-toolkit-cli pi-extension remove pi-title-renamer
HOME="$tmp_home" uv run agent-toolkit-cli pi-extension uninstall -g pi-title-renamer
```

Expected: both commands refuse mutation and print why agent-toolkit cannot remove it, the settings path, and `npm:pi-title-renamer` removal advice.

- [ ] **Step 4: Commit implementation**

```bash
git add README.md docs/asset-types/pi-extensions.md src/agent_toolkit_cli src/agent_toolkit_tui tests
HOSTNAME_SHORT=$(hostname -s)
git commit -m "fix(pi-extension): clarify unmanaged npm lifecycle" -m "Device: ${HOSTNAME_SHORT}"
```

## Self-review checklist

- Spec coverage: Tasks 1–7 cover inventory metadata, managed npm preservation, unmanaged refusal, CLI display, TUI display/interactivity, docs, and verification.
- Placeholder scan: no TBD/TODO placeholders; each task includes concrete files, commands, and expected behavior.
- Type consistency: `managed`, package spec, and config path fields are named consistently across inventory JSON, CLI output, and TUI state.
