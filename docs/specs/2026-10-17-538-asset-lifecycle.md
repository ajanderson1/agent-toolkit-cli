Issue: #538

# Clear asset discovery, management, enablement and removal

Status: proposed implementation contract, not a description of shipped behavior.
Owner: AJ; preparation requested 2026-10-17. Applies to CLI, TUI and doctor across
all six supported asset types, retaining their real capability differences.

## 1. Outcome and evidence

Toolkit must show all relevant content within declared discovery boundaries and
let humans and coding agents safely control its complete lifecycle. Users should
not need to understand locks, aliases, parent caches or an ambiguous “library” to
answer: what is this, where are its copies, which agents can use it, what changed,
and what will my action actually remove?

Observed in Herdr panes w3E:p3/p4 during preparation:

1. Removing global `skills-workflow` left the project's separate checkout and
   source records intact, plus a remaining global `aj-bootstrap` child record.
2. Eleven children appeared in one collection. `aj-bootstrap` was marked dirty
   because Git status covered the shared checkout, although edits were in `aj-pm`.
   Other children displayed `unlisted`, suppressing their Git-state dimension.
3. `skills uninstall aj-pm -p` removed its project exposure and lock record,
   preserving the store alias and modified checkout content as intended.
4. Refresh displayed twelve skills: ten collection children plus `aj-pm` and
   `skills-workflow:aj-pm`, two aliases of the same remaining payload. Both lost
   known collection/source context and appeared untracked.
5. The CLI printed `uninstalled aj-pm for None`; TUI “Diff” previews only link
   operations, not content edits. The user expected coherent end-to-end control.

Discovery and preservation are intentional. Duplicate identities, lost provenance,
misleading changes, inconsistent action names and non-actionable retained content
are the failures. Reproduce with disposable fixtures, not the live installation.

Related groundwork: #515 discovery/adoption, #529 collection exposure/recovery.
Open PR #537 already repairs narrower project Save/doctor behavior and was observed
at head `2735b298d88d78ada7afb498d55c7a4c82ca7c3e`. Before implementation begins,
require that PR merged into the fetched base; re-read its final changes rather than
reimplementing or reverting its preservation guarantees. Preparation base is
`5a1bd4285a552b0ef8e82c135789862db9bfeb28`.

## 2. Product decisions and alternatives

Approved decisions:

- Keep comprehensive bounded discovery, including disabled and unmanaged content.
- Exactly two scopes: Global and Project. Profile/company is harness context, not
  another generic scope. Inventory is the product's view, not a third scope.
- Remove “library membership” from normal user-facing status and navigation.
- Separate identity, physical copies, management, exposure, changes and health.
- Enable/disable is canonical vocabulary; old behavior stays available through
  compatibility aliases. Adding a source does not enable it.
- Add sources directly in either supported scope, without a global prerequisite.
- All discovered items are inspectable; every actionable item offers management
  through the same operation layer used by CLI and doctor.
- Preserve local work; safe refusal is preferable to misleading success.
- Concise root `GLOSSARY.md` is the canonical core vocabulary, usable by people
  and agents. Published docs reuse it, preserving old inbound glossary anchors.

Alternatives rejected:

1. Hide disabled/orphaned content: neat display but violates comprehensive control.
2. Auto-register everything on scan: changes authority/intent during observation,
   can promote third-party configuration and unexpectedly enable future operations.
3. Keep lock-first rows plus independent discovery rows: minimal patch but repeats
   the alias/count/source-loss bug and divergent doctor interpretations.

Chosen: observational reconciliation into one typed inventory, then explicit
planned actions with ownership checks. No background watcher, daemon, new database,
new runtime dependency, new asset type or full-disk crawler is required.

### Scope split: local-content viewer is a separate issue

At AJ's explicit request, [issue #540](https://github.com/ajanderson1/agent-toolkit-cli/issues/540)
owns the View local changes action, content-diff rendering, CLI diff commands and
viewer-specific tests/docs. None is a deliverable or prerequisite of #538. This
issue retains asset-scoped change indicators and path/status observations, checkout
warnings, publication checks and all deletion/refusal safeguards. Its Preview
changes action displays proposed Toolkit operations, not content patches. Deletion
safety must work without a built-in content viewer; report exact paths/reasons and
external Git/manual inspection guidance where necessary.

## 3. Glossary and user-facing state

Use [GLOSSARY.md](../../GLOSSARY.md) for definitions. “Library” remains permissible
inside legacy file names/APIs and compatibility help, never as a third scope.
“Clean” means no observed local changes, NOT “matches global” or “safe to delete.”

Primary TUI facts:

| Surface | Meaning |
|---|---|
| Identity / collection | Human name plus proven source/ref context |
| Harness cells | Explicit exposure at the selected scope; not all effective availability |
| Management | Managed / Discovered; not publishing or deletion authority |
| Changes | Modified / Clean / No Git / Unknown, scoped to this asset |
| Health | Problems such as missing content, conflict, broken link, incomplete inspection |
| Info: copies | Global, This project, or external location; real separate copies listed |
| Info: source | Recorded / inferred / unknown, with evidence and ref/HEAD distinction |
| Info: effective availability | Local and global routes plus evidenced loader behavior |

Health problems take visual priority but never erase the other facts. A modified,
discovered and broken asset can express all three conditions. No single mutually
exclusive `State` enum may be the authoritative inventory model. Compact layouts
may combine badges, but Info and JSON retain every dimension.

“Project only” and “In library” are retired as unexplained primary statuses. Prefer
“Project copy exists; no global copy” or “Enabled here; also available globally.”
A project-managed asset absent from global records is healthy if its own content
and exposure are healthy. Doctor must not recommend global registration as repair.

## 4. Inventory, identity and provenance contract

### 4.1 Reconciliation order and identity

Per-kind readers return observations, not display rows. Reconcile recorded source
metadata, content roots, aliases, ownership sidecars, pointers, config entries and
interrupted-operation records before producing CLI/TUI/doctor output.

A local asset-instance key includes asset type, scope/context, physical payload
identity and asset-relative entrypoint. Resolved payload identity distinguishes
Git worktrees even when they share a common Git directory; repo URL/ref/HEAD or
matching bytes alone cannot identify a physical copy. For config-backed assets,
use the actual scope/context, config resource and entry key plus normalized source
identity. Paths are normalized safely without following cycles or treating a
failed resolution as equality. Resource aliases are evidence, not extra rows.

- Store `aj-pm` alias and checkout `skills-workflow/aj-pm` resolving to one payload
  become one inventory instance. Stable selection survives scan order and refresh.
- Same slug/source in separate global/project clones remains separate copies.
- Same source/ref/path in different physical clones in one scope is a visible
  copy/identity conflict. Show qualified locations; never silently choose one.
- Same content used by multiple harness links stays one instance with several
  exposures. Standard shared paths count once as resources, not once per reader.
- Missing recorded payloads remain visible logical instances with missing health;
  do not invent a physical target. Alias conflicts and missing identity are
  diagnosed explicitly, not assigned guessed ownership.
- Groups derive from proven source/ref and checkout relationships. Disabling,
  unmanaging or losing one lock entry cannot erase independently proven source or
  collection context. Inferred identity is labelled and cannot authorize writes.
- Rootless repository wrappers are storage/exposure containers, not real skills.
  Genuine root SKILL.md remains a real asset. Unknown nested isolation remains a
  refusal before writes, preserving #529/#537 exposure safety.

Source confidence and management authority are independent. Git origin can support
“inferred source”; it does not prove which installer owns a projection or grant
permission to overwrite/deploy/publish/delete it.

### 4.2 Local metadata, portable records and actual truth

