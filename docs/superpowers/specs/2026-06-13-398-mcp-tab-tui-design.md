# Spec — #398 feat(tui): add an MCP tab to the asset-types sidebar

**Issue:** [#398](https://github.com/ajanderson1/agent-toolkit-cli/issues/398)
**Tier:** standard
**Date:** 2026-06-13
**Depends on:** [#399](https://github.com/ajanderson1/agent-toolkit-cli/issues/399) (MCP `standard` projection) — **hard blocker.** `/aj-run 398` MUST NOT start until #399 is merged to `main`. This spec is written assuming #399 has landed.

---

## 1. Problem

The TUI (`agent-toolkit-tui`) has a sidebar with one tab per asset type: `instruction`, `skill`, `pi-extension`, `agent` (`AssetType` literal, `app.py:46`). The **MCP** kind shipped CLI-first in #329 (v4.0.0) and is fully usable from the command line, but it has **no tab in the TUI** — MCP servers can't be browsed or managed visually the way every other asset type can.

This is the planned TUI follow-up to #329, the same staged path every other kind took (`instruction` tab → #319, `agent` tab → #361). #398 brings the TUI to parity with the CLI for MCP by parity-porting the **agent** tab.

## 2. Goal

A new `mcp` sidebar tab with full interactive parity to the agent tab: an `McpGrid` showing one row per library MCP with per-harness projection columns, a `State` and `Source` column, and working `^s` Apply / `^d` Diff / `^r` Refresh / `^z` Revert / `/` Filter / `^g` scope-toggle. The grid reuses the existing CLI projection/lock machinery (`mcp_install`, `mcp_lock`, `mcp_standard` from #399, the MCP adapters) — **no parallel reader**.

## 3. The #399 assumption (read first)

#399 promotes the shared project `.mcp.json`/`mcpServers` file to a first-class **`standard`** projection. The pieces #398 consumes, all added by #399 (confirmed absent on `main` today):

- `agent_toolkit_cli/mcp_standard.py` — `STANDARD_MCP_READERS: dict[str, frozenset[str]] = {"project": frozenset({"claude-code", "pi"})}` and `mcp_standard_covered(scope) -> frozenset[str]` (**`KeyError` on unknown scope — fail loud; there is NO `"global"` key**).
- `"standard"` as a new **value** of `McpLockEntry.harness` (no schema migration).
- MCP `parse_harness_tokens` / `normalize_harness_tokens` that, at **project scope only**, normalize `claude-code` and `pi` to `standard`.
- `mcp_lock.collapse_covered(lock, slug, covered)` — drops covered legacy rows when a `standard` row is written.

### 3.1 The load-bearing asymmetry (do not blind-copy from the agent grid)

The agent grid's `agents_standard_covered("global")` **returns a set** because `STANDARD_AGENT_READERS` has a `"global"` key (`agent_adapters/standard.py:25-28`). **MCP's `STANDARD_MCP_READERS` has ONLY a `"project"` key** — so `mcp_standard_covered("global")` **raises `KeyError`**. Any code that calls it at global scope MUST guard the `KeyError` and treat the global covered set as **empty**. This is the same scope-dependent invariant flagged as load-bearing in #399's critical review; #398 inherits it at the composition + column-build seams.

## 4. Architecture — five touchpoints

A parity-port of the agent tab. Units, all mirroring an existing agent-tab counterpart:

| # | Unit | File | Role |
|---|---|---|---|
| 1 | `AssetType` literal + label | `src/agent_toolkit_tui/app.py:46,48-53` | add `"mcp"` and `"MCP"` label |
| 2 | sidebar Option + grid swap + refresh + apply | `src/agent_toolkit_tui/app.py` | add `mcp` Option after `agent` (no separator); `McpGrid` in `compose()`; `_show_asset_type` elif; `_refresh_mcp_view`; `_apply_mcp_pending` |
| 3 | `McpGrid` widget | `src/agent_toolkit_tui/widgets/mcp_grid.py` (new) | DataTable grid, structural copy of `widgets/agent_grid.py` |
| 4 | `build_mcp_rows` + `McpRow`/`McpCell` + `mcp_interactive_harnesses(scope)` (a per-scope **function**, not a frozen constant — see §5.1) | `src/agent_toolkit_tui/mcp_state.py` (new) | row-builder over union(library **directory**, scope lock) + filesystem probe |
| 5 | `mcp_nonstandard_main(scope)` | `src/agent_toolkit_tui/composition.py` | covered-set-aware column helper (KeyError-guarded at global) |

Plus two registry touches in `column_info.py`: (1) its generic `_standard_info` factory already reads `asset_type`/`names`/`extra_lines`/`global_linked` from context, but its title ternary (`column_info.py:69`) only special-cases `agents` — add an `mcps` branch so the modal title reads `Standard projection (.mcp.json)` instead of the wrong `Standard bundle`; (2) the 🌐 global marker stays off for `mcps` (MCP standard is project-only) — the `show_marker` set at `column_info.py:51` is left as `("skills", "agents")`, **not** extended to `mcps`.

## 5. Column set (scope-dependent)

Columns = `("standard",) + mcp_nonstandard_main(scope)` mirroring `agent_grid` / `agent_state.INTERACTIVE_HARNESSES`:

- **Project scope:** `MCP ⓘ | Standard ⓘ | codex ⓘ | opencode ⓘ | State | Source` — `claude-code` and `pi` fold into Standard because `mcp_standard_covered("project") = {claude-code, pi}`.
- **Global scope:** `MCP ⓘ | claude-code ⓘ | codex ⓘ | opencode ⓘ | pi ⓘ | State | Source` — **no Standard column**: at global, `mcp_standard_covered` raises `KeyError`, the covered set is empty, so all four concrete harnesses get their own column.

Layout is the agent-grid layout: `[0]=slug, [1..N]=harness-columns, [N+1]=state, [N+2]=source` (`agent_grid.py:3-5`).

### 5.1 `mcp_nonstandard_main(scope)` (composition.py)

```python
def mcp_nonstandard_main(scope: str) -> tuple[str, ...]:
    """Main harnesses that need their own MCP column at `scope`:
    the four real MCP harnesses minus those covered by the standard
    project .mcp.json projection (#399). Global has no standard, so all
    four render their own column."""
    try:
        covered = mcp_standard_covered(scope)   # raises KeyError at global
    except KeyError:
        covered = frozenset()
    return tuple(h for h in _MCP_HARNESSES if h not in covered)
```

where `_MCP_HARNESSES = ("claude-code", "codex", "opencode", "pi")` (the `commands/mcp/_common.py:30` `_HARNESSES` set, in canonical render order). The coverage invariant — every `_MCP_HARNESSES` member is either standard-covered or has its own column, for every scope — is test-guarded (mirrors `test_tui/test_composition.py` for agents).

> **Note — DataTable rebuild on scope toggle.** Because the column *set* differs by scope (Standard appears only at project), `McpGrid` must rebuild columns on scope change. **This is a genuine divergence from the agent grid, not a copy:** `agents_nonstandard_main` returns the *same* tuple at both scopes, so `AgentGrid.set_scope` does NOT rebuild columns (`agent_grid.py:102-104` only sets `_scope` + clears pending). MCP's column set genuinely changes, so the rebuild must ride `set_rows` → `_rebuild` (which reads the harness tuple fresh each render), and `McpGrid.set_scope` additionally rebuilds when mounted (defensive). The harness tuple is produced by the per-scope **function** `mcp_interactive_harnesses(scope)` — it is NOT a frozen module constant. (The agent grid freezes a `("standard",) + agents_nonstandard_main("global")` module constant at `agent_state.py:37` precisely because its set is scope-invariant; MCP must NOT freeze one.)

## 6. Rows, cells, state

`mcp_state.py`:

```python
State = Literal["installed", "library", "unlisted"]

@dataclass(frozen=True)
class McpCell:
    linked: bool

@dataclass
class McpRow:
    slug: str
    source: str            # install_method: npx | uvx | docker | url | local
    pin: str | None
    state: State = "installed"
    cells: dict[tuple[str, str], McpCell] = field(default_factory=dict)  # (harness, scope) -> cell
```

- **State set** mirrors the agent grid (`installed` / `library` / `unlisted`) — MCP has no git-working-tree states (no `dirty`/`drifted`/`stray` like skill: MCP entries are config-injection, not symlinks/working copies). `_STATE_MARKUP` copied verbatim from `agent_grid.py:44-48`.
- **Row universe** = union(library **directory**, scope lock) + filesystem probe. **Critical MCP difference (review F1):** the MCP library is a **directory** (`~/.agent-toolkit/mcps/<slug>/config.json`), NOT a lock — `mcp add` writes the directory and never touches `mcps-lock.json`. So the library half of the universe comes from `mcp_library.list_library(library_root(home))` (the directory scan — what `mcp list` uses, `list_cmd.py:86`), NOT from reading the global lock. Reading the lock as the library would silently drop every never-installed library MCP, defeating the `library` state.
  - `installed` — in the library directory AND in the scope lock.
  - `library` — in the library directory, not in the scope lock.
  - `unlisted` — in the scope lock, not in the library directory (warning state).
  - **Source/pin** come from the **library asset** (`load_mcp_asset(library, slug).install_method/.resolved_version`) for library/installed rows; `unlisted` rows (no library asset) fall back to the lock entry's `source`/`pin`.
- **Cell** — `linked=True` iff the named entry exists on disk for that `(harness, scope)`:
  - For concrete harness cells: probe the harness's config target (`.mcp.json`/`mcpServers`, `~/.claude.json`, `opencode.json`/`mcp`, `config.toml`) via the existing MCP adapter `is_installed(slug, *, scope, home, project)` read.
  - For the **standard** cell (project scope): `linked=True` iff `<project>/.mcp.json` has `mcpServers.<slug>` (the `mcp_standard` adapter's read).
  - `_cell_for` returns `None` when the adapter is unreachable. **Note (review F6):** the real MCP adapters raise `InstallError` (not `ValueError`) for an unreachable target — `get_adapter` raises `UnsupportedMcpHarnessError` (an `InstallError`) for an unknown harness, the standard adapter raises `InstallError` for a global target. `_cell_for` catches `(InstallError, ValueError)`, and `home` is typed `Path` (not `Path | None`): the adapter contract is `home: Path` and the TUI always supplies `Path.home()`. Do NOT carry the agent grid's `home: Path | None` / `ValueError`-only shape.

## 7. Standard cell — interactive + column info

- **Toggleable.** The Standard cell toggles like any harness column (parity with the agent grid, whose Standard column IS a real installable destination — `agent_grid.py:8-12`). Queueing it adds `(scope, "standard", slug) -> "link"/"unlink"` to pending. On apply, a `standard` link calls `mcp_install.apply(..., harnesses=["standard"], scope="project")`, which (via #399) writes one `mcpServers.<slug>` entry and `collapse_covered`s any legacy claude-code/pi rows.
- **Header affordance (review F9).** The Standard column header shows the covered count — `Standard (2) ⓘ` — so the project↔global fold is legible without pressing `i` (the column "vanishing" into Standard at project scope reads as intentional, not a glitch).
- **Column info (`i` on the Standard column)** opens the registry-backed `ColumnInfoModal` via `get_column_info("standard", context=...)` (`agent_grid.py:31,154-217`). Context: `{"asset_type": "mcps", "names": sorted(mcp_standard_covered("project")), "extra_lines": [<toggle-consequence lines>], "global_linked": False}`.
  - `asset_type="mcps"` → the body copy adapts ("Covered by the standard convention for mcps (2): …") AND the title gets an `mcps` branch (review F5) reading `Standard projection (.mcp.json)` (without it the title falls through to the wrong `Standard bundle`).
  - **`extra_lines` populated (review F9):** spell out the toggle consequence — "Toggling this cell installs into all 2 at once (one shared .mcp.json entry). Project scope only — at global scope these are separate columns." (Unlike agents' devin note, which is a coverage caveat; MCP's is a fold explanation.)
  - **No `global_linked` / 🌐 marker** — MCP standard is project-only; `column_info.py:51` `show_marker` is NOT extended to `mcps`.
  - `_column_key_for_index` returns `"standard"` only when the column maps to the standard harness; `_context_for` builds the dict above (mirrors `agent_grid.py:300-343`, minus the global_linked lookup).
- **`pin` surfaced (review F8):** `pin` is not a column. The slug-cell info screen (`i` on the slug column) shows `MCP <slug> / Source: <source> / Pin: <pin or "—"> / State: <state>` (substituting `pin` for the agent grid's `ref`), so a pinned MCP's locked version is visible somewhere in the TUI.

## 8. Apply path

`_apply_mcp_pending` (mirrors `_apply_agent_pending`):

1. Read `grid.pending_entries()` → keys `(scope, harness, slug)`.
2. Group by `(scope, slug)` into adds (`"link"`) and removes (`"unlink"`) harness sets.
3. For each group: `mcp_install.apply(slug=…, harnesses=adds, scope=…, …)` then `mcp_install.uninstall(slug=…, harnesses=removes, scope=…, …)` (signatures at `mcp_install.py:101,188`).
4. Refresh the grid + status bar; surface `ApplyResult` skipped/collisions the same way the agent path does.

Pending key shape `(scope, harness, slug)` matches `_scope_tag`'s `key[0]==scope` assumption (`app.py:56-60`), so the "(N global, M project)" footer tag works unchanged.

## 9. Keybindings

All bindings are app-level and already fire app-wide (`app.py` `BINDINGS`, priority bindings past the filter Input): `^s` Apply, `^d` Diff, `^r` Refresh, `^z` Revert, `/` Filter, `^g` scope toggle. `McpGrid` copies the grid-level `BINDINGS` (`space` toggle, `a` all/none, `i` info) verbatim from `agent_grid.py:72-75`. `^g` rebuilds columns on toggle (per §5.1). No new app-level binding is added.

## 10. Out of scope

- #399 itself (the standard projection) — separate issue, the dependency.
- Codex/OpenCode standard folding — they stay explicit per-harness cells at all scopes (#399 leaves them unaffected).
- A global `~/.mcp.json` standard — dropped in #399 (zero readers); the MCP grid has no Standard column at global scope as a direct consequence.
- Any change to the MCP CLI behavior — #398 is a TUI-only consumer of existing facades.

## 11. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Blind-copying the agent grid's `agents_standard_covered("global")` (returns a set) breaks on MCP (raises `KeyError`). | §3.1 + §5.1: `mcp_nonstandard_main` explicitly `try/except KeyError`; a global-scope test asserts no Standard column and no exception. |
| Freezing `INTERACTIVE_MCP_HARNESSES` as a module constant (agent does this at `agent_state.py:37`) would bake in one scope's column set. | §5.1 note: derive per-scope; `_rebuild` recomputes on scope toggle. |
| #399 not yet merged → `mcp_standard` import fails. | Hard-blocker note in issue body; `/aj-run` re-validates and will see it. Spec/plan are written but execution is gated. |
| Standard cell toggle double-writes (claude-code+pi+standard) — the data-integrity bug #399's review caught. | #399's `collapse_covered` is invoked inside `mcp_install.apply()` — #398 calls the facade, inheriting the fix. **Auto-tested (review F3):** a Task 0 behavioral gate exercises the real `apply()` collapse, and a Task 8 integration test (real facade, no monkeypatch) asserts one `standard` lock row + the `.mcp.json` entry — the collapse is no longer QA-only. |
| Library universe sourced from the lock instead of the directory → never-installed library MCPs vanish (review F1). | `build_mcp_rows` reads `list_library(library_root(home))` (directory scan, as `mcp list` does), NOT the lock; source/pin come from `load_mcp_asset`. A Task-4 test seeds an actual library entry (config.json, no lock) and asserts the `library` state. |

## 12. Test surface (summary; full detail in the plan)

- **Unit (TUI):** `tests/test_tui/test_mcp_state.py` (row universe, cell linked-probe, state classification), `tests/test_tui/test_composition.py` additions (`mcp_nonstandard_main` project vs global, KeyError guard, coverage invariant), `tests/test_tui/test_mcp_grid.py` (column set per scope, Standard toggle queues pending, column-info context, scope-toggle rebuild).
- **App-level:** sidebar shows `mcp`; selecting swaps to `McpGrid`; `_apply_mcp_pending` groups + calls the facade (facade monkeypatched).
- **QA playbook (Stage 3):** launch the TUI on a scratch project, select MCP, toggle Standard on a library MCP, `^s`, confirm `.mcp.json` gains `mcpServers.<slug>` + one `standard` lock row (no duplicate claude-code/pi rows); `^g` to global, confirm four flat columns + no Standard; visual judgment on the grid render.
