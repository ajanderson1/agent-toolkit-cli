# Spec — `_sanitize_ref` strictness parity with `git check-ref-format`

**Issue:** #199 · **Type:** fix · **Risk:** cosmetic (better errors at parse time vs cryptic Git errors later)

## Problem

`_sanitize_ref` in `src/agent_toolkit_cli/skill_source.py:51-62` accepts ref strings that Git later refuses. The gap surfaces as a cryptic `git fetch` / `git rev-parse` failure instead of a clean `SourceParseError`.

Current parser blocks: empty, whitespace, leading `-`, `..` as a full segment.

## In-scope additions

Extend `_sanitize_ref` to also refuse, matching the documented rules in `git-check-ref-format(1)` that are realistically reachable from a user-supplied `owner/repo@<ref>` shorthand:

1. Any segment that **starts with `.`** (e.g. `.hidden`).
2. Any segment that **ends with `.lock`** (e.g. `feat.lock`).
3. The substring `..` anywhere in the ref (e.g. `feat..main`), not just as a full segment.
4. Any segment that **ends with `/`** (i.e. trailing slash, empty trailing segment).
5. The substring `@{` anywhere (Git reflog syntax).
6. The character `\` (backslash) anywhere.

Control characters and whitespace are already covered by the existing `isspace()` guard plus the regex shape; no extra check needed.

## Acceptance (from the issue)

- `parse_source("o/r@<bad>")` raises `SourceParseError` for: `feat.lock`, `.hidden`, `feat..main`. (The issue's table examples include the `o/r@` prefix where needed.)
- `parse_source("o/r@HEAD~1")` continues to parse — positive test added.
- Error messages name the offending pattern (".lock suffix", "leading dot", "'..' substring", etc.) so users can fix without guessing.

## Out of scope

- Shelling out to `git check-ref-format` (heavier, optional alternative in the issue — rejected for now: keeps parsing self-contained, no external process).
- Validating refs from `https://.../tree/<ref>` URL parsing — that path doesn't call `_sanitize_ref` today and the issue is scoped to `_sanitize_ref` only. Touching it is a separate improvement.
- Any change to subpath sanitization.

## Approach

Pure addition to `_sanitize_ref`. Each new rule is one `if` branch with a precise `SourceParseError` message. No regex rewrite; the function stays a short readable sequence of guards. Add corresponding negative tests in `tests/test_cli/test_skill_source.py` adjacent to the existing ref-rejection tests, plus one positive test for `HEAD~1`.

## Risk / impact

- Tightens an internal validator only. No public API change.
- Any caller relying on previously-accepted-but-actually-broken refs (none expected — they would have surfaced as Git errors downstream) gets a cleaner error earlier.
- Test coverage delta: +1 positive test, +6 negative tests (one per new rule).
