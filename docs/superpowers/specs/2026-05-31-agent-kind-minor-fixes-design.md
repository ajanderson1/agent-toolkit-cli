# Design — agent kind (minor) fixes · issue #304

**Mode:** `--auto`  ·  **Branch:** `fix/304-agent-kind-minor-fixes`  ·  **Type:** `fix`

Three small, independent defects on the `agent` kind, all surfaced by the same
v3.5.0 sandbox smoke test that turned up #303 (the serious uninstall data-loss
bug, tracked separately). None of these is data-destructive; they are honesty /
consistency defects.

## Problem statement

### Bug 1 — `agent status` scope-default mismatch
`agent status` (no scope flag) can report an empty library while `agent list -g`
shows the agent present and projected. The two commands resolve scope through the
**same** helper (`scope_and_roots(..., read_only=True)`), so they are *not*
literally inconsistent — but the reporter compared **`list -g`** (explicit global)
against **bare `status`** (default scope). When cwd contains an `agents-lock.json`,
bare `status` defaults to *project* scope and finds that project's (empty/other)
lock, while `list -g` reads the global library. Two further honesty gaps compound
the confusion:

- **Empty-lock silence.** When the lock file *exists* but `lock.skills` is empty,
  `status` prints **nothing at all** (the render loop simply doesn't iterate),
  whereas `list` prints `no agents found`. A blank screen reads as "broken",
  not "empty".
- **Scope-blind empty message.** `status`'s only empty message is
  `no agents found` on `FileNotFoundError`, with no indication of *which scope*
  was searched — so the user can't tell they're looking at the wrong lock.

This is the same family as the documented `skill list/status` scope trap.

### Bug 2 — `agent add` records a lock entry pointing at a missing content file
`add_cmd.py:112` hardcodes `agent_path=f"{final_slug}.md"` and never checks that
file exists in the freshly-cloned canonical directory. If the source's content
file is named anything else (e.g. `AGENT.md`), `add` still writes a lock entry
that points at an absent file and prints success. A later
`agent install <slug>` then **prints "installed" while projecting nothing**, and
only `agent doctor` catches it (`missing-content-file`) — too late. This is the
#283 lock-honesty class: never write a lock entry that asserts something the
filesystem contradicts. `doctor_cmd.py:74-79` already owns the canonical check
(`canonical / f"{slug}.md"` must exist); `add` should apply the same check at
add time and fail loud.

### Bug 3 — TUI skill grid still shows the `universal` display label
The v3 `universal`→`general` rename reached the CLI (alias) but the TUI's
*human-readable* strings lag:
- `widgets/skill_grid.py:552` renders the column header `"Universal"`.
- `column_info.py:48` renders the column-info modal title `"Universal bundle"`.

Display-label only. The literal token `"universal"` is load-bearing — it is the
bundle-toggle key compared in `INTERACTIVE_AGENTS` (`skill_state.py:34`), the
detection branches (`skill_state.py:103`, `skill_grid.py:329,477,484,552`), and
the `COLUMN_INFO` dict key (`column_info.py:72`). **Do not rename the token** —
renaming it breaks bundle detection. Only the rendered text changes.

## Goals

1. `agent status` is honest and consistent with `agent list` about scope and
   empty state — no blank screen, scope named in every empty message.
2. `agent add` fails loud at add time when `<slug>.md` is absent in the source,
   rather than recording a lock entry that points at a missing file.
3. TUI skill grid header + column-info modal read **General**, matching the v3
   rename, without touching the load-bearing `"universal"` token.

## Non-goals

- No change to `scope_and_roots`'s default-scope *policy* (read verbs default to
  global outside a project; that convention is intentional and cross-cutting).
  Bug 1 is a message/empty-state fix, not a policy change.
- No auto-detection of alternative content-file names in `add` (e.g. picking up
  `AGENT.md`). Fail-loud is the chosen behaviour; auto-detect is explicitly out
  of scope (a flexible system where a boring default suffices — the user passes a
  conforming source or `--slug`).
- No rename of the internal `"universal"` token anywhere.
- #303 (uninstall data-loss) is out of scope — separate issue.

## Approach

### Bug 1 — `status_cmd.py`
- After resolving scope, when the lock load yields **no matching agents**, print
  a **scope-named** empty message (mirroring `list`'s `no agents found` but
  naming the scope), covering both branches:
  - `FileNotFoundError` (no lock file), and
  - lock exists but `targets` is empty (currently silent).
- Message form: `no agents in the <scope> library` (matches the wording the
  reporter saw, and names the scope so the wrong-lock case is obvious).
- When `slugs` were requested but none matched, keep that distinct (don't claim
  the library is empty if the user filtered to a non-present slug) — emit a
  per-requested-slug `not found` line, consistent with how other verbs report
  an unknown slug. (If the existing convention is simpler, match it.)

### Bug 2 — `add_cmd.py`
- After the clone block (and after the idempotent-existing short-circuit), before
  building the `LockEntry`, check `(canonical / f"{final_slug}.md").exists()`.
- If absent → raise `click.ClickException` with a clear message naming the
  expected file and the slug, and **do not** write the lock entry. Mirror
  doctor's `missing-content-file` detail wording so the two are recognisably the
  same check.
- Leave the clone on disk (it's the canonical; a re-run with a correct `--slug`
  is idempotent) — or clean it up if that's the established pattern; match
  whatever `add` already does on its other failure paths.

### Bug 3 — `skill_grid.py` + `column_info.py`
- `skill_grid.py:552`: `"Universal"` → `"General"` (display string only).
- `column_info.py:48`: title `"Universal bundle"` → `"General bundle"`.
- Token `"universal"` and all detection comparisons unchanged.

## Test plan (TDD — tests first, per project convention)

CLI tests live in `tests/test_cli/`, TUI tests in `tests/test_tui/`.

1. **Bug 1 — status scope + empty state**
   - `agent status -g` with an empty global lock → prints a scope-named empty
     message (not blank).
   - `agent status -g` after adding an agent globally → lists it (parity with
     `list -g`).
   - `agent status` from a project dir with an empty/absent project lock → message
     names the *project* scope (so the wrong-scope case is legible).
2. **Bug 2 — add validation**
   - `agent add <local-source-with-no-matching-slug.md>` → raises, non-zero exit,
     message names the expected `<slug>.md`, and **no lock entry written**
     (assert the lock has no entry for the slug afterward).
   - `agent add <local-source-with-matching-slug.md>` → succeeds, lock entry
     written (happy-path regression guard).
3. **Bug 3 — TUI label**
   - Headless render assertion that the grid header contains `General` and not
     `Universal`; column-info modal title is `General bundle`. Assert the
     `"universal"` token still drives detection (existing bundle tests stay
     green).

## Risk / blast radius

- Bug 1: message-only + one new empty-branch; cannot change projection or scope
  policy. Low risk.
- Bug 2: adds a failure path to `add`. Risk = a *previously-"successful"* add of a
  malformed source now fails — which is the intended correction (it was silently
  broken). Happy path unchanged.
- Bug 3: pure display string. Risk is only if a test asserts on the old literal
  `"Universal"` header — update those assertions. Zero behavioural change.

## Acceptance

- `agent status` parity with `agent list -g` for a globally-added agent; no blank
  output for an empty lock; scope named in empty messages.
- `agent add` of a source whose `<slug>.md` is absent fails loud with no lock
  entry; happy path still writes the entry.
- TUI header + modal read "General"; bundle detection (token `"universal"`)
  unchanged and existing TUI tests pass.
- `uv run pytest -q` green; `ruff` clean.
