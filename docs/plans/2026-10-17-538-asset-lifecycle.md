Issue: #538

# Asset lifecycle implementation plan

> For agentic workers: execute task-by-task in an owned Worktrunk worktree using
> the executing-plans procedure. Delegated review uses visible Herdr panes, never
> invisible workers. This preparation request does not authorize implementation.

**Goal:** Make every relevant discovered asset understandable and controllable,
without duplicate identities, ambiguous scopes, unsafe removal or divergent doctor.

**Architecture:** Reconcile per-kind observations into typed inventory instances
and storage/exposure relationships. Share planned, guarded lifecycle operations
between CLI, TUI and doctor; keep existing per-kind facades as execution authority.
Persist minimum local provenance/recovery separately from portable source locks.

**Stack:** Existing Python >=3.12, Click, Textual, pytest, uv, MkDocs. No new runtime
dependency, database or background service. No named model/provider requirement.

**Specification:** [Design contract](../specs/2026-10-17-538-asset-lifecycle.md).
**Vocabulary:** [GLOSSARY.md](../../GLOSSARY.md).

**Scope split:** [#540](https://github.com/ajanderson1/agent-toolkit-cli/issues/540)
exclusively owns View local changes, content rendering, CLI diff commands and
viewer tests/docs. #538 retains Modified/Clean/No Git/Unknown and changed-path
summaries plus deletion/publication guards, but neither implements nor depends on
the viewer. Implement lifecycle refusal/manual Git guidance without it.

## Execution rules and delivery sequence

This is one coordinated L (substantial) issue with eight ordered, independently
verifiable milestones, not permission to ship inconsistent half-migrations.
P1-P3 establish additive infrastructure; P4-P6 integrate it; P7-P8 prove and deliver
the full product contract. Use incremental commits and a draft implementation PR
if needed. Do not mark the issue complete until AC01-AC15 all pass. An implementer
may split reviewable PRs along these milestones, retaining this issue as the parent
contract; later milestones must explicitly depend on merged prerequisites.

- [ ] Obtain explicit implementation dispatch; re-read live issue, spec and plan.
- [ ] Fetch current origin/main. Confirm PR #537 is merged and its actual merge
  commit is contained in the fetched implementation base. Inspect final changes,
  especially wrapper ownership, actual child/root --path selection, preserved
  backing, exact preview/action parity and project-only healthy records.
- [ ] Create a new unique `feat/538-asset-lifecycle-*` Worktrunk worktree. Record
  base/branch/path, preserve source checkout and unrelated active worktrees.
- [ ] Run `uv sync --all-extras`; inspect any generated `uv.lock` delta. No new
  dependency/version bump is in scope. Avoid adopting incidental lock noise.
- [ ] Confirm test isolation from `tests/conftest.py` before invoking mutations.
  Use disposable HOME, XDG, harness/state roots and local Git remotes. Record
  sentinels proving no outside fixture content/config was changed.

Before each behavior change: add its regression, run it and record the real
failure, implement the bounded change, rerun to green, inspect diff and commit
with `Device: <actual hostname>`. New tests should fail on missing behavior, not a
broken fixture/network denial. Existing public default/alias behavior remains
covered. Never count planning review or baseline green as implemented acceptance.

## File and responsibility map

New narrowly focused modules (under `src/agent_toolkit_cli/`):

| Module | Responsibility |
|---|---|
| `asset_inventory.py` | Immutable observations/instances, identity reconciliation, copy/resource graph and scan coverage |
| `asset_provenance.py` | Versioned local manifest, scoped paths, fresh-record merges and provenance/recovery persistence |
| `asset_operations.py` | Typed lifecycle plans, expected-state/ownership checks, action execution results and guarded recovery |
| `asset_doctor.py` | Common finding schema, severity/exit mapping, coverage and aggregate diagnosis/repair dispatch |
| `asset_output.py` | Versioned JSON envelopes and redacted human summaries; no execution decisions |
| `asset_capabilities.py` | Per-kind capability contracts and adapters into existing facades |
| `commands/doctor_cmd.py` | Top-level aggregate doctor command |
| `commands/operations_cmd.py` | Conditional reviewed-plan Apply and inspect/resume/rollback recovery |
| `commands/storage_cmd.py` | Exact storage-unit list/preview/delete, separate from collection headings |

Keep these boundaries small. Do not consolidate all existing installers or replace
Instructions/MCP authority with a universal lock. Reuse existing facade functions
through explicit adapters; avoid display-model imports in the CLI core.

Existing integration points:

- `cli.py`, `_paths_core.py`; `skill_paths.py`, `agent_paths.py`,
  `command_paths.py`, `pi_extension_paths.py`, `instructions_paths.py`.
- `commands/{skill,agent,command,instructions,pi_extension,mcp}/` registration,
  add/install/uninstall/list/status/doctor/remove/import help and wrappers.
  Skill commands also live in `commands/skill/__init__.py`.
- `skill_collections.py`, `skill_collection_register.py`, `skill_doctor.py`,
  `skill_git.py`, `skill_install.py`; corresponding agent/command/Pi facades,
  `pi_extension_inventory.py`, `pi_extension_doctor.py`, `_pi_settings.py`.
- `mcp_library.py`, `mcp_manifest.py`, `mcp_lock.py`, `mcp_install.py` and MCP
  command modules; `instructions_install.py`, `instructions_adapters/`.
- TUI `{skill,agent,command,instruction,pi_extension,mcp}_state.py`, `app.py`,
  `widgets/`, `screens/`, `column_info.py`, `display_names.py`.
- Current docs, `README.md`, `AGENTS.md` terminology pointer, `GLOSSARY.md`,
  `docs/glossary.md`, `mkdocs.yml`, generated-document input/generator and
  `scripts/capture_docs_tui.py`. Do not hand-edit generated harness outputs.

## P1. Vocabulary, compatibility inventory and contract fixtures

**Files:** update root `GLOSSARY.md`; create
`docs/agent-toolkit/asset-lifecycle.md`, `docs/agent-toolkit/lifecycle-compatibility.md`
and `tests/test_cli/test_asset_lifecycle_contract.py` during implementation;
inspect all command groups and current glossary/reference pages.

- [ ] Encode the frozen six-kind table in Spec §6 from executable help/registration
  and source behavior. Recheck the merged #537 base; escalate material differences,
  do not defer choosing defaults to implementation. Include record effects, singular
  aliases and Bundles. Preserve old `remove` differences and canonical/legacy
  Disable source-record differences rather than mapping them by name.
- [ ] Add table-driven baseline tests for existing legacy resolution/defaults,
  portable-record effects/results and JSON schemas. These can pass in P1. In P4
  extend the same table with canonical verbs and additive local-provenance receipts,
  capture RED there and then implement to GREEN; no permanent xfail or skipped
  final acceptance test to make an intermediate milestone appear successful.
- [ ] Define fixture builders for managed/discovered assets, two scopes, shared
  checkouts, actual aliases and config resources. Reuse existing GitSandbox and
  per-kind helpers; never import the real user's configs into fixtures.
- [ ] Prepare core vocabulary reuse: root definitions remain authoritative;
  published glossary uses snippets or generated extraction while retaining old
  inbound anchors. Until implementation ships, label target behavior proposed.
- [ ] Record explicit unsupported capabilities rather than pretending Instructions
  supports source-cloning or remote MCP deletion. Document canonical new scope
  rules and unchanged legacy defaults in the compatibility table.

Run: `uv run pytest -q tests/test_cli/test_asset_lifecycle_contract.py`.
Expected GREEN for baseline legacy compatibility fixtures only. Canonical-verb
and JSON-v1 behavior is added/red-green verified in P4, not claimed passed in P1.
Keep test ownership staged without permanently xfail-ing final requirements.

## P2. Reconciled read-only inventory and truthful change indicators

**Files:** create `asset_inventory.py`, `asset_capabilities.py`, `asset_output.py`;
modify per-kind inventory/state providers and `skill_git.py` as necessary.
Create `tests/test_cli/test_asset_inventory.py`,
`tests/test_cli/test_asset_inventory_coverage.py` and
`tests/test_tui/test_asset_inventory_identity.py`.

Required normalized structures, defined here for later tasks:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ScanCoverage:
    inspected: tuple[str, ...]
    skipped: tuple[str, ...]
    errors: tuple[str, ...]
    complete: bool

@dataclass(frozen=True)
class InstanceKey:
    asset_type: str
    scope: str
    context: str
    payload_locator: str
    entrypoint: str

@dataclass(frozen=True)
class LocalChanges:
    staged: tuple[str, ...]
    unstaged: tuple[str, ...]
    untracked: tuple[str, ...]
    publication: str  # published, unpublished, unknown, not-applicable
```

Use typed enums/records for the specified domain values in production. These
structures establish field semantics, not a license to accept unchecked strings.
All later tasks use this single model, not new per-surface enums.

- [ ] Add actual symlink fixture: `store/aj-pm -> checkout/aj-pm`. Existing row
  assembly emits two unmanaged identities after deleting the child record; assert
  normalized inventory emits one instance with two locators and stable selection.
- [ ] Add same-source/ref/slug but distinct global/project clones, same-scope
  duplicate checkouts, Git linked worktrees, genuine root/nested, wrapper, dangling
  and cyclic aliases. Assert distinct physical copies remain distinct and conflicts
  are qualified. Missing content gets a missing logical instance, not guessed ID.
- [ ] Implement safe resolution, observation union and graph reconciliation before
  row assembly. Preserve custom slugs, source-confidence evidence and active-scope
  precedence. Deduplicate shared Standard resources, not just displayed names.
- [ ] Add regression with only `aj-pm` modified in an 11-child checkout. Scope Git
  changes by child entrypoint with staged/unstaged/untracked categories; summarize
  checkout-wide state separately. Preserve deleted child-document health.
- [ ] Implement frozen D-S/D-A/D-C/D-I/D-P/D-M source classes and declarative
  discovery.json roots from Spec §4.5, avoiding dependency caches/executable imports. Test permission failure, malformed records, unsupported
  config, disappearing roots, escaping links and timeouts with incomplete coverage.
- [ ] Implement effective availability as evidence-backed routes, including global
  exposure in project view and root/nested uncertainty; never invent suppression.
- [ ] Assert observational behavior preserves lock/config bytes, directory entries,
  file modes/mtimes where relevant, Git HEAD/index and no outside-root writes.

Run: `uv run pytest -q tests/test_cli/test_asset_inventory.py tests/test_cli/test_asset_inventory_coverage.py tests/test_tui/test_asset_inventory_identity.py tests/test_tui/test_skill_collection_boundaries.py tests/test_tui/test_instruction_pointer_identity.py`.
Expected GREEN: alias count invariant, distinct copies, child-only modifications,
truthful missing/unknown health, nonmutating scans. No runtime assets changed.

## P3. Durable scoped management and provenance without activation

**Files:** create `asset_provenance.py`; modify existing path resolvers and per-kind
source registration/adoption helpers. Create
`tests/test_cli/test_asset_provenance.py`,
`tests/test_cli/test_asset_management.py`,
`tests/test_cli/test_scoped_source_add.py`.

- [ ] Implement manifest v1 and exact per-kind roots from Spec §§4.2/4.4 with
  schema validation, unknown-field preservation and serialized affected-record
  compare/merge. Use stdlib fcntl resource locks in sorted order with 5-second busy
  refusal and fsync/atomic durable writes from §9.1; atomic replacement alone fails
  the contract. Store non-secret provenance/recovery with protected snapshot locators.
- [ ] Add actual two-process overlapping writer tests on unrelated and conflicting
  manifest/config records. Unrelated edits survive; conflicting reviewed plans
  refuse. Test process death/resource-write gap and stale/noncooperating replacement.
- [ ] Add read-without-manifest legacy fixture; identical visible rows must be
  produced before/after explicit adoption, fresh process and restart. Scan does
  not create metadata. Stale/newer/corrupt metadata remains visible, never reset.
- [ ] Implement Manage as lossless registration of an exact existing instance.
  Validate identity/content/ownership before writes; no source content relocation,
  HEAD change, configuration rewrite, fetch or execution. Foreign active exposure
  remains unchanged. Unsupported adoption returns a reason and manual guidance.
- [ ] Add direct project add for Skills/Agents/Commands/Pi definitions using scoped
  existing locks/backing stores. Add project-local MCP definition resolution at
  the specified state paths using existing manifest format. No global prerequisite
  or automatic exposure. Instructions reports source-add unsupported.
- [ ] Route new Agents to their own project agents namespace, not Skills; honor
  injected home while keeping Skills root override Skills-only. Preserve legacy
  locators on scan, including Agents/Skills namespace collisions and old Pi paths.
- [ ] Enable direct project Pi Git/package and MCP definition lookup under the
  frozen routing table. Mark existing global-backed project routes Shared with
  Global. Implement explicit `add --from-id` acquisition without exposure changes;
  preserve source pins/filters and refuse transport that would lose local work.
  Global bytes/index/history and unrelated definitions must remain identical.
- [ ] Implement Unmanage only for disabled selected resources, preserving content
  and shared-needed records. Rediscovery remains visible with source context and
  no fabricated “removed from disk” claim. External sources stay reference-owned.
- [ ] Inject manifest/lock-write failure and unrelated-record insertion; preserve
  pre-existing records/config/source, surface failed recovery and exact paths.

Run: `uv run pytest -q tests/test_cli/test_asset_provenance.py tests/test_cli/test_asset_management.py tests/test_cli/test_scoped_source_add.py`.
Expected GREEN: discover/manage/unmanage/restart on initially disabled fixtures
retains identity/local work; actual canonical Disable is integrated in P4. Project
source operations leave global sentinels byte-identical; metadata alone
cannot override actual missing/conflicting paths. Document local metadata schema
as implementation detail, never a third scope or new portable installation lock.

## P4. Shared operation plans, enable/disable, safe deletion and machine API

**Files:** create `asset_operations.py`; extend `asset_output.py` and
`asset_capabilities.py`; integrate all six command groups and per-kind facades.
Create `schemas/asset-inventory.v1.json`, `schemas/asset-operation.v1.json`,
`schemas/asset-finding.v1.json`, `tests/test_cli/test_asset_operations.py`,
`tests/test_cli/test_asset_delete_safety.py`,
`tests/test_cli/test_asset_machine_contract.py`,
`tests/test_cli/test_asset_vocabulary_compatibility.py`.

The action pipeline is one implementation:

```text
observe -> select exact instance/resources -> capability and ownership preflight
-> typed plan -> preview/authorization -> immediate expected-state revalidation
-> per-kind facade -> fresh affected-record merge -> reinspect -> typed result
```

- [ ] Define versioned operation/result contracts and stable reason codes: exact
  identity/scope/context/targets, expected resources, planned effects, preservation,
  remaining routes, failure/recovery and reload guidance. Both preview and Apply
  consume this plan, not separately assembled shell previews.
- [ ] Register canonical enable/disable with compatibility wrappers (not literal
  aliases), preserving old install/uninstall flags/defaults/exits and portable
  record effects. Before legacy Skills/Pi record pruning save verified durable
  local provenance. Canonical Disable retains scoped source records. New canonical mutations require explicit
  scope; `-g/-p` and `--scope` must agree. Keep old remove/import/reset behavior;
  help describes effects and canonical safer alternatives.
- [ ] Support unambiguous slug and exact instance ID selectors, project-only source
  batches, exact source/ref groups, noninteractive errors on ambiguity. JSON-v1
  stdout is pure JSON; old `--json` shapes remain unchanged; diagnostics stderr.
- [ ] Implement read-only stateless reviewed plan_token/semantic digest and
  `operations apply --plan-file` conditional execution from Spec §6. Compare only
  affected resource/record fingerprints under locks; never silently replan changed
  effects. Test separate processes, unrelated-record insertion and stale-plan refusal.
- [ ] Implement `operations recover --id --scope --mode inspect/resume/rollback`;
  inspect defaults read-only. Follow durable prepared/applying/observed-applied/
  committed/recovery-needed transitions, including crash after resource write but
  before journal persistence. Unprovable ownership is manual refusal; permanent
  deletion has no fictional rollback.
- [ ] Implement dry-run/read-only result and exit codes from Spec §6. Test
  no-TTY/EOF/decline, exact IDs, scope mismatch, informational versus blocking
  findings, partial operations, redaction and deterministic ordering.
- [ ] Disable retracts only owned selected exposure; keep managed source/provenance
  records. Test global exposure remaining, Standard shared reader resources,
  Instructions source-chain protection and unproven root/nested isolation refusal.
- [ ] Enable uses preserved target-scope content; do not reset it or falsely claim
  cross-scope acquisition transports dirty/unpublished work. Plan any materialized
  copy explicitly and preserve existing supported ref semantics.
- [ ] Implement exact `storage list/delete --id STORAGE_ID` and per-instance
  independent-unit deletion using Spec §5.5's positive per-kind units. Inactive
  selected member/self records are removable effects; live/dependent/foreign refs
  block. Historical created-storage receipts survive Unmanage without granting
  authority over changed or external content. Do not require Unmanage first.
- [ ] Refuse live projections, incomplete reference scan, external paths,
  shared-child deletion, foreign ownership, stale plans and unproven publication.
  Inspect ignored files, staged/unstaged/untracked data, refs/worktrees/submodules.
  Test successful whole-owned-checkout and exported owned non-Git deletion/restart,
  Pi definition-only and MCP local-definition deletion without touching endpoints.
- [ ] Implement explicit discard flags `--discard-local-work` and
  `--confirm-storage STORAGE_ID`, distinct from `--yes` or ordinary doctor repair.
  They never bypass references/ownership/stale-plan checks. Produce a verified
  preservation/export plan first; refuse if local work cannot be preserved/exported
  with verified ownership, rather than inventing recovery.
- [ ] Ensure MCP deletion cannot destroy a remote endpoint, Pi cannot recursively
  clear shared caches, and Instructions never deletes user canonical content.
- [ ] Journal narrow operations before mutation; revalidate forward/recovery
  resources and merge fresh records. Expose persistent interrupted/failed-recovery
  state; do not overwrite unrelated concurrent configuration or whole lock files.

Run: `uv run pytest -q tests/test_cli/test_asset_operations.py tests/test_cli/test_asset_delete_safety.py tests/test_cli/test_asset_machine_contract.py tests/test_cli/test_asset_vocabulary_compatibility.py tests/test_cli/test_cli_group_aliases_help.py`.
Expected GREEN: preview/action target parity, no implicit destruction, defined
machine envelopes/exits, stable old scripts and explicit truthful preservation.

## P5. Doctor total classification and safe repair across six kinds

**Files:** create `asset_doctor.py`, `commands/doctor_cmd.py`; integrate existing
six per-kind doctor modules, `skill_doctor.py`, `pi_extension_doctor.py` and CLI
registration. Create `tests/test_cli/test_asset_doctor_matrix.py`,
`tests/test_cli/test_asset_doctor_repair.py` and
`docs/agent-toolkit/doctor-coverage.md`.

- [ ] Implement the frozen F01-F22 minimum kind/action/severity matrix in Spec
  §8.1; add actual test nodes to the published coverage table. Product repairs are
  already decided there, not optional according to existing facade convenience.
  Explicit N/A/report-only reasons remain tested. Cover Global/Project and real
  native/translated/config mechanisms through equivalence fixtures.
- [ ] Implement pure diagnosis from reconciled inventory. Add aggregate doctor at
  explicit scope plus per-kind adapters. Informational discovered/disabled/modified
  content is not broken; incomplete coverage never produces all-clean.
- [ ] Make default doctor report-only and document this deliberate safety-default
  change for formerly prompting doctors. Retain `--no-fix` with precedence over
  repair flags. Add repeatable `--finding ID`, `--id`, explicit scope and `--yes`
  for exact noninteractive repair. New JSON exposes stable finding IDs,
  evidence/completeness, affected resources, action capabilities/refusals, redacted
  source details and exit severity. Keep legacy JSON shapes unchanged; no default
  doctor path prompts or writes without an explicit repair request.
- [ ] Required repair plans use P4 actions/ownership checks; extend facades where
  necessary for the mandatory matrix. Include MCP local materialization rebuild
  from valid authority without endpoint/secret calls, owned generated projection
  repair, stale-record repair and Pi owned filter correction. Preserve missing
  source/foreign-content cases as explicit report-only refusals.
- [ ] Expose legacy Instructions relocation only as `adopt-instructions-file`,
  distinct from lossless Manage, with source-chain and no-overwrite backup guards.
  Multiple actions require exact --action choice. No hidden whole-home cleanup,
  re-add-global shortcut or forced conversion.
- [ ] Test opt-in repair with default No, exact noninteractive IDs/scope/yes, no TTY,
  repeated repair, partial result, concurrent changes and forward/recovery errors.
  Reinspect before claiming findings resolved; preserve unsupported error severity.
- [ ] Assert no credential values, env dumps, secret provider calls, package imports,
  MCP connection probes, source fetch/reset or server starts during diagnosis.
- [ ] Verify three-way CLI/TUI/doctor parity over the same fixture and typed plan,
  including root `--path .`, custom slug and branch/tag/SHA selection preserved
  from #537. No human preview may advertise an action its executor cannot perform.

Run: `uv run pytest -q tests/test_cli/test_asset_doctor_matrix.py tests/test_cli/test_asset_doctor_repair.py tests/test_cli/test_asset_machine_contract.py`.
Expected GREEN: complete applicability table, shared effects, actionable refusals,
no false clean, no global dependency for project-only content and idempotent repair.

## P6. Human-native lifecycle TUI journeys and change indicators

**Files:** integrate six `*_state.py` readers; modify `app.py`, relevant widgets,
Info/column help and screens; add focused `screens/asset_actions.py` if existing
modals do not fit. Create `tests/test_tui/test_asset_lifecycle_journeys.py`,
`tests/test_tui/test_asset_action_queue.py` and
`tests/test_tui/test_asset_lifecycle_visuals.py`. No content-viewer screen/test module
or CLI diff registration is part of this issue.

- [ ] Render reconciled identities, orthogonal management/changes/health and
  qualified copies; preserve hierarchy and useful counters. Enabled count means
  unique assets with explicit selected-scope exposure, not links per reader.
- [ ] Explain global routes in project view, actual scope/context, source confidence,
  storage sharing, exact physical copies and running-session reload caveat in Info.
- [ ] Provide Add source toolbar/palette form for current explicit scope/context,
  kind-specific source inputs and Add from this copy (--from-id). Preview acquisition
  without enabling; no network/acquisition before explicit Apply. Instructions
  explains unsupported acquisition; MCP accepts env names, not credential values.
- [ ] Provide accessible action menu and keyboard/mouse activation, including Inspect
  storage/Delete checkout for exact units. All discoveries are inspectable and
  manageable or show an exact unsupported reason.
- [ ] Rename Ctrl+D/footer/palette to Preview changes and verify it shows queued
  Toolkit operations only. Render asset-scoped Changes indicators and path/status
  summaries; no content viewer/action/shortcut. Keep config secrets redacted.
  Deletion refusals identify affected paths and external Git/manual inspection
  guidance without requiring #540.
- [ ] Queue supported Manage/Unmanage/Delete plans alongside existing cross-kind
  enable/disable intents. Preview destructive targets and confirm separately.
  Preserve successful independent operations, failed intents, aggregate counts,
  cross-tab/scope queues and documented Refresh/Revert behavior.
- [ ] Drive all seven journeys from Spec §7 with real disposable content plus
  headless Textual pilot: initial 11 children, disable -> refresh -> restart ->
  re-enable; legacy duplicate; direct project add; global inherited exposure;
  blocked shared/dirty deletion; foreign unsupported content; failed recovery.
- [ ] Capture both 120x40 and 180x50 images. Inspect actual rendered images for
  scope, names, health, modified child, distinct pending/mixed indicators,
  inherited availability, actions, preview and recovery. Write per-image verdicts.

Run: `uv run pytest -q tests/test_tui/test_asset_lifecycle_journeys.py tests/test_tui/test_asset_action_queue.py tests/test_tui/test_asset_lifecycle_visuals.py tests/test_tui/test_cross_asset_save_revert.py tests/test_tui/test_cross_asset_review_regressions.py`.
Expected GREEN: one disabled retained item, no count growth, no loss of source or
edits, correct global caveat, usable keyboard workflows and truthful error states.

## P7. Adversarial recovery, round trips and installed-package verification

**Files:** create `tests/test_cli/test_asset_lifecycle_roundtrip.py`,
`tests/test_cli/test_asset_recovery_faults.py`,
`tests/test_cli/test_asset_lifecycle_packaging.py`; extend isolation, doctor and
TUI fixtures. Evidence index under `assets/verification/538/`.

- [ ] Complete AC01-AC15/test-node traceability and doctor applicability table.
  Each bug regression records genuine pre-fix failure and post-fix success.
- [ ] Inject failures at alias/projection creation/removal, config replacement,
  portable lock write, provenance write, journal transition and rollback writes.
  Insert unrelated records and retarget affected links immediately before writes.
  Assert safe refusal/targeted recovery and exact remaining truth after restart.
- [ ] Exercise stale reviewed-plan tokens across processes, same-path changed
  inode/target, same-source distinct clone, checkout ref change, foreign destination
  and unreadable sibling project records. Run genuine overlapping writers rather
  than only injected sequential callbacks. Verify lock-busy timeout and the stated
  noncooperating-writer limit. Unknown reference closure blocks deletion.
- [ ] Test protected snapshot modes/redaction, resource-write/journal-write crash
  gaps, metadata-commit gaps, whole-storage successful removal and partial permanent
  deletion cleanup. Recovered results must not claim deleted bytes were restored.
- [ ] Inspect fresh-process inventory after every lifecycle action. Verify metadata
  corruption/newer schema, local-only source, copied asset, external package and
  Instructions chain cases. No automatic migration during observation.
- [ ] Build ordinary wheel with `uv build`; install into an isolated temporary
  environment without overwriting the user's tool. Bind source/installed payloads
  to candidate SHA and wheel digest; run CLI/TUI/doctor lifecycle probes without
  importing from the source checkout or relying on pytest-only monkeypatches.
- [ ] Exercise macOS and Linux CI filesystem/config behavior; use platform-specific
  assertions where symlink/permission semantics differ. Keep all roots host-portable.
- [ ] Run focused tests, then `uv run pytest -q` and `make docs-build`. Record skips
  and failures accurately; do not weaken a required gate for unrelated failures.

Expected GREEN: all required regression/integration/compatibility checks, complete
fault/recovery matrix, correct installed behavior and outside-root preservation.
Human image-based verdicts are required in addition to headless assertions.

## P8. Vocabulary rollout, documentation and final review

**Files:** current `README.md`, `AGENTS.md` glossary pointer, `GLOSSARY.md`,
`docs/glossary.md`, `docs/agent-toolkit/{cli,tui,skill-lock,lock-files,roadmap}.md`,
all six `docs/asset-types/*.md`, lifecycle/compatibility/doctor coverage pages,
`mkdocs.yml`, generated-document inputs, `scripts/capture_docs_tui.py` and any
tracked usage scripts/tests identified by the compatibility audit.

- [ ] Publish concise definitions from root glossary without duplicated competing
  semantics; preserve old anchors. Transition proposed labels only when capability
  actually ships. Document two scopes, copies versus exposure, Manage versus Add,
  Unmanage versus Delete, inheritance and disable-not-unload.
- [ ] Audit install/uninstall/library/remove/import/reset references in maintained
  help/CLI/TUI/examples, instructions and utility workflows. Keep historical
  reports/release notes untouched. Generated harness pages change via generator.
- [ ] Lead with enable/disable; retain legacy aliases and semantics throughout the
  current major line plus at least two following minor releases. Any later removal
  needs separate explicit breaking-release approval. Do not hand-bump versions.
- [ ] Document exact capability exceptions, explicit new mutation scopes, legacy
  defaults, JSON-v1 envelopes/exit codes and safe automation examples. Include
  complete discover -> manage -> enable -> disable -> unmanage/delete examples.
- [ ] Run `make docs-build`, full `uv run pytest -q` and normal pre-push hook.
  Bind evidence to the exact published candidate and nonempty hosted CI result.
- [ ] Obtain fresh independent PR review for product clarity/compatibility and
  preservation/security/recovery, in a visible Herdr reviewer pane. Re-run issue
  gates at PR head; resolve every required finding or obtain an authorized waiver.
- [ ] Update durable project memory with the final identity/lifecycle decision and
  discovered nontrivial failure lessons. Attach evidence index, coverage table,
  visual verdicts and installed-wheel proof to implementation PR.
- [ ] Only then seek merge-ready QA. No self-approval, automatic merge, live tool
  reinstall, installed-asset repair or release is part of this plan's execution.

## Acceptance and evidence handoff

Required implementation commands:

```bash
uv sync --all-extras
uv run pytest -q
make docs-build
uv build
```

Focused commands per milestone are additional, not replacements for the full gates.
New test paths in this plan are implementation deliverables, not existing tests
claimed to have run during preparation. Do not run unfinished-path commands as a
pretend readiness check. Existing pre-push full-suite hook must not be bypassed.

Evidence index must contain: candidate/base SHAs and dependency proof; red/green
logs; six-kind compatibility and doctor coverage tables; full suite/docs results;
outside-root sentinels; fault-injection/restart outcomes; wheel digest and isolated
installed probes; all visual scenarios at both sizes with actual-image verdicts;
independent review findings and dispositions; remaining unsupported capabilities.

Preparation completion means firm spec/plan/issue plus resolved independent
critical review, not passing unimplemented product tests. Execution remains gated
on PR #537 merge and fresh-base verification; build-ready is not implementation
or merge authorization.