Keep portable per-kind source locks, actual Instructions pointers, MCP definition
authority and per-scope projection records with their existing distinct meanings.
Never replace them with one universal lock. Instructions remains installation-lock
free. Actual paths/configuration establish exposure, not remembered checkbox bits.

Add a versioned **local inventory manifest** solely for provenance, stable instance
IDs, adopted external-root references and operation recovery ownership. Global:
`<state>/inventory.json`; project: `<state>/projects/<existing-project-id>/inventory.json`.
`<state>` means `Path.home()/.agent-toolkit`, with explicit injected home in tests.
It is not the Skills root override: `AGENT_TOOLKIT_SKILLS_ROOT` remains Skills-only.
The per-kind routing table below defines storage without relocating other kinds.
No machine-specific absolute paths are written into portable project locks.

Manifest v1 top-level fields: `schema: atk-local-inventory/v1`, `revision`,
`instances`, `storage_units`, `operations`. Each storage unit records its ID, kind,
physical locator/identity, verified creation receipt or reference-only classification,
member instance IDs and current/historical ownership evidence. Each instance stores `instance_id`, `asset_type`,
`scope`, `context`, `payload_locator`, `entrypoint`, `aliases`, `source_evidence`,
`management`, `ownership_evidence`. Each operation stores its ID, affected
instance/resource IDs, expected-before values, completed steps and recovery state.
Do not store credentials, entire config contents, executable discovery hooks or
persisted parent-selection/effective-availability flags. Unknown fields survive
round trips. Unsupported newer schemas and corruption are visible read-only
failures, never empty success or grounds to overwrite the file.

A management action records identity/provenance even when no exposure is active;
disable does not remove those management records. Scanning alone never writes or
migrates this manifest. If an older installation has no manifest, reconstruct the
same visible inventory from locks/paths; persist only on an explicit action.
A manifest entry is not proof of extant files, ongoing ownership or deletion
safety. Validate against actual resources on every mutation. A stale locator
remains an actionable finding; do not silently retarget it to a similar clone.
Unmanage removes its management authority but may retain minimum non-authoritative
source evidence needed to explain surviving content. This is not a hide/tombstone
list. Deleting stale observation records cannot hide a discoverable payload.

All writers use the serialized protocol in §9.1 in addition to fresh
read/compare/merge and atomic replacement; atomic rename alone is not concurrency
control. Revalidate affected records/resources immediately before mutation.
Preserve unrelated record bytes/unknown fields where serializers promise this.
An operation ID ties a preview to its expected state, not blanket permission for
later changed resources. Recovery never restores an old complete manifest or lock
snapshot. Safe interrupted-step decisions require persisted before/after evidence.

### 4.3 Scope and scan coverage

Default inventory examines active project/context, current user's global records,
Toolkit backing stores (including referenced legacy locations), supported harness
slots and explicitly configured additional roots. Enumerate other project stores
as locators for reference/deletion safety; do not recursively load every project's
content in the current project's grid. Present other known copies in Info and
refuse deletion if complete reference coverage cannot be established.

Every scan reports inspected roots, skipped/excluded roots, permission/errors,
unsupported configurations and completeness. UI shows a warning when incomplete;
JSON reports coverage. A clean verdict cannot conceal unreadable roots or invalid
records. No indiscriminate home crawl, dependency/cache recursion, hidden network
fetch, package import, service start or executable plugin loading during discovery.
Git status uses read-only probing (`--no-optional-locks`). Bound subprocesses and
filesystem traversal; handle symlink loops, escaping links, dangling links and
concurrent disappearance. Explicit external roots are inspected without treating
the whole enclosing checkout as owned/deletable.

Completeness is bounded and honest: Toolkit cannot prove absence outside configured
roots or unmanaged references it cannot inspect. Unknown ownership/references
block destructive cleanup, not ordinary independent inspection or disabling of
verified owned links.

### 4.4 Frozen storage routing and legacy transitions

Notation: H = explicitly resolved home; S = H/.agent-toolkit; K = existing
Skills root (AGENT_TOOLKIT_SKILLS_ROOT or S/skills); P = selected consumer project;
I = existing project_id(P). No new general root override is introduced.

| Kind | Global authority/content | New project authority/content | Legacy transition |
|---|---|---|---|
| Skills | K.parent/skills-lock.json; K/slug and K/_parents | P/skills-lock.json; K.parent/projects/I/skills | Keep referenced skills-workflow and other legacy backing locators in place |
| Agents | S/agents-lock.json; S/agents | P/agents-lock.json; S/projects/I/agents, including its own _parents | Existing project Agents in Skills namespace remain located by proven records/targets; never reuse that namespace for new Agents |
| Commands | S/commands-lock.json; S/commands | P/commands-lock.json; S/projects/I/commands | Retain existing locators and sidecar ownership |
| Pi extensions | S/pi-extensions-lock.json; S/pi-extensions for Git; package records for registry sources | P/pi-extensions-lock.json; S/projects/I/pi-extensions for Git; scoped package records | Existing project links into global backing are explicitly Shared with Global, not independent copies |
| Instructions | Existing global canonical AGENTS.md and its chain via instructions_paths | P/AGENTS.md and its chain; no source or installation lock | Actual chain stays authoritative; no relocation on observation |
| MCP | Existing S/mcps-library.json and S/mcps definition/materializations | S/projects/I/mcps-library.json and S/projects/I/mcps; P/mcps-lock.json for projection records | Existing project projections of global definitions stay explicitly shared until a selected action changes them |

Each new per-kind namespace prevents same-slug cross-kind collisions. All normal
HOME overrides/injected homes are honored; Skills root override must not relocate
Agents/Commands/Pi/MCP or the shared local inventory manifest. Legacy Pi project
storage under K.parent is still observed by exact proven locator, never moved on
scan. A locator registered to another kind/source/ref is a conflict, not free space.

Legacy shared Pi/MCP routes remain operational and visibly shared. Disable removes
only the selected project route and does not touch global storage. To make an
independent project instance, `add --from-id INSTANCE --scope project` is an
explicit source acquisition action with no exposure change. For Git it reproduces
the selected ref/commit in the new project namespace; if dirty or unpublished work
cannot be transported losslessly through the supported acquisition path, refuse
and offer export/manual management rather than claim it was copied. For a package,
copy the resolved package definition/pin and filter/override metadata, not package
cache contents; for MCP, copy only a supported definition and env-variable names,
never credential values. Refuse credential-bearing definitions until the user
provides a redacted/scoped definition. The next explicit Enable plan can replace
the verified old project projection with the new instance; it names both identities.

Same-name different scoped definitions are separate identities. Any same-target
collision requires exact ID selection and an explicit replacement plan; no silent
fallback to the global definition. Pi's existing duplicate-global-load guard stays
in force where loader precedence/co-loading cannot be proven safe. Report-only
shared/unsupported state is valid; no automatic detachment or runtime execution.
Require fresh-process project-only Git/package Pi and MCP add-enable-disable tests,
legacy-shared disable/materialization tests, and same-slug Agents/Skills tests with
global content/index/history/records byte-identical.

### 4.5 Enumerable discovery boundary

Per-row fixture codes below are required test families in P2/P7, not runtime IDs.
Catalog = shipped skill_agents/harness matrix plus actual enabled adapter path
resolvers; never guess all harnesses from a directory name.

