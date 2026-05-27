---
title: Bitwarden skill relies on session TTL expiry instead of an explicit bw lock
date: 2026-05-25
category: tooling-decisions
module: bitwarden-skill
problem_type: tooling_decision
component: tooling
severity: medium
applies_when:
  - Designing the session lifecycle for a skill that wraps an unlock/lock-style CLI (bw, gpg-agent, ssh-agent)
  - Deciding whether a skill should explicitly tear down a credential session or let a time limit expire it
  - Weighing convenience (one unlock per conversation) against credential-exposure window
tags: [bitwarden, session-management, ttl, security-tradeoff, skill-design, credential-lifecycle]
---

# Bitwarden skill relies on session TTL expiry instead of an explicit bw lock

## Context

The bitwarden skill (`~/GitHub/skill_library/bitwarden`, repo `ajanderson1/bitwarden-skill`) gated every vault command behind a two-file session: `/tmp/bw_session` (the raw key, mode 600) plus `/tmp/bw_session.expires` (an epoch deadline). A "Step 1 prelude" pasted at the top of each Bash call deleted both files and exited non-zero once `NOW >= EXP`, forcing a re-unlock. The original TTL was 15 minutes, and a mandatory "Step 3: lock the vault" ran `bw lock` plus an `rm` of both files at the end of every task.

The question raised: if the file-TTL gate already works, extend the TTL to 1 hour and drop the explicit lock step entirely — just let the session time out each time.

## Guidance

**Two protections were conflated and are in fact different:**

- **`bw lock`** invalidates the session key inside the `bw` daemon. After it runs, the key is cryptographically dead.
- **The file-TTL gate** only stops *the skill* from reusing the cached key. It deletes the `/tmp` files but does not touch the daemon's unlocked state.

The decision made (deliberately, per user choice): **extend TTL 15 min → 1 hour AND drop the explicit `bw lock`/`rm` step**, relying on the gate to expire and self-clean. The skill keeps a manual hard-lock snippet for the "lock now" case, but it is no longer the default end-of-task action.

This was verified empirically before changing anything:

- The TTL gate logic is correct: tested missing / valid / expired / boundary (`NOW == EXP`) cases — it distinguishes all four and self-cleans both files on expiry.
- A session key is dead once `bw lock` has run: a leftover `/tmp/bw_session` key issued against a locked vault returned `"Vault is locked."` — confirming `bw lock`'s protection is real and not reproduced by file deletion alone.

## Why This Matters

Dropping `bw lock` is **not** a pure simplification — it is a security-posture change, and it must be recorded as a deliberate trade-off rather than slipped in as cleanup:

- With the old flow, the vault was hard-locked the moment a task finished. The key was dead immediately.
- With the new flow, the vault stays **unlocked in the `bw` daemon** and the live key sits in `/tmp/bw_session` (mode 600) until the TTL elapses. Anything that can read that file — or inherit `BW_SESSION` — can decrypt the vault for the rest of the window.
- Extending the TTL to 1 hour widens that live-key window **4×** (15 min → 60 min).

The trade was accepted for convenience (one unlock covers an entire conversation, no per-task ceremony), but the skill now documents the exposure explicitly and keeps a manual `bw lock --nointeraction && rm -f /tmp/bw_session*` for the hard-lock case. The general lesson: **when a "remove the lock step" request lands, separate the soft protection (does the agent reuse the key?) from the hard protection (is the key alive in the daemon?) and surface the difference to the user before acting — don't treat "the timeout works" as proof the lock is redundant.**

## When to Apply

- Any skill wrapping an agent-style credential CLI where "unlock" leaves a live key reachable on disk or in a daemon
- Whenever a request to "drop the cleanup/lock step because the timeout handles it" appears — the timeout almost never reproduces the cryptographic teardown
- When choosing a TTL: every increase directly multiplies the worst-case live-credential window

## Examples

Old end-of-task step (hard teardown, default):

```bash
bw lock --nointeraction 2>/dev/null
rm -f /tmp/bw_session /tmp/bw_session.expires
```

New default: do nothing — the Step 1 gate expires and removes the files on the next vault command after the TTL. The unlock TTL changed from `900` to `3600`:

```bash
# Default TTL: 1 hour. Override by exporting BW_UNLOCK_TTL_SECS before this call.
TTL=${BW_UNLOCK_TTL_SECS:-3600}
```

Hard-lock retained as a manual escape hatch (run only when locking immediately matters):

```bash
bw lock --nointeraction 2>/dev/null
rm -f /tmp/bw_session /tmp/bw_session.expires
```

## Related

- Skill source: `ajanderson1/bitwarden-skill` (`SKILL.md` → Session Management; `references/unlock-procedure.md`)
- Related auto-memory: GIT_* env-leak and /tmp-clone-origin notes share the "verify the boundary before trusting it" theme
