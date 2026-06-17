# Commands Asset Type Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reintroduce a complete `commands` asset type with CLI, adapters, TUI, docs, tests, and a version bump without breaking existing asset types.

**Architecture:** Add a fifth per-kind module family (`command_*`) that mirrors the skill implementation where source/library/lock behavior matches, and uses adapter translation for harness-specific command formats. Keep `_install_core` generic via facade injection; do not add runtime `asset_type=` discriminators. Commands use canonical `COMMAND.md` folders, `commands-lock.json`, and first-cut harness adapters for Claude, Pi, Gemini, plus explicit/deprecated Codex. Cursor stays a documented gap unless a worker records deterministic validation evidence.

**Tech Stack:** Python 3.12, Click, pytest, Textual, JSON lock files, git-backed libraries, symlink/copy projections, TOML translation via existing `tomlkit` dependency.

---

## File structure

Create:

- `src/agent_toolkit_cli/command_paths.py` — commands library/project path facade.
- `src/agent_toolkit_cli/command_lock.py` — `commands-lock.json` reader/writer with `commandPath` support.
- `src/agent_toolkit_cli/command_install.py` — command-specific install facade and adapter dispatch.
- `src/agent_toolkit_cli/command_adapters/__init__.py` — harness adapter dispatcher.
- `src/agent_toolkit_cli/command_adapters/base.py` — protocol/helpers for ownership sentinels and destination calculation.
- `src/agent_toolkit_cli/command_adapters/markdown.py` — Claude/Pi/Codex markdown projection helpers.
- `src/agent_toolkit_cli/command_adapters/gemini.py` — TOML translation adapter.
- `src/agent_toolkit_cli/commands/command/__init__.py` — Click group registration.
- `src/agent_toolkit_cli/commands/command/_common.py` — scope/harness parsing.
- `src/agent_toolkit_cli/commands/command/add_cmd.py`
- `src/agent_toolkit_cli/commands/command/install_cmd.py`
- `src/agent_toolkit_cli/commands/command/uninstall_cmd.py`
- `src/agent_toolkit_cli/commands/command/list_cmd.py`
- `src/agent_toolkit_cli/commands/command/status_cmd.py`
- `src/agent_toolkit_cli/commands/command/update_cmd.py`
- `src/agent_toolkit_cli/commands/command/push_cmd.py`
- `src/agent_toolkit_cli/commands/command/import_cmd.py`
- `src/agent_toolkit_cli/commands/command/reset_cmd.py`
- `src/agent_toolkit_cli/commands/command/remove_cmd.py`
- `src/agent_toolkit_cli/commands/command/doctor_cmd.py`
- `src/agent_toolkit_tui/command_state.py`
- `src/agent_toolkit_tui/widgets/command_grid.py`
- `docs/asset-types/commands.md`
- `tests/test_cli/test_command_*.py` and `tests/test_cli/test_command_adapters/*.py`
- `tests/test_tui/test_command_*.py`

Modify:

- `src/agent_toolkit_cli/_paths_core.py` — add `COMMAND_BINDING`, include command lock in project detection.
- `src/agent_toolkit_cli/cli.py` — add `commands` group and singular aliases.
- `src/agent_toolkit_tui/app.py`, `src/agent_toolkit_tui/widgets/__init__.py`, `src/agent_toolkit_tui/column_info.py`, `src/agent_toolkit_tui/composition.py` — commands tab.
- `pyproject.toml` — version bump after verified implementation.
- `uv.lock` — update if package metadata version changes.
- `README.md`, `docs/index.md`, `docs/agent-toolkit/cli.md`, `docs/agent-toolkit/harness-matrix.md`, `docs/matrix.md`, `docs/glossary.md`, `docs/agent-toolkit/lock-files.md`, `docs/asset-types/skills.md`, `docs/agent-toolkit/tui.md`, `mkdocs.yml`, relevant `docs/harnesses/*.md`.
- `scripts/gen_harness_docs.py` — emit Commands matrix column.
- Architecture/parity tests — expect fifth asset type.

## Task 1: Binding, paths, and lock-file foundation