| Fixture | Kind / authoritative inputs | Included content and exposure observations |
|---|---|---|
| D-S | Skills: skill_paths, skill_lock, skill_collections, skill_collection_register, catalog | Both scoped locks; normal/legacy backing and aliases; real SKILL.md at root or nested supported source paths; Standard and every supported per-harness skill slot; wrappers, missing records, dangling/orphan projections |
| D-A | Agents: agent_paths/agent_lock and agent_adapters/catalog | Global/new project/legacy backing; canonical agent entry documents and direct files in supported slots; native/symlink/translated entries and .attk ownership; stale covered-harness shadows and orphan sidecars |
| D-C | Commands: command_paths/command_lock and command_adapters/catalog | Scoped COMMAND.md sources; supported .md/.toml and translated prompt formats at adapter-defined slots; owned/unowned sidecars and recordless sources/projections |
| D-I | Instructions: instructions_paths/install/adapters and instructions_matrix | Scoped canonical chain, every catalog pointer/native target, regular-file conflicts, broken/foreign links and source-chain participants; no directory-wide skill-style crawl |
| D-P | Pi: pi_extension_paths/lock/inventory, _pi_settings and Pi adapter | Scoped Git backing, settings packages[] strings/objects, extensions[] loose paths, enabled/disabled overrides and package filters; direct supported extension files/directories and local package manifests/entrypoints; missing/recordless/filter-shadowed registrations |
| D-M | MCP: mcp_manifest/library/lock and mcp_adapters | Both scoped definition authorities, materialization config/sidecar pairs, scoped projection locks, every supported harness's named MCP entries and missing/orphan/unmanaged entries; no remote endpoint crawl |

Registered source roots may contain nested supported entrypoints; recursively
inspect within the declared source root, excluding VCS internals, node_modules,
virtualenvs, caches/build outputs and hidden implementation directories. Skills
nested source discovery preserves all supported real root/nested skills. Agent/
Command backing source discovery follows their existing supported manifest/entry
format; arbitrary unrelated Markdown is not assumed to be a definition. Harness
slots follow each adapter's supported direct/nested layout rather than recursively
searching an entire harness home. Discovery bounds (depth/node/time limits) may be
tuned, but truncation must report incomplete coverage and not silently omit rows.

An encountered symlink outside a root yields an observed alias and narrowly inspects
its supported target entrypoint/declared package metadata; it does not grant recursive
inspection or ownership of the enclosing external tree. Registered exact external
locators and explicitly added roots may be inspected within their declared bounds.
Do not follow package dependency trees or execute package exports/imports.

Extra roots are declared in S/discovery.json or S/projects/I/discovery.json with
`schema: atk-discovery/v1` and a `roots` array of asset_type/path/context objects.
Only literal filesystem paths and supported kinds are accepted; no commands,
interpolation, glob-to-home expansion or executable hooks. Paths are resolved
against that config's declared base, with exact roots included in scan coverage.
Invalid config is an incomplete/error finding, not silently ignored.

Missing optional unregistered roots are inspected-absent and can be complete;
missing required recorded content is an error finding, not a scan failure by
itself. Deliberate standard exclusions are reported with rationale and do not
imply full-disk completeness. Unsupported configured formats, unreadable roots,
failed resolution and budget truncation mark the affected coverage incomplete.
Registered excluded targets remain visible as unresolved records with explicit
reason. Each D-* test family covers record-only, content-only, active foreign
exposure, aliases and incomplete cases, with documented N/A for non-filesystem
source concepts such as remote MCP content and Instructions Git acquisition.

## 5. Lifecycle and exact operation effects

### 5.1 Common flow

`Discover -> Inspect -> Manage -> Enable -> Disable -> [Keep | Unmanage | Delete]`

Discovery need not precede add-from-source. Managed content may stay disabled
indefinitely. Foreign content may already be effectively available before adoption;
management does not rewrite its existing exposure. There is no automatic adoption,
activation, reset, relocation, deletion or publication at startup/refresh/doctor.

| Action | Content | Records | Exposure |
|---|---|---|---|
| Add source | Acquire absent selected-scope content; reuse only proven matching copies without advancing HEAD | Register source and local provenance | Unchanged |
| Manage | Preserve existing bytes, modes, index/history and locations | Add verified management metadata | Unchanged |
| Enable | Prepare missing scope copy if explicitly planned; never fetch/reset an existing copy implicitly | Record supported source/projection facts | Add selected owned targets |
| Disable | Preserve all source content and local work | Preserve source/provenance; update projection records only | Remove selected verified targets |
| Unmanage | Preserve content | Remove selected management authority; preserve shared needed records | Must already be disabled at those targets |
| Delete local copy | Delete only explicitly selected owned storage unit after safety checks | Remove only selected inactive member/self records invalidated by deletion | Must already be disabled; no implicit cross-scope disable |

Manage supports local-only content without invented upstream URLs. It must refuse
unsupported lossless representation with a specific reason and manual guidance,
not copy/convert/execute it merely to make it managed. Adopted external content is
reference-owned, not storage-owned: deleting its source remains unsupported;
Toolkit may remove its own aliases/metadata after disabling them.

Unmanage with active managed projections refuses and offers an explicit separate
disable plan. After unmanage, surviving files remain visible as Discovered with
source evidence where available. Deleting a real payload makes it disappear only
when no recorded missing reference remains; remaining broken references are shown,
not silently dropped. No “forget” action hides files from scans.

### 5.2 Global/project copies and inheritance

A project add/manage/enable requires no global record or clone. A global change
never silently changes project content, and a project change never mutates the
global copy. Project backing storage may be outside the project repository;
label scope by ownership/consumer, not physical directory location.

Enable uses the selected scoped source if present. If only another scope has
content, preview explicitly names the source copy, destination and preservation
semantics. Do not silently link a project directly to mutable global content where
the adapter promises independent project copies. The default materialization for
Git content must preserve the selected recorded ref/commit; transporting dirty or
unpublished work requires a separately explicit copy plan, never a reclone that
claims those edits were carried. Existing compatible enable behavior may retain
its supported source reconstruction route but must state what is not transported.

Harness cells represent scoped exposure. Info/effective indicators show global
routes too. Disable-project with global exposure remaining succeeds only as a
local-link operation, with explicit remaining availability. It must not report
“unavailable.” There is no invented generic deny/override mechanism. Where root
exposure or loader behavior prevents requested isolation, refuse and explain.
Disable does not unload already-running agents; show restart/reload guidance where
known and “runtime reload behavior unknown” otherwise. Disk configuration cannot
certify the running agent's state.

### 5.3 Removal and shared-storage safeguards

Deletion is a separate operation, not a side effect of disable/unmanage/doctor.
Its preview lists exact selected copy/checkout, scope, affected assets, bytes or
files, remaining aliases/references, local-work status and recovery limitations.
Recheck ownership, identity, config/lock values, link targets and reference closure
immediately before each write. Refuse symlink swaps, foreign file/config collisions,
permission uncertainty, stale plans and active operations with actionable errors.

For Git storage inspect staged/unstaged/untracked/ignored content, refs/history,
worktrees, submodules and publication reachability. Clean status is not sufficient.
Offline/unverified upstream publication is Unknown, not Safe. Dirty work, unique
commits, ignored user data or uncertainty block ordinary deletion. An explicitly
authorized discard action must name the exact storage unit and risks; `--yes`
never implies discard. Export/preserve local work before destructive escalation.
No automatic network request is needed merely to diagnose local uncertainty.

A child in a shared checkout cannot be deleted as an independent Git repository.
Offer Disable/Unmanage for that child; whole-checkout deletion requires all member
references across known scopes/contexts accounted for and deactivated through explicit
prior actions; selected inactive member/self-records may be removed within the
whole-storage deletion plan as specified in §5.5. Never rmtree a checkout because its last selected child lock vanished.
Git linked worktrees/common directories are checked as related storage units.
Package cache entries, external paths and remote MCP servers are never interpreted
as owned local copies eligible for recursive deletion. Crash recovery records must
survive until resolved; do not automatically remove interrupted-operation evidence.

