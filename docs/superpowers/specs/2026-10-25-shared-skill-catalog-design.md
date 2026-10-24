# Shared skill catalog — minimal design

Status: approved by AJ on 2026-10-25, including autonomous build, review, commits
and PRs for Toolkit and the private catalog. No merge or release authorized.

## Goal

Add one optional shared Git-backed skill catalog to Toolkit. Host its repository
on AJ's Tailscale network. Keep skills in their upstream repositories and reuse
Toolkit's existing library, enable/disable, projection and update behavior.
This is an incremental skills feature, not a new package manager.

Follow GLOSSARY.md. Add/remove concerns library membership; enable/disable
concerns harness exposure. Keep existing command spellings and scope semantics.

## Basic behavior

- **No subscription:** Toolkit works as today, including CLI, TUI and doctor.
- **Subscription:** configure one Git URL and optional catalog ref through CLI.
  Proposed simplicity choice: one user-global subscription in Toolkit's shared
  behavior configuration, visible across projects; no project-specific catalog
  settings. This does not change project/global harness exposure choices.
  No credentials in the catalog; use existing Git authentication.
- **Browse/refresh:** read a freshly obtained catalog revision. Display its skills
  alongside local inventory. Do not download skill repositories just to browse.
  One read per inventory load/explicit refresh, not per row render or keystroke.
- **Catalog unavailable or invalid:** hide catalog-only rows and show a warning.
  Never fall back to stale catalog listings. Acquired library entries remain
  visible and usable. Bound network waits; do not hang the interface.
- **Matching local entry:** show one row when repository, skill directory and
  configured ref match. Preserve existing slugs, backing and projections.
  Proposed simplicity choice: browsing only joins observations, without writes.
  Explicit catalog Add/Enable records a small provenance association when reusing
  an exact existing managed entry; it does not change source selection, ownership,
  content or existing exposure. Associated entries participate in the same CLI
  update checks and catalog-difference guidance as newly acquired catalog skills.
  Preserve that provenance after unsubscription; do not adopt unmanaged entries.
- **Name/source conflict:** report it; do not overwrite, adopt or guess. Reuse
  existing source-conflict refusals rather than build a resolution interface.
- **Add:** obtain/register the selected upstream skill without enabling it.
- **Enable:** obtain missing content, then create only the selected scope/harness
  projections through existing engines. A pending TUI toggle does no acquisition
  until Apply. Revert performs no acquisition.
- **Disable:** retract selected exposure, retaining library content. Independent
  global/native exposure may still make the skill available.
- **Nested monorepo skill:** identify its exact repository-relative directory.
  Reuse shared-parent support; selecting one child does not enable its siblings.
- **Enable existing content:** reuse recorded backing, without implicit update.
- **Catalog entry removed or subscription removed:** retain acquired content,
  local records, local work and projections. Do not delete or disable anything.
- **Failure/retry:** use existing ownership/cleanup safeguards. No successful
  enable state for failed content acquisition or projections; preserve foreign
  destinations and existing work. A changed catalog selection before Apply
  must refuse/reselect, not silently obtain a different source.

## Catalog repository

A small versioned JSON file lists a stable key, description, upstream Git source,
exact skill directory and optional ref for each skill. Use current source parsing.
Reject malformed/unsupported manifests visibly; never execute catalog content.
No skill payloads, machine paths, secrets or enabled-state records in the catalog.
No repurposing of existing local locks as remote catalog listings.

Exact filename/field spelling and internal module placement are builder choices.
Only one subscription is supported in this first slice. No new runtime service.

## Updates — confirmed minimal approach

AJ confirmed CLI-only checks on 2026-10-25. A CLI check records update observations
for catalog-acquired local skills. The TUI only displays the result and its timestamp;
it does not automatically query every skill upstream. Ordinary catalog discovery
remains live as required above. Local check records are not cached catalog rows.

- Compare each downloaded skill against its locally recorded upstream selector.
- Report current, update available, pinned, or unknown/check failed, with existing
  local-work/conflict information. Historical checks are explicitly timestamped,
  not presented as proof of current remote state.