**Files:**
- Modify: `src/agent_toolkit_cli/_paths_core.py`
- Create: `src/agent_toolkit_cli/command_paths.py`
- Create: `src/agent_toolkit_cli/command_lock.py`
- Test: `tests/test_cli/test_command_paths.py`
- Test: `tests/test_cli/test_command_lock.py`
- Modify: `tests/test_cli/test_paths_core_default_scope.py`
- Modify: `tests/test_cli/test_asset_type_architecture.py`

- [ ] **Step 1: Write failing binding/path tests**

Add tests asserting commands paths mirror other git-backed kinds:

```python
from pathlib import Path

from agent_toolkit_cli.command_paths import (
    canonical_command_dir,
    library_command_path,
    library_lock_path,
    library_root,
    lock_file_path,
)


def test_command_library_paths_use_agent_toolkit_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert library_root() == tmp_path / ".agent-toolkit" / "commands"
    assert library_command_path("demo") == tmp_path / ".agent-toolkit" / "commands" / "demo"
    assert library_lock_path() == tmp_path / ".agent-toolkit" / "commands-lock.json"


def test_command_project_paths_use_external_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "repo"
    project.mkdir()
    assert lock_file_path(scope="project", project=project) == project / "commands-lock.json"
    assert canonical_command_dir("demo", scope="project", project=project).name == "demo"
    assert ".agent-toolkit" in str(canonical_command_dir("demo", scope="project", project=project))
```

Add lock round-trip tests:

```python
from agent_toolkit_cli.command_lock import LockEntry, LockFile, read_lock, write_lock


def test_command_lock_round_trips_command_path(tmp_path):
    path = tmp_path / "commands-lock.json"
    lock = LockFile(version=1, skills={
        "demo": LockEntry(
            source="owner/repo",
            source_type="github",
            ref="main",
            command_path="COMMAND.md",
            upstream_sha="abc1234",
        )
    })
    write_lock(path, lock)
    loaded = read_lock(path)
    assert loaded.skills["demo"].command_path == "COMMAND.md"
```

Run:

```bash
uv run pytest tests/test_cli/test_command_paths.py tests/test_cli/test_command_lock.py -q
```

Expected: FAIL because modules do not exist.

- [ ] **Step 2: Add command binding**

In `_paths_core.py`, add:

```python
COMMAND_BINDING = AssetTypeBinding(
    asset_type="command",
    canonical_dirname="commands",
    library_subdir="commands",
    lock_filename="commands-lock.json",
    standard_harness_name="standard-command",
)
```

Update `_PROJECT_LOCK_FILENAMES`:

```python
_PROJECT_LOCK_FILENAMES: tuple[str, ...] = (
    SKILL_BINDING.lock_filename,
    AGENT_BINDING.lock_filename,
    PI_EXTENSION_BINDING.lock_filename,
    COMMAND_BINDING.lock_filename,
)
```

- [ ] **Step 3: Implement `command_paths.py`**

Use this shape:

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_toolkit_cli._paths_core import (
    COMMAND_BINDING,
    library_lock_path_for_asset_type,
    library_root_for_asset_type,
)
from agent_toolkit_cli.skill_paths import (
    parent_clone_path,
    project_id,
    project_parents_root,
    project_store_root,
)

Scope = Literal["project", "global"]


def library_root(env: dict[str, str] | None = None) -> Path:
    return library_root_for_asset_type(COMMAND_BINDING, env)


def library_command_path(slug: str, *, env: dict[str, str] | None = None) -> Path:
    return library_root(env) / slug


def command_parent_clone_path(owner: str, repo: str, *, ref: str | None, env: dict[str, str] | None = None) -> Path:
    return parent_clone_path(owner, repo, ref=ref, root=library_root(env))


def library_lock_path(env: dict[str, str] | None = None) -> Path:
    return library_lock_path_for_asset_type(COMMAND_BINDING, env)


def canonical_command_dir(slug: str, *, scope: Scope, home: Path | None = None, project: Path | None = None) -> Path:
    if scope == "global":
        return library_command_path(slug)
    if project is None:
        raise ValueError("project scope requires project")
    return project_store_root(project).parent / "commands" / slug


def lock_file_path(*, scope: Scope, home: Path | None = None, project: Path | None = None) -> Path:
    if scope == "global":
        return library_lock_path()
    if project is None:
        raise ValueError("project scope requires project")
    return project / COMMAND_BINDING.lock_filename