### 5.4 Capability matrix: common intent, honest differences

| Asset type | Source/manage contract | Enable/disable contract | Delete/doctor limits |
|---|---|---|---|
| Skills | Scoped Git/local content; source/ref/path and collection provenance | Existing Standard/nonstandard exposure; independent project copy | Shared-checkout and real-root isolation guards apply |
| Agents | Scoped Git/local definition, not global lookup masquerading as project storage | Symlink/translation/sidecar adapters | Preserve foreign definitions and exact ownership |
| Commands | Scoped canonical prompt, existing translations and ownership | Supported generated formats/links only | Never delete a user's foreign destination file |
| Instructions | Identify existing user-owned canonical chain; no add-source clone API, no installation lock | Actual canonical pointers; shared/no-op native targets accurately described | No delete-source action; protect source-chain participants; adoption with content relocation remains separate explicit legacy repair |
| Pi extensions | Scoped Git/local or package definition; no package execution during scan/adoption | Settings/config changes through existing guarded adapters | External local packages reference-owned; preserve filters/overrides/unrelated settings; no blanket package-cache deletion |
| MCP servers | Definition registration in either scope, using existing definition format | Named guarded config entries and projection records | No endpoint/server destruction; no secret copying, credential discovery or live connectivity probe on scan |

For project MCP definitions add the existing-format authoritative definition store
under S/projects/I/mcps with mcps-library.json at S/projects/I, as frozen in §4.4;
global stores remain at their existing paths. Resolve project
first then global **only for availability suggestions**, not silent mutation or
shared identity. Portable project projection records remain in their existing
consumer lock location. Explicit export/import of definitions remains responsible
for moving machines; do not embed environment secret values into project locks.
For other source-backed kinds extend existing project source-lock/store mechanisms
without introducing global prerequisites. Instructions correctly reports source
addition/deletion unsupported instead of manufacturing parity.

### 5.5 Positive storage deletion route and retained ownership

Asset instances and storage units are separately selectable. Introduce:

```text
agent-toolkit-cli storage list --scope project --format json-v1
agent-toolkit-cli storage delete --id STORAGE_ID --scope project --dry-run --format json-v1
```

TUI Info shows the storage unit; its Actions menu provides Inspect storage and
Delete checkout/copy when supported. This uses a storage ID, never a synthetic
collection asset key. `kind delete --id INSTANCE` may delete an independent owned
unit; for a shared child it refuses and links to the storage-unit plan.

Live projections, foreign/dependent links, another managed context's references,
shared Git common directories/worktrees and unresolved coverage are blockers.
The selected unit's inactive member/source records and its own provenance/creation
receipts are removable self-records, not blockers. The whole-unit preview enumerates
all of them and removes them only after successful deletion. Unmanage is not a
prerequisite: disable all dependent exposures, then select whole-storage deletion.

Unmanage releases asset-management authority, but a verifiable Toolkit-created
storage receipt may remain as historical evidence for a separately authorized
storage deletion. It is not renewed blanket ownership: current storage identity,
contents, references and local-work checks must all pass. Adopted external units
never gain this storage-delete capability. Lost/inadequate creation evidence means
report-only/manual removal, not a guessed deletion right.

| Kind/unit | Positive supported deletion and records |
|---|---|
| Skills/Agents/Commands Git | Whole owned independent/shared checkout after references and publication/work checks; remove selected inactive member records and owned aliases, never sibling payload paths individually |
| Owned non-Git local copy | Whole Toolkit-created directory/file with verified creation/baseline identity and no dependent references; changed/unknown content requires verified export plus explicit discard confirmation |
| Pi Git | Whole scoped owned Git unit under the same Git checks; preserve another scope's independently stored copy |
| Pi registry definition | Delete the disabled selected scoped definition/lock/provenance record; no package cache is a selected storage unit and none is removed |
| MCP definition | Delete the disabled selected scoped definition record and its exclusively owned config/sidecar materializations; preserve shared manifest's other entries; no endpoint/service/container removal |
| Instructions/external references | Source deletion unsupported; Disable and Unmanage only where meaningful; protected canonical chains remain untouched |

Deletion is permanent for the selected unit after any explicitly requested verified
export. Do not promise undo or silently create an invisible trash copy. For a
partially completed recursive removal, recovery reports exact remaining paths and
finishes cleanup only when identity/ownership/reference checks still pass; it does
not claim to restore already-deleted bytes. Work requiring preservation cannot
enter deletion until the explicit export has been verified. A safe published clean
owned checkout, and an owned non-Git unit with verified export, must each have a
successful delete -> restart -> no phantom rows test. Also test reference refusal,
shared-child refusal, changed foreign contents and interrupted deletion cleanup.

## 6. CLI, automation and compatibility

New canonical commands for applicable kinds:

```text
agent-toolkit-cli --project /consumer skills add SOURCE --scope project
agent-toolkit-cli --project /consumer skills list --scope project --format json-v1
agent-toolkit-cli --project /consumer skills manage --id INSTANCE --scope project --dry-run
agent-toolkit-cli --project /consumer skills enable --id INSTANCE --scope project --agents standard
agent-toolkit-cli --project /consumer skills disable --id INSTANCE --scope project --agents standard
agent-toolkit-cli --project /consumer skills unmanage --id INSTANCE --scope project --dry-run
agent-toolkit-cli --project /consumer skills delete --id INSTANCE --scope project --dry-run
agent-toolkit-cli --project /consumer skills doctor --scope project --format json-v1
```

`INSTANCE` is the exact inventory ID, not a literal example value for execution.
Keep slug positional selectors when unambiguous. Ambiguous slugs fail with qualified
choices; never prompt-pick a destructive target in noninteractive use. New mutating
verbs require explicit `--scope` or `-g/-p`, reject conflicting scope flags, and
name resolved project/context. New add supports both scopes; omitted scope retains
its existing global default for compatibility, prints it in human output, and
never enables. Existing add flags/selectors retain behavior; project scope is new.
`--agents` remains the supported target spelling for Skills; other kinds preserve
their existing adapter-specific harness option aliases and expose consistent
capability metadata. No fictitious target support is implied.

Common new operation flags: `--dry-run`, `--format json-v1`, `--yes` (confirmation
only), `--id`. Read inventory and doctor share `--scope`; no scope must be inferred
from filesystem dirt or a library term. Legacy `list --json` schemas remain stable;
`json-v1` is the explicit new envelope. Existing read-command scope defaults remain
unchanged during this issue; both are documented, not silently unified.

Machine envelope `schema: atk-inventory/v1` includes scan coverage, typed instances,
source confidence, copy locators, exposure/effective routes, changes, health,
capabilities, safe available actions and findings. Operation envelope
`schema: atk-operation/v1` includes operation ID, selected resources, scope/targets,
planned/completed/failed steps, preservation summary, remaining exposure, refusals,
recovery state and reload guidance. Secrets/config credential values are redacted;
stdout contains exactly JSON, diagnostics to stderr. JSON shape/types and stable
reason codes are tested; no parsing of colored human prose is required.

For new machine surfaces exit 0 means successful observation/action with no blocking
health findings (informational discoveries/modifications may remain); 1 means
unresolved actionable health findings or safe operation refusal; 2 means invalid
usage; 3 means incomplete inspection, I/O/schema failure or partial action/recovery.
If several apply, 3 takes precedence, then 2 for pre-execution usage, then 1. A
successful repair may exit 0 only after reinspection proves its selected findings
resolved; remaining report-only error findings keep exit 1/3. Preserve old commands'
exit behavior unless explicitly documented through the new format/verb contract.

