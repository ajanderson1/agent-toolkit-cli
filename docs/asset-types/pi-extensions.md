# Pi extensions

This kind manages **Pi** extensions only; it does not classify other harnesses' plugin systems. Inventory includes Git-backed library packages, npm registrations and local extensions/packages.

## Storage and loading

- Git-backed library: `~/.agent-toolkit/pi-extensions/<slug>`; source/ref/observed commit metadata in `pi-extensions-lock.json`.
- Library projection: `~/.pi/agent/extensions/<slug>` globally or `<project>/.pi/extensions/<slug>` in a project. Both scopes link to the global library copy; new project skills also use central backing.
- npm registrations use Pi settings/package handling rather than a library symlink. Toolkit-registered enable/disable adds/removes the settings reference, not package files. Updates use Pi package handling, not Toolkit Git update. References Toolkit did not register cannot be toggled; Info explains native Pi removal and the exact manual settings edit. A registered npm row does not prove package files are downloaded. Info shows global and project enablement separately: Yes means a reference in that scope’s `settings.json`, not running-session status.
- Loose extensions and local filesystem packages declared in settings are labeled `local` in the TUI and remain usable in place. A loose file is enabled in the TUI only when that scope’s `settings.json` explicitly selects it in `extensions[]`; discovering it in an extensions folder is not enablement. Local packages use their `packages[]` reference. They have no TUI enable/disable or deletion action. Info shows the actual path and manual removal instructions: deleting a file/directory is permanent, unlinking a symlink keeps its target, and removing a local package reference from `packages[]` keeps the package files. Never delete a shared parent checkout to remove one child.

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

Library installation refuses foreign links or regular destination files; uninstall removes only the matching owned projection. Doctor reports orphaned `extensions[]` overrides but does not edit that settings array. Local discovery remains report-only even with `--repair`: doctor does not register local packages or rewrite their settings/source. Ordinary source registration, lock-file import and unrelated repairs remain supported. Registry packages and settings values that cannot be represented losslessly remain report-only. `--no-fix` is read-only.

[Pi harness](../harnesses/pi.md) · [Locks](../agent-toolkit/lock-files.md) · [TUI](../agent-toolkit/tui.md)
