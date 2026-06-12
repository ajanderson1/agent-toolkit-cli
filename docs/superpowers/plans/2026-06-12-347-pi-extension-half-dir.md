# pi-extension half-dir heal + doctor Implementation Plan (#347)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pi-extension add` stops reporting success over a half-written non-git-repo store dir (it heals it), and `pi-extension doctor` surfaces such a dir as a `half_dir` finding with a working reclone fix.

**Architecture:** Two coordinated edits per the spec (`docs/superpowers/specs/2026-06-12-347-pi-extension-half-dir-design.md`). `add()` reorders its `canonical.exists()` block: a **valid git repo** runs the existing source-mismatch-refuse + idempotent return unchanged; a **non-repo** dir (half/empty) is `rmtree`'d and falls through to the normal clone path. `doctor` gains a `half_dir` `FindingType` emitted when `canonical.exists()` but `not is_git_repo`, reusing `_make_reclone_action` — which gains a `force=True` flag to `rmtree` a pre-existing dir before cloning (its `if canonical.exists(): return` would otherwise no-op the half_dir fix).

**Tech Stack:** Python 3.12, pytest, the `git_sandbox` conftest fixture (bare-repo source), `uv run pytest …` from the repo root.

**Verified baseline (main @ 07a0a3f):** `add()`'s `canonical.exists()` block starts at `pi_extension_add.py:95`; the failed-checkout cleanup that creates half-dirs is `:133`. Doctor's `_check_slug` store-owned block is `pi_extension_doctor.py:120-153`; `_make_reclone_action` is `:339-383` with the `if canonical.exists(): return` guard at `:360-361`. The doctor CLI renders `f.finding_type` verbatim (`commands/pi_extension/doctor_cmd.py:62`), so a new finding type needs no label map.

---

### Task 1: doctor — `_make_reclone_action` gains `force` to clear a non-repo dir