Doctor defaults to read-only. This is an intentional, documented safety-default
change for doctors that currently prompt without `--repair`, not an unnoticed
compatibility alias change. Retain `--no-fix`; it always overrides repair flags.
`--repair` exposes supported plans; interactive confirmation defaults No.
Noninteractive repair requires repeatable `--finding ID`, exact `--id` selectors,
explicit scope and `--yes`; EOF/no TTY never silently accepts or hangs. Destructive
repair is not bundled into `--repair --yes`; delete/discard uses its distinct
explicit action and guards. Batch/source actions enumerate the selected scope's
reconciled membership, not only the global lock, so project-only assets participate.
`--source` remains exact source identity; explicit refs disambiguate separate groups.

### Versioned machine contract details

`json-v1` documents are JSON objects. Required inventory fields are `schema`
(string literal), `scope` (global/project), `context` (object with project/profile
locators or null), `coverage` (object: inspected/skipped/errors arrays and complete
boolean), `instances` (array), `storage_units` (array), `findings` (array), and
`summary` (counts object). Storage list uses this same envelope; units include ID,
locator, type, member IDs, ownership classification, reference coverage and allowed
actions/refusals.
Each instance requires `id`, `asset_type`, `name`, `source` (recorded/inferred/unknown
confidence plus safe origin/ref/observed-commit fields), `copies` (array of storage
IDs/locators), `management` (managed/discovered), `exposures` (resource/target/scope
records), `effective_availability` (available/unavailable/unknown plus routes),
`changes` (staged/unstaged/untracked arrays and publication classification),
`health` (finding references), and `capabilities` (action-to-supported/reason map).
Unavailable facts are null or unknown, never guessed empty-clean values.

Required operation fields are `schema`, `id`, `action`, `scope`, `instance_ids`,
`expected_revision`, `plan_token` (string on preview, nullable after application),
`dry_run`, `steps`, `result`, `preserved`, `remaining_exposure`, `recovery`, and
`reload_guidance`. `result` is planned/applied/refused/partial/failed;
each step names resource ID, effect, state and safe reason code. Doctor uses the
inventory envelope plus complete finding records; findings include `id`, `code`,
`severity` (info/warning/error), `instance_ids`, `resources`, `evidence`,
`inspection_complete`, `actions`, `reason`, and `guidance`. Redacted fields carry an
explicit redaction marker rather than secret content. Serialize sorted collections
for deterministic comparisons; preserve unknown fields on persisted inputs.

Check in JSON Schema documents under `schemas/asset-inventory.v1.json`,
`schemas/asset-operation.v1.json` and `schemas/asset-finding.v1.json`; test the same
shapes/types with the existing Python test stack, without requiring a new runtime
validator dependency. Additive optional fields are permitted within v1; removing,
renaming or changing required types/enums requires a new version. Never change
legacy `--json` output to the new envelope without explicit format selection.

Ordinary delete never discards protected work. An explicit discard request uses
`delete --discard-local-work --confirm-storage STORAGE_ID` in addition to selected
instance/scope and confirmation; it must produce a preservation/export plan first.
If preserving that work cannot be verified or references remain, refuse. This
flag cannot bypass ownership, shared-storage, live-reference or stale-plan checks.
These selectors/flags are implementation deliverables, not shipped commands.

### Compatibility policy

- Introduce canonical enable/disable and retain install/uninstall as compatibility
  spellings implemented by wrappers, NOT literal function aliases. Keep their
  existing flags/defaults/exit codes and portable-record effects, including Skills
  and Pi project uninstall record pruning. Before a legacy wrapper removes known
  source metadata, preserve verified identity/source/ownership in the local manifest
  under the new guarded protocol. This additive non-content migration is explicit;
  refresh/restart still shows the retained instance as Managed and disabled.
  Canonical Disable retains portable source records; legacy wrappers may prune them
  exactly as before. Both preserve content, observed exposure and durable provenance.
  Do not broaden omitted-target behavior. See the frozen compatibility table.
- Keep old remove/import/reset behavior intact and clearly mark effects in legacy
  help. No automatic mapping of destructive remove to nondestructive disable.
- Main help/docs/TUI lead with new terms. A legacy-help section explains aliases;
  warnings go to stderr, never pollute existing JSON or change success codes.
- Retain aliases for all releases in the current major line and at least two
  subsequent minor releases after introduction. Removal, default changes and any
  JSON replacement require separate approved breaking-release work. ReleasePlease
  owns versioning; do not hand-bump versions or rewrite historical release notes.
- Audit six groups, singular aliases, CLI examples/completions, error/help text,
  TUI/palette/footer/Info, scripts, bundles' outward descriptions, current docs,
  generated documentation inputs and agent-facing instructions. Historical reports
  remain historical. Bundles install/validate is a composite utility, not blindly
  renamed to enable; explain acquisition plus exposure and preserve its API.

### Frozen six-kind legacy compatibility table

This table is the planning decision, not work delegated to P1. Recheck PR #537's
merged base for changes; materially different behavior requires updating this
contract before implementation, not silently choosing another default.

| Kind | Legacy install/uninstall omitted scope and target flags/defaults | Legacy uninstall records / remove behavior |
|---|---|---|
| Skills | install/uninstall Global except detected Paperclip company Project; --scope or -p; install --agents standard; uninstall omitted --agents = Standard + detected agents (Paperclip only where available) | Project uninstall prunes selected source record, Global keeps source; remove is global-only entry/canonical plus owned global exposure, shared backing guarded |
| Agents | Writes default Project; -g/-p; --harnesses list; install Standard + supported adapters not covered by it; uninstall Standard + every enabled adapter | Uninstall preserves scoped source records/content; remove is global source/canonical removal plus owned global exposure |
| Commands | -g/-p; omitted scope uses existing default_scope over any supported source-kind project lock, otherwise Global; --harnesses; install Standard + Pi + Gemini; uninstall Standard + all supported command targets | Uninstall updates exposure metadata while retaining source/content; remove deletes selected scoped record/canonical after projection removal |
| Instructions | --scope defaults Project; install repeated --harness, omitted = all supported symlink-verdict pointers; uninstall retracts all owned scoped pointers | No installation lock; uninstall keeps canonical; no source add/remove/delete verb |
| Pi extensions | Writes default Project; -g/-p; Pi only, no harness fanout flag | Global uninstall keeps source; project Git uninstall prunes project source record, registry uninstall removes matching scoped packages[] through current ops; remove deletes global definition/owned store/projection |
| MCP | Writes default Project; -g/-p; repeated --harness; install Project Standard+Codex+OpenCode, Global four concrete supported adapters; uninstall defaults to harnesses recorded for slug at scope | Uninstall removes selected projection records, definition retained; remove removes every locked scoped projection, definition still retained; --force running-Claude guard is NOT a content-discard flag |

Canonical Enable/Disable requires explicit scope and uses those same applicable
target defaults unless a target is selected. Canonical Disable retains source
metadata for every source-backed kind. Legacy wrappers retain the table's portable
record effects and save durable verified provenance first; resulting disabled
instances stay visible and manageable after restart. New per-kind IDs and source
selectors are additive; old slug behavior/JSON remains stable where unambiguous.

### Reviewed-plan application and recovery API

Preview is read-only: it returns the operation envelope plus `plan_token`, a
base64url encoding of canonical non-secret desired effects and expected affected
resource/record fingerprints. Its ID is a digest of that semantic plan. The token
contains no raw credentials or config snapshots, is not a permission credential,
and grants no exception to normal capability/ownership checks. No preview file or
journal is created by Toolkit. The caller may save the JSON to a chosen file.