```

- [ ] **Step 4: Implement `command_lock.py`**

Before writing code, define `commandPath` as a relative content-file path ending in `COMMAND.md`. For single-repo commands it is `COMMAND.md`; for monorepo commands it is `<subpath>/COMMAND.md`. On read/import, validate that `commandPath` is relative, contains no `..`, is not absolute, normalizes inside the clone root, and ends in `COMMAND.md`.

Copy `skill_lock.py` structure into `command_lock.py`, then rename command-specific fields:

```python
@dataclass
class LockEntry:
    source: str
    source_type: str
    ref: str | None = None
    command_path: str | None = None
    upstream_sha: str | None = None
    local_sha: str | None = None
    parent_url: str | None = None
    read_only: bool = False
    extras: dict[str, object] = field(default_factory=dict)
```

Entry field sets include `commandPath`. Preserve unknown extras. `clone_url_from_entry`, SHA-pin helpers, add/remove/write functions should match skill semantics.

- [ ] **Step 5: Update architecture guards**

Change expected module lists in `tests/test_cli/test_asset_type_architecture.py` from four to five by adding:

```python
"agent_toolkit_cli.command_install"
"agent_toolkit_cli.command_lock"
"agent_toolkit_cli.command_paths"
```

Add `agent_toolkit_cli.command_install` to `INSTALL_ENTRYPOINTS` after Task 3 creates it.

- [ ] **Step 6: Run path/lock tests**

```bash
uv run pytest tests/test_cli/test_command_paths.py tests/test_cli/test_command_lock.py tests/test_cli/test_paths_core_default_scope.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/_paths_core.py src/agent_toolkit_cli/command_paths.py src/agent_toolkit_cli/command_lock.py tests/test_cli/test_command_paths.py tests/test_cli/test_command_lock.py tests/test_cli/test_paths_core_default_scope.py tests/test_cli/test_asset_type_architecture.py
git commit -m "feat(commands): add command paths and lock foundation" -m "Device: $(hostname -s)"
```

## Task 2: Command adapters and install facade

**Files:**
- Create: `src/agent_toolkit_cli/command_adapters/__init__.py`
- Create: `src/agent_toolkit_cli/command_adapters/base.py`
- Create: `src/agent_toolkit_cli/command_adapters/markdown.py`
- Create: `src/agent_toolkit_cli/command_adapters/gemini.py`
- Create: `src/agent_toolkit_cli/command_install.py`
- Test: `tests/test_cli/test_command_adapters/test_markdown.py`
- Test: `tests/test_cli/test_command_adapters/test_gemini.py`
- Test: `tests/test_cli/test_command_install.py`

- [ ] **Step 1: Write failing adapter tests**

Adapter tests must cover every shipped harness and safety boundary: Claude global/project, Pi global/project, Gemini global/project, Codex global, Codex project refusal, unknown harness rejection, synthetic `standard-command` rejection, unmanaged destination conflict refusal, foreign symlink refusal, managed uninstall only, hand-authored file preservation, symlinked canonical `COMMAND.md` refusal, and multi-harness preflight/rollback on partial conflicts.

Test destinations:

```python
from pathlib import Path

from agent_toolkit_cli.command_adapters import get_adapter


def test_claude_command_destination_global(tmp_path):
    adapter = get_adapter("claude-code")
    dest = adapter.destination("demo", scope="global", home=tmp_path, project=None)
    assert dest == tmp_path / ".claude" / "commands" / "demo.md"


def test_pi_command_destination_project(tmp_path):
    adapter = get_adapter("pi")
    project = tmp_path / "repo"
    dest = adapter.destination("demo", scope="project", home=None, project=project)
    assert dest == project / ".pi" / "prompts" / "demo.md"


def test_gemini_command_destination_global(tmp_path):
    adapter = get_adapter("gemini-cli")
    dest = adapter.destination("demo", scope="global", home=tmp_path, project=None)
    assert dest == tmp_path / ".gemini" / "commands" / "demo.toml"


def test_codex_project_scope_is_refused(tmp_path):
    adapter = get_adapter("codex")
    try:
        adapter.destination("demo", scope="project", home=None, project=tmp_path)
    except ValueError as exc:
        assert "Codex commands are global-only" in str(exc)
    else:
        raise AssertionError("expected project-scope Codex refusal")
