# Design: reject `@<ref>/<subpath>` shorthand to eliminate silent slash-ref mis-parse

Closes #198.

## Problem

The GitHub-shorthand parser at `src/agent_toolkit_cli/skill_source.py:197-215` accepts:

```
owner/repo[@ref][/subpath]
```

The ref group is `[^\s/][^\s/]*` — it stops at the first slash. So `o/r@feature/branch` parses as `ref='feature', subpath='branch'`, even though the user clearly intended `ref='feature/branch'`. The mis-parse is silent at the parser level; downstream the wrong ref either fetches or fails opaquely.

`docs/agent-toolkit/cli.md:61` already documents the escape hatch: refs containing `/` need the URL form `https://github.com/<owner>/<repo>/tree/<ref>/<subpath>`. The parser doesn't enforce that — slash-refs are silently re-interpreted.

## Decision

**Reject `@<ref>/<subpath>` shorthand at the parser.** Whenever the GitHub shorthand regex matches with **both `ref` and `subpath` set**, raise `SourceParseError` naming two unambiguous alternatives:

1. URL form: `https://github.com/<owner>/<repo>/tree/<ref>/<subpath>` — for refs **without** a slash.
2. `--ref <ref>` flag combined with `<owner>/<repo>/<subpath>` — for refs **with** a slash.

This:

- Eliminates the silent mis-parse of `o/r@feature/branch`.
- Preserves the no-subpath form `o/r@feature` (most common shorthand use).
- Preserves the URL form for monorepo addressing.
- Trades the `@<ref>/<subpath>` shorthand (added in #185) for unambiguous-or-explicit. That shorthand stops working; the URL form takes over for the no-slash-ref case.

The issue's option (1) ("reject loudly") matches this. Option (2) ("accept slash-refs greedily") cannot be done syntactically — there is no delimiter that distinguishes `feature/branch` from `main/skills/foo`. Option (3) ("better docs only") leaves the silent mis-parse in place.

## Implementation

In `parse_source`, after the shorthand regex matches:

```python
if m["ref"] and m["subpath"]:
    raise SourceParseError(
        f"Ambiguous shorthand '{input_}': @<ref>/<subpath> form is not supported "
        f"because refs may themselves contain '/'. Use one of:\n"
        f"  • URL form (no-slash ref):   https://github.com/{owner_repo}/tree/{m['ref']}/{m['subpath']}\n"
        f"  • --ref flag (any ref):      skill add {owner_repo}/{m['subpath']} --ref <ref>"
    )
```

The trailing `parse_source` body for ref-only or subpath-only shorthand stays as-is. Only the **both-set** branch is refused.

## Acceptance

- [ ] `parse_source('o/r@feature/branch')` raises `SourceParseError`; message names the URL form and the `--ref` flag.
- [ ] `parse_source('o/r@main/skills/foo')` raises `SourceParseError` (new behaviour; previously parsed successfully).
- [ ] `parse_source('o/r@main')` unchanged — `ref='main', subpath=None`.
- [ ] `parse_source('o/r@v1.2.3')` unchanged.
- [ ] `parse_source('o/r/skills/foo')` unchanged — `ref=None, subpath='skills/foo'`.
- [ ] `parse_source('https://github.com/o/r/tree/main/skills/foo')` unchanged — URL form remains the supported path.
- [ ] Existing test `test_github_shorthand_with_ref_and_subpath` updated to expect `SourceParseError`.
- [ ] New test `test_github_shorthand_ref_with_subpath_rejected` covers the slash-ref case from the issue.
- [ ] `docs/agent-toolkit/cli.md:60-61` updated: shorthand source forms now list `<owner>/<repo>`, `<owner>/<repo>@<ref>`, `<owner>/<repo>/<subpath>`, URL. The `@<ref>/<subpath>` entry is removed.

## Files touched

- `src/agent_toolkit_cli/skill_source.py` — add the refusal branch.
- `tests/test_cli/test_skill_source.py` — update one test, add one test.
- `docs/agent-toolkit/cli.md` — tighten the source-form table.

## Non-goals

- Supporting slash-containing refs in any URL form (the `tree/` URL also splits on the first `/` after the ref — out of scope; users use `--ref` for that).
- Touching SSH or `file://` parsers.
- Adding warnings or non-fatal modes.