- Update content through existing `agent-toolkit-cli skills update` behavior and
  correct scope. No TUI update control and no implicit update on enable/refresh.
- Catalog source/ref changes are reported separately; never silently switch local
  backing or pins. Ordinary update does not adopt a changed catalog selector.
- Preserve existing update, merge, ownership, pin and shared-checkout safeguards
  and limitations. Do not redesign them in this feature.
- Check once per shared upstream in a batch where practical. A newer parent
  revision need not mean a nested skill changed; label revision comparison
  honestly rather than promise content-level comparison in this first slice.

Exact new check-command syntax is a builder choice; document it and test help.
No dedicated catalog refresh command is needed: catalog reads are always live.

## TUI Info and doctor

Info shows catalog provenance when recorded, upstream source/directory/ref, local
revision, update-check result/time, relevant warnings and the exact CLI command
for checking/updating that backing. Do not add a new screen or update queue.

Doctor recognizes catalog-only entries as not acquired, not missing content.
Acquired entries receive existing content/source/projection checks. No subscription
is normal; catalog unavailability is distinct from corrupted local state.
Available updates and changed catalog selectors are advisory, not automatic repairs.
Preserve existing repair and `--no-fix` contracts. Doctor never acquires, enables,
updates, resets or changes a source/ref merely because of catalog metadata.
No new skill-upstream network checks in doctor; reuse timestamped observations.

## Demo and tests

AJ confirmed a private `skill-catalog` repository on the existing Broadpeak Gitea
service over Tailscale. After full design approval and verifying the exact remote
and access, create the separate demo catalog repository. Seed two
verified public upstream skills from one monorepo to exercise nested selection.
Check real paths, license and required supporting files; pin a full commit for
repeatable demo acquisition. Both skills start disabled. Do not execute scripts.

Use disposable local Git remotes for deterministic updates/offline tests. Cover:

- No subscription and existing CLI/TUI/doctor regression behavior.
- Live discovery; offline/auth/timeout/invalid-manifest behavior; disappearance of
  catalog-only rows after failed refresh while acquired rows remain usable.
- Dedup/conflicts, selected child/scope/harness, pending Apply/Revert, safe retry.
- CLI check/update, timestamps, pins/local edits, shared backing and Info guidance.
- Removed listing/subscription retains library content and exposure.

Run focused tests, full pytest and strict docs before completion. Update current
reference/help with actual behavior. No package version changes by hand.

## Complexity explicitly deferred

- LiteLLM integration, well-known discovery/publication, archives and HTTP hosting.
- Multiple catalogs, profiles, central enforcement and other asset kinds.
- Automatic/background upstream checking, automatic updates and daemons.
- New source/ref adoption workflow; report differences and use existing safe CLI
  operations. If no existing safe operation suffices, explain the limitation.
- Per-skill subtree update analysis, semantic release selection and version solver.
- Deduplicating unprovable URL aliases or merging separate private backing trees.
- Multi-version backing redesign, lock migration, scope changes or CLI verb renames.

If existing machinery cannot safely handle a catalog case, refuse with a clear
explanation and record the limitation rather than widen scope silently.

## Clarifications resolved

AJ confirmed both on 2026-10-25:

1. CLI-only upstream checking with timestamped TUI Info is sufficient; automatic
   skill-upstream checks are deferred.
2. Use the existing Broadpeak Gitea service over Tailscale and a private
   `skill-catalog` repository. Resolve the exact remote and local checkout before
   hosting; do not change the service or expose the repository publicly.

## Builder check and proposed defaults

A fresh read-only reviewer identified subscription scope and provenance for reused
entries as additional gaps. The proposed choices above settle both minimally:
user-global subscription, and provenance recorded only on explicit catalog
Add/Enable, never browse. These are author recommendations for AJ to confirm or
correct, not previously agreed requirements. No extra settings UI or adoption
workflow is included.

All proposed choices remain subject to approval. No host access, remote repo
creation or product implementation has occurred. After answers and approval,
finalize/commit this spec and write the implementation plan before building.
