# Expanded skill catalogue collections

Date: 2026-10-25. Scope and failure policy approved by AJ in conversation; implementation plan pending review.
Baseline: canonical GitHub `origin/main`, `74a41448cab89586fc4b048bd4d423da455e61a1` (6.1.0).

## Intent

An advertised monorepo expands just like a library monorepo. The user chooses individual children or uses the existing parent All/None control. Acquisition adds a selected missing skill to the library before enabling it. Already-acquired skills remain ordinary library skills; catalogue membership is not another user-facing lifecycle state.

Reuse Python/Click, Textual, existing source registration, projections and collection transactions. This is a skills-only increment, not the separate proposed multi-kind catalogue project.

## Identity and inventory

- A collection is identified by normalized Git repository URL plus the configured ref. A child additionally requires its repository-relative directory. Names and catalogue keys are labels/lookup identifiers, not proof of source identity.
- Preserve conservative URL normalization. Different hosts and configured refs must not merge merely because owner/repository names or current commit IDs coincide. Equivalent ref spellings are not automatically adopted.
- Join library/scoped inventory with advertised children, then derive expandable presentation groups. An acquired child occupies one library row, retaining its slug, backing, local work and exposure. Existing provenance conflict checks remain authoritative; changed recommendations do not retarget local content.
- Group catalogue-only siblings and mixed library/advertised siblings with the existing collection controls. Preserve no-subscription behavior. A known collection can lose its parent presentation when only one child remains; the surviving child identity/content does not change.
- The existing version 1 manifest's child entries provide expansion metadata. No schema change, persisted collection asset, whole-repository payload or new CLI verb is required. The collection includes known advertised/library children, not undiscovered upstream files.
- Expansion, filtering and inventory building never acquire skills or probe their upstream repositories. Existing live catalogue fetching remains bounded and read-only. Failed catalogue reads hide catalogue-only rows with a warning, never a stale listing fallback; acquired inventory remains usable.
- Avoid redundant catalogue-membership badges for library skills. Keep source/selector conflicts and maintenance guidance available in Info.

## Selection and pending intent

- Existing individual cells, parent All/None, mixed selection, collapse and filter behavior apply to the union of known children.
- Parent All/None affects all supported members, including collapsed/filter-hidden children. Unsupported/skipped/unmanaged cells remain excluded.
- Queue exact child identities and their original scope/harness targets. Later advertised children never silently join an already-queued All operation.
- Preserve pending identities across asynchronous inventory results and acquisition regrouping. Refuse changed source/ref/path, conflicting local identity or changed subscription for catalogue-dependent work; never retarget an intent to another child sharing its slug.
- Revert performs no acquisition. Scope changes retain the established cross-scope queue contract and never redirect existing operations to another scope.

## Apply and failure boundary

1. Obtain one fresh catalogue snapshot for catalogue-dependent pending work. Validate selected advertisement identities and subscription URL/ref against queued intent before acquiring anything in the affected collection.
2. Preflight supported targets, known real-root/nested isolation rules and conflicting destinations. Catalogue metadata does not override ownership or exposure limits.
3. Acquire only selected missing children through the existing registration facade. Reuse proven backing and recorded local identities without advancing HEAD, replacing pins or discarding work. Unselected advertised siblings remain unacquired.
4. Regroup actual acquired/scoped records and apply complete desired selections for the requested harnesses through the existing collection transaction. Do not pass unacquired virtual children to an engine that materializes every supplied member. Preserve already-enabled siblings and unrelated targets unless explicitly changed.
5. The failure unit is one repository/ref collection in one scope, across its requested harness targets. If a selected child fails preflight/acquisition, make no enable/disable changes for that unit. Projection failure restores that unit's affected links/records through the existing journal. Other unrelated collections/scopes may succeed.
6. Safely acquired library content is retained on failure; acquisition is not rolled back by deleting shared backing. Report retained library content separately from failed exposure. Preserve failed pending intents and make retry/Revert available.
7. Local-only operations do not require catalogue availability, even if the skill was originally acquired through it.

Removing a library entry does not edit the publisher's catalogue: a still-advertised child remains available to acquire again. Delisting, unsubscription and catalogue outages do not remove library content or retract exposure. Existing private/legacy backing, foreign destinations and ambiguous-copy safeguards remain unchanged.

## Git checks and Info

- `skills check [SLUGS...] -g|-p [--json]` works for registered Git-backed skills without requiring catalogue provenance. With no explicit names, target registered Git-backed entries in the selected scope; malformed, missing or non-Git backing is not a successful clean result.
- Retain existing CLI scope rules, JSON result fields, timestamped local observations, batching of identical remote queries, pin protection, origin verification, failure/staleness behavior and nonzero unknown/error results.
- Local working-tree condition and upstream revision are different facts. Clean does not imply latest. Different SHAs do not prove a child changed, that local history is behind, or that a fast-forward update is safe.
- Info provides the actual local revision, timestamped observations and exact CLI commands even without catalogue association. Do not add background upstream checks, TUI updates or automatic source adoption.

## Boundaries and ownership

- No new dependency, subscription, asset kind, catalogue format or persisted collection registry.
- No multi-kind implementation, hosted catalogue edits, live HOME/config/skill changes, merge, release, installed Toolkit replacement or hand-authored version bump.
- Preserve the original checkout's local documentation commit and uncommitted files, including its project lock. Keep the existing demo worktree intact. Build in the isolated `feat/catalog-collections` worktree based on canonical 6.1.0.
- The separately reproduced library-removal bug involving active project consumers is not repaired by grouping rows. Do not claim it fixed or silently broaden this increment into deletion-policy redesign. Tests of advertisement reappearance remove only unused library children.

## Acceptance

Use disposable HOME/config/assets and local Git remotes. Cover catalogue-only and mixed collections; single-child to full-repo registration; custom slugs and local work; individual/parent/mixed/filter/collapse controls; no unselected acquisition or duplicate backing; late-result and stale-intent handling; one Apply snapshot; acquisition/projection failures and retry; independent successful collections; unsupported targets, collisions and root/nested refusal; offline local operations; unused-library removal revealing an advertisement; catalogue-independent Git checks/Info; unchanged no-subscription behavior.

Run focused tests RED to GREEN, the full pytest suite, strict docs build and package build. Preserve historical reports/release notes and generated harness views. Record verification commands and exact source/artifact identity for any validation build; do not install it live.