Do this first: the half_dir finding (Task 2) depends on it, and it is a pure addition (missing_canonical behavior is preserved by the `force=False` default).

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_doctor.py:339-383` (`_make_reclone_action`)
- Test: `tests/test_cli/test_cli_pi_extension_lifecycle.py`

- [x] **Step 1: Write the failing test** (append to the lifecycle test file; it already imports `subprocess`, `pep`, `ped` is imported locally in sibling tests, `LockEntry`/`LockFile`/`write_lock` at module top, and provides `git_sandbox`). NOTE the `git_sandbox.env` loop — `_make_reclone_action.apply()` clones, and `git_sandbox.env` carries the `GIT_AUTHOR_*`/`GIT_COMMITTER_*` identity the conftest scrubs from the ambient environment; without it the clone runs with no git identity:

```python
def test_reclone_force_replaces_non_repo_dir(tmp_path, monkeypatch, git_sandbox):
    """#347: a forced reclone over a non-git-repo dir rmtrees it then clones
    (the un-forced _apply would no-op on canonical.exists())."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    from agent_toolkit_cli import pi_extension_doctor as ped

    # A non-repo half-dir squatting the canonical path.
    canonical = pep.library_pi_extension_path("demo", env={})
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")
    assert not (canonical / ".git").exists()

    entry = LockEntry(
        source=str(git_sandbox.upstream), source_type="git",
        ref=None, pi_extension_path="demo", upstream_sha=None,
    )
    action = ped._make_reclone_action(slug="demo", entry=entry, force=True)
    action.apply()

    # Now a real git repo, junk gone.
    assert (canonical / ".git").exists()
    assert not (canonical / "JUNK.md").exists()
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest "tests/test_cli/test_cli_pi_extension_lifecycle.py::test_reclone_force_replaces_non_repo_dir" -v`
Expected: FAIL — `_make_reclone_action() got an unexpected keyword argument 'force'`.

- [x] **Step 3: Implement.** In `pi_extension_doctor.py`, change the signature and the `_apply` guard:

```python
def _make_reclone_action(*, slug: str, entry: object, force: bool = False) -> FixAction:
```

and replace the opening of `_apply`:

```python
    def _apply() -> None:
        if canonical.exists():
            return  # idempotent
        canonical.parent.mkdir(parents=True, exist_ok=True)
```

with:

```python
    def _apply() -> None:
        if canonical.exists():
            if not force:
                return  # idempotent (missing_canonical: a race re-created it)
            # half_dir (#347): a non-repo dir is squatting the path — remove
            # it so the clone below has a clean target.
            shutil.rmtree(canonical, ignore_errors=True)
        canonical.parent.mkdir(parents=True, exist_ok=True)
```

(`shutil` is already imported at the top of `pi_extension_doctor.py`.)

- [x] **Step 4: Run test to verify it passes**

Run: `uv run pytest "tests/test_cli/test_cli_pi_extension_lifecycle.py::test_reclone_force_replaces_non_repo_dir" -v`
Expected: PASS.

- [x] **Step 5: Commit**

```bash
git commit --only tests/test_cli/test_cli_pi_extension_lifecycle.py --only src/agent_toolkit_cli/pi_extension_doctor.py -m "feat(pi-extension): _make_reclone_action force-replaces a non-repo dir (#347)"
```

---

### Task 2: doctor — `half_dir` finding for a non-repo canonical

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_doctor.py:41-49` (FindingType literal), `:120-153` (`_check_slug` store-owned block)
- Test: `tests/test_cli/test_cli_pi_extension_lifecycle.py`

- [x] **Step 1: Write the failing tests:**

```python
def test_doctor_detects_half_dir(tmp_path, monkeypatch, git_sandbox):
    """#347: a store-owned lock entry whose canonical exists but is NOT a
    git repo yields a half_dir finding (not missing_canonical, not dirty)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)

    # Corrupt the store copy into a non-repo half-dir.
    import shutil
    canonical = pep.library_pi_extension_path("demo", env={})
    shutil.rmtree(canonical)
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    half = [f for f in findings if f.finding_type == "half_dir"]
    assert len(half) == 1, [f.finding_type for f in findings]
    assert half[0].slug == "demo"
    assert not [f for f in findings if f.finding_type == "missing_canonical"]
    assert not [f for f in findings if f.finding_type == "dirty_tree"]


def test_doctor_half_dir_fix_repairs(tmp_path, monkeypatch, git_sandbox):
    """#347: applying the half_dir fix_action turns the dir into a valid repo."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    import shutil
    canonical = pep.library_pi_extension_path("demo", env={})
    shutil.rmtree(canonical)
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    half = next(f for f in findings if f.finding_type == "half_dir")
    assert half.fix_action is not None
    half.fix_action.apply()
    assert (canonical / ".git").exists()
    assert not (canonical / "JUNK.md").exists()


def test_doctor_missing_canonical_still_detected(tmp_path, monkeypatch, git_sandbox):
    """#347 regression: an ABSENT canonical stays missing_canonical, not half_dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    _add_store_owned(tmp_path, git_sandbox.env, git_sandbox.upstream)
    import shutil
    shutil.rmtree(pep.library_pi_extension_path("demo", env={}))

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    assert [f for f in findings if f.finding_type == "missing_canonical"]
    assert not [f for f in findings if f.finding_type == "half_dir"]


