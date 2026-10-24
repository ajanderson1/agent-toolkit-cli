# Native Pi npm lifecycle

Approved by AJ in chat on 2026-10-24, including implementation, independent review,
local merge, commit/push and local installation. Implementation is inline; review
is delegated read-only. No live Pi package/settings migration is authorized.

## Intent

Pi settings and npm's installation records are authoritative. Toolkit must not
maintain a second npm catalogue whose stale registration keeps a removed package
visible. npm sources differ from Git-backed library assets; retain the latter's
source locks and lifecycle unchanged. Preserve local extension controls and other
asset kinds.

## Native facts and operations

- Inventory is the union of configured npm sources and relevant direct npm
  installations, keyed by native npm identity (scoped names retained, versions not
  part of row identity). Never list arbitrary transitive modules as installations.
- Keep per-scope declarations, installation paths/versions and effective selection
  distinct. No native footprint means no row, irrespective of old Toolkit locks.
- Read-only discovery must not install, execute extension code, mutate settings,
  run project-provided commands or change trust. Missing packages remain visible
  as configured/missing; unsupported native interfaces fail explicitly.
- Use one backend for CLI, TUI, Info and counts. Use installed Pi's resolver,
  offline with missing-source skip, rather than another independent matcher.
- `add npm:SOURCE` and npm `install` perform Pi's install/configure operation in
  explicit scope, default global like Pi. Git add/install keep existing semantics.
- Raw npm installation only supplies files. Show compatible direct packages as
  available; activation requires native configuration. Unsupported external roots
  require an explicit native installation, not implicit relocation/local aliases.
- Enable/disable changes only the package's `extensions` selection; retains its
  declaration, package files, version and skills/prompts/themes settings. Whole
  package off must remain off across new entrypoints. Partial selection is mixed;
  Space on mixed enables all. Enabling missing/scope-unavailable packages must
  report install required rather than fetch during a settings-only toggle.
- Global policy is independent from project policy. With a global declaration,
  project inherit/on/off uses native `autoload:false` deltas without creating a
  project installation. Reset removes only extension overrides, preserving other
  resource deltas. A separate project install/version replaces global normally;
  reset its extension filter without deleting its installation/declaration.
- Removal means actual installation/declaration removal in selected scope, not
  unregister. Observe postconditions; native `No matching package` alone is not
  proof of failure or success. Do not hide genuine installer errors. Other scopes
  and global fallback can legitimately keep a row enabled/visible.
- External installations require origin-specific explicit removal and confirmation;
  do not silently use Pi uninstall for a global npm-owned folder or expand scope.
- Checkbox and explicit enable/disable commands share exact target snapshots,
  selected-scope locking, reread/merge and effective-state validation. Conflicting
  concurrent changes fail visibly and remain pending. Refresh preserves these
  npm intents as well as local intents; Revert explicitly discards them.
- Mixed native arrays of strings and objects are valid. Preserve unrelated entry
  forms, unknown metadata, filters, file mode and symlinks. Never rewrite entire
  scope from an old in-memory snapshot.

## Compatibility and migration

Installation-capable add and destructive uninstall are breaking npm CLI changes.
Expose explicit enable/disable/reset controls. Require explicit confirmation for
physical removal (noninteractive callers pass --yes); warn about the changed
contract and bundled resource removal. Default npm scope is global, never inferred
from a Toolkit lock or TUI presentation settings. Keep Git behavior unchanged.

Ignore legacy npm lock records for state immediately. Supply an explicit dry-run
and apply migration which backs up the original lock before pruning npm records,
retaining all non-npm records. Never activate, download or delete package files
as part of migration or local binary installation. Registration-only records are
reported as retired, not automatically converted into Pi configuration.

## Verification and delivery

Tests must exercise actual Space / Apply / scope / refresh / fresh-app behavior,
not only Info or mocked success. Native oracle cases cover global/project inheritance,
explicit overrides, reset, independent project version, multiple/hidden/new
entrypoints, mixed strings/objects, preservation of bundled resources, direct
versus transitive installs, installed-without-reference and removed-without-lock,
missing or incompatible versions, busy locks, stale snapshots and failures.
Installation/removal subprocess tests use isolated homes and offline local npm
fixtures with lifecycle scripts/audit disabled. No extension code executes.

Run full pytest and strict docs; build wheel/sdist and verify exact payload.
Independent whole-branch review precedes merge; reproduce/fix important findings.
Recheck main before local merge and push, respect pre-push tests and exact-SHA CI.
Release Please owns versions. Local install may use an exact-commit verified
candidate (clearly labelled as such) unless a published release is authorized;
never hand-edit versions. Verify installed payload and installed native workflows,
retain previous verified wheel for rollback, and hash protected live Pi files.

## Implementation decisions

Use a small packaged Node ESM bridge to the installed native Pi package manager
for read-only resolution. Python owns typed state, settings transactions, native
CLI lifecycle delegation, and UI integration. Node/Pi are required only for native
npm controls, not for other asset kinds. No new Python runtime dependencies.
The bridge has an in-memory settings storage, skips missing sources and disables
legacy command discovery in favor of an explicitly supplied legacy root. No project
`npmCommand` executes during inventory. Native CLI install/remove retains Pi trust
checks. External root discovery uses a bounded system npm root query, never a
project-configured command; fixtures provide an isolated root override.
