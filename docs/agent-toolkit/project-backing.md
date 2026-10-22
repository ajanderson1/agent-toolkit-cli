# Project backing

New project installations of skills, agents and commands use the same central
library backing as global installations. Project locks still record source/ref
and projection state. Removing a project's projection does not remove backing
used by another project. Pi extensions retain their existing central behavior;
instructions and MCP retain their own native mechanisms.

CLI and TUI use the same installation engines. Behavior configuration is a small
JSON object at `~/.agent-toolkit/config.json` (not the TUI presentation settings):

```json
{
  "projectBacking": "central",
  "allowIsolatedProjects": false
}
```

These are the defaults when the file is absent. To deliberately create legacy
private backing, **both** select `"isolated"` and set
`"allowIsolatedProjects": true`. Selecting isolated while it is disabled refuses
new creation, including source-driven engine and collection/TUI paths. Existing
recorded private installations remain private and usable without enabling new
creation. Detaching a private skill keeps its existing project provenance,
including TUI detach after removal from library membership. Status reports no
active target after detach; re-registration and reinstall reuse unique private
work even with new isolation disabled. Creating
isolated agent/command copies from linked-worktree/gitfile backing is refused
before writes, rather than copying a pointer to shared Git metadata. Legitimate
central linked worktrees remain usable. Old copied gitfiles whose native Git
backlink identifies another worktree are refused before mutation, preserving
both trees for explicit recovery. A missing old backing directory is not silently reinterpreted as a
central install. Agent private directories now use `projects/<id>/agents/`, not
the historical shared skills directory; recorded legacy agent paths are retained.

A failed first materialization/install removes newly claimed backing and partial
new target files/links, not foreign slots or existing dirty backing. Cleanup
checks filesystem identity before deleting claimed nodes; replaced nodes are
preserved and incomplete cleanup is reported. This is scoped failure cleanup,
not a general transaction or automatic adoption of old unrecorded backing.

## Agent source refresh and reset

Fresh agent acquisitions are staged before publication. Refreshes fetch a
prospective commit without exposing its checkout, validate recorded entries for
all known agents sharing that parent, and only then fast-forward or explicitly
reset to that exact commit. Entry symlinks, escaping/dangling/cyclic resource
symlinks and unproven submodule resources are refused. Internal repository
resource symlinks remain supported. Unrecorded canonical aliases sharing a
parent block refresh rather than guessing their selection; restore their
registration before advancing that backing. These checks cover add, import,
update, reset and the legacy source-driven installation helper.

`agents reset -p` selects the recorded project backing, not the library clone.
A private clone or legitimate linked worktree uses its own HEAD/index. Missing
private backing, aliases to another checkout, redirected Git working trees and
copied gitfiles pointing at another worktree are refused. A branch checked out
in multiple worktrees also blocks mutation, even with `--force`. There is no
fallback to resetting central or another worktree.

## Explicit migration

For one existing project installation:

```bash
agent-toolkit-cli skills install my-skill -p --migrate-to-central
agent-toolkit-cli agents install my-agent -p --harnesses pi --migrate-to-central
agent-toolkit-cli commands install my-command -p --harnesses pi --migrate-to-central
```

Targets/context are validated before migration. The requested single-asset
projection refresh runs inside migration's narrow rollback boundary: a failure
restores the prior scope lock, owned projection slots and sidecars. Agent
migrating installs support simple file/directory targets (`pi`/`standard`); use
a separate install for translated/registry targets after successful migration.

Migration reports old/new backing paths, requires matching project/library
source, ref and content paths, clean Git checkouts with matching origins and
commits, identical resources, and provably matching destinations. Dirty,
divergent, foreign, ambiguous or malformed state is refused. It does not merge
or discard unique work. External private backing is left in place. A legacy
real in-tree skill checkout is renamed intact to `<slug>.pre-central` (refused
if occupied) before replacing its slot with a central link. Preserve these
checkouts until recovery is no longer needed.

The operation is intentionally conservative: translated/customized legacy
projections which cannot be proved identical require manual inspection and
restoration/detachment before migration. There is no force bypass. Keep lock
and link backups for cutover recovery. Do not run global library removal while
consumers depend on that library entry; project uninstall is the detach operation.

## Source identity

Generic Git/Gitea standalone sources retain their complete clone URL, including
scheme, host, port and `.git`, in exported locks. Monorepo sources retain the
complete `parentUrl` plus source-relative resource path and ref. Gitea
`/src/branch/<ref>/<path>`, `/src/tag/…` and `/src/commit/…` URLs are supported;
use `--ref` for refs containing slashes. Parent-cache reuse verifies origin
identity rather than choosing another host with the same owner/repository name.
Malformed/unknown-version locks are refused, never treated as empty for overwrite.
