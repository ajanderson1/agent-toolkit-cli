# Shared asset catalogue

One optional Git subscription supplies skills, agents, commands and Pi extensions.
The repository contains `catalog.json`, not asset payloads or enabled-state records.
There is no `.well-known` HTTP endpoint. Catalogue membership is not library
membership, harness support or proof that code is loaded in a running session.

## Browse and acquire

```bash
agent-toolkit-cli catalog subscribe ssh://git@example-tailnet/org/catalog.git --ref main
agent-toolkit-cli catalog list --json
agent-toolkit-cli catalog list --kind agents
agent-toolkit-cli agents catalog list
agent-toolkit-cli commands catalog list
agent-toolkit-cli pi-extensions catalog list
```

The subscription is user-global, shared across projects and these four kinds.
It retains the historical `skillCatalog` key in `~/.agent-toolkit/config.json`.
`skills catalog subscribe` / `unsubscribe` affect this same shared subscription;
`skills catalog list` remains skills-only. No subscription means no catalogue
network calls. Invalid/unavailable subscribed catalogues produce a warning in
ordinary inventory and an error in explicit catalogue listing.

For Git assets, Add obtains global library backing without enabling it. Enable
obtains missing backing and enables only the explicit scope and harness targets:

```bash
agent-toolkit-cli agents catalog add reviewer
agent-toolkit-cli agents catalog enable reviewer --scope project --harnesses pi
agent-toolkit-cli commands catalog enable summarize --scope project --harnesses standard
agent-toolkit-cli pi-extensions catalog enable git-tools --scope project
```

The new exposure commands require `--scope`; agents/commands also require
`--harnesses`. Existing lifecycle verbs/defaults are unchanged. A complete-directory
agent supports Pi only; a command projects its prompt, not adjacent resources;
Git Pi extensions currently require repository-root sources.

Exact existing source/path/ref/agent-entry matches reuse recorded backing and local
work without updating it. Name collisions, ambiguous copies and changed selectors
refuse acquisition, not overwrite/adopt. A failed projection can leave successfully
acquired library content; inspect the error and retry only the intended targets.
Catalogue source changes never retarget existing acquisitions. Inspect kind-specific
`status` and `doctor`; back up local work and disable affected consumers before
explicitly removing/re-adding content with a new selector. There is no automatic
source migration or npm version replacement.

### Native Pi npm packages

Catalogue npm entries are metadata, not Toolkit registrations. Install explicitly:

```bash
agent-toolkit-cli pi-extensions catalog install native-tools --scope project
# Automation must explicitly confirm side effects:
agent-toolkit-cli pi-extensions catalog install native-tools --scope project --yes
```

Installation delegates to native Pi, can execute package lifecycle scripts and may
activate bundled resources. Confirmation is required. Native filters, inheritance,
settings locking and project trust still apply; Toolkit does not grant trust.
Conflicting installed/requested versions or ambiguous declarations require native
maintenance. Catalogue Add/Enable does not install npm packages, and no Toolkit npm
lock is created. Use ordinary native enable/disable controls after installation.

Git Pi catalogue actions validate regular entrypoints and safe declared paths before
registration and on reuse, without executing extension code. A rejected fresh
checkout can remain unregistered for inspection; validation does not discard
preexisting edits or commits.

## TUI and updates

The existing four grids share one fresh catalogue read per refresh generation.
Tab rendering does not fetch assets, npm metadata or another copy of the catalogue.
Git catalogue-only rows are labelled `catalog`, not acquired/enabled. Space queues
acquisition/exposure; Apply revalidates the original subscription and selected
identities once for the whole batch. Revert acquires nothing. Changed sources
remain pending with refresh/reselect guidance; independent successful changes clear.
Npm catalogue-only rows are read-only and their Info panel gives the explicit
installation command. Installed native npm rows keep their normal controls.

Failed refresh hides catalogue-only rows across all four kinds with a warning;
local assets stay usable. There is no stale-listing fallback. Unsubscribing or
removing a catalogue entry never deletes library content or disables exposure.
For example, delisting an agent already enabled in Pi leaves that agent in the
library and enabled in Pi: the catalogue is not a remote removal switch.

```bash
agent-toolkit-cli agents check reviewer -g --json
agent-toolkit-cli commands check summarize -g
agent-toolkit-cli pi-extensions check git-tools -g
agent-toolkit-cli catalog unsubscribe
```