def test_doctor_npm_row_no_half_dir(tmp_path, monkeypatch):
    """#347: an npm (registry-tracked) row has no canonical, so it can never
    yield a half_dir finding even if a same-named dir squats the store path."""
    monkeypatch.setenv("HOME", str(tmp_path))
    from agent_toolkit_cli import pi_extension_add as pea
    pea.add(source="npm:@scope/widget", slug=None, env={})
    # A stray dir at the would-be canonical path must be ignored for npm rows.
    canonical = pep.library_pi_extension_path("@scope/widget", env={})
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    assert not [f for f in findings if f.finding_type == "half_dir"]
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest "tests/test_cli/test_cli_pi_extension_lifecycle.py" -k "half_dir or missing_canonical_still or npm_row_no_half" -v`
Expected: the two half_dir tests FAIL (no `half_dir` finding emitted — the non-repo dir falls through silently); `missing_canonical_still` and `npm_row_no_half_dir` PASS (already correct — npm rows skip the canonical check).

- [x] **Step 3: Implement.** In `pi_extension_doctor.py`, add `"half_dir"` to the `FindingType` literal:

```python
FindingType = Literal[
    "missing_canonical",
    "half_dir",             # canonical exists but is not a git repo (#347)
    "drifted_symlink",
    "stray_symlink",
    "dirty_tree",
    "orphaned_override",
    "squatted_projection",
]
```

Then in `_check_slug`, insert the half_dir check between the `missing_canonical` return and the dirty-tree `is_git_repo` branch. The current code is:

```python
        if not canonical.exists():
            findings.append(Finding(
                finding_type="missing_canonical", slug=slug, scope=scope,
                ...
            ))
            # Can't check projection if canonical is gone.
            return findings

        # Check dirty working tree (informational).
        if skill_git.is_git_repo(canonical):
```

Insert before `# Check dirty working tree`:

```python
        if not skill_git.is_git_repo(canonical):
            # #347: exists but not a git repo — a half-written/failed clone.
            findings.append(Finding(
                finding_type="half_dir", slug=slug, scope=scope,
                path=canonical,
                detail=(
                    f"store copy at {canonical} exists but is not a git repo "
                    f"(partial/failed clone). Source: {getattr(entry, 'source', '?')}"
                ),
                fix_action=_make_reclone_action(slug=slug, entry=entry, force=True),
            ))
            # Can't check projection/dirty-tree over a broken store.
            return findings
```

(The existing `if skill_git.is_git_repo(canonical):` dirty-tree block stays as-is; it is now only reached for a valid repo.)

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest "tests/test_cli/test_cli_pi_extension_lifecycle.py" -k "half_dir or missing_canonical_still or npm_row_no_half" -v`
Expected: all PASS.

- [x] **Step 5: Commit**

```bash
git commit --only tests/test_cli/test_cli_pi_extension_lifecycle.py --only src/agent_toolkit_cli/pi_extension_doctor.py -m "feat(pi-extension): doctor surfaces a half_dir non-repo canonical (#347)"
```

---

### Task 3: add — heal a non-repo canonical instead of trusting it

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_add.py:99-110` (the `canonical.exists()` block)
- Test: `tests/test_cli/test_pi_extension_add.py`

- [x] **Step 1: Write the failing tests** (append to `test_pi_extension_add.py`; it imports `pea`, `pep`, `read_lock`, `pytest`, and uses `git_sandbox`):

```python
def test_add_heals_half_dir(tmp_path, monkeypatch, git_sandbox):
    """#347: a non-repo half-dir at the canonical path is rmtree'd and the
    source re-cloned — idempotent success only over a VALID repo."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Pre-seed a non-repo half-dir + a stale lock entry (as a prior failed
    # add would leave).
    canonical = pep.library_pi_extension_path("demo", env={})
    canonical.mkdir(parents=True)
    (canonical / "JUNK.md").write_text("leftover\n")
    assert not (canonical / ".git").exists()

    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)

    # Healed: now a valid git repo, junk gone, lock entry present.
    assert (canonical / ".git").exists()
    assert not (canonical / "JUNK.md").exists()
    lock = read_lock(pep.library_lock_path(env={}))
    assert lock.skills["demo"].pi_extension_path == "demo"


def test_add_heals_empty_dir(tmp_path, monkeypatch, git_sandbox):
    """#347: an EMPTY canonical dir is also not-a-repo → healed, not trusted."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = pep.library_pi_extension_path("demo", env={})
    canonical.mkdir(parents=True)

    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)

    assert (canonical / ".git").exists()


def test_add_idempotent_over_valid_repo(tmp_path, monkeypatch, git_sandbox):
    """#347 regression: a second add over a VALID store copy is a no-op
    success (does NOT rmtree the repo)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)
    canonical = pep.library_pi_extension_path("demo", env={})
    (canonical / "MARKER.md").write_text("survives\n")

    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)

    # The valid repo was NOT blown away — our marker survives.
    assert (canonical / "MARKER.md").exists()


def test_add_refuses_source_mismatch_over_valid_repo(tmp_path, monkeypatch, git_sandbox):
    """#347 regression: a valid repo with a different source still REFUSES
    (is NOT silently re-cloned), and is left intact."""
    monkeypatch.setenv("HOME", str(tmp_path))
    pea.add(source=str(git_sandbox.upstream), slug="demo", env=git_sandbox.env)
    canonical = pep.library_pi_extension_path("demo", env={})
    (canonical / "MARKER.md").write_text("survives\n")

    with pytest.raises(pea.AddError, match="different source"):
        pea.add(source="other/different-repo", slug="demo", env=git_sandbox.env)
    assert (canonical / "MARKER.md").exists()
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest "tests/test_cli/test_pi_extension_add.py" -k "heals or idempotent_over_valid or refuses_source_mismatch" -v`
Expected: `test_add_heals_half_dir` and `test_add_heals_empty_dir` FAIL (the current early-return reports success without cloning, so `.git` is absent). `idempotent_over_valid` and `refuses_source_mismatch` PASS (existing behavior — they are regression guards).

