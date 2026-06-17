# Pi-extension project/global install guard

Issue: https://github.com/ajanderson1/agent-toolkit-cli/issues/449

## Problem statement

Pi extensions can currently be installed at project scope even when the same extension is already installed globally. Pi then has two effective load paths for one extension slug: the global Pi extension location and the project Pi extension location. The CLI and TUI should not let users create that duplicate loaded state.

This applies to both pi-extension origins:

- `store-owned` entries, where install creates a managed symlink into Pi's extension discovery directory.
- `npm` entries, where install writes a package spec into Pi `settings.json` packages for the selected scope.

## Acceptance criteria

1. `agent-toolkit-cli pi-extension install <slug> -p` fails when `<slug>` is already globally loaded.
2. The CLI guard covers both store-owned and npm pi-extension entries.
3. The TUI cannot queue or apply a project-scope install for a row that is already globally loaded.
4. The TUI still shows the global-loaded indicator in project scope and explains why project install is unavailable.
5. Project-scope uninstall still works for a project-loaded extension, even if global is also loaded.
6. Global install/uninstall behavior remains unchanged.
7. Project install succeeds after the global loaded state is removed.
8. Tests cover CLI/shared-ops behavior and TUI behavior for the guard.

## Classification

Size: M.

Reasoning: the change spans shared CLI/TUI install logic, TUI interaction state, and tests. No `L` risk signal applies: no new asset kind, dependency, schema/migration, auth/secrets, top-level directory, or strategy change.

## Design

Use the shared pi-extension operation layer as the source of truth. `src/agent_toolkit_cli/pi_extension_ops.py` already sits between the Click command and TUI apply path, so the invariant belongs there rather than only in one surface.

Add a project-install guard before the origin-specific install branch:

- If requested scope is not `project`, do nothing.
- If the slug is not globally loaded, do nothing.
- If the slug is globally loaded, raise `pi_extension_install.InstallError` with a clear message such as: `<slug>: already installed at global scope; uninstall globally before installing at project scope`.

The global-loaded predicate must cover both origins:

- Store-owned: the global Pi extension discovery path exists as the managed symlink for this slug.
- Npm: the global Pi settings package list already contains the global lock entry's package identity.

Keep existing uninstall behavior. Project uninstall should remain possible so a user can clean up old duplicate state. Global uninstall should not touch project state.

## CLI behavior

The Click command already catches `InstallError`, so the shared guard should naturally produce a non-zero CLI exit for project installs while leaving other operations unchanged.

Expected command behavior:

```text
agent-toolkit-cli pi-extension install demo -p
Error: demo: already installed at global scope; uninstall globally before installing at project scope
```

## TUI behavior

`PiGrid` already knows `row.global_cell.global_loaded` and renders a global indicator in project scope. Extend project-scope interaction so a global-loaded row cannot queue a project install.

When user focuses a project-scope unloaded cell for a globally loaded row:

- Cell still displays unloaded plus global indicator.
- Info/help text says project install is unavailable because the extension is already global.
- Pressing space should not enqueue a `link` pending op.
- If a stale queued project `link` somehow reaches apply, shared `pi_extension_ops.install` still rejects it.

## Test plan

- CLI/shared ops:
  - store-owned global install followed by project install fails.
  - npm global install followed by project install fails.
  - project install after global uninstall succeeds.
  - project uninstall remains allowed when both scopes are already loaded.
- TUI grid:
  - project-scope global-loaded row does not enqueue `link` on toggle.
  - project-scope info text explains blocked install.
- TUI/app:
  - stale project `link` pending op for global-loaded row fails through shared guard and surfaces apply error.

## Out of scope

- Changing Pi's extension loading semantics.
- Deleting or auto-migrating existing duplicate project installs.
- Changing `pi-extension add`, `remove`, `update`, `reset`, or `doctor` behavior beyond any wording needed to explain this guard.
- Changing non-pi-extension asset types.