`expected_revision` is an affected-resource/record fingerprint map plus an advisory
manifest revision, NOT a global compare that rejects unrelated edits. Conditional
apply reconstructs the plan from that token, validates its digest/shape and all
requested action rules, locks resources and compares current affected fingerprints.
It executes only those reviewed effects; changes require stale-plan refusal, never
silent replanning. Unrelated record edits are merged freshly and preserved.

Example separate-process automation (proposed API; IDs selected from real output):

```text
agent-toolkit-cli --project /consumer skills list --scope project --format json-v1
# select one returned instance ID and inspect its capabilities
agent-toolkit-cli --project /consumer skills disable --id asset-123 --scope project --agents standard --dry-run --format json-v1 > preview.json
agent-toolkit-cli --project /consumer operations apply --scope project --plan-file preview.json --yes --format json-v1
agent-toolkit-cli --project /consumer skills list --scope project --format json-v1
```

If the selected link/record changes between processes, Apply exits 1 with reason
`stale-plan` and zero affected writes. It does not disable a newly discovered target.
Malformed tokens are usage errors; incomplete inspection/recovery remains exit 3.
A plain direct mutating command may freshly plan but must still preview/confirm its
current effects, or require explicit --yes; agents wanting reviewed guarantees use
`operations apply`. Format/JSON alone never implies authorization.

After actual application begins, the operation is persisted. Supported recovery:

```text
agent-toolkit-cli --project /consumer operations recover --id op-123 --scope project --mode inspect --format json-v1
agent-toolkit-cli --project /consumer operations recover --id op-123 --scope project --mode resume --yes --format json-v1
agent-toolkit-cli --project /consumer operations recover --id op-123 --scope project --mode rollback --yes --format json-v1
```

Inspect is read-only/default. Resume/rollback lock and revalidate exact resources,
never resolve ownership conflicts by force. Rollback is unsupported for already
permanently deleted bytes and explicitly reports this. Unknown external changes
require manual resolution with exact paths; reinspection can later close recovery
only when observed final state and retained evidence prove it. Doctor and the TUI
expose these same actions/reasons. Restart and separate-process tests must cover
conditional apply, unrelated-record preservation, stale tokens and each crash gap.

## 7. TUI contract and exact journeys

Always-visible inventory includes managed and discovered content in declared roots.
Filters may narrow presentation but never silently suppress problems or alter
collection action membership. Counts use unique reconciled assets, with copy and
conflict totals separate; aliases/containers are not skills. Distinct same-scope
copies get qualified subrows/details, not one misleading shared toggle.

Retain six grids and aggregate cross-kind/scope pending queues. Provide an Add
source entry in the command palette and active grid toolbar; its form names the
current scope/context, kind-specific source/selection fields and acquisition-only
consequences. Instructions explains why source addition is unsupported. Validate
and preview with the same scoped Add operation as CLI; no acquisition/network
request occurs until explicit Apply. Source entry accepts URLs/local paths or a
selected existing instance via Add from this copy. MCP fields accept env names,
not secret values. Introduce an Actions menu accessible by keyboard and mouse:
Inspect, Manage, Enable/Disable, Unmanage, Delete local copy,
Inspect storage/Delete checkout, Doctor. Unsupported actions are disabled with
a reason and alternative, not absent mysteries. Opening menus/Info/previews never
writes. Rename Ctrl+D to Preview changes; it previews queued Toolkit operations
only. Do not add a content viewer, content-diff shortcut or View local changes
menu item under #538; those belong exclusively to #540. Changes badges/path-status
summaries remain visible, with sensitive config/environment values omitted.

Keep queue ownership intact across tabs/scopes. Add management/deletion action
plans to the shared preview/Apply layer with explicit destructive confirmation.
Revert is pending-operation cancellation, not Git reset. Apply reports exact
per-resource results; failed work stays actionable; successful unrelated work is
not rolled back or silently requeued. A queued plan invalidated by external edits
refuses and requests refreshed inspection. Explicit Refresh's existing discard
contract remains documented; this issue does not silently change it.

Required end-to-end journeys:

1. **Known skill disable:** 11 unique children -> disable aj-pm -> refresh/restart:
   still 11, same collection/source/instance, aj-pm unchecked and Modified;
   other clean children stay Clean. Re-enable uses preserved edits without a reset.
2. **Already-discovered legacy duplicate:** no manifest and aj-pm lock missing:
   two aliases reconcile to one Discovered row under proven collection context;
   Manage preserves bytes/HEAD/index, then enable works. No mandatory global add.
3. **Project-only source:** add to project with no global source/copy -> managed,
   disabled -> enable -> disable -> unmanage -> visible Discovered. Global state
   remains byte-identical throughout. Delete only if independently safe/owned.
4. **Global inherited exposure:** project disable leaves global route visible with
   plain explanation and correct effective availability, never a false off verdict.
5. **Removal with local work:** modified/unpublished content blocks ordinary delete;
   inspect affected-path/publication findings and external Git/manual guidance;
   preserve/export work; only explicitly
   authorized whole-storage action can proceed. Shared child deletion refuses.
6. **Foreign/unsupported discovery:** inspect and actionable adoption or refusal;
   foreign config/files remain unchanged; unsupported does not disappear.
7. **Interrupted operation:** restart sees persistent recovery finding, current
   physical truth and safe resume/manual guidance. Never “all clean” on rollback
   failure. Independent operations remain usable where ownership is unaffected.

At 120x40 and 180x50, names remain distinguishable; health is not color-only;
focused scope, remaining global availability and destructive consequences are
readable. Save screenshot artifacts with written image-based judgments.

## 8. Doctor: exhaustive within explicit boundaries

“All eventualities” means a total, testable classification of supported observed
states and failure modes, not a claim that arbitrary external systems are repairable.
All kinds consume the same reconciled observations and operation plans. New
`agent-toolkit-cli doctor` aggregates all six kinds at explicit selected scope;
per-kind doctor remains available. No separate diagnosis universe or repair shell
string diverging from the action actually executed. Preview is rendered from the
same typed operation plan that Apply executes.

Every finding contains stable ID/code, severity, scope/context, affected instances
and paths/entry keys, evidence, inspection completeness, explanation, available
safe actions, refusal reason/manual guidance and reload requirement if relevant.
Informational discovered/disabled/modified states are not automatically broken.
Finding IDs survive unchanged observations, not arbitrary scan order.

