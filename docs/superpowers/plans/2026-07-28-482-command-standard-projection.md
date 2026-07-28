# Commands Standard Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install one owned `.claude/commands/<slug>.md` projection that Claude
Code and Neovate consume at both scopes, with Devin also importing it as a
project skill; expose it as `standard` across the CLI, lock, doctor, and TUI.

**Architecture:** Add a scope-aware `STANDARD_COMMAND_READERS` SSOT and a
sentinel-owning Standard adapter. Normalize the Claude alias to that one
destination, record normalized projection tokens in an optional v1 lock field,
and make the TUI derive its Standard-first columns, reader count, state, and
Apply behavior from the same SSOT. Pi/Gemini remain individual adapters;
Codex remains explicit/global-only.

**Tech Stack:** Python 3.13, Click, Textual, pytest + pytest-asyncio, existing
Markdown/symlink/`.attk` sidecar adapters; no new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-07-28-482-command-standard-projection.md`

**Research:** `docs/agent-toolkit/research/2026-07-28-command-standard-readers.md`

## Global Constraints

- The reader sets are exact: global `{claude-code, neovate}`; project
  `{claude-code, neovate, devin}`. Do not add readers without current upstream
  evidence.
- `standard` is a real install target. `standard-command` is rejected. An
  explicit `claude-code` target normalizes to `standard` before planning,
  scanning, locking, or mutation.
- Do not add Neovate/Devin adapters or alter `MAIN_HARNESSES`; they consume the
  shared file and do not need individual projection cells.
- Preserve all existing command-source behavior: `COMMAND.md` remains regular,
  Pi remains Markdown, Gemini remains generated TOML, and Codex remains
  explicit/global-only.
- Keep the lock envelope at version 1. Missing `harnesses` means legacy state;
  reads are non-mutating.
- Use `git add -f docs/superpowers/specs/2026-07-28-482-command-standard-projection.md docs/superpowers/plans/2026-07-28-482-command-standard-projection.md`
  for planning artifacts. Every authored implementation commit includes
  `Device: $(hostname -s)`.

## Implementation Units

| Unit | Deliverable | Primary files |
|---|---|---|
| U1 | Standard reader SSOT and safe shared-slot adapter | `command_adapters/standard.py`, adapter registry, adapter tests |
| U2 | Normalized projection/lock lifecycle | `command_lock.py`, `command_install.py`, install/lock tests |
| U3 | CLI verbs and project materialisation | `commands/command/*.py`, CLI tests |
| U4 | Standard-first Command data/TUI composition | composition, command state/grid, display names, column info, settings |
| U5 | TUI Apply and user docs | `app.py`, TUI tests, command docs |
| U6 | Verification evidence | `assets/verification/issue-482/` |

---

### Task 1: Define and test the Standard slot adapter

**Files:**
- Create: `src/agent_toolkit_cli/command_adapters/standard.py`
- Modify: `src/agent_toolkit_cli/command_adapters/__init__.py`
- Modify: `src/agent_toolkit_cli/command_adapters/base.py`
- Modify: `src/agent_toolkit_cli/command_adapters/markdown.py`
- Modify: `src/agent_toolkit_cli/command_adapters/gemini.py`
- Create: `tests/test_cli/test_command_adapters/test_standard.py`
- Modify: `tests/test_cli/test_command_adapters/test_markdown.py`
- Modify: `tests/test_cli/test_command_adapters/test_gemini.py`

**Interfaces:**
- Produces: `STANDARD_COMMAND_READERS`, `commands_standard_covered(scope)`,
  `StandardCommandAdapter`, and `adapter_for()`. Every command adapter also
  implements `is_installed(slug, source_file, scope, home, project)` so the
  facade can distinguish ownership from mere path existence.
- Consumes: `ensure_regular_command_file`, `is_managed_file`,
  `remove_managed_file`, `sidecar_path`, and `write_sidecar` from
  `command_adapters.base`.
- `get_adapter("standard")` returns the Standard adapter; concrete adapter
  names retain their existing behavior.

- [ ] **Step 1: Write the red reader/ownership tests**

Create `test_standard.py` with direct tests for:

```python
assert STANDARD_COMMAND_READERS == {
    "global": frozenset({"claude-code", "neovate"}),
    "project": frozenset({"claude-code", "neovate", "devin"}),
}
assert commands_standard_covered("global") == STANDARD_COMMAND_READERS["global"]
with pytest.raises(KeyError):
    commands_standard_covered("unknown")
```

Use one canonical `COMMAND.md` fixture. Assert the adapter resolves exactly:

```python
home / ".claude" / "commands" / "demo.md"
project / ".claude" / "commands" / "demo.md"
```

Then pin all ownership cases at both scopes:

1. absent slot → canonical-resolving symlink or managed fallback copy plus
   `.attk` with `harness == "standard"`;
2. byte-identical regular pre-existing Claude file → adopted with a Standard
   sidecar, no content rewrite;
3. canonical-resolving legacy symlink → adopted, not duplicated;
4. divergent regular file and foreign symlink → `InstallError`, byte-for-byte
   untouched;
5. sidecar-owned stale copy → refreshes to canonical content;
6. stale Standard sidecar plus user-replaced symlink → unlink and recreate the
   slot without writing through or changing the foreign symlink target;
7. standard uninstall removes an owned/adopted slot and sidecar, removes a
   sentinel-less matching legacy file, but retains a divergent unowned file;
8. missing slot removes only a dangling Standard sidecar;
9. an adoptable legacy Claude symlink or byte-identical file returns `False`
   from Standard `is_installed()` until the adapter writes its Standard
   sidecar, while an owned live Standard slot returns `True`; and
10. `"../bad"`, `"..\\bad"`, `"."`, `".."`, and `""` raise from
    `destination()`.

Add a registry test that `get_adapter("standard")` succeeds while
`get_adapter("standard-command")` remains a clear unsupported-harness error.

- [ ] **Step 2: Run the focused test to establish the red state**

Run:

```bash
uv run pytest -q tests/test_cli/test_command_adapters/test_standard.py
```

Expected: collection/import failure because `standard.py` and its registry entry
do not exist yet.

- [ ] **Step 3: Implement the reader SSOT and adapter**

Create `standard.py` with this public shape:

```python
STANDARD_COMMAND_READERS: dict[str, frozenset[str]] = {
    "global": frozenset({"claude-code", "neovate"}),
    "project": frozenset({"claude-code", "neovate", "devin"}),
}

_TEMPLATES = {
    "global": (".claude", "commands"),
    "project": (".claude", "commands"),
}


def commands_standard_covered(scope: str) -> frozenset[str]:
    return STANDARD_COMMAND_READERS[scope]
```

`StandardCommandAdapter.destination()` validates the slug exactly as the
existing adapters do, requires `home` for global and `project` for project, and
returns the shared `.claude/commands/<slug>.md` target.

`install()` must first call `ensure_regular_command_file(source_file)`. Use this
ownership algorithm:

```python
if destination is absent:
    make destination parent
    try symlink_to(source_file)
    except OSError: copyfile(source_file, destination)
    write Standard sidecar
elif destination is symlink and resolves to source_file:
    write/update Standard sidecar; keep symlink
elif destination is a regular file and bytes equal source_file:
    write/update Standard sidecar; keep file
elif destination has a valid Standard sidecar:
    unlink any symlink before refreshing; recreate symlink/copy + sidecar
else:
    raise InstallError(f"{dest}: unmanaged command exists")
```

For a managed copy refresh, never use an operation that writes through a
symlink. If adapter-internal sidecar creation fails after a new file is made,
remove only the new file and re-raise. `uninstall()` recognizes the Standard
sidecar, a source-resolving symlink, or exact canonical content as ownership;
otherwise it returns `None` without deleting the user file. `is_installed()` is
stricter: it returns true only for a valid Standard sidecar plus a live
canonical-resolving symlink or matching regular-file bytes, never for an
adoptable legacy path. Add equivalent ownership checks to Markdown and Gemini:
a canonical-resolving Markdown symlink or valid matching sidecar is installed;
Gemini requires a valid matching sidecar. Include an adapter test whose
canonical source contains `allowed-tools` and `argument-hint` frontmatter: both
a symlink target and forced-copy projection must have exactly the same bytes as
the source.

Register `standard` before the Markdown-name set in `get_adapter()`. Keep
`SUPPORTED_HARNESSES` concrete-only and add a separate public
`INSTALLABLE_HARNESSES = ("standard", *SUPPORTED_HARNESSES)` so a virtual slot
is never mistaken for a concrete harness catalog entry.

- [ ] **Step 4: Run the adapter suite**

Run:

```bash
uv run pytest -q tests/test_cli/test_command_adapters
```

Expected: all Markdown, Gemini, and new Standard adapter tests pass.

- [ ] **Step 5: Commit U1**

```bash
git add src/agent_toolkit_cli/command_adapters \
  tests/test_cli/test_command_adapters
git commit -m "feat(commands): add standard slot adapter" \
  -m "Device: $(hostname -s)"
```

### Task 2: Add normalized projection state and facade-level dedupe

**Files:**
- Modify: `src/agent_toolkit_cli/command_lock.py`
- Modify: `src/agent_toolkit_cli/command_install.py`
- Modify: `src/agent_toolkit_cli/commands/command/import_cmd.py`
- Modify: `tests/test_cli/test_command_lock.py`
- Modify: `tests/test_cli/test_command_install.py`
- Create: `tests/test_cli/test_command_standard_projection.py`

**Interfaces:**
- Produces: optional `LockEntry.harnesses: tuple[str, ...]`,
  `ensure_project_command_canonical()`, normalized target/scanner helpers, and
  an `InstallResult` whose lock action is accurate.
- Consumes: Task 1 `commands_standard_covered()`/`get_adapter("standard")` and
  existing `InstallPlan`.

- [ ] **Step 1: Write lock compatibility red tests**

Add tests proving that:

```python
legacy = {
    "version": 1,
    "skills": {"demo": {"source": "o/r", "sourceType": "github"}},
}
assert read_lock(path).skills["demo"].harnesses == ()
```

and that a non-list `harnesses`, or a list containing a non-string, raises
`ValueError`. Assert `write_lock()` emits no `harnesses` key for `()` and emits
one deterministic, duplicate-free JSON list for `("standard", "pi")`. Preserve
unknown existing entry extras through the round trip. Construct a legacy
positional `LockEntry` whose final argument is its extras mapping and assert it
still binds to `extras`, with `harnesses == ()`.

- [ ] **Step 2: Write facade lifecycle red tests**

Create a focused projection test module that seeds canonical content and locks
under a temporary `HOME`. Cover:

1. `_current_linked_harnesses()` reports only `("standard",)` when a
   Standard-owned shared slot exists; it never also reports `claude-code`;
2. `plan(slug="demo", scope="global", target_agents=("claude-code",))`
   normalizes the target to
   `standard`, and `("standard", "claude-code")` produces one add/remove
   decision, not a self-cancelling delta;
3. default global install records `("standard", "pi", "gemini-cli")`, creates
   one shared slot, and does not create a second Claude file;
4. an existing lock list containing `claude-code` becomes `standard` only after
   a successful Standard mutation;
5. old locks without `harnesses` remain untouched by a read-only scan;
6. project `source=None` install derives source/ref/commandPath from the global
   library entry only after a real projection succeeds;
7. project first-install conflict leaves no derived lock entry, preserves the
   foreign file, and rolls back its newly materialised project canonical;
8. an all-failed/unsupported project attempt leaves no new entry;
9. a manual global canonical with no source lock retains the existing unlisted
   behavior and doctor reports its physical Standard projection as untracked;
10. a failure in Pi or Gemini before Standard runs rolls back only newly-created
    non-standard projections and does not adopt/write a Standard sidecar;
11. a foreign or merely-adoptable `.claude/commands/demo.md` makes a Standard
    target appear in `plan.add_agents`, so `apply()` reaches the ownership guard
    instead of returning a false successful no-op; and
12. a direct `apply()` whose Pi target already resolves to canonical and whose
    later Standard target fails retains that pre-existing Pi path rather than
    unlinking it during rollback; and
13. a first project projection from a manual global canonical creates no project
    source entry and doctor reports its physical slot as untracked; and
14. importing an incoming entry with `harnesses=["standard", "pi"]` creates a
    library entry with `harnesses == ()`, because projection ownership is local
    state rather than source metadata.

- [ ] **Step 3: Extend the lock model without a version bump**

Add the field with a safe default:

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
    harnesses: tuple[str, ...] = ()
```

Add a small parser that accepts only `list[str]`, returns ordered unique tuple
values, and raises `ValueError` for malformed data. Append `harnesses` after
`extras` in the dataclass so existing positional callers keep their extras
argument. Put `"harnesses"` in `_FIELDS`; emit it only when non-empty, ahead of
`out.update(e.extras)`, so it cannot be silently overridden. Do not change
`CURRENT_VERSION` or `SUPPORTED_VERSIONS`.

- [ ] **Step 4: Make the facade own normalization, project setup, and lock writes**

In `command_install.py`, add `_normalize_to_standard(name: str, slug: str, *,
scope: Scope, home: Path | None, project: Path | None) -> str`,
`_ordered_tokens(tokens: Iterable[str]) -> tuple[str, ...]`,
`ensure_project_command_canonical(*, slug: str, project: Path) -> bool`, and
`_project_entry_from_global(slug: str) -> LockEntry`.

`_normalize_to_standard()` compares a concrete adapter destination with the
Standard adapter destination and returns `"standard"` only when they are the
same path. It must catch only known destination-resolution failures; a broken
adapter is not silently hidden. `ensure_project_command_canonical()` verifies
the global canonical's regular `COMMAND.md`, creates the missing project
canonical by symlink or `shutil.copytree(global_canonical, project_canonical,
symlinks=True)`, returns `True` only when
it created that directory, and makes no lock write. An existing project
canonical returns `False` and is validated by `apply()` rather than overwritten.

Revise `_current_linked_harnesses()` to resolve the canonical source once, then
probe Standard first. Add every successfully resolved Standard destination to a
`seen_destinations: set[Path]` **before** its ownership check; append
`"standard"` only if `StandardCommandAdapter.is_installed()` passes. Then probe
every concrete adapter, skipping a destination already reserved by Standard
and appending a concrete token only when that adapter's `is_installed()` passes.
It returns normalized owned tokens, so one shared file is observed once and an
unowned shared file cannot suppress the install guard.

At `apply()` entry, when `scope == "project"` and there are add targets,
call `ensure_project_command_canonical()` inside the facade; it returns whether
it created the project canonical. Validate that canonical `COMMAND.md` before
writing anything. Normalize and deduplicate both add and remove tokens. For
mutation ordering, execute all non-standard adds first and Standard last; this
keeps the only adopting action after fallible Pi/Gemini writes. Before every
adapter install, snapshot whether its destination and sidecar already exist.
Track successful add tokens separately from truly new destinations. On failure,
remove only destinations created during this call; if Standard adopted an
existing destination whose sidecar was absent before the call, remove only that
new sidecar and preserve the legacy path. Never reuse the old `created` list as
a blind rollback-delete list. Additionally remove the project canonical only
when this call created it: `unlink()` a created directory symlink, otherwise
`shutil.rmtree()` its created real directory, never recursively follow a
symlink. Standard's own install cleans up its partial new slot if it fails.

After all requested operations succeed, merge actual successful tokens into the
active lock entry and write once. Remove only tokens whose managed destination
was actually removed. On project scope, derive a fresh source entry from the
global lock only after a successful projection; copy source/ref/commandPath and
extras, reset SHAs, and start with empty `harnesses`. Never copy the global
projection list into a project entry. If the global canonical is manual and has
no library lock entry, do not invent either scope's source metadata; leave the
physical project projection untracked. In `import_cmd.py`, pass `harnesses=()`
explicitly when constructing the new library `LockEntry`; imports deliberately
carry source metadata but not a different machine's projection state.

- [ ] **Step 5: Run red-to-green focused tests**

Run:

```bash
uv run pytest -q \
  tests/test_cli/test_command_lock.py \
  tests/test_cli/test_command_install.py \
  tests/test_cli/test_command_standard_projection.py
```

Expected: pass, including legacy v1 reads and failure-atomic project behavior.

- [ ] **Step 6: Commit U2**

```bash
git add src/agent_toolkit_cli/command_lock.py \
  src/agent_toolkit_cli/command_install.py \
  src/agent_toolkit_cli/commands/command/import_cmd.py \
  tests/test_cli/test_command_lock.py \
  tests/test_cli/test_command_install.py \
  tests/test_cli/test_command_standard_projection.py
git commit -m "feat(commands): track standard projections" \
  -m "Device: $(hostname -s)"
```

### Task 3: Route every Commands CLI verb through the standard contract

**Files:**
- Modify: `src/agent_toolkit_cli/commands/command/_common.py`
- Modify: `src/agent_toolkit_cli/commands/command/install_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/command/uninstall_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/command/remove_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/command/list_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/command/status_cmd.py`
- Modify: `src/agent_toolkit_cli/commands/command/doctor_cmd.py`
- Modify: `tests/test_cli/test_command_add.py`
- Modify: `tests/test_cli/test_command_verbs.py`
- Create: `tests/test_cli/test_command_cli_standard.py`

**Interfaces:**
- Consumes: `INSTALLABLE_HARNESSES` and the Task 2 lock/facade contract.
- Produces: shared default/parse helpers and user-visible normalized command
  output.

- [ ] **Step 1: Write CLI behavior tests before changing command parsing**

Add test cases for all of these exact invocations:

```python
["command", "install", "demo", "-g"]
["command", "install", "demo", "-g", "--harnesses", "claude-code"]
["command", "install", "demo", "-p", "--harnesses", "standard"]
["command", "uninstall", "demo", "-g"]
["command", "list", "-g", "--json"]
["command", "status", "-g"]
["command", "doctor", "-g"]
```

Assert that the default creates Standard/Pi/Gemini, the explicit Claude spelling
prints/reports Standard, project Standard is legal, and an explicit project
Codex target still fails with the existing global-only error.

For list JSON, assert `harnesses == ["standard", "pi", "gemini-cli"]` after a
default install. For human status, assert `standard` is present and
`claude-code` is absent. For doctor, snapshot lock bytes before invocation and
assert they are unchanged; seed a tracked-but-missing standard slot and an
untracked slot in separate tests, asserting both diagnostics are visible. Also
seed a direct manual canonical directory with a regular `COMMAND.md` but no
lock at global and project scope; doctor must discover its slug from canonical
inventory and report its Standard projection as untracked without writing a
lock entry.

- [ ] **Step 2: Centralize CLI target resolution**

In `_common.py`, keep concrete `SUPPORTED_COMMAND_HARNESSES`, import the
installable set, and implement `parse_harness_tokens(raw: str, *, scope: str,
slug: str, home: Path | None, project: Path | None) -> tuple[str, ...]`,
`default_install_harnesses(scope: str) -> tuple[str, ...]`, and
`default_uninstall_harnesses(scope: str) -> tuple[str, ...]`.

The install default is exactly `("standard", "pi", "gemini-cli")`. The
uninstall default is `("standard", *SUPPORTED_COMMAND_HARNESSES)` normalized
and deduplicated, preserving legacy cleanup. The parser accepts `standard`,
normalizes a valid `claude-code` alias using Task 2, rejects
`standard-command`, and does not expose Neovate or Devin as independent target
names.

- [ ] **Step 3: Update install and uninstall command paths**

`install_cmd` removes its inline `copytree` block and enters only through
`command_install.apply()`; the facade owns project materialisation and rollback.
Its help says “Default: standard + Pi + Gemini.” It emits each actual projected
destination and reports `installed <slug> [<scope>]` as today.

`uninstall_cmd` calls the maximal default when `--harnesses` is omitted and
passes the resolved list to the facade. It prints only paths actually removed;
a foreign Standard refusal is visibly reported by the adapter and its lock token
remains.

- [ ] **Step 4: Make destructive and read verbs truthful**

Change `remove_cmd` to call the same non-destructive projection removal helper
with the entry's tracked tokens (or the maximal legacy default when the field is
absent) before dropping the active-scope lock/canonical. This makes Standard
sidecar cleanup part of destructive remove rather than an orphan.

Extend `list_cmd` rows with `harnesses: list(entry.harnesses)` and append the
same comma-separated field to human output (`(none)` for a library-only entry).

Extend `status_cmd` with the normalized physical scanner. Its emitted target
list is sorted with `standard` first and never double-counts Claude.

Keep `doctor_cmd` read-only. Build its slug set from active-lock keys plus
immediate canonical-store child directories whose `COMMAND.md` is a regular
file (`library_root()` globally, `project_store_root(project)` for a project).
For each slug, compare `entry.harnesses` when present with the scanner's actual
token set and print deterministic `missing projection:` and `untracked
projection:` diagnostics, including `standard`; retain the existing canonical
`COMMAND.md` check and clean verdict behavior.

- [ ] **Step 5: Run the CLI slice**

Run:

```bash
uv run pytest -q \
  tests/test_cli/test_command_add.py \
  tests/test_cli/test_command_install.py \
  tests/test_cli/test_command_verbs.py \
  tests/test_cli/test_command_cli_standard.py
```

Expected: pass; no existing maintenance verb loses its test invocation.

- [ ] **Step 6: Commit U3**

```bash
git add src/agent_toolkit_cli/commands/command \
  tests/test_cli/test_command_add.py \
  tests/test_cli/test_command_verbs.py \
  tests/test_cli/test_command_cli_standard.py
git commit -m "feat(commands): expose standard projection in CLI" \
  -m "Device: $(hostname -s)"
```

### Task 4: Make Commands composition and state scope-aware

**Files:**
- Modify: `src/agent_toolkit_tui/composition.py`
- Modify: `src/agent_toolkit_tui/command_state.py`
- Modify: `src/agent_toolkit_tui/display_names.py`
- Modify: `src/agent_toolkit_tui/column_info.py`
- Modify: `src/agent_toolkit_tui/screens/settings.py`
- Modify: `tests/test_tui/test_composition.py`
- Modify: `tests/test_tui/test_command_state.py`
- Modify: `tests/test_tui/test_standard_column_rule.py`
- Modify: `tests/test_tui/test_column_info.py`
- Modify: `tests/test_tui/test_settings_screen.py`

**Interfaces:**
- Produces: `commands_nonstandard_main(scope, selection)` and
  `commands_main(scope, selection)`, where the latter begins with `standard`.
- Consumes: `commands_standard_covered(scope)` from Task 1.

- [ ] **Step 1: Add scope-aware composition red tests**

Replace existing Commands composition assertions with these contracts:

```python
assert commands_main("global") == ("standard", "pi", "gemini-cli")
assert commands_main("project") == ("standard", "pi", "gemini-cli")
assert commands_main("global", ("claude-code", "pi")) == ("standard", "pi")
assert commands_main("project", ()) == ("standard",)
```

Add a coverage invariant: for every selected concrete command harness, it is
standard-covered at the active scope or appears in
`commands_nonstandard_main(scope, selection)`. Assert Claude is covered and
never appears as a separate command column.

Update the #478 standard rule test by removing both Commands entries from
`NO_STANDARD_SLOT`, then assert the live headers are `Standard (2)` globally
and `Standard (3)` project-scope.

- [ ] **Step 2: Implement composition and state**

Implement:

```python
def commands_nonstandard_main(
    scope: str, selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    chosen = effective_main_harnesses(selection)
    covered = commands_standard_covered(scope)
    return tuple(
        name for name in ("claude-code", "pi", "gemini-cli")
        if name not in covered and name in chosen
    )


def commands_main(
    scope: str, selection: tuple[str, ...] | None = None,
) -> tuple[str, ...]:
    return ("standard", *commands_nonstandard_main(scope, selection))
```

Do not derive the render set from `INSTALLABLE_HARNESSES`: Codex remains a CLI
choice, not a Commands grid column.

Change `command_state.interactive_harnesses()` and every caller to accept/pass
`scope`. `_cell_for()` must query the Standard adapter like any other adapter.
Build state from the active scope entry's `harnesses`: no tracked projection is
`library`, a tracked one is `installed`, and a scope-only entry is `unlisted`.
Continue probing physical cells so lock/file disagreement remains visible.

- [ ] **Step 3: Extend Standard header and info factories**

In `display_names._standard_covered_count()`, resolve Commands at call time:

```python
if asset_type == "command":
    from agent_toolkit_cli.command_adapters.standard import commands_standard_covered
    return len(commands_standard_covered(scope))
```

In `column_info.py`, add `("command", "standard")` to `COLUMN_INFO` and a
factory that calls `commands_standard_covered(_scope(context, default="global"))`
when opened. Its
sentence is scope-specific and exact:

- global: `One Markdown command slot at .claude/commands/<slug>.md serves Claude and Neovate.`
- project: `One Markdown command slot at .claude/commands/<slug>.md serves Claude and Neovate; Devin imports it as a skill.`

Remove the now-unrendered `("command", "claude-code")` pair and its old
harness sentence. Add test assertions that each live Standard panel displays
all names from its SSOT and the project-only Devin explanation.

Update Settings so Claude's checkbox label includes Commands in its
Standard-covered set and `_has_standalone_column()` evaluates Commands at both
scopes. Do not add Neovate/Devin checkboxes.

- [ ] **Step 4: Run the state/composition suite**

Run:

```bash
uv run pytest -q \
  tests/test_tui/test_composition.py \
  tests/test_tui/test_command_state.py \
  tests/test_tui/test_standard_column_rule.py \
  tests/test_tui/test_column_info.py \
  tests/test_tui/test_settings_screen.py
```

Expected: Commands has a real Standard slot at both scopes; selection never
hides it and no duplicate Claude cell returns.

- [ ] **Step 5: Commit U4**

```bash
git add src/agent_toolkit_tui/composition.py \
  src/agent_toolkit_tui/command_state.py \
  src/agent_toolkit_tui/display_names.py \
  src/agent_toolkit_tui/column_info.py \
  src/agent_toolkit_tui/screens/settings.py \
  tests/test_tui
git commit -m "feat(tui): compose commands through standard slot" \
  -m "Device: $(hostname -s)"
```

### Task 5: Render and apply the Standard Commands column

**Files:**
- Modify: `src/agent_toolkit_tui/widgets/command_grid.py`
- Modify: `src/agent_toolkit_tui/app.py`
- Modify: `tests/test_tui/test_command_grid.py`
- Modify: `tests/test_tui/test_command_app.py`
- Create: `tests/test_tui/test_command_apply.py`
- Modify: `tests/test_tui/test_source_column_width.py`
- Modify: `tests/test_tui/test_header_click_info.py`

**Interfaces:**
- Consumes: scope-aware `interactive_harnesses(scope, selection)`,
  `standard_column_header("command", scope)`, and the facade project helper.
- Produces: a leading actionable Standard column and a safe
  `_apply_command_pending()` implementation.

- [ ] **Step 1: Write widget/app red tests**

Add tests that mount `CommandGrid`, set each scope, and assert:

```python
# slug, Standard (N), Pi, Gemini, State, Source
assert headers[1].startswith("Standard (2)")  # global
# after set_scope("project"):
assert headers[1].startswith("Standard (3)")
assert not any(header.startswith("Claude") for header in headers)
```

Click the Standard header and assert a `ColumnInfoModal` contains its live
reader names and the project Devin-as-skill sentence. Exercise Space on the
Standard cell and assert pending key `("global", "standard", "demo")`.

Create an app-level Apply test that seeds a canonical/global lock, toggles the
Standard cell, calls `action_apply()`, and asserts the standard destination and
lock `harnesses` field appear. Repeat unlink and assert both are removed. This
is the regression test for the currently missing `_apply_command_pending()`.

- [ ] **Step 2: Make `CommandGrid` follow its active scope**

Change `_harnesses()` to:

```python
return interactive_harnesses(self._scope, self._selection)
```

Have `set_scope()` clear pending and rebuild the table when mounted, matching
`McpGrid`. Rewrite the module, `CommandGrid`, and `_context_for()` docstrings
so they say Commands has a live Standard slot and document the Standard-first
column order; remove the obsolete “no convergence projection yet” claim. In
`_rebuild()`, call `standard_column_header("command", self._scope)`: assert its presence iff
`"standard"` is in the harness tuple, use it only for that first column, and
use `harness_label()` for Pi/Gemini. Existing generic
`_harness_for_column()`/`_column_key_for_index()` then naturally route the
Standard column to the new info registry; do not reintroduce a bespoke dead
branch.

Keep widths derived from `len(self._harnesses())`; update the source-width test
rather than hardcoding the old three-column count.

- [ ] **Step 3: Implement `TUIApp._apply_command_pending()`**

Add the method alongside the other `_apply_*_pending()` methods. It must:

1. read pending `(scope, harness, slug)` operations from `CommandGrid`;
2. group by `(scope, slug)` into add/remove token sets;
3. resolve `home = Path.home()` globally and this app's project root for
   project scope;
4. let `command_install.apply()` materialise and roll back a missing project
   canonical for add operations;
5. call `command_install.apply(InstallPlan(slug=slug, scope=scope,
   source=None, ref=None, add_agents=tuple(sorted(adds)),
   remove_agents=tuple(sorted(removes))))` once per group;
6. retain only failed groups in pending state, refresh the Command view/status,
   and show aggregate success/failure feedback in the same style as the other
   asset panes.

Do not hand-edit lock JSON in the app. The facade owns normalization, rollback,
and lock mutation. A project canonical/foreign-file exception must leave its
pending operations retryable and must not clear successful unrelated groups.

- [ ] **Step 4: Run all affected Textual tests**

Run:

```bash
uv run pytest -q \
  tests/test_tui/test_command_grid.py \
  tests/test_tui/test_command_app.py \
  tests/test_tui/test_command_apply.py \
  tests/test_tui/test_header_click_info.py \
  tests/test_tui/test_source_column_width.py
```

Expected: the grid rebuilds safely on scope change, header info works, and
applying Standard does not raise `AttributeError`.

- [ ] **Step 5: Commit U5 code**

```bash
git add src/agent_toolkit_tui/widgets/command_grid.py \
  src/agent_toolkit_tui/app.py \
  tests/test_tui/test_command_grid.py \
  tests/test_tui/test_command_app.py \
  tests/test_tui/test_command_apply.py \
  tests/test_tui/test_source_column_width.py \
  tests/test_tui/test_header_click_info.py
git commit -m "feat(tui): make command standard slot actionable" \
  -m "Device: $(hostname -s)"
```

### Task 6: Document the shipped contract

**Files:**
- Modify: `docs/asset-types/commands.md`
- Modify: `docs/agent-toolkit/cli.md`
- Modify: `docs/agent-toolkit/research/2026-07-28-command-standard-readers.md`

- [ ] **Step 1: Update the asset-type page**

Replace the Claude-only projection framing with a Standard row that says:

- global slot `~/.claude/commands/<slug>.md` serves Claude Code + Neovate;
- project slot `<project>/.claude/commands/<slug>.md` additionally reaches
  Devin as an imported skill;
- Pi/Gemini remain separate; Codex is explicit/global-only; and
- only verified readers are included (OpenCode/Kode remain excluded pending
  merged/deterministic upstream evidence).

Document `harnesses` as optional projection state, legacy v1 compatibility, and
mutation-only backfill. Do not claim Devin has an identical slash-command menu.

- [ ] **Step 2: Update CLI reference**

Change default Command targets to `standard,pi,gemini-cli`; add examples for
`--harnesses standard` and alias-normalizing `--harnesses claude-code`; document
maximal no-flag uninstall and Standard-first TUI presentation. State that
`command doctor` is read-only and reports tracked/missing Standard projections.

- [ ] **Step 3: Reconcile research outcome wording**

Leave citations and reader map intact, but add a short “Implemented by #482”
line only after the code lands. Do not weaken the rejected OpenCode/Kode
findings or turn research evidence into runtime source code.

- [ ] **Step 4: Validate documentation and commit**

Run:

```bash
git diff --check
rg -n "claude-code,pi,gemini-cli|no standard projection yet" \
  docs/asset-types/commands.md docs/agent-toolkit/cli.md \
  src/agent_toolkit_tui tests/test_tui
```

Expected: no stale Commands default or no-standard claim remains outside
historical #478 planning artifacts.

```bash
git add docs/asset-types/commands.md docs/agent-toolkit/cli.md \
  docs/agent-toolkit/research/2026-07-28-command-standard-readers.md
git commit -m "docs(commands): describe standard projection" \
  -m "Device: $(hostname -s)"
```

### Task 7: Verify the completed feature and capture evidence

**Files:**
- Create during implementation: `assets/verification/issue-482/README.md`
- Create during implementation: focused-command, full-suite, and TUI visual
  evidence files beneath `assets/verification/issue-482/`

- [ ] **Step 1: Run focused CLI tests**

```bash
uv run pytest -q \
  tests/test_cli/test_command_adapters \
  tests/test_cli/test_command_lock.py \
  tests/test_cli/test_command_install.py \
  tests/test_cli/test_command_standard_projection.py \
  tests/test_cli/test_command_cli_standard.py
```

Expected: all green.

- [ ] **Step 2: Run focused TUI tests**

```bash
uv run pytest -q \
  tests/test_tui/test_command_state.py \
  tests/test_tui/test_command_grid.py \
  tests/test_tui/test_command_app.py \
  tests/test_tui/test_command_apply.py \
  tests/test_tui/test_composition.py \
  tests/test_tui/test_standard_column_rule.py \
  tests/test_tui/test_column_info.py
```

Expected: all green.

- [ ] **Step 3: Run the project verification command**

```bash
uv run pytest -q
```

Expected: exit 0. Save the raw summaries and command lines under
`assets/verification/issue-482/`.

- [ ] **Step 4: Perform the R1 visual judgment**

Launch the Textual TUI against a temporary HOME with one seeded command, then
record a screenshot or textual capture showing both scopes:

1. `Standard (2)` first, followed by Pi and Gemini, at global scope;
2. `Standard (3)` first at project scope;
3. header info lists the correct readers and calls out Devin-as-skill; and
4. toggling Standard then Apply changes exactly the shared slot, not a second
   Claude projection.

Write the verdict in `assets/verification/issue-482/README.md`: “Standard is
first, the scope count is legible, the info copy distinguishes Devin, and one
slot is visibly actionable.”

- [ ] **Step 5: Commit verification evidence**

```bash
git add assets/verification/issue-482
git commit -m "test(commands): record standard projection verification" \
  -m "Device: $(hostname -s)"
```
