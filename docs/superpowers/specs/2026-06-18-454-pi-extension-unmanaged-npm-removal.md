# Pi Extension Unmanaged npm Disambiguation Design

## Issue

GitHub: https://github.com/ajanderson1/agent-toolkit-cli/issues/454

## Problem

`agent-toolkit-cli pi-extension list` correctly reports npm Pi extensions that Pi loads from `settings.json`, including packages installed or hand-edited outside agent-toolkit. Today those rows are indistinguishable from npm packages managed through `agent-toolkit-cli pi-extension add npm:<package>`, so users try normal lifecycle commands and get confusing errors such as `not in the global library`.

The current managed npm model is valid: `pi-extension add npm:<package>` records toolkit ownership in the Pi extension lock, and `install` / `uninstall` manage Pi `settings.json` `packages[]`. The bug is that unmanaged npm rows discovered directly from Pi settings look managed. Agent-toolkit should keep showing them because they affect Pi runtime, but it must clearly label them as unmanaged and explain why toolkit will not remove them.

## Goals

- Keep `agent-toolkit-cli pi-extension add npm:<package>` as the supported managed npm flow.
- Clearly distinguish toolkit-managed npm entries from unmanaged npm entries in CLI and TUI.
- Keep unmanaged npm entries visible in inventory.
- Refuse toolkit removal/uninstall actions for unmanaged npm entries, because agent-toolkit did not create or own them.
- For CLI removal/uninstall attempts on unmanaged npm entries, print exact manual removal advice: which `settings.json` file contains the package and which `packages[]` string to remove.
- In TUI, show a warning explaining unmanaged npm entries cannot be removed by agent-toolkit and where they came from.
- Preserve source-backed Pi extension behavior.

## Non-goals

- Do not retire or reject `pi-extension add npm:<package>`.
- Do not delete unmanaged npm packages automatically.
- Do not scan `node_modules` or infer installed packages from package-manager caches.
- Do not change Pi's native loading behavior.
- Do not change loose local extension import semantics except where display copy references unmanaged status.

## Terminology

- **Library extension:** source-backed extension cloned into the agent-toolkit library and projected by symlink into Pi's extension directory. This aligns with skills, agents, instructions, and MCP wording: `add` creates library membership; `install` creates visibility/projection.
- **Managed npm extension:** npm package entry represented in an agent-toolkit Pi extension lock row, normally created by `agent-toolkit-cli pi-extension add npm:<package>`.
- **Unmanaged npm extension:** npm package entry found in Pi `settings.json` with no matching agent-toolkit ownership record.
- **Loaded:** Pi will load the extension in the relevant scope because the package spec is present in that scope's `packages[]`.

`store-owned` is implementation-era wording and should not appear in user-facing CLI or TUI copy. Prefer `library` / `Library` everywhere visible. Internal enum names may remain if changing them creates migration risk, but output boundaries should map them to `library`.

## Desired managed npm behavior

The existing managed flow stays valid:

```console
agent-toolkit-cli pi-extension add npm:@tifan/pi-recap
agent-toolkit-cli pi-extension install -g @tifan/pi-recap
agent-toolkit-cli pi-extension uninstall -g @tifan/pi-recap
agent-toolkit-cli pi-extension remove @tifan/pi-recap
```

`add npm:<package>` records the npm package in the global Pi extension lock. `install -g|-p <slug>` adds the managed package spec to the selected Pi `settings.json` `packages[]`. `uninstall -g|-p <slug>` removes the managed package spec from selected scope. `remove <slug>` removes the managed global lock row.

## Desired unmanaged npm behavior

If an npm package appears only in Pi settings, agent-toolkit treats it as observed but not owned.

CLI list/status should make this explicit:

```text
pi-title-renamer  ✔  ☐  npm unmanaged  npm:pi-title-renamer
pi-messenger      ✔  ☐  npm managed    npm:pi-messenger
clear-alias       ✔  ☐  library        ajanderson1/clear-alias
```

JSON output should include machine-readable managed state and settings metadata:

```json
{
  "slug": "pi-title-renamer",
  "origin": "npm",
  "managed": false,
  "source": "npm:pi-title-renamer",
  "globalLoaded": true,
  "projectLoaded": false,
  "globalPackageSpec": "npm:pi-title-renamer",
  "globalConfigPath": "/Users/ajanderson/.pi/agent/settings.json"
}
```

If backwards compatibility requires keeping `origin: "store-owned"` internally or in JSON for source-backed rows, add a preferred display field such as `originLabel: "library"`. Visible table/status/TUI copy must use `library`.

## Removal guidance

Unmanaged npm removal attempts should refuse to mutate and explain why.

Example for `remove`:

