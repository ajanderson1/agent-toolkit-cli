# Plan — tighten `_sanitize_ref`

**Spec:** [`docs/superpowers/specs/2026-05-22-sanitize-ref-stricter-than-git-design.md`](../specs/2026-05-22-sanitize-ref-stricter-than-git-design.md) · **Issue:** #199

## Task list

### 1. Tighten `_sanitize_ref` in `src/agent_toolkit_cli/skill_source.py`

Insert new guards into `_sanitize_ref` (between existing checks where they fit). Order chosen so each error is distinct and the cheaper checks run first:

```python
def _sanitize_ref(ref: str) -> str:
    if not ref:
        raise SourceParseError("Empty ref")
    if any(ch.isspace() for ch in ref):
        raise SourceParseError(f"Unsafe ref: '{ref}' contains whitespace")
    if ref.startswith("-"):
        raise SourceParseError(f"Unsafe ref: '{ref}' must not start with '-'")
    if "\\" in ref:
        raise SourceParseError(f"Unsafe ref: '{ref}' contains backslash")
    if "@{" in ref:
        raise SourceParseError(f"Unsafe ref: '{ref}' contains '@{{'")
    if ".." in ref:
        raise SourceParseError(f"Unsafe ref: '{ref}' contains '..'")
    if ref.endswith("/"):
        raise SourceParseError(f"Unsafe ref: '{ref}' ends with '/'")
    for seg in ref.split("/"):
        if seg.startswith("."):
            raise SourceParseError(
                f"Unsafe ref: '{ref}' has a segment starting with '.'"
            )
        if seg.endswith(".lock"):
            raise SourceParseError(
                f"Unsafe ref: '{ref}' has a segment ending in '.lock'"
            )
    return ref
```

Notes:
- The old `seg == ".."` segment check is subsumed by the new `".." in ref` substring check; remove the now-redundant loop branch.
- Empty segments from a leading `/` or `//` are caught by the `segment starts with '.'` check only when relevant — but a leading `/` would already have failed the surrounding regex in `parse_source`, so we don't add a separate "empty segment" rule. Trailing slash is caught explicitly.
- The error string mentions `'@{{'` because of f-string escaping; rendered text reads `'@{'`.

### 2. Tests in `tests/test_cli/test_skill_source.py`

Add at the bottom of the file, mirroring the existing ref-test style.

```python
def test_github_shorthand_ref_dot_lock_rejected():
    with pytest.raises(SourceParseError, match="lock"):
        parse_source("o/r@feat.lock")


def test_github_shorthand_ref_leading_dot_rejected():
    with pytest.raises(SourceParseError, match="starting with '.'"):
        parse_source("o/r@.hidden")


def test_github_shorthand_ref_double_dot_substring_rejected():
    with pytest.raises(SourceParseError, match=r"'\.\.'"):
        parse_source("o/r@feat..main")


def test_github_shorthand_ref_trailing_slash_rejected():
    with pytest.raises(SourceParseError, match="ends with '/'"):
        parse_source("o/r@feat/")


def test_github_shorthand_ref_reflog_syntax_rejected():
    with pytest.raises(SourceParseError, match=r"'@\{'"):
        parse_source("o/r@main@{1}")


def test_github_shorthand_ref_backslash_rejected():
    with pytest.raises(SourceParseError, match="backslash"):
        parse_source(r"o/r@bad\path")


def test_github_shorthand_ref_head_with_tilde_accepted():
    s = parse_source("o/r@HEAD~1")
    assert s.ref == "HEAD~1"
    assert s.subpath is None
```

`HEAD~1`: `~` and `1` are not blocked by any rule. Git accepts `HEAD~1` as a rev-spec; `check-ref-format` itself doesn't accept tildes, but the issue explicitly lists it as the positive case (parse-time tolerance for rev-spec syntax users will write). Keep accepted.

### 3. Verify behaviour

- `uv run pytest tests/test_cli/test_skill_source.py -q` — should show new tests pass and the existing suite unchanged.
- Full suite: `uv run pytest -q`.
- Lint: `uv run ruff check src tests`.

### 4. Commit

Single conventional commit:

```
fix(skill-source): align _sanitize_ref with git check-ref-format

Refs #199.
```

## Non-goals

- No changes to `_parse_https` ref extraction (out of scope per spec).
- No CLI surface change.
- No changelog entry beyond what release-please derives from the conventional commit.