These new checks apply to catalogue-associated Git backings and compare their
recorded selector, even after unsubscription. Results are timestamped, and a
changed local revision/identity makes them stale. Different repository revisions
are not proof that one child changed or that an update can safely merge. Git pins
remain pinned. Native npm uses Pi package updates, not Git checks. Skills retain
their existing check behavior, including directly added Git skills.

Info shows source/provenance, actual backing/scope, local revision and check time.
Checks/updates remain CLI-only; neither TUI refresh nor doctor acquires or updates
assets. Existing per-kind update and private/shared-backing limitations still apply.

## Manifest format

New catalogues use version 2, supported by the official **7.0.1** release. The
existing small version-1 skills parser remains accepted, but older Toolkit clients
cannot consume version 2. The version string
alone is not proof that a particular build contains this feature.

```json
{
  "version": 2,
  "entries": [
    {
      "kind": "agent",
      "key": "reviewer",
      "description": "Review supplied code changes",
      "sourceType": "git",
      "source": "example/agents",
      "path": "agents/reviewer",
      "entryFile": "reviewer.md",
      "ref": "FULL_REVIEWED_COMMIT_SHA"
    },
    {
      "kind": "pi-extension",
      "key": "native-tools",
      "description": "Native Pi tools",
      "sourceType": "npm",
      "source": "npm:@example/tools@1.2.3"
    }
  ]
}
```

Replace illustrative coordinates before use. Kinds are `skill`, `agent`, `command`,
`pi-extension`. Keys are unique within each kind: lowercase kebab-case, at most 64
characters. Descriptions are nonempty, at most 1024 characters. Duplicate selectors
within one kind are refused. Git sources select a repository only: use separate
safe relative `path` and optional sanitized `ref`; `.` means repository root.
Agents require `entryFile`: `<key>.md` or `AGENTS.md`. A competing flat file refuses
a declared directory-agent shape. Only Pi extensions support `sourceType: npm`;
use an exact package version, no Git path/ref, credentials or custom npm alias.
The catalogue selects one version per native npm package identity; alternate-version
listings for the same package are refused rather than competing for one native row.

## Admission: inspect before publishing

Consumer `catalog add KEY` means adding an already-published asset to a local
library. Adding an entry to the **shared catalogue** is a separate curator workflow:

1. Inspect the exact upstream content, packaging, resources and prerequisites.
2. Evaluate content quality for its stated task and representative behavior in the
   claimed disposable harness/scope. Inspect security, dependencies and licensing.
   Do not execute upstream code on production machines merely to publish metadata.
3. Pin Git listings to the full inspected commit; pin npm to an exact version and
   record archive integrity. Record reviewer, date, evidence, tested targets and
   limitations under `reviews/<kind>/<key>.json` beside the catalogue.
4. Run admission validation before accepting/publishing new or changed selectors.

```bash
# Syntax only; explicitly does NOT certify source fit or content quality:
agent-toolkit-cli catalog validate catalog.json
# Every entry requires review if no previously accepted base is supplied:
agent-toolkit-cli catalog validate catalog.json --admission
# Compare with a saved, previously accepted manifest:
agent-toolkit-cli catalog validate catalog.json --admission --base previous-catalog.json
```

A review is version 1 with `selector` equal to the normalized entry JSON excluding
`description`; `revision` is the inspected full Git commit or npm version. For npm,
include `integrity` as the inspected archive's `sha512-...`. Required fields also
include `reviewer`, `reviewedAt` (`YYYY-MM-DD`), `targets` (an array of objects with
`harness` and `scope`), `limitations` (an array of strings), and `checks` containing
`fit`, `quality`, `functional`, `security`, `license`. Each check requires
`{"passed": true, "evidence": "concrete inspection/test findings"}`. Do not mark
unperformed checks passed. `--reviews DIR` overrides the evidence directory.

Admission verifies evidence exists and matches the selector, then checks actual
upstream packaging and revision. Git is inspected without checkout; npm uses
`npm pack --ignore-scripts` and reads, but never extracts/executes, the archive.
Npm inspection requires npm and registry access. These checks do **not** automate
or prove the reviewer's quality judgement. They do not continuously certify future
upstream changes. The accepted base is a curator trust boundary, not a way to
claim previously unperformed reviews. A changed selected source/version/path/shape
requires a new review; a description-only edit or delisting does not acquire or
reinspect unrelated assets. Browsing never invokes admission inspection.