| Finding class | Required handling |
|---|---|
| Healthy managed enabled/disabled | Correct facts; no repair required |
| Healthy project absent globally | Healthy project state; no global re-add suggestion |
| Foreign/discovered enabled or disabled | Visible; lossless Manage plan or explicit unsupported reason |
| Alias/legacy wrapper | Deduplicate physical identity, retain source; targeted exposure reconciliation only on action |
| Duplicate real copies, same slug or source/ref/path | Qualified copies/conflict; never pick/delete/rehome automatically |
| Missing source content / missing entrypoint / missing managed copy | Distinguish absent, locally deleted and unreadable; no blind upstream reset |
| Dangling/missing/drifted projection or ownership sidecar | Recreate/remove only proven owned resource under exact plan |
| Foreign regular file/link/config collision | Preserve; explicit conflict; no “repair all” overwrite |
| Unexpected root/nested/global effective exposure | Show actual route; supported narrow disable or isolation refusal |
| Git staged/unstaged/untracked/ignored edits | Asset-scoped path/status details and shared-checkout summary, not content patches; never reset as repair |
| Ahead/diverged/detached/unknown publication | Accurate status; protect unique history; no implicit fetch/push/checkout |
| Ref/pin/origin/path mismatch or escaping target | Identity conflict; block unsafe mutation, report evidence |
| Referenced backing / unused retained backing | Referenced is protected; retained is visible, not auto-garbage |
| Stale records / moved/deleted project / missing profile/company | Actionable locator/context problem; do not infer new owner |
| Corrupt/newer lock or manifest / malformed config | Incomplete/error, preserve bytes; explicit recovery guidance |
| Permission errors / broken filesystem / cycles / timeout | Incomplete scan, bounded failure, never false clean |
| Adapter unsupported / loader isolation unproven / lossy adoption | Visible report-only refusal with supported alternative |
| MCP env reference absent / settings filter or precedence conflict | Redacted diagnosis; no secret lookup, environment mutation or server start |
| Shared config, Standard aliases, Instructions source chain | Dedupe resources; preserve unrelated keys/source content; chain protection |
| Concurrent record/path/config replacement | Stale-plan refusal; no overwrite; refresh unrelated work safely |
| Partial action / failed rollback / interrupted recovery | Persistent exact remaining state; guarded retry/resume or manual conflict resolution |
| No remaining files but recorded references | Missing/broken record findings remain until explicit repair |

Cross every applicable class with all six kinds, Global/Project, managed/discovered,
enabled/disabled, healthy/unreadable, native/translated/config mechanism and
supported/unsupported adapter. Use equivalence classes and explicit N/A reasons;
not an unmaintainable brute-force Cartesian test suite. A checked-in coverage table
maps every class/kind to test IDs or justified unsupported/report-only behavior.

Repairs are individually scoped, additive where possible, idempotent and previewable.
Report-only doctor, startup, refresh and operation previews preserve lock/config bytes,
source content/index/history and managed-path state. Repair confirmation neither
waives ownership checks nor authorizes publication, upstream updates, destructive
discard, network execution or cross-scope mutation. Reinspect after each action.

### 8.1 Minimum mandatory applicability and repair matrix

S/A/C/I/P/M = Skills/Agents/Commands/Instructions/Pi/MCP. Each F-code is a planned
fixture family under test_asset_doctor_matrix/repair, mapped to every indicated
kind with its real mechanism. `info/0` does not fail doctor; `error/1` is an
unresolved health/refusal; `incomplete/3` takes precedence over error/1. Warning/1
is actionable but non-destructive. N/A is explicit in the Kind column.

Action names below are minimum required capabilities, not implementation options.
All require exact finding/resource IDs, full affected inspection, user authorization,
current ownership and safe expected-state checks. Missing prerequisites turn into
an explicit refusal with guidance; they do not silently remove the required action.
Where several repairs exist require `--action ACTION`; never pick a destructive one.

| Fixture | Kind applicability | Class / severity | Required action or deliberate report-only result |
|---|---|---|---|
| F01 | S A C I P M | Healthy enabled/disabled, project absent globally; info/0 | No repair; report scope and effective routes |
| F02 | S A C P M; I canonical/pointer recognition | Discovered local content/config; info/0 | Manage exact losslessly representable source/definition; unsupported format report-only with reason; I valid pointers need no registration |
| F03 | S A C P; M config aliases; I pointer aliases | Duplicate aliases; info/0 | Reconcile presentation read-only; no repair necessary merely to deduplicate |
| F04 | S A C P M; I conflicting source chains | Distinct copies/slug/ref/origin mismatch; error/1 | Report qualified IDs; explicit selection/replacement via lifecycle actions only, never automatic merge/delete |
| F05 | S A C P; I canonical; M authoritative definition | Missing/deleted source or entrypoint; error/1 | Report-only; inspect/export/reconstruct explicitly through Add, never doctor reset/fetch locally deleted source |
| F06 | S A C I P M | Missing/dangling verified owned projection; error/1 | Required Enable/rebuild projection from healthy selected source; disable/remove stale owned link offered if source unavailable |
| F07 | S A C P; M owned materialization; I pointer | Drifted owned generated resource/sidecar; error/1 | Required regenerate/relink only when exact ownership and unmodified-destination evidence hold; otherwise F08 |
| F08 | S A C I P M | Foreign regular file/link/config collision; error/1 | Report-only/manual preserve/relocate; no automatic overwrite or ownership manufacture |
| F09 | S root/nested; all global/project routes | Unexpected actual exposure; warning/1 | Required exact narrow Disable when representable; unknown isolation report-only refusal; show remaining global route |
| F10 | S A C P; I if underlying source Git; M local definition edits | Modified/staged/untracked source; info/0 | Report affected paths/status and checkout summary with external inspection guidance; no built-in content viewer, repair or reset |
| F11 | S A C P; I if Git; M if definition source Git | Unpublished/diverged/detached/unknown publication; info/0 | Report-only Git guidance; blocks Delete independently; no implicit network/push |
| F12 | S A C I P M | Permission/cycle/timeouts/corrupt or newer metadata/unsupported input; incomplete/3 | Report-only exact error/recovery guidance; never rewrite as empty; independent safe inspection continues |
| F13 | S A C P; M definition/materialization units; I source chains | Retained/referenced backing; info/0 | Inspect storage; required safe Delete plan only for proven owned inactive storage; protected/external report-only |
| F14 | S A C P M; I moved canonical context | Stale/moved project/profile/locator; error/1 | Report-only exact current/recorded paths; explicit Manage/Add after user resolves identity; never guessed retarget |
| F15 | S A C I P M | Unsupported adapter/lossy adoption/unproven loader; warning/1 | Report-only reason plus supported alternative; no fake enablement |
| F16 | P packages/filters/overrides; M env references | Effective filter/precedence or missing required env; warning/1 | Required exact supported settings override correction for owned P entry; unknown filters and M missing env are report-only, no secret lookup/injection |
| F17 | M; N/A other kinds | Missing owned materialization with valid scoped authoritative definition; error/1 | Required reconstruct local config/sidecar from that exact definition, with no endpoint call/credential fetch; corrupted authority is F12 |
| F18 | I; N/A other kinds | Foreign regular Instructions file requiring relocation; warning/1 | Separate explicit legacy action adopt-instructions-file with source-chain checks and non-overwriting backup; not lossless Manage; collision/ambiguous merge report-only |
| F19 | S A C I P M | Shared Standard/config records/source-chain danger; error/1 | Required resource dedupe and safe own-entry rebuild/disable; source-chain/external dependencies refuse deletion |
| F20 | S A C I P M | Concurrent/stale-plan ownership replacement; error/1 | Report-only refresh/replan; no overwritten external state |
| F21 | S A C I P M | Interrupted action/failed recovery; incomplete/3 | Required operations recover inspect, guarded resume/rollback where provable, otherwise exact manual guidance |
| F22 | S A C I P M | Absent payload with remaining source/projection references; error/1 | Show missing reference; explicit remove-stale-record only after proving reference is obsolete and no content/exposure is destroyed |

Git-publication concepts are N/A for registry-only P definitions, remote M endpoints
and non-Git I content. Source-clone/delete-source is N/A for Instructions; remote
connectivity/server deletion is N/A for MCP diagnosis. F06/F07 rebuilding does not
promise restoring unpublished missing source data. F18 deliberately preserves the
existing Instructions relocation repair behind an explicit distinct plan and
confirmation; it may not be silently selected as Manage.

## 9. Architecture and failure boundaries

Add small shared inventory/action/doctor contract modules rather than another
installer framework. Existing per-kind facades/adapters remain execution authority.
TUI, CLI and doctor consume the same typed model and per-kind capability providers.
Keep display formatting outside the model. A graph relates asset instances,
storage units, aliases, projection resources, source evidence and record references.
No parent/collection presentation key is ever passed as a real asset selector.

