---
title: Pi extension unmanaged npm rows must be read-only
date: 2026-06-18
category: docs/solutions/logic-errors
module: pi-extension lifecycle
problem_type: logic_error
component: tooling
symptoms:
  - Unmanaged npm packages discovered from Pi settings looked like toolkit-managed rows
  - Users could try remove or uninstall on packages agent-toolkit did not add
  - Lifecycle errors did not explain which settings.json entry to edit manually
root_cause: logic_error
resolution_type: code_fix
severity: medium
tags: [pi-extension, npm, settings-json, lifecycle, tui]
---

# Pi extension unmanaged npm rows must be read-only

## Problem

Pi extensions can come from the agent-toolkit lockfile, loose local extension files, or Pi `settings.json` `packages[]`. npm packages found only in Pi settings are visible runtime state, but agent-toolkit does not own them; treating them like managed npm rows makes `remove` and `uninstall` misleading and potentially unsafe.

## Symptoms

- `agent-toolkit-cli pi-extension list` showed npm rows without enough ownership state to distinguish managed from unmanaged packages.
- `pi-extension remove <slug>` on an unmanaged npm package fell through to a generic `not in the global library` error.
- `pi-extension uninstall -g|-p <slug>` could attempt normal lifecycle handling instead of refusing with manual-removal advice.
- TUI npm rows were all toggleable, even when the package was only observed in Pi settings and not backed by a toolkit lock row.

## What Didn't Work

- Hiding unmanaged npm rows would avoid lifecycle confusion, but it would also hide Pi runtime state that affects the user.
- Automatically editing unmanaged `packages[]` entries would be unsafe because agent-toolkit cannot know whether another workflow or manual edit owns that package.
- Reusing the internal `store-owned` terminology in visible output made inventory harder to understand; users need `library`, `npm managed`, and `npm unmanaged` labels.

## Solution

Make ownership explicit in the shared inventory model, then route CLI and TUI behavior through that model.

`InventoryRecord` now carries managed state plus package/config metadata for npm rows:

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

Lock-backed rows are managed. npm rows discovered only from `settings.json` remain unmanaged but record the exact package spec and settings path.

The shared operation layer exposes unmanaged-removal advice before normal uninstall planning:

```python
def unmanaged_npm_advice(..., action: Literal["remove", "uninstall"]) -> str | None:
    path = _pi_settings.settings_path(scope=scope, home=home, project=project)
    for spec in _pi_settings.read_packages(scope=scope, home=home, project=project):
        if spec.startswith("npm:") and _pi_settings.npm_identity(spec) == _pi_settings.npm_identity(slug):
            return (
                f"{slug} is an unmanaged npm package in Pi settings.\n"
                "agent-toolkit-cli will not remove packages it did not add.\n"
                f"To remove it manually, edit {path} and remove \"{spec}\" from packages[]."
            )
    return None
```

CLI `remove` checks project settings first, then global settings, before falling back to `not in the global library`. CLI list/status maps visible origins to `library`, `npm managed`, or `npm unmanaged`, while JSON includes compatibility fields plus `managed`, package spec, and config path metadata.

TUI rows carry the same metadata. Managed npm rows remain toggleable; unmanaged npm rows are labeled `npm unmanaged`, refuse toggles, and show manual-removal advice in the info screen.

## Why This Works

Ownership and observed runtime state are different facts. The inventory can still show every Pi extension that affects runtime, while lifecycle commands only mutate entries agent-toolkit owns. Storing the exact `settings.json` path and package string makes refusal actionable instead of vague.

The fix also preserves the supported managed npm flow:

```bash
agent-toolkit-cli pi-extension add npm:pi-title-renamer
agent-toolkit-cli pi-extension install -g pi-title-renamer
agent-toolkit-cli pi-extension uninstall -g pi-title-renamer
agent-toolkit-cli pi-extension remove pi-title-renamer
```

That flow remains lock-backed and managed. Only npm packages discovered directly from Pi settings without a matching lock row become read-only advice rows.

## Prevention

- Treat inventory rows as a union of owned state and observed runtime state; lifecycle code must check ownership before mutating.
- Put ownership metadata in shared state (`InventoryRecord` / TUI row), not only in display code, so CLI and TUI cannot diverge.
- User-facing origin labels should describe behavior: `library`, `npm managed`, `npm unmanaged`, `untracked`.
- Tests should cover both managed and unmanaged npm rows across JSON output, table/status output, CLI lifecycle refusal, and TUI toggle blocking.

## Related Issues

- GitHub issue #454: `bug(pi-extension): cannot remove unmanaged npm package`