- [x] **Step 3: Implement.** In `pi_extension_add.py`, replace the current block:

```python
    canonical = library_pi_extension_path(ext_slug, env={})
    if canonical.exists():
        # Already present — verify source matches, else refuse (mirror skill add).
        lock = read_lock(lock_path)
        existing = lock.skills.get(ext_slug)
        requested = parsed.owner_repo or parsed.url
        if existing is not None and existing.source != requested:
            raise AddError(
                f"{ext_slug}: library already has a different source "
                f"({existing.source!r}); run `pi-extension remove {ext_slug}` first"
            )
        return ext_slug
```

with:

```python
    canonical = library_pi_extension_path(ext_slug, env={})
    if canonical.exists():
        if skill_git.is_git_repo(canonical):
            # Valid store copy — verify source matches, else refuse (mirror
            # skill add). Idempotent success ONLY over a valid repo.
            lock = read_lock(lock_path)
            existing = lock.skills.get(ext_slug)
            requested = parsed.owner_repo or parsed.url
            if existing is not None and existing.source != requested:
                raise AddError(
                    f"{ext_slug}: library already has a different source "
                    f"({existing.source!r}); run `pi-extension remove {ext_slug}` first"
                )
            return ext_slug
        # #347: exists but NOT a git repo — a half-written/empty dir left by a
        # partially-failed cleanup. Treat as not-present: remove it and fall
        # through to the clone path below (which rewrites the lock entry).
        shutil.rmtree(canonical, ignore_errors=True)
```

(`shutil` and `skill_git` are already imported at the top of `pi_extension_add.py`.)

- [x] **Step 4: Run tests to verify they pass**

Run: `uv run pytest "tests/test_cli/test_pi_extension_add.py" -k "heals or idempotent_over_valid or refuses_source_mismatch" -v`
Expected: all PASS.

- [x] **Step 5: Commit**

```bash
git commit --only tests/test_cli/test_pi_extension_add.py --only src/agent_toolkit_cli/pi_extension_add.py -m "fix(pi-extension): add heals a non-repo half-dir instead of false success (#347)"
```

---

### Task 4: full verification

- [x] **Step 1: Targeted suites**

Run: `uv run pytest tests/test_cli/test_pi_extension_add.py tests/test_cli/test_cli_pi_extension_lifecycle.py -q`
Expected: all PASS.

- [x] **Step 2: Full suite**

Run: `uv run pytest -q`
Expected: green except the 2 known HOME-isolation env failures (`test_empty_machine_is_empty`, `test_build_instruction_rows_empty_lock_no_canonical`) — pre-existing on main; reproduce on a clean checkout before whitelisting anything else.

- [x] **Step 3: Lint/type checks**

Run: `uv run ruff check src tests && uv run mypy src`
Expected: no NEW errors versus main (compare counts on the touched files if non-zero).