Per action: observe -> resolve exact targets -> preflight capabilities/ownership
and reference closure -> preview -> obtain required authorization -> revalidate ->
write affected resources -> merge fresh metadata -> reinspect -> report. Multi-kind
Apply is not globally atomic. Narrow transactions journal affected values only;
rollback checks current ownership before restoring. Recovery failure cannot be
masked by success in another kind. Migration must be idempotent and preserve
unknown metadata, modes, index/history, custom slugs and separate refs/checkouts.

Legacy remove/update/reset/push/doctor implementations must be audited for whole
checkout dirtiness, global-record enumeration and swallowed errors. Route canonical
lifecycle operations through the new guards. Retain compatibility wrappers rather
than retroactively changing all historical behaviors without notice. No fake
cross-kind support: unsupported capability is a structured refusal.

### 9.1 Serialized writes and interrupted-step protocol

Cooperating Toolkit writers acquire advisory OS locks using Python stdlib fcntl
on supported macOS/Linux hosts. Lock files live under S/locks and are keyed by
canonical resource identity, including shared config files and affected lock/
manifest files. Acquire the complete resource set in sorted ID order before fresh
read/preflight; bounded 5-second nonblocking acquisition reports resource-busy
without mutation. All old command wrappers, canonical verbs, TUI and doctor route
through these locks; a wrapper calling an unguarded writer is not acceptable.
Locks release on process exit. No global multi-kind transaction is claimed.

Under lock: reread current affected records, validate reviewed fingerprints,
merge unrelated current values, write a same-directory temporary file, fsync it,
replace atomically and fsync the containing directory where supported. Maintain
unknown fields and per-kind serializers' promises. Two real overlapping processes
must be tested: unrelated records on one manifest/config serialize without loss;
conflicting records refuse stale plans. Holding only an in-process mutex or doing
atomic replacement without resource locks does not satisfy this requirement.

External writers do not honor advisory locks. Preserve existing running-process
config guards, detect resource changes immediately before/after writes, and refuse
when required quiescence/ownership cannot be established. There is no claim of
atomic compare-and-swap against arbitrary simultaneous noncooperating writers;
this filesystem limitation is explicit in help for shared-config mutation. Never
force a running-harness guard merely because --yes is present. Destructive actions
require all known writers quiescent and safe reference closure. Tests inject
foreign replacement at each supported boundary and verify refusal/preservation;
this is not a promise to control an arbitrary rogue process between syscalls.

Before the first resource mutation, persist/fsync operation intent with selected
identities, affected before fingerprints, intended after fingerprints/effects,
ownership evidence and ordered step state. States: prepared, applying,
observed-applied, committed, recovery-needed. A step is marked applying durably
before its resource write; mark observed-applied only after readback verifies the
owned expected result. Retain intent until metadata/result commit is durable.

Protected recovery snapshots, when necessary, live in S/operations/OP_ID or the
project state's operations directory (0700 directory, 0600 files). Manifest stores
only their locators/digests, never secret/config contents. Preserve only affected
values where representable; if a config needs a full snapshot, keep it protected
locally with original restrictive permissions, never log/export/commit it. No raw
credential values enter JSON, tokens, issue evidence or diagnostic output. No secret
provider is queried. Explicit successful recovery resolves snapshot retention;
failed/uncertain recovery never erases evidence automatically.

After a crash between resource write and journal update: inspect both before and
intended-after states under lock. Exact before means the step may be retried;
provably owned exact-after means record completion without repeating side effects;
anything else is recovery-needed/manual conflict. Matching bytes alone without
ownership proof do not authorize mutation. Crash after resource commit but before
metadata commit merges only affected intended records if still valid. Permanent
delete cannot be rolled back; report known deleted/remaining paths and offer only
guarded remaining cleanup. Test every journal/resource transition gap in fresh
processes, not only exceptions inside one transaction.

## 10. Acceptance criteria and verification mapping

| ID | Acceptance criterion | Plan tasks |
|---|---|---|
| AC01 | Canonical concise GLOSSARY.md; no library-as-scope; accurate help/docs/Info definitions | P1, P8 |
| AC02 | One payload via aliases counts once; distinct clones/worktrees remain distinct; source/collection survive disable | P2, P3 |
| AC03 | Independent management/exposure/changes/health; only modified child marked Modified; checkout warnings retained | P2, P6 |
| AC04 | Read-only complete bounded discovery and honest incomplete coverage for six kinds | P2, P5 |
| AC05 | Direct source registration in both applicable scopes without implicit enable/global dependency | P3, P4 |
| AC06 | Manage/discover/unmanage/delete lifecycle preserves local work, identity and visibility | P3, P4, P6 |
| AC07 | Correct global/project effective availability, shared-root isolation and running-agent caveats | P2, P4, P6 |
| AC08 | Explicit guarded deletion; no shared-child rmtree, false publication safety, secret/cache/remote destruction | P4, P5 |
| AC09 | Six-kind enable/disable vocabulary, stable legacy aliases/defaults/JSON, full help/examples audit | P4, P8 |
| AC10 | CLI/TUI/doctor identical targets/effects; stable versioned JSON, exit codes, exact selectors, noninteractive safety | P4, P5, P6 |
| AC11 | Total doctor coverage matrix, actionable report-only limitations, no false clean or global re-add for project-only | P5, P7 |
| AC12 | Fresh-state ownership checks, targeted recovery, no unrelated overwrite, restart and fault-injection proofs | P3, P4, P7 |
| AC13 | TUI all-kind queues, accurately named operation preview, status-only change indicators, accessible lifecycle actions and two-size visual evidence | P6, P7 |
| AC14 | Portable locks/Instructions contract and isolated wheel/source behavior agree | P3, P7, P8 |
| AC15 | Existing full suite, strict docs, hosted compatible-platform checks and independent exact-head review pass | P7, P8 |

Implementation required checks: `uv run pytest -q`, `make docs-build`, ordinary
pre-push hooks and independent exact-head PR review. New regressions must fail
before fixes and pass after. Tests use disposable HOME/config/assets/Git remotes,
existing startup GIT-variable scrubbing and outside-root sentinels. No live repair,
credential use, external MCP call, release or installed-tool mutation is authorized.

Require real local-filesystem/Git integration, headless Textual journeys at both
sizes, installed-wheel CLI/TUI/doctor parity in an isolated environment and
failure-injection sequences. Linux/macOS-specific behavior uses platform-appropriate
fixtures/CI, no hard-coded host paths. Evidence binds exact candidate SHA, test
commands, red/green logs, coverage table and image verdicts under
`assets/verification/538/`; attach durable evidence/index to the implementation PR.
Preparation is docs-only and is not evidence that these implementation gates pass.

## 11. Authorization, boundaries and delivery

Current request authorizes issue/spec/plan preparation and independent critical
review through build-ready. No implementation, live adoption, deletion, installed
asset changes, merge or release under this preparation session. Implementation
requires a subsequent explicit dispatch; L3 (conditional autonomy) is recommended.
Escalate material acceptance/safety divergence, not routine reversible details.

Non-goals: local-content viewer/CLI diff (owned by #540), new asset kind,
invisible discovered content, automatic startup
registration/repair, full-home scanning, global/project clone consolidation,
filtered-copy loader redesign, universal runtime unloading, arbitrary foreign
content deletion, public publishing, config secrets transport or provider choices.
All semantic writes belong in the issue's Worktrunk worktree. Existing user edits,
other workers and PR #537 remain untouched. ReleasePlease owns package versioning.
