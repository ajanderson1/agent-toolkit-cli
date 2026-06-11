# #365 — architecture guard bans BOTH `kind` and `asset_type` discriminators

**Tier: light** (paragraph-sized spec). Issue: #365.

## Problem

`tests/test_cli/test_asset_type_architecture.py` pins the per-asset-type-module
design by asserting that install entrypoints accept no runtime discriminator
parameter. PR #363 (the #355 `kind` → `asset_type` rename) translated the three
asserts to ban only `asset_type` (lines 111, 126, 139). During the vocabulary
transition, a branch authored with pre-rename vocabulary — or an agent
pattern-matching on older code/specs in history — can reintroduce the rejected
discriminator under its OLD name, `kind=`, and the guard stays green. The #355
grep acceptance criterion caught `kind` once at merge time; CI runs pytest only,
so this file is the sole standing guard.

## Design (approved by PM, scope extended per picker)

Replace section 2's two hand-written tests (`agent_install` + `skill_install`
only) with **one parametrized test over all four install modules**, driven by a
per-module entrypoint map — the public verb surfaces genuinely differ:

| module | entrypoints |
|---|---|
| `skill_install` | `plan, apply, install, uninstall` |
| `agent_install` | `plan, apply, install, uninstall, remove` |
| `instructions_install` | `plan, apply, uninstall` |
| `pi_extension_install` | `plan, apply` |

Each mapped entrypoint is asserted to **exist** and to accept **neither**
`kind=` nor `asset_type=`, by exact parameter-name membership against a
module-level `BANNED_DISCRIMINATORS = ("kind", "asset_type")`. Section 3's
`_install_core.plan()` assert gets the same both-spellings loop.
`_install_core._doctor_hint(asset_type_noun=...)` is untouched — a display noun
on a private helper; exact-name matching never sees it.

One test file changed; entrypoint-existence coverage strictly widens
(instructions/pi-extension gain it), never weakens.

## Acceptance criteria

1. All four install modules' mapped public entrypoints are asserted to exist
   and to ban both `kind=` and `asset_type=` by exact parameter name.
2. `_install_core.plan()` is asserted to ban both spellings.
3. Guard proven RED in development: temporarily adding a `kind=` parameter to
   one covered entrypoint fails the suite; reverted before commit.
4. Full pytest suite green; **no non-test files changed**.

## Out of scope

- The #355-follow-up grep-based CI terminology gate (separate issue if wanted).
- Banning further spellings (`asset_kind`, …) — no evidence of use.
- Any runtime-module change.
