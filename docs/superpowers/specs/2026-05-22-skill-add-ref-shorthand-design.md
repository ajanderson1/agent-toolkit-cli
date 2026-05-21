# Spec — `skill add` shorthand with `@<ref>` suffix

**Issue:** [#181](https://github.com/ajanderson1/agent-toolkit-cli/issues/181)
**Status:** Drafted
**Mode:** `--ship-it`

## Problem

`agent-toolkit-cli skill add` accepts three shorthand families today:

1. `owner/repo`
2. `owner/repo/<subpath>`
3. Full HTTPS URLs (incl. `…/tree/<ref>[/<subpath>]`)

Ref selection works only via family 3. The "GitHub-style at-ref" convention shared with `npx skills add` (`owner/repo@ref`) is unrecognised:

```
$ agent-toolkit-cli skill add anthropics/claude-code@plugin-settings
Error: Unrecognised source: anthropics/claude-code@plugin-settings
```

The shorthand regex in `src/agent_toolkit_cli/skill_source.py:182-197` restricts the `repo` segment to `[A-Za-z0-9_.\-]`, so the `@` is never matched.

## Goal

Accept `@<ref>` in shorthand inputs so a user can pin a skill (or a monorepo subpath) to a specific branch, tag, or short SHA without having to write the full GitHub URL.

## In scope

Two shapes:

- `owner/repo@<ref>`
- `owner/repo@<ref>/<subpath>`

The ref comes **immediately after** the repo segment. This matches `npx skills add` and the cache-key convention already in the codebase (`_parents/<owner>/<repo>@<ref>/`).

The `@` form is **only** for shorthand. The `/tree/<ref>/` form continues to be the canonical way to pin in HTTPS URLs; we do not introduce `https://github.com/o/r@ref` (not how GitHub URLs work) or `git@github.com:o/r@ref` (collides with the SSH `@`).

## Out of scope

- `owner/repo/<subpath>@<ref>` (subpath-then-ref). Picking one shape only — `npx skills add` uses ref-before-subpath, so we follow.
- Multiple refs, range refs, abbreviated qualified refs (`refs/heads/foo`). A bare ref string is enough.
- Resolving the ref against the remote at parse time. The parser stores the literal string; later git operations (clone / pull) carry it.

## Behaviour

| Input | `owner_repo` | `ref` | `subpath` |
|---|---|---|---|
| `o/r` | `o/r` | `None` | `None` |
| `o/r@main` | `o/r` | `main` | `None` |
| `o/r@v1.2.3` | `o/r` | `v1.2.3` | `None` |
| `o/r@abc123` | `o/r` | `abc123` | `None` |
| `o/r@feat/x` | `o/r` | `feat/x` | `None` |
| `o/r@main/skills/foo` | `o/r` | `main` | `skills/foo` |
| `o/r/skills/foo` (existing) | `o/r` | `None` | `skills/foo` |

Slashes inside `<ref>` are allowed (Git permits them in branch names), but the parser uses the **first** `/` after the `@` as the ref/subpath separator. Refs containing `/` therefore have to be written with the `/tree/<ref>/<subpath>` URL form. (One-line warning in the user-facing docs.)

## Validation

A ref must:

- be non-empty
- contain no whitespace
- contain no `..`
- contain no leading `-` (would look like a CLI flag if echoed back)

These mirror Git's safety constraints (`git check-ref-format`-adjacent) and the existing `_sanitize_subpath` philosophy. Failure → `SourceParseError` with a message naming the offending ref.

## Implementation sketch

In `src/agent_toolkit_cli/skill_source.py`, extend the shorthand regex to optionally accept `@<ref>` between `repo` and the rest:

```python
m = re.fullmatch(
    r"(?P<owner>[A-Za-z0-9_.\-]+)"
    r"/(?P<repo>[A-Za-z0-9_.\-]+)"
    r"(?:@(?P<ref>[^\s/][^\s]*?))?"
    r"(?:/(?P<subpath>[^\s].*))?",
    input_,
)
```

then sanitise via a new `_sanitize_ref` helper and pass through to `ParsedSource(ref=…)`.

The downstream pipeline already threads `ref` end-to-end (PR #177 spec line 140); no callers change.

## Tests

Add to `tests/test_cli/test_skill_source.py` (or `test_skill_source_monorepo.py`):

1. `o/r@main` → ref=`main`, subpath=`None`
2. `o/r@v1.2.3` → ref=`v1.2.3`
3. `o/r@main/skills/foo` → ref=`main`, subpath=`skills/foo`
4. `anthropics/claude-code@plugin-settings` → matches the exact reproduction in #181
5. Bad refs → `SourceParseError`: empty (`o/r@`), whitespace, `..`, leading `-`
6. Existing `o/r` and `o/r/subpath` still parse identically (regression guard)

## Risks

- **Backwards-compat:** the regex change is additive; any string that matched before still matches (the `@`-group is optional). The existing `test_github_shorthand` test guards this.
- **Ambiguity with `git@host:…` SSH syntax:** ruled out by ordering — the SSH branch runs before the shorthand regex, and SSH inputs start with `git@`, which fails the shorthand owner regex anyway (`@` is not in the owner char class).
- **Refs with `/` (e.g. `feat/foo`):** handled by greedy ref-then-slash semantics. Documented escape hatch: use the `/tree/<ref>/<subpath>` URL form when the ref itself contains `/`.

## Acceptance

- [ ] `parse_source('anthropics/claude-code@plugin-settings')` returns the expected `ParsedSource`
- [ ] Combined ref+subpath form round-trips through parse
- [ ] Unit tests added (above)
- [ ] CLI smoke: `agent-toolkit-cli skill add anthropics/claude-code@plugin-settings --help` no longer errors at parse, and a `--dry-run` style or canonicalised URL is observable
- [ ] PR #177's existing tests still pass
