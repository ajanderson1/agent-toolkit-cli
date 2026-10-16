---
title: Instructions installation truth must not authorize deleting its source chain
date: 2026-10-16
category: docs/solutions/logic-errors
module: instructions lifecycle
problem_type: logic_error
component: tooling
symptoms:
  - Manual canonical pointers disagreed with lock-driven inventory
  - A harness slot could resolve to canonical while also supporting its source chain
root_cause: logic_error
resolution_type: code_fix
severity: high
tags: [instructions, symlink, canonical, source-preservation, tui]
---

# Instructions: installation truth and deletion authority are different

Issue: #525. Independent specification review: Herdr pane `w3D:pK`, reviewed code
`899301a3f9fa63c3da3f05092d847ed979509646` and issue snapshot
`2026-10-16T14:47:04Z`. PM accepted the reviewer's P1 resolution before execution.

## Problem

Instructions had no upstream acquisition model, but kept a second installation
record in a lock. That made manual symlinks invisible to CLI status and
incorrectly "stray" in doctor, and made TUI save reconcile unrelated pointers.

Removing the lock is not enough: `AGENTS.md → CLAUDE.md → user-source.md` means
both files resolve to the same terminal target. That is installation truth, but
not permission to remove `CLAUDE.md`: deletion breaks canonical readability.

## Resolution

- Derive inventory from bounded documented pointer slots. Keep canonical content
  and its external source chain user-owned; do not invent a replacement registry.
- Pass explicit link/unlink intent to the shared API. Never infer a pruning set
  from an absent record. Leave legacy files unchanged, even if malformed.
- Before batch mutations, walk canonical's symlink chain, including directory
  components, comparing physical symlink-node device/inode identities. Spelled
  paths miss case/Unicode aliases; final resolved source identities conflate
  distinct pointers. Refuse the entire removal batch if any requested slot participates;
  fail closed if the chain cannot be safely inspected. Order requested dependent
  pointers before requested referents and recheck exact device/inode/raw-target
  snapshots before unlink, so an earlier removal cannot strand a requested link.
  Never prune or rewrite an unrequested dependent to make a batch look successful.
- Keep directory-slot identity separate from node identity. Distinct directory
  entries can hardlink the same symlink inode: deduplicate intent using physical
  parent device/inode plus the fixed matrix leaf, and order dependencies using
  traversed entries. For alternate traversal spellings, bounded parent lookup
  prefers exact names, validates node identity and refuses ambiguous matches.
  Existing action slots must use that same actual-entry lookup: a literal
  `CLAUDE.md` key misses a dependency through an actual stored `claude.md` entry
  on case-insensitive filesystems. Only absent slots retain literal leaves.
  Planning absent parents uses resolved paths without creating directories.
  Canonical protection intentionally remains conservative: it may refuse a
  distinct hardlinked sibling sharing a source-chain inode. This safe over-refusal
  is not authority to weaken the source guard or mutate an unrequested link.
- Separate pointer ownership from canonical usability: an owned dangling link is
  still visible/removable, while missing source content is reported unhealthy.
- Preserve doctor adoption as a separate opt-in transaction with backups and
  slot-local rollback. TUI partial I/O failures reload disk truth and retain only
  unsatisfied intents.

## Regression coverage

`tests/test_cli/test_instructions_lockless.py` and
`tests/test_tui/test_instruction_lockless.py` exercise direct/multi-hop canonical
source chains, whole-batch refusal, unchanged links/bytes, canonical readability,
manual installs, malformed legacy records, scope isolation and partial retry.
`test_instructions_pointer_identity.py` and `test_instruction_pointer_identity.py`
add native case/Unicode alias and portable simulated-node-identity regressions,
directory-component protection, requested pointer dependency ordering and partial
removal retries. Native alias checks skip explicitly where the filesystem does not
support those aliases; portable emulation is not native-filesystem proof.

Fresh review `w3D:pX` of `1510c36` reproduced both identity and ordering gaps after
the initial suite passed; neither finding was waived. Worker red/green checks do
not replace the required corrected-head independent recheck/full gate.

`test_instructions_directory_slots.py` and `test_instruction_directory_slots.py`
cover native hardlinked symlink entries through API/CLI/TUI in both scopes,
independent and genuinely dependent removals, distinct-entry opposing intents,
actual shared-slot coalescing/refusal, parent case aliases, stored-lowercase
requested chains (both caller orders), and read-only missing parents. Portable ambiguous-spelling emulation is explicitly not native filesystem
proof. Fresh b93 review found inode-based deduplication lost an action and also
manufactured dependency cycles; both must be corrected together.

Other Instructions tests cover adoption, relative/dangling/cyclic pointers and
source-backed asset architecture remaining intact. All homes/projects are disposable.
