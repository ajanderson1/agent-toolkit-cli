# Pi extensions

This kind manages **Pi** extensions only; it does not classify other harnesses' plugin systems. Inventory includes Git-backed library packages, npm registrations and local extensions/packages.

## Storage and loading

- Git-backed library: `~/.agent-toolkit/pi-extensions/<slug>`; source/ref/observed commit metadata in `pi-extensions-lock.json`.
- Library projection: `~/.pi/agent/extensions/<slug>` globally or `<project>/.pi/extensions/<slug>` in a project. Both scopes link to the global library copy; new project skills also use central backing.
- npm registrations use Pi settings/package handling rather than a library symlink. Toolkit-registered enable/disable adds/removes the settings reference, not package files. Updates use Pi package handling, not Toolkit Git update. References Toolkit did not register cannot be toggled; Info explains native Pi removal and the exact manual settings edit. A registered npm row does not prove package files are downloaded. Info shows global and project enablement separately: Yes means a reference in that scope’s `settings.json`, not running-session status.
- Loose extensions in Pi’s conventional global/project extension directories are labeled `local` and enabled by default, unless native `extensions[]` selectors exclude them. Project state includes inherited global resources. **Space → Ctrl+S** enables/disables these resources through settings only: exact `+path`/`-path` selectors; a project override also names an inherited file by its absolute path. No registration, source-file changes, projections or Toolkit lock are required.
- A directory can resolve several manifest entrypoints. Its checkbox is checked when all are enabled, empty when none are, and **◐** when mixed. Space on a mixed row queues Enable for every entrypoint; Info lists them. Merely viewing a mixed row changes nothing. Discovery follows Pi’s manifest/index, ignore and duplicate-resource rules; `package.json` alone does not make a directory loadable.
- Local filesystem packages declared through `packages[]` remain a separate, read-only surface; they are not converted to loose extensions. Package-selected resources do not gain duplicate loose controls. If a package starts selecting an already-queued loose resource, Apply refuses the loose change without rewriting settings or losing the intent. In a row spanning both scopes, a package-controlled cell stays read-only while the other scope may retain loose controls. Info gives exact paths and manual removal guidance. Deleting a file/directory is permanent; unlinking a symlink keeps its target; removing a package reference keeps its files. Never delete a shared parent checkout to remove one child.

Library symlink states are shown as **Linked**, not settings enablement, and counted separately. The TUI uses **Enable/Disable** for controls, including pending actions, rather than Install/Uninstall. Space queues the selected scope’s change; Ctrl+S applies it. Disabling keeps downloaded files. To remove an npm package with native Pi, use `pi uninstall npm:<package>` globally, or `pi uninstall npm:<package> -l` from the project directory. Pi removes its package and settings reference, but does not remove Toolkit registration; the row may remain visible. Info uses the recorded package spec, including any version. These actions do not change an already-running Pi session.

## Use

```bash
agent-toolkit-cli pi-extensions add owner/repo@main --slug my-extension
agent-toolkit-cli pi-extensions install my-extension -p
agent-toolkit-cli pi-extensions list -p --json
agent-toolkit-cli pi-extensions doctor -p --no-fix
agent-toolkit-cli pi-extensions uninstall my-extension -p
```

Add takes a ref as part of SOURCE, **not `--ref`**. Add/remove/import operate on the global library. Install/uninstall default project; list/status/update/push/reset/doctor infer project from `pi-extensions-lock.json`, otherwise global. Git-backed update merges; push uses a PR by default; reset requires explicit slugs. Registry-backed entries do not acquire Git ownership just because these verbs exist. [Exact CLI surface](../agent-toolkit/cli.md#pi-extensions).

Git-backed add accepts repository-root sources only. Subdirectory sources such as `https://github.com/obra/superpowers/tree/main/.pi/extensions` are rejected rather than silently projecting the repository root. A root URL with `/tree/REF` remains supported.

If a checkout already exists but its lock entry is missing, add registers it only when its `origin` matches the requested repository (equivalent SSH/HTTPS URLs are accepted). A missing or mismatched origin produces an error without deleting or changing the checkout. Existing matching registrations remain idempotent. Registration makes the extension visible in CLI/TUI inventory; activation still requires a separate install.

## Safety

Local toggles preserve unrelated settings, source files and Toolkit locks. Apply refuses invalid settings, busy native settings locks, or entrypoints that changed since queueing. Failed intents stay pending; successful ones clear. Refresh preserves queued loose-local Pi intents and their original targets; **Ctrl+Z** discards them. Settings writes are serialized with native Pi and reread under the lock. Explicit plain resource references are retained so disabling a selected symlink alias does not activate a different alias. A failed refresh keeps the grid aligned with the visible scope.

Library installation refuses foreign links or regular destination files; uninstall removes only the matching owned projection. Doctor reports orphaned `extensions[]` overrides but does not edit that settings array. Local discovery remains report-only even with `--repair`: doctor does not register local packages or rewrite their settings/source. Ordinary source registration, lock-file import and unrelated repairs remain supported. Registry packages and settings values that cannot be represented losslessly remain report-only. `--no-fix` is read-only.

To recheck native compatibility from a source checkout, run
`uv run python scripts/verify_pi_local_controls.py --pi-package /path/to/pi-coding-agent`.
It drives real keys against disposable assets, compares both scopes with the
installed Pi resolver, and checks native settings-lock contention. It never
loads extension code or changes your live configuration.

[Pi harness](../harnesses/pi.md) · [Locks](../agent-toolkit/lock-files.md) · [TUI](../agent-toolkit/tui.md)
