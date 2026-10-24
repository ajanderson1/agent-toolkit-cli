# Pi extensions

This kind manages **Pi** extensions only. Inventory combines Git-backed library
extensions, native npm packages, loose extensions and declared filesystem packages.
Configuration selection is not a report of code loaded in a running Pi session.

## Native npm packages

**Pi settings and npm installation metadata are authoritative. There is no
Toolkit npm registration or installation lock.** Relevant direct installations
and configured npm sources form the inventory; transitive dependencies and caches
do not create package rows. Package identity retains scoped names but excludes
version suffixes. Info and JSON inventory distinguish requested source, selected
installation/version, separate scope-local copies and project inheritance.

| Operation | npm behavior |
|---|---|
| `add npm:SOURCE` / `install npm:SOURCE` | Delegate installation/configuration to Pi, default global; `-p` selects the consumer project. Existing native filters are preserved. |
| `enable ID` / `disable ID` | Change only native extension filters; retain declaration, files, source/version and bundled resource policies. No downloads. |
| `reset-selection ID -p` | Remove extension-specific project overrides; inherit global policy when using a global package. An owned project declaration/install is retained. |
| `remove ID` / `uninstall ID` | Remove the selected installation/declaration; ask for confirmation (`--yes` for automation). Other scopes or global fallback can remain. |

This is a **breaking npm CLI change**: add is no longer catalogue-only and
uninstall is no longer a settings-only disable. Use `disable` to retain files.
Git library add/install/uninstall/remove retain their existing meanings.

```bash
agent-toolkit-cli pi-extensions add npm:@scope/package@1.2.3
agent-toolkit-cli pi-extensions add npm:@scope/package@1.2.3 -p
agent-toolkit-cli pi-extensions disable @scope/package -p
agent-toolkit-cli pi-extensions enable @scope/package -p
agent-toolkit-cli pi-extensions reset-selection @scope/package -p
agent-toolkit-cli pi-extensions list --json
agent-toolkit-cli pi-extensions remove npm:@scope/package -p --yes
```

Global policy applies to projects that inherit it. A project may explicitly enable
or disable extensions regardless of global selection, using native `autoload:false`
package deltas without downloading a duplicate. A normal project package declaration
instead replaces that global package and can select another version. Native install
preserves existing filters, including delta mode: downloading a project copy does
not silently replace an existing inheritance policy. Info distinguishes an unused
scope-local copy from the installation Pi actually selects.

A checkbox is checked when all package extensions are selected, empty when none
are, and **◐** when mixed. Space on mixed enables all. Package-wide off also covers
new and hidden entrypoints after updates. **R → Ctrl+S** resets this scope's extension
filter. Available, missing/repair-needed and ambiguous declarations are distinct
from enabled state. Duplicate declarations are reported; resolve them in Pi settings
before bulk changes. Project resources still require Pi trust, which Toolkit does
not grant.

Raw `npm install` supplies files, not Pi configuration. Compatible direct installs
appear as available, unchecked. Enabling previously unconfigured files activates
extensions only, leaving bundled skills/prompts/themes off. Unsupported locations
require explicit native installation; Toolkit does not relocate files or invent
local-path aliases. External global discovery uses the system npm command, never a
command from project settings. Custom installer roots can be supplied explicitly
with `AGENT_TOOLKIT_NPM_GLOBAL_ROOT`; physical removal refuses unsupported installer
layouts instead of guessing a prefix.

Externally installed global packages require `remove --external` and confirmation.
Toolkit uses their actual npm prefix rather than claiming `pi uninstall` removed
external files. Whole-package removal can affect bundled skills, prompts and themes.
Global removal leaves project declarations/overrides intact; an orphaned native
project declaration can cause Pi to install a project copy later. Inspect remaining
project state rather than assuming removal means disabled everywhere. Pi's misleading
“No matching package” is accepted only when its known no-reference case and observed
removal postconditions agree; genuine installer errors remain errors.

