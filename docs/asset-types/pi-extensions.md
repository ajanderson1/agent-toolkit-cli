# Pi extensions

This kind manages **Pi** extensions only; it does not classify other harnesses' plugin systems. Inventory includes Git-backed library packages, npm registrations and unmanaged local extensions/packages.

## Storage and loading

- Git-backed library: `~/.agent-toolkit/pi-extensions/<slug>`; source/ref/observed commit metadata in `pi-extensions-lock.json`.
- Store-owned projection: `~/.pi/agent/extensions/<slug>` globally or `<project>/.pi/extensions/<slug>` in a project. Both scopes link to the global library copy, unlike the separate project skill backing store.
- npm registrations use Pi settings/package handling rather than the store-owned symlink path.
- Loose extensions and local filesystem packages declared in settings remain observable even when untracked. A visible row is not necessarily managed or toggleable.

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

Store-owned installation refuses foreign links or regular destination files; uninstall removes only the matching owned projection. Doctor reports orphaned `extensions[]` overrides but does not edit that settings array. Local-package `--repair` import requires explicit confirmation and records the original path without copying or rewriting package source/settings. Registry packages and settings values that cannot be represented losslessly remain report-only. `--no-fix` is read-only.

[Pi harness](../harnesses/pi.md) · [Locks](../agent-toolkit/lock-files.md) · [TUI](../agent-toolkit/tui.md)
