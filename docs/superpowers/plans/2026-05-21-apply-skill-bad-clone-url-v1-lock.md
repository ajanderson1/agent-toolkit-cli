# Plan — fix #159 apply-skill bad clone URL for v1 lock

**Spec:** [`docs/superpowers/specs/2026-05-21-apply-skill-bad-clone-url-v1-lock-design.md`](../specs/2026-05-21-apply-skill-bad-clone-url-v1-lock-design.md)
**Date:** 2026-05-21

## Tasks (sequential — small)

### 1. Audit other call sites that resolve URL from a `LockEntry`

`grep -rn 'extras.get("sourceUrl")\|entry.source\b' src/agent_toolkit_cli/` and read each hit. If any other site reproduces the same `extras.get("sourceUrl") or entry.source` pattern, list it for migration in Task 3. Expected: only `skill_install.py:365` and the writer in `skill_lock.py`. If anything else turns up, surface it before writing code.

### 2. Add helper `clone_url_from_entry(entry: LockEntry) -> str` in `skill_lock.py`

Place next to the existing v3 writer. Logic mirrors the writer ladder, in this order:

1. `entry.extras.get("sourceUrl")` — explicit override wins.
2. `source_type == "github"` and `"/"` in `source` → `https://github.com/{source}.git`.
3. `source_type == "gitlab"` and `"/"` in `source` → `https://gitlab.com/{source}.git`.
4. Else — return `entry.source` as-is (covers `source_type="local"` and any pre-synthesised URL).

Module-level helper (not on the dataclass) to keep `LockEntry` a plain data carrier.

Type hint: returns `str`. Never returns `None` — `source` is required on `LockEntry`.

### 3. Wire the helper

- `skill_lock.py` `_entry_to_dict_v3`: replace the inline `elif` ladder with `out["sourceUrl"] = clone_url_from_entry(e)`. Keep the precedence (extras override → github → gitlab → fallback) identical so the on-disk format doesn't shift.
- `skill_install.py` `ensure_project_canonical`: replace

  ```python
  source_url = entry.extras.get("sourceUrl") or entry.source
  ```

  with

  ```python
  source_url = clone_url_from_entry(entry)
  ```

  Import from `agent_toolkit_cli.skill_lock`.
- Any other call sites flagged in Task 1.

### 4. Regression test

New test in `tests/test_cli/test_skill_install_engine.py`, beside the existing `ensure_project_canonical` cases:

```python
def test_ensure_project_canonical_synthesises_github_url_for_v1_lock(tmp_path, monkeypatch):
    """v1 lock with sourceType=github + bare owner/repo → clone called with https URL."""
    from agent_toolkit_cli import skill_install as si
    from agent_toolkit_cli.skill_lock import LockEntry, LockFile, add_entry, write_lock

    library_root = tmp_path / "lib" / "skills"
    library_root.mkdir(parents=True)
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))

    global_lock_path = library_root.parent / "skills-lock.json"
    entry = LockEntry(
        source="ajanderson1/journal-skill",
        source_type="github",
        ref=None,
        skill_path="SKILL.md",
    )
    write_lock(global_lock_path, add_entry(LockFile(version=1, skills={}), "journal", entry))

    captured: dict = {}
    def fake_clone(url, dest, *, ref, env):
        captured["url"] = url
        dest.mkdir(parents=True, exist_ok=True)
        return None
    monkeypatch.setattr(si.skill_git, "clone", fake_clone)

    si.ensure_project_canonical(
        slug="journal", project=project,
        global_lock_path=global_lock_path, env=None,
    )
    assert captured["url"] == "https://github.com/ajanderson1/journal-skill.git"
```

Unit-level — no real git, no network. Asserts the synthesised URL ends up in the `git clone` argument list.

Also add a focused unit test in `tests/test_cli/test_skill_lock.py` for the helper itself:

```python
def test_clone_url_from_entry_github_short_form():
    from agent_toolkit_cli.skill_lock import LockEntry, clone_url_from_entry
    e = LockEntry(source="foo/bar", source_type="github")
    assert clone_url_from_entry(e) == "https://github.com/foo/bar.git"

def test_clone_url_from_entry_gitlab_short_form():
    from agent_toolkit_cli.skill_lock import LockEntry, clone_url_from_entry
    e = LockEntry(source="foo/bar", source_type="gitlab")
    assert clone_url_from_entry(e) == "https://gitlab.com/foo/bar.git"

def test_clone_url_from_entry_extras_override_wins():
    from agent_toolkit_cli.skill_lock import LockEntry, clone_url_from_entry
    e = LockEntry(source="foo/bar", source_type="github",
                  extras={"sourceUrl": "git@github.com:override/x.git"})
    assert clone_url_from_entry(e) == "git@github.com:override/x.git"

def test_clone_url_from_entry_passthrough_for_local():
    from agent_toolkit_cli.skill_lock import LockEntry, clone_url_from_entry
    e = LockEntry(source="/tmp/some-upstream", source_type="local")
    assert clone_url_from_entry(e) == "/tmp/some-upstream"
```

### 5. Run pre-flight

`uv run pytest -q` and `uv run ruff check .` (whatever the project's lint command is — confirm from `lefthook.yml` / `pyproject.toml`). Capture logs.

## Out of scope

- Migration of v1 global locks to v3.
- Auth protocol switch (SSH vs HTTPS).
- TUI changes — the bug is in the CLI layer the TUI calls.

## Verification (post-build)

Manual smoke check (outside the test harness): with the real `~/.agent-toolkit/skills-lock.json` intact, run the TUI flow once and confirm the clone succeeds. Capture a terminal screenshot to `assets/verification/159/`. If the user's lock file points to a private repo, surface that as a known caveat rather than fixing auth.