Native npm controls require Node.js and an installed Pi SDK (verified against
Pi **1.4.0**, whose Node requirement is **>=22.19.0**). Nonstandard SDK installations
can use `AGENT_TOOLKIT_PI_PACKAGE`. Native npm state and operations honor
`PI_CODING_AGENT_DIR`; project settings stay at `<consumer>/.pi/settings.json`.
Inventory is offline and never imports extension code or installs missing packages.
Use Pi's package update commands, not Toolkit Git update, for npm updates.

### Retiring old npm records

Legacy npm entries in Toolkit locks are ignored immediately. A package with no
native configuration or direct installation disappears without an unregister step.
Nothing is automatically downloaded, enabled, deleted or migrated during upgrade.

```bash
agent-toolkit-cli pi-extensions migrate-npm-records           # dry-run
agent-toolkit-cli pi-extensions migrate-npm-records --apply   # back up, then prune npm records
```

Use `-p` for a project lock. Non-npm entries and unknown metadata are preserved.
Old npm lock imports are skipped rather than recreating the retired catalogue.
Bundles install npm members once in the selected scope and roll back only their
new scoped installation. Preexisting native installations/declarations are retained;
conflicts or repair needs require explicit handling outside the bundle.

## Git-backed library extensions

- Canonical source: `~/.agent-toolkit/pi-extensions/<slug>`; source/ref/observed commit
  metadata remains in `pi-extensions-lock.json`.
- Global projection: `~/.pi/agent/extensions/<slug>`; project projection:
  `<project>/.pi/extensions/<slug>`. Both link to the global library source.
- Connections are shown as **Linked**, counted separately from native enablement.

```bash
agent-toolkit-cli pi-extensions add owner/repo@main --slug my-extension
agent-toolkit-cli pi-extensions install my-extension -p
agent-toolkit-cli pi-extensions doctor -p --no-fix
agent-toolkit-cli pi-extensions uninstall my-extension -p
```

Git refs belong in SOURCE, not `--ref`. Git add/remove/import operate on the global
library; install/uninstall default project. Git lifecycle read/update verbs retain
their existing lock-based scope selection. Add accepts repository-root sources only;
subdirectories are rejected. An orphan checkout is registered only if its origin
matches the requested source; missing/mismatched origins leave the checkout intact.
Install refuses foreign links/files. Uninstall removes only the matching projection;
remove retains its dirty-source guard.

## Loose files and filesystem packages

Loose extensions in conventional Pi extension directories are enabled by native
discovery unless `extensions[]` selectors exclude them. Project selection includes
global inheritance. **Space → Ctrl+S** writes exact native selectors without
registration, file changes or projections. Mixed manifest directories show **◐**;
Space enables all current entrypoints. Discovery follows native manifest/index,
ignore and duplicate rules; `package.json` alone does not make a directory loadable.

Declared local filesystem packages remain read-only, separate from loose controls.
Package-selected resources do not gain duplicate loose controls. Apply rejects a
new package overlap without losing the queued loose intent. Removing a reference
keeps files; deleting a file/directory is permanent; unlinking a symlink keeps its
target. Never delete a shared parent checkout to remove one child.

## Safety and verification

Native npm and loose-local drafts survive refresh/scope switches with their original
target snapshots; **Ctrl+Z** discards them. Failed changes stay pending; successful
ones clear individually. Settings writes use Pi-compatible locking, reread under
lock, merge unrelated entries and preserve symlinks/modes. Changed source/version,
entrypoints or settings pointers refuse stale Apply. Global/project settings that
alias one file cannot support independent scoped changes and are refused.

Doctor does not register discovered local assets or rewrite their settings/source,
even with `--repair`; unrelated Git repairs and `--no-fix` behavior are unchanged.

Run the installed-wheel checks against disposable assets:

```bash
uv run python scripts/verify_pi_npm_controls.py --pi-package /path/to/pi-coding-agent
uv run python scripts/verify_pi_local_controls.py --pi-package /path/to/pi-coding-agent
```

These drive actual controls and compare native resolution without executing
extensions or changing live settings. Restart an already-open Toolkit TUI after
upgrading its binary; configuration changes do not unload running Pi sessions.

[Pi harness](../harnesses/pi.md) · [Locks](../agent-toolkit/lock-files.md) · [TUI](../agent-toolkit/tui.md)