```console
$ agent-toolkit-cli pi-extension remove pi-title-renamer
Error: pi-title-renamer is not managed by agent-toolkit.
Found unmanaged npm package in /Users/ajanderson/.pi/agent/settings.json.
agent-toolkit-cli will not remove packages it did not add.
To remove it manually, remove "npm:pi-title-renamer" from packages[].
```

Example for scoped `uninstall`:

```console
$ agent-toolkit-cli pi-extension uninstall -g pi-title-renamer
Error: pi-title-renamer is an unmanaged npm package in Pi settings.
agent-toolkit-cli will not remove packages it did not add.
To remove it manually, edit /Users/ajanderson/.pi/agent/settings.json and remove "npm:pi-title-renamer" from packages[].
```

Project-scope advice should name `<project>/.pi/settings.json` when the package is found there. `remove` has no scope flag, so it should check project settings first when the current directory is a project with Pi settings, then check global settings.

## Desired TUI behavior

The Pi Extensions grid should show unmanaged npm entries, but they must be visibly not owned by agent-toolkit.

Required behavior:

- Origin/copy distinguishes `npm managed` from `npm unmanaged`.
- Unmanaged npm rows cannot be toggled with space, or any attempted toggle shows a warning without queuing a pending change.
- Cell info for unmanaged npm says agent-toolkit cannot remove it because it did not add/manage it.
- Cell info gives the relevant settings path and package string:
  - global scope: `~/.pi/agent/settings.json`, remove package string from `packages[]`;
  - project scope: `<project>/.pi/settings.json`, remove package string from `packages[]`.
- Managed npm rows remain toggleable and keep current pending/apply behavior.

## Acceptance criteria

1. `agent-toolkit-cli pi-extension add npm:<package>` remains supported and continues creating a managed npm lock row.
2. CLI inventory distinguishes npm managed from npm unmanaged in both table/status output and JSON.
3. CLI JSON includes `managed` plus package spec/config path fields for npm rows discovered from settings.
4. CLI table/status output renders source-backed rows as `library` / `Library`, not `store-owned`.
5. `remove <slug>` for an unmanaged npm package refuses to mutate config and prints why agent-toolkit cannot remove it, the settings file path, and exact package string to remove from `packages[]`.
6. `uninstall -g|-p <slug>` for an unmanaged npm package refuses to mutate config and prints why agent-toolkit cannot remove it, the settings file path, and exact package string to remove from `packages[]`.
7. TUI shows unmanaged npm entries as non-interactive/non-toggleable or warns without queuing a pending change.
8. TUI unmanaged npm info explains why agent-toolkit cannot remove the package and gives path/spec manual removal advice.
9. TUI managed npm rows remain interactive and keep current pending/apply behavior.
10. Tests cover managed npm still working, unmanaged npm refusal, CLI list/status display, JSON managed flag, no user-facing `store-owned` leakage in visible copy, and TUI unmanaged npm copy/toggle blocking.

## Classification

Size: M

Reasoning: this changes CLI/TUI behavior and inventory metadata but does not retire a supported command or introduce a new asset kind. Critical review is still useful because it touches user-facing lifecycle semantics across CLI and TUI.

## Test surface

- CLI unit tests:
  - `tests/test_cli/test_pi_extension_add.py` for preserving `add npm:<package>` behavior.
  - `tests/test_cli/test_pi_extension_ops.py` for unmanaged refusal and managed uninstall still working.
  - `tests/test_cli/test_pi_extension_inventory.py` for managed flag and config paths.
  - `tests/test_cli/test_cli_pi_extension_list.py` and/or `tests/test_cli/test_pi_extension_list_table.py` for visible managed/unmanaged output.
- TUI tests:
  - `tests/test_tui/test_pi_grid.py` for non-interactive unmanaged npm rows and info text with exact removal advice.
  - `tests/test_tui/test_pi_apply_roundtrip.py` for managed npm pending/apply behavior.
- Regression command:
  - `uv run pytest tests/test_cli/test_pi_extension_add.py tests/test_cli/test_pi_extension_ops.py tests/test_cli/test_pi_extension_inventory.py tests/test_cli/test_cli_pi_extension_list.py tests/test_cli/test_pi_extension_list_table.py tests/test_tui/test_pi_grid.py tests/test_tui/test_pi_apply_roundtrip.py -q`

## Out of scope

- Automatically editing unmanaged npm entries.
- Retiring the managed npm lock-row model.
- Scanning package caches.
- Changing Pi native loading behavior.
- TUI layout redesign beyond required labels, warning, disabled state, and info copy.

## Open questions resolved

- `pi-extension add npm:<package>` remains the correct way to make an npm Pi extension toolkit-managed.
- Unmanaged npm packages remain allowed because Pi supports native package entries outside agent-toolkit.
- Agent-toolkit should surface unmanaged npm packages rather than hide them.
- Agent-toolkit should not remove unmanaged npm packages; it should explain why and show exact manual removal instructions.