```

Test Gemini render:

```python
from agent_toolkit_cli.command_adapters.gemini import render_gemini_toml


def test_gemini_render_translates_arguments():
    text = "---\ndescription: Demo\nargument-hint: [issue]\n---\nFix: $ARGUMENTS\n"
    rendered = render_gemini_toml(text)
    assert 'description = "Demo"' in rendered
    assert 'prompt = ' in rendered
    assert "Fix: {{args}}" in rendered
```

Run:

```bash
uv run pytest tests/test_cli/test_command_adapters -q
```

Expected: FAIL because adapters do not exist.

- [ ] **Step 2: Implement adapter protocol**

`base.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

Scope = Literal["global", "project"]


class CommandAdapter(Protocol):
    name: str

    def destination(self, slug: str, *, scope: Scope, home: Path | None, project: Path | None) -> Path: ...
    def install(self, slug: str, source_file: Path, *, scope: Scope, home: Path | None, project: Path | None) -> Path: ...
    def uninstall(self, slug: str, *, scope: Scope, home: Path | None, project: Path | None) -> Path | None: ...
```

Use `.attk` sidecars for managed generated files, matching agent adapter ownership style. Sidecar JSON must include `tool: "agent-toolkit-cli"`, `asset_type: "command"`, `slug`, `harness`, `scope`, `canonical`, and `sha256` of generated content. For symlinks, ownership is symlink target equality to canonical `COMMAND.md`; refuse foreign symlinks. Canonical `COMMAND.md` must be a regular file, not a symlink.

- [ ] **Step 3: Implement Markdown adapters**

Support destination maps:

```python
DESTINATIONS = {
    "claude-code": ((".claude", "commands"), (".claude", "commands")),
    "pi": ((".pi", "agent", "prompts"), (".pi", "prompts")),
    "codex": ((".codex", "prompts"), None),
}
```

Global uses `home`; project uses `project`; `codex` project raises `ValueError`.

Install should preflight all requested destinations before writing. Symlink `COMMAND.md` to `<dest>/<slug>.md` when possible and refuse conflicting non-symlink files or foreign symlinks. If symlink fallback is needed on Windows, copy and write sidecar. If any later write fails, roll back projections created earlier in the same apply call and leave lock state unchanged.

- [ ] **Step 4: Implement Gemini adapter**

`render_gemini_toml(command_text: str) -> str` should:

1. Parse leading YAML frontmatter with `yaml.safe_load`.
2. Strip frontmatter from body.
3. Replace `$ARGUMENTS` with `{{args}}` only.
4. Detect Gemini injection tokens `!{` and `@{`; emit an install warning unless future metadata explicitly opts in. Do not silently strip them.
5. Write TOML with `tomlkit`:

```python
import tomlkit

doc = tomlkit.document()
if description:
    doc["description"] = description
doc["prompt"] = body
return tomlkit.dumps(doc)
```

Install writes a managed `.toml` file and refuses unmanaged conflicts. Uninstall removes only managed files.

- [ ] **Step 5: Implement adapter dispatcher**

`command_adapters/__init__.py`:

```python
from agent_toolkit_cli.command_adapters.gemini import GeminiCommandAdapter
from agent_toolkit_cli.command_adapters.markdown import MarkdownCommandAdapter

SUPPORTED_HARNESSES = ("claude-code", "pi", "codex", "gemini-cli")


def get_adapter(name: str):
    if name == "gemini-cli":
        return GeminiCommandAdapter()
    if name in {"claude-code", "pi", "codex"}:
        return MarkdownCommandAdapter(name)
    raise ValueError(f"unsupported command harness: {name}")
```

- [ ] **Step 6: Implement `command_install.py` facade**

Expose `plan()`, `apply()`, `install()`, `uninstall()`, and `_current_linked_harnesses()`. `apply()` reads `COMMAND.md` from canonical dir and dispatches adapters.

Core shape:

```python
COMMAND_SYNTHETIC_NAMES = frozenset({"standard-command"})


def plan(*, slug, scope, source=None, ref=None, target_agents=(), home=None, project=None):
    return _core_plan(
        slug=slug,
        scope=scope,
        source=source,
        ref=ref,
        target_agents=target_agents,
        home=home,
        project=project,
        canonical_dir_resolver=canonical_command_dir,
        standard_bundle_link=None,
        synthetic_names=COMMAND_SYNTHETIC_NAMES,
        current_linked_resolver=_current_linked_harnesses,
    )
```

- [ ] **Step 7: Run adapter/install tests**

```bash
uv run pytest tests/test_cli/test_command_adapters tests/test_cli/test_command_install.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/agent_toolkit_cli/command_adapters src/agent_toolkit_cli/command_install.py tests/test_cli/test_command_adapters tests/test_cli/test_command_install.py tests/test_cli/test_asset_type_architecture.py
git commit -m "feat(commands): add command projection adapters" -m "Device: $(hostname -s)"
```

## Task 3: CLI group and add/install lifecycle

**Files:**
- Modify: `src/agent_toolkit_cli/cli.py`
- Create: `src/agent_toolkit_cli/commands/command/*.py`
- Test: `tests/test_cli/test_cli_command_group.py`
- Test: `tests/test_cli/test_command_add.py`
- Test: `tests/test_cli/test_command_add_monorepo.py`
- Test: `tests/test_cli/test_command_install.py`

- [ ] **Step 1: Write failing CLI tests**

```python
from click.testing import CliRunner
from agent_toolkit_cli.cli import main


def test_commands_group_and_singular_alias_exist():
    runner = CliRunner()
    plural = runner.invoke(main, ["commands", "--help"])
    singular = runner.invoke(main, ["command", "--help"])
    assert plural.exit_code == 0
    assert singular.exit_code == 0
    assert "Manage commands" in plural.output


def test_command_add_requires_command_md(git_sandbox, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    runner = CliRunner()
    result = runner.invoke(main, ["command", "add", str(git_sandbox.upstream), "--slug", "demo"])
    assert result.exit_code != 0
    assert "COMMAND.md" in result.output
```

Create a command-specific git fixture with `COMMAND.md` and assert `command add` writes `commands-lock.json`.

Run:

```bash
uv run pytest tests/test_cli/test_cli_command_group.py tests/test_cli/test_command_add.py -q
```

Expected: FAIL.

- [ ] **Step 2: Register command group**

In `cli.py`:

```python
from agent_toolkit_cli.commands.command import command

_ASSET_COMMAND_ALIASES = {
    "skill": "skills",
    "agent": "agents",
    "command": "commands",
    "mcp": "mcps",
    "pi-extension": "pi-extensions",
    "bundle": "bundles",
    "instruction": "instructions",
}

main.add_command(command, name="commands")
```

- [ ] **Step 3: Implement `_common.py`**

Mirror agent `_common.py` with command harness tokens:

```python
SUPPORTED_COMMAND_HARNESSES = ("claude-code", "pi", "codex", "gemini-cli")


def parse_harness_tokens(raw: str) -> tuple[str, ...]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    unknown = [p for p in parts if p not in SUPPORTED_COMMAND_HARNESSES]
    if unknown:
        raise click.UsageError(f"unknown harness(es): {', '.join(unknown)}")
    return tuple(dict.fromkeys(parts))
```

Scope resolution mirrors skill/agent behavior; read-only verbs default global outside project.

- [ ] **Step 4: Implement `add_cmd.py`**

Mirror `agent add` but require `COMMAND.md`:

- Validate slug with strict path-stem regex before any filesystem access.
- Single repo: canonical `<library>/commands/<slug>/COMMAND.md` exists and is a regular file, not a symlink.
- Monorepo: source subpath's `COMMAND.md` exists, is a regular file, and resolves inside parent clone.
- Lock entry stores `command_path="COMMAND.md"` or `<subpath>/COMMAND.md`.
- Fresh failed clone is removed before raising.
- Existing same source is idempotent.
- Do not add `--command` or `--owned` in the first cut; monorepo commands are addressed by explicit subpath only.

- [ ] **Step 5: Implement install/uninstall/list/status/update/push/import/reset/remove/doctor**

Copy skill/agent command surfaces and adapt names:

Do not implement the maintenance verbs here. Task 3 ends after group/add/install/uninstall/list minimum lifecycle passes. Task 4 adds failing tests first, then implements `status/update/push/import/reset/remove/doctor`.

For Task 3 lifecycle:

- `install` default harnesses: `claude-code,pi,gemini-cli`.
- `codex` installs only when explicitly requested and prints a deprecation warning.
- `uninstall` no-harness default removes every known command harness projection.
- `list --json` emits `slug`, `source`, `ref`, `upstream_sha`, `local_sha`, `scope`.

- [ ] **Step 6: Run lifecycle tests**

```bash
uv run pytest tests/test_cli/test_cli_command_group.py tests/test_cli/test_command_add.py tests/test_cli/test_command_add_monorepo.py tests/test_cli/test_command_install.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/cli.py src/agent_toolkit_cli/commands/command tests/test_cli/test_cli_command_group.py tests/test_cli/test_command_add.py tests/test_cli/test_command_add_monorepo.py tests/test_cli/test_command_install.py
git commit -m "feat(commands): add command CLI lifecycle" -m "Device: $(hostname -s)"
```

## Task 4: Full command maintenance verbs and no-break regression suite

**Files:**
- Modify: command verb modules from Task 3
- Test: `tests/test_cli/test_command_status.py`
- Test: `tests/test_cli/test_command_update.py`
- Test: `tests/test_cli/test_command_push.py`
- Test: `tests/test_cli/test_command_import.py`
- Test: `tests/test_cli/test_command_reset.py`
- Test: `tests/test_cli/test_command_remove.py`
- Test: `tests/test_cli/test_command_doctor.py`
- Test: existing skill/agent/pi-extension smoke tests

- [ ] **Step 1: Write verb parity tests**

Use existing skill tests as templates. Required assertions:

```python
def test_command_import_is_additive_and_skip_existing(...): ...
def test_command_update_fast_forwards_clean_clone(...): ...
def test_command_update_refuses_dirty_clone(...): ...
def test_command_push_creates_pr_branch_by_default(...): ...
def test_command_reset_requires_slug_and_discards_only_with_force(...): ...
def test_command_remove_uninstalls_then_deletes_canonical(...): ...
def test_command_doctor_reports_drifted_projection(...): ...
```

Run:

```bash
uv run pytest tests/test_cli/test_command_status.py tests/test_cli/test_command_update.py tests/test_cli/test_command_push.py tests/test_cli/test_command_import.py tests/test_cli/test_command_reset.py tests/test_cli/test_command_remove.py tests/test_cli/test_command_doctor.py -q
```

Expected: FAIL until verbs are complete.

- [ ] **Step 2: Complete verbs**

Copy proven skill/agent patterns. Preserve command-specific wording, paths, and `COMMAND.md` content checks.

- [ ] **Step 3: Run no-break subset**

```bash
uv run pytest tests/test_cli/test_cli_skill_add.py tests/test_cli/test_cli_skill_install.py tests/test_cli/test_cli_agent_group.py tests/test_cli/test_cli_pi_extension_lifecycle.py tests/test_cli/test_instructions_cli.py tests/test_cli/test_mcp_scope_banner.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/agent_toolkit_cli/commands/command tests/test_cli/test_command_status.py tests/test_cli/test_command_update.py tests/test_cli/test_command_push.py tests/test_cli/test_command_import.py tests/test_cli/test_command_reset.py tests/test_cli/test_command_remove.py tests/test_cli/test_command_doctor.py
git commit -m "feat(commands): complete command maintenance verbs" -m "Device: $(hostname -s)"
```

## Task 5: TUI support

**Files:**
- Create: `src/agent_toolkit_tui/command_state.py`
- Create: `src/agent_toolkit_tui/widgets/command_grid.py`
- Modify: `src/agent_toolkit_tui/widgets/__init__.py`
- Modify: `src/agent_toolkit_tui/app.py`
- Modify: `src/agent_toolkit_tui/column_info.py`
- Modify: `src/agent_toolkit_tui/composition.py`
- Test: `tests/test_tui/test_command_state.py`
- Test: `tests/test_tui/test_command_grid.py`
- Modify: `tests/test_tui/test_app.py`
- Modify: `tests/test_tui/test_composition.py`

- [ ] **Step 1: Write failing TUI tests**

Assert sidebar includes command:

```python
async def test_app_sidebar_includes_commands():
    app = TUIApp()
    async with app.run_test() as pilot:
        option_list = app.query_one("#asset-types-list")
        labels = [str(option.prompt) for option in option_list.options]
        assert "command" in labels
```

Assert command rows union library/project locks and cells report projection state.

- [ ] **Step 2: Implement `command_state.py`**

Mirror `agent_state.py` row-universe contract with command adapters:

```python
@dataclass(frozen=True)
class CommandCell:
    linked: bool

@dataclass
class CommandRow:
    slug: str
    source: str
    ref: str
    state: Literal["installed", "library", "unlisted"]
    cells: dict[tuple[str, str], CommandCell] = field(default_factory=dict)
```

- [ ] **Step 3: Implement grid widget**

Mirror `AgentGrid` behavior: render slug/source/ref/state plus command harness columns. Use glyphs consistent with other grids.

- [ ] **Step 4: Wire app**

Update `AssetType` literal and labels:

```python
AssetType = Literal["instruction", "skill", "command", "pi-extension", "agent", "mcp"]
```

Add `CommandGrid` compose/show/refresh/apply paths. Preserve existing default active asset type (`skill`) to avoid changing startup behavior.

- [ ] **Step 5: Run TUI tests**

```bash
uv run pytest tests/test_tui/test_command_state.py tests/test_tui/test_command_grid.py tests/test_tui/test_app.py tests/test_tui/test_composition.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_tui tests/test_tui
git commit -m "feat(tui): show command assets" -m "Device: $(hostname -s)"
```

## Task 6: Documentation and harness matrix

**Files:**
- Create: `docs/asset-types/commands.md`
- Modify: `docs/agent-toolkit/cli.md`
- Modify: `docs/agent-toolkit/harness-matrix.md`
- Modify: `scripts/gen_harness_docs.py`
- Modify: generated `docs/matrix.md` and harness pages
- Modify: `README.md`, `docs/index.md`, `docs/glossary.md`, `docs/agent-toolkit/lock-files.md`, `docs/agent-toolkit/tui.md`
- Test: docs/matrix parity tests

- [ ] **Step 1: Write docs asset page**

`docs/asset-types/commands.md` must include:

```markdown
# Commands

The `command` asset type manages reusable slash-command prompts. Commands live in the toolkit library as `COMMAND.md` folders and are projected into harness-specific command or prompt-template locations.

- Lock file: `commands-lock.json`
- Canonical entrypoint: `COMMAND.md`
- Portable argument recommendation: `$ARGUMENTS`
- Initial supported harnesses: Claude Code, Pi, Gemini CLI, and explicit/deprecated Codex custom prompts
```

Include the evidence table from the spec.

- [ ] **Step 2: Update CLI docs**

Add command group reference to `docs/agent-toolkit/cli.md` top-level command list and full command section.

- [ ] **Step 3: Update harness matrix SSOT and generator**

Add Commands as sixth asset type. If generator uses hard-coded columns, add `commands` column with supported/gap/N/A state for main harnesses and generated harness pages.

Use initial matrix semantics:

- Claude Code: ✅ commands, legacy markdown commands, note skills preferred.
- Pi: ✅ prompt templates.
- Codex: ✅ deprecated custom prompts, global only.
- Gemini CLI: ✅ TOML custom commands.
- Cursor: — gap with research note unless deterministic validation evidence is added.
- Other harnesses: `?` unless documented, or N/A if no slash command concept.

- [ ] **Step 4: Regenerate docs**

```bash
uv run python scripts/gen_harness_docs.py
```

Expected: `docs/matrix.md` and relevant `docs/harnesses/*.md` update.

- [ ] **Step 5: Update README and TUI docs**

Mention `commands` in asset type lists, examples, and TUI sidebar docs. Do not overwrite unrelated existing README edits; inspect `git diff README.md` first and preserve user changes.

- [ ] **Step 6: Update command coverage guard**

Update `tests/test_cli/test_command_coverage_guard.py` so command verbs are not skipped:

```python
_GROUP_ALIASES = {
    "commands": ("commands", "command"),
    # existing groups...
}
```

Then run the guard after command group lands.

- [ ] **Step 7: Run docs tests**

```bash
uv run pytest tests/test_cli/test_instructions_packaging.py tests/test_cli/test_command_coverage_guard.py -q
uv run mkdocs build --strict
```

If matrix-specific tests have different names, run:

```bash
uv run pytest tests -q -k "matrix or harness or docs"
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add docs scripts tests README.md mkdocs.yml
git commit -m "docs(commands): document command asset support" -m "Device: $(hostname -s)"
```

## Task 7: Version bump and full verification

**Files:**
- Modify: `pyproject.toml`
- Modify: `uv.lock` if project metadata is recorded there

- [ ] **Step 1: Bump version and lock metadata**

Change:

```toml
version = "4.3.0"
```

to:

```toml
version = "4.4.0"
```

Use `4.4.0` because this is a backwards-compatible feature. Then run `uv lock` if `uv.lock` records the package version. If release-please demands a different workflow, stop and escalate before changing release config.

- [ ] **Step 2: Run focused command tests**

```bash
uv run pytest tests/test_cli/test_command_*.py tests/test_cli/test_command_adapters tests/test_tui/test_command_*.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

```bash
uv run pytest -q
uv run mkdocs build --strict
```

Expected: PASS.

- [ ] **Step 4: Smoke CLI help**

```bash
uv run agent-toolkit-cli --version
uv run agent-toolkit-cli commands --help
uv run agent-toolkit-cli command --help
uv run agent-toolkit-cli skills --help
uv run agent-toolkit-cli agents --help
```

Expected:

- Version prints `4.4.0`.
- Command help works for plural and singular.
- Existing skill/agent help still works.

- [ ] **Step 5: Final no-break audit**

Check:

```bash
git diff --stat main...HEAD
git status --short
```

Confirm:

- `uv run mkdocs build --strict` passes.
- No existing lock file schema changed except adding independent `commands-lock.json` support.
- No existing CLI command removed or renamed.
- No project/user hand-authored command files are removed in tests.
- README pre-existing user edit remains intact.

- [ ] **Step 6: Commit version bump**

```bash
git add pyproject.toml uv.lock
git commit -m "chore(commands): bump version for command assets" -m "Device: $(hostname -s)"
```

## Critical review findings

Resolved during `/aj-issue` critical-review gate:

- ✓ Cursor support contradiction resolved: first cut marks Cursor as a documented gap unless deterministic validation evidence is captured.
- ✓ `--command` / `--owned` ambiguity resolved: first cut omits both flags; monorepo commands use explicit subpaths.
- ✓ Slug path traversal resolved: spec and plan require strict path-stem validation before filesystem access.
- ✓ `commandPath` ambiguity resolved: `commandPath` is a relative content-file path ending in `COMMAND.md`.
- ✓ Supporting files ambiguity resolved: first-cut projections install only `COMMAND.md`; supporting files are source-only/non-portable.
- ✓ Bundle scope resolved: commands are out of scope for bundles in first cut unless explicitly implemented with tests.
- ✓ Docs generator/nav gap resolved: `mkdocs.yml`, `docs/asset-types/skills.md`, generated matrix/docs, and `mkdocs build --strict` are in plan.
- ✓ `uv.lock` version drift resolved: version bump task includes `uv lock`/`uv.lock` when metadata changes.
- ✓ TDD ordering resolved: maintenance verbs move to Task 4 after failing tests are written.
- ✓ Adapter/ownership safety resolved: adapter tests include all supported harness scopes, unmanaged conflict refusal, foreign symlink refusal, sidecars, hand-authored preservation, and partial rollback.
- ✓ Gemini injection risk resolved: adapter must warn on `!{`/`@{` tokens unless future opt-in metadata exists.
- ✓ Command coverage guard resolved: plan updates `tests/test_cli/test_command_coverage_guard.py` for `commands`/`command` aliases.

No findings waived.

## Implementation handoff notes

- Treat Cursor as out of scope unless deterministic validation evidence is captured. Default plan marks it as a gap, not a supported adapter.
- Do not stage or commit unrelated existing README changes unless they are part of this implementation and explicitly reconciled.
- Keep command asset support additive. Existing tests for skills, agents, instructions, MCP, pi-extension, and bundle must pass unchanged.
- Use TDD. Every adapter path and translated output needs a focused test before implementation.
- Prefer copying/adapting established skill/agent modules over introducing a new abstraction layer.
