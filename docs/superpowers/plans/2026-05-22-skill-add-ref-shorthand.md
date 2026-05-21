# Plan — `skill add` shorthand with `@<ref>` suffix

**Spec:** [`../specs/2026-05-22-skill-add-ref-shorthand-design.md`](../specs/2026-05-22-skill-add-ref-shorthand-design.md)
**Issue:** [#181](https://github.com/ajanderson1/agent-toolkit-cli/issues/181)
**Branch:** `fix/181-skill-add-ref-shorthand`
**Mode:** `--ship-it`

## Task list (TDD)

### Task 1 — failing tests

In `tests/test_cli/test_skill_source.py`, add the following cases. They must all fail before any production code changes.

```python
def test_github_shorthand_with_ref():
    s = parse_source("anthropics/claude-code@plugin-settings")
    assert s == ParsedSource(
        type="github",
        url="https://github.com/anthropics/claude-code",
        owner_repo="anthropics/claude-code",
        ref="plugin-settings",
        subpath=None,
    )


def test_github_shorthand_with_ref_tag():
    s = parse_source("o/r@v1.2.3")
    assert s.ref == "v1.2.3"
    assert s.subpath is None


def test_github_shorthand_with_ref_and_subpath():
    s = parse_source("o/r@main/skills/foo")
    assert s.owner_repo == "o/r"
    assert s.ref == "main"
    assert s.subpath == "skills/foo"


def test_github_shorthand_empty_ref_rejected():
    with pytest.raises(SourceParseError):
        parse_source("o/r@")


def test_github_shorthand_whitespace_ref_rejected():
    with pytest.raises(SourceParseError):
        parse_source("o/r@ main")


def test_github_shorthand_ref_traversal_rejected():
    with pytest.raises(SourceParseError, match="path traversal|ref"):
        parse_source("o/r@..")


def test_github_shorthand_ref_leading_dash_rejected():
    with pytest.raises(SourceParseError):
        parse_source("o/r@-bad")
```

**Acceptance for Task 1:** `uv run pytest tests/test_cli/test_skill_source.py -q` shows the seven new tests **failing**. No production code touched yet.

### Task 2 — implement

Edit `src/agent_toolkit_cli/skill_source.py`:

1. Add `_sanitize_ref(ref: str) -> str`:
   - non-empty, no whitespace, no `..` segment, no leading `-`
   - raise `SourceParseError(f"Unsafe ref: {ref!r}")` on failure
2. Extend the shorthand regex inside `parse_source` to include an optional `@<ref>` group:

   ```python
   m = re.fullmatch(
       r"(?P<owner>[A-Za-z0-9_.\-]+)"
       r"/(?P<repo>[A-Za-z0-9_.\-]+)"
       r"(?:@(?P<ref>[^\s/][^\s]*?))?"
       r"(?:/(?P<subpath>[^\s].*))?",
       input_,
   )
   ```

   If the optional `@` is present but the captured ref is empty (input ends in literal `@`), the `fullmatch` will fail because `[^\s/]` requires at least one char — so the parser falls through to `SourceParseError("Unrecognised source: …")`. Treat that as the empty-ref rejection. Verify against Task 1's `o/r@` test.

3. When the regex matches and `m["ref"]` is non-empty, run `_sanitize_ref` and pass the result to `ParsedSource(ref=…)`.

**Acceptance for Task 2:** all seven new tests **and** every existing test in `tests/test_cli/test_skill_source.py` + `tests/test_cli/test_skill_source_monorepo.py` pass.

### Task 3 — full pytest

Run the full suite to make sure no other module assumed `ref is None` from shorthand inputs:

```bash
uv run pytest -q
```

**Acceptance for Task 3:** all tests pass (target: 232 passed, 2 skipped — current is 225 passed + 7 new).

### Task 4 — CLI doc tweak

`docs/agent-toolkit/cli.md` — append one sentence to the existing `skill add` section noting the new shorthand:

> `skill add owner/repo@<ref>[/subpath]` pins the install to a branch, tag, or short SHA. Refs containing `/` need the full `https://github.com/owner/repo/tree/<ref>/<subpath>` URL form.

**Acceptance for Task 4:** doc edit committed; spell-check / lint-free.

## Order & isolation

Tasks are strictly sequential — each depends on the previous. No subagents needed; one focused change in one file plus tests plus doc.

## Out-of-scope notes

If a follow-up surfaces (e.g. user asks for `subpath@ref` form, or for shorthand to be accepted in `--skill` flag inputs too), file a new issue. Do not expand scope in this PR.
