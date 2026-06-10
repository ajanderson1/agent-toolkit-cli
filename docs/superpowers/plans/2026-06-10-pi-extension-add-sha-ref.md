# Fix SHA-pinned `pi-extension add` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `pi-extension add <source>@<sha>` (and the doctor reclone of a SHA-pinned lock entry) land on the pinned commit instead of failing with `fatal: Remote branch <sha> not found`.

**Architecture:** `git clone --branch` accepts only branch/tag names, never a raw SHA. The fix mirrors the proven import pattern (`pi_extension/import_cmd.py:115-122`): when the parsed ref *looks like* a SHA, clone at default HEAD (no `--branch`), then `fetch_ref(<sha>)` + `checkout(<sha>)`. Unlike `import` (best-effort batch that swallows pin failures), `add` is a single deliberate pin → a missing SHA **fails loudly** and cleans up the partial store directory (no lock entry per #283, no orphan dir per #313). No shallow-clone is added (measured: no benefit — see spec).

**Tech Stack:** Python 3.12, `uv run pytest`, existing `skill_git` primitives (`clone`, `fetch_ref`, `checkout`, `is_git_repo`) — no new dependencies, no lock-schema change.

**Spec:** `docs/superpowers/specs/2026-06-10-pi-extension-add-sha-ref-design.md`
**Issue:** #330

---

## Worker notes (read first)

- **Pre-commit hook runs the FULL pytest suite** (`lefthook.yml` → `uv run pytest -q`, ~90 s). One test is a **known local-only failure** on AJ's machine: `tests/test_cli/test_pi_extension_inventory.py::test_empty_machine_is_empty` (global pi inventory ignores `home=`; green on CI). `git commit --no-verify` is justified **only** when that is the sole failure. Any other failure must be fixed, not skipped.
- All tests are hermetic: local bare repos, no network. The GitHub-shorthand form (`owner/repo@<sha>`) resolves to an `https://github.com/...` URL, so it cannot be exercised hermetically — the tests use the `file:///path/tree/<sha>` source form, which produces the **same** `ParsedSource.ref` value; the code under test branches only on `parsed.ref`, so coverage is equivalent.
- Existing fixture: `git_sandbox` in `tests/conftest.py` (bare `upstream` repo + `clone` + scrubbed `env` dict with identity vars and a fake `HOME`). Tests below that need a second commit push it via the sandbox's `clone`.

## File structure

| File | Responsibility | Change |
|---|---|---|
| `src/agent_toolkit_cli/pi_extension_add.py` | `add()` core | Add public `looks_like_sha()` helper; branch the clone site on it; fail-loud + cleanup on pin failure |
| `src/agent_toolkit_cli/pi_extension_doctor.py` | doctor engine | `_make_reclone_action` applies the same SHA treatment (pin = `upstream_sha`, else a SHA-looking `ref`) |
| `tests/test_cli/test_pi_extension_add.py` | add tests | `looks_like_sha` unit table; SHA happy path; bad-SHA fail-loud; branch-ref regression |
| `tests/test_cli/test_cli_pi_extension_lifecycle.py` | doctor tests (§ Task B5) | reclone of a SHA-pinned entry lands on the pin |

---

### Task 1: `looks_like_sha` helper

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_add.py` (helper + import)
- Test: `tests/test_cli/test_pi_extension_add.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_pi_extension_add.py`:

```python
@pytest.mark.parametrize("ref,expected", [
    ("22d0c764cd6c10ed06a7877e55a606d3435f1ec5", True),   # full SHA
    ("22d0c76", True),                                     # abbreviated SHA
    ("deadbeef", True),                                    # 8-hex
    ("main", False),                                       # branch
    ("v1.2.3", False),                                     # tag
    ("feature/foo", False),                                # slashed branch
    (None, False),                                         # no ref
    ("22d0c7", False),                                     # 6 hex chars: below git's 7-char floor
    ("g2d0c764", False),                                   # non-hex char
    ("DEADBEEF", False),                                   # uppercase: git SHAs print lowercase
])
def test_looks_like_sha(ref, expected):
    assert pea.looks_like_sha(ref) is expected
```

(`pytest` and `pea` are already imported at the top of the file — `import pytest` / `from agent_toolkit_cli import pi_extension_add as pea`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_pi_extension_add.py -q -k looks_like_sha`
Expected: 10 FAILED with `AttributeError: module ... has no attribute 'looks_like_sha'`

- [ ] **Step 3: Implement the helper**

In `src/agent_toolkit_cli/pi_extension_add.py`, add `import re` to the imports block, then add below `_npm_slug`:

```python
def looks_like_sha(ref: str | None) -> bool:
    """True when `ref` can only sensibly be a commit SHA (lowercase hex,
    7-40 chars — git's abbreviated-to-full range).

    Why a heuristic is safe both ways: `git clone --branch` rejects a 40-hex
    *branch name* anyway, so classifying one as a SHA is strictly more
    correct than today; and a short all-hex *tag* (e.g. `abc1234`) classified
    as a SHA still resolves — `fetch_ref` + `checkout` accept tag names too.
    """
    return bool(ref) and re.fullmatch(r"[0-9a-f]{7,40}", ref) is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_pi_extension_add.py -q`
Expected: all PASS (existing 4 + new 10)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_add.py tests/test_cli/test_pi_extension_add.py
git commit -m "feat(pi-extension): add looks_like_sha ref classifier (#330)"
```

(If the pre-commit suite fails ONLY on the known `test_empty_machine_is_empty` local-only failure, re-run with `--no-verify` — see Worker notes.)

---

### Task 2: SHA-pinned `add` — happy path

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_add.py:93-95` (the clone site)
- Test: `tests/test_cli/test_pi_extension_add.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_pi_extension_add.py`:

```python
import subprocess


def _push_second_commit(git_sandbox) -> tuple[str, str]:
    """Create a second upstream commit; return (first_sha, second_sha)."""
    def git(*args):
        return subprocess.run(
            ["git", "-C", str(git_sandbox.clone), *args],
            check=True, env=git_sandbox.env, capture_output=True, text=True,
        ).stdout.strip()

    first_sha = git("rev-parse", "HEAD")
    (git_sandbox.clone / "EXTRA.md").write_text("second\n")
    git("add", "-A")
    git("commit", "-m", "second")
    git("push", "origin", "main")
    second_sha = git("rev-parse", "HEAD")
    return first_sha, second_sha


def test_add_sha_pinned_lands_on_pin(tmp_path, monkeypatch, git_sandbox):
    """A /tree/<sha> source must land the store copy on the pinned commit,
    not the branch HEAD (#330). Same parsed.ref shape as owner/repo@<sha>."""
    monkeypatch.setenv("HOME", str(tmp_path))
    first_sha, second_sha = _push_second_commit(git_sandbox)

    pea.add(
        source=f"file://{git_sandbox.upstream}/tree/{first_sha}",
        slug="pinned", env=git_sandbox.env,
    )

    canonical = pep.library_pi_extension_path("pinned", env={})
    head = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert head == first_sha != second_sha
    # Worktree reflects the pinned commit, not HEAD.
    assert not (canonical / "EXTRA.md").exists()
    # Lock records the pin (consistent with the import path).
    entry = read_lock(pep.library_lock_path(env={})).skills["pinned"]
    assert entry.ref == first_sha
    assert entry.local_sha == first_sha
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_pi_extension_add.py::test_add_sha_pinned_lands_on_pin -q`
Expected: FAIL — `GitError` from `git clone --branch <first_sha>`: `Remote branch <sha> not found in upstream origin`

- [ ] **Step 3: Implement the SHA branch at the clone site**

In `src/agent_toolkit_cli/pi_extension_add.py`, add `import shutil` to the imports, then replace lines 93-95:

```python
    canonical.parent.mkdir(parents=True, exist_ok=True)
    # May raise GitError -> no lock write (lock honesty, #283).
    skill_git.clone(parsed.url, canonical, ref=parsed.ref, env=env)
```

with:

```python
    canonical.parent.mkdir(parents=True, exist_ok=True)
    # `git clone --branch` accepts only branch/tag names — a raw SHA must be
    # cloned at HEAD then fetched + checked out (the import pattern, #259).
    pin_sha = parsed.ref if looks_like_sha(parsed.ref) else None
    # May raise GitError -> no lock write (lock honesty, #283).
    skill_git.clone(
        parsed.url, canonical, ref=None if pin_sha else parsed.ref, env=env,
    )
    if pin_sha and skill_git.is_git_repo(canonical):
        # Deliberate divergence from import's `except GitError: pass`:
        # import is a best-effort batch refresh, but add is a single
        # explicit pin — silently landing on the wrong commit would
        # violate fail-loud. Clean up the clone so a failed pin leaves
        # no orphaned store dir (#313) and no lock entry (#283).
        try:
            skill_git.fetch_ref(canonical, ref=pin_sha, env=env)
            skill_git.checkout(canonical, ref=pin_sha, env=env)
        except skill_git.GitError:
            shutil.rmtree(canonical, ignore_errors=True)
            raise
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_pi_extension_add.py -q`
Expected: all PASS (including the existing branch-ref and ref-less adds — regression guard)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_add.py tests/test_cli/test_pi_extension_add.py
git commit -m "fix(pi-extension): SHA-pinned add lands on the pinned commit (#330)"
```

---

### Task 3: SHA-pinned `add` — fail loudly, leave nothing behind

**Files:**
- Test: `tests/test_cli/test_pi_extension_add.py`
- Modify: `src/agent_toolkit_cli/pi_extension_add.py` (only if the test exposes a gap — Task 2's implementation already includes the cleanup)

- [ ] **Step 1: Write the test**

Append to `tests/test_cli/test_pi_extension_add.py`:

```python
def test_add_bad_sha_fails_loud_no_orphans(tmp_path, monkeypatch, git_sandbox):
    """A pin absent from the remote must raise (fail-loud, NOT silently stay
    at HEAD), write no lock entry (#283), and leave no store dir (#313)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    bogus = "0" * 40  # 40-hex, classified as SHA, exists nowhere

    with pytest.raises(Exception):  # GitError from fetch_ref
        pea.add(
            source=f"file://{git_sandbox.upstream}/tree/{bogus}",
            slug="ghost-pin", env=git_sandbox.env,
        )

    assert "ghost-pin" not in read_lock(pep.library_lock_path(env={})).skills
    assert not pep.library_pi_extension_path("ghost-pin", env={}).exists()
```

- [ ] **Step 2: Run test — expected to pass already (Task 2 shipped the cleanup)**

Run: `uv run pytest tests/test_cli/test_pi_extension_add.py::test_add_bad_sha_fails_loud_no_orphans -q`
Expected: PASS. **If it FAILS**, the cleanup in Task 2 Step 3 has a gap — fix it there (the `except skill_git.GitError: shutil.rmtree(...); raise` block) until this test passes. Do not weaken the test.

- [ ] **Step 3: Prove the test is real (it must bite without the cleanup)**

Do NOT use `git stash` to peek at a baseline. Instead, temporarily edit
`src/agent_toolkit_cli/pi_extension_add.py`: in the `except skill_git.GitError:`
block from Task 2, replace `shutil.rmtree(canonical, ignore_errors=True)` with
`pass`. Run:

`uv run pytest tests/test_cli/test_pi_extension_add.py::test_add_bad_sha_fails_loud_no_orphans -q`

Expected: FAIL on the final assertion (`library_pi_extension_path(...).exists()` is True — orphan dir left behind). Then restore the `shutil.rmtree(...)` line and re-run: PASS. If the test passes even with the cleanup stubbed out, it is vacuous — stop and fix the test.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli/test_pi_extension_add.py
git commit -m "test(pi-extension): bad SHA pin fails loud, no lock entry, no orphan dir (#330)"
```

---

### Task 4: doctor reclone honours the pin

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_doctor.py:337-353` (`_make_reclone_action`)
- Test: `tests/test_cli/test_cli_pi_extension_lifecycle.py` (§ `# Task B5: doctor`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli/test_cli_pi_extension_lifecycle.py` in the doctor section (after `test_doctor_detects_missing_canonical`). Reuse that test's seeding idiom — read it first and match its imports/helpers (it already has `git_sandbox`, lock seeding, and `pep`/lock imports in scope):

```python
def test_doctor_reclone_sha_pinned_lands_on_pin(tmp_path, monkeypatch, git_sandbox):
    """Reclone of a SHA-pinned entry must land on upstream_sha, not HEAD (#330)."""
    import subprocess
    monkeypatch.setenv("HOME", str(tmp_path))

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(git_sandbox.clone), *args],
            check=True, env=git_sandbox.env, capture_output=True, text=True,
        ).stdout.strip()

    first_sha = git("rev-parse", "HEAD")
    (git_sandbox.clone / "EXTRA.md").write_text("second\n")
    git("add", "-A"); git("commit", "-m", "second"); git("push", "origin", "main")

    # Lock entry: store-owned, pinned to first_sha, store copy MISSING.
    from agent_toolkit_cli.pi_extension_lock import LockEntry, LockFile, write_lock
    from agent_toolkit_cli import pi_extension_paths as pep
    lock_path = pep.library_lock_path(env={})
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock(lock_path, LockFile(version=1, skills={
        "pinned": LockEntry(
            source=str(git_sandbox.upstream), source_type="git",
            ref=first_sha, pi_extension_path="pinned", upstream_sha=first_sha,
        ),
    }))

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(home=tmp_path)
    reclone = next(
        f for f in findings
        if f.fix_action is not None and "Re-clone" in f.fix_action.description
    )
    reclone.fix_action.apply()

    canonical = pep.library_pi_extension_path("pinned", env={})
    head = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert head == first_sha
    assert not (canonical / "EXTRA.md").exists()
```

> The `diagnose(...)` signature: read `pi_extension_doctor.py:71` first and
> match the test call to the real parameters (it may take `home=`/`env=` or
> scope args — adapt the call, keep the assertions).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py::test_doctor_reclone_sha_pinned_lands_on_pin -q`
Expected: FAIL — either `GitError` (`--branch <sha>` rejected) or `head == second commit` (landed on HEAD, pin ignored)

- [ ] **Step 3: Implement the fix in `_make_reclone_action`**

In `src/agent_toolkit_cli/pi_extension_doctor.py`, add imports: `import shutil` and extend the existing `from agent_toolkit_cli import _pi_settings, skill_git` line's sibling imports with `from agent_toolkit_cli.pi_extension_add import looks_like_sha`. Replace the body of `_make_reclone_action` (`:337-353`):

```python
def _make_reclone_action(*, slug: str, entry: object) -> FixAction:
    """Re-clone the store copy from the lock entry's source.

    Pin resolution mirrors the import path: prefer `upstream_sha`, else a
    SHA-looking `ref`. `git clone --branch` rejects raw SHAs, so a pin is
    applied post-clone via fetch_ref + checkout (#330). A failed pin removes
    the partial clone and re-raises — fail loud, no orphan dir (#313).
    """
    source = getattr(entry, "source", "")
    ref = getattr(entry, "ref", None)
    upstream_sha = getattr(entry, "upstream_sha", None)
    canonical = library_pi_extension_path(slug)

    ref_is_sha = looks_like_sha(ref)
    pin_sha = upstream_sha or (ref if ref_is_sha else None)
    clone_ref = None if ref_is_sha else ref

    def _apply() -> None:
        if canonical.exists():
            return  # idempotent
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(source, canonical, ref=clone_ref, env=None)
        if pin_sha and skill_git.is_git_repo(canonical):
            try:
                skill_git.fetch_ref(canonical, ref=pin_sha, env=None)
                skill_git.checkout(canonical, ref=pin_sha, env=None)
            except skill_git.GitError:
                shutil.rmtree(canonical, ignore_errors=True)
                raise

    return FixAction(
        description=f"Re-clone {slug} from {source}",
        shell_preview=(
            f"git clone{(' --branch ' + clone_ref) if clone_ref else ''} "
            f"{source} {canonical}"
            + (f" && git -C {canonical} fetch origin {pin_sha}"
               f" && git -C {canonical} checkout {pin_sha}" if pin_sha else "")
        ),
        apply=_apply,
    )
```

- [ ] **Step 4: Run the doctor tests**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -q`
Expected: all PASS (new test + existing doctor tests — the no-pin path is unchanged: `clone_ref == ref`, `pin_sha is None`)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_doctor.py tests/test_cli/test_cli_pi_extension_lifecycle.py
git commit -m "fix(pi-extension): doctor reclone honours a SHA pin (#330)"
```

---

### Task 5: full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Run the entire suite**

Run: `uv run pytest -q`
Expected: everything green **except** (possibly, machine-dependent) the known local-only `test_empty_machine_is_empty` — see Worker notes. Any other failure is yours: fix before proceeding.

- [ ] **Step 2: Acceptance-criteria sweep**

Check each spec §2 criterion against a test or code line:

| Criterion | Evidence |
|---|---|
| 1. shorthand `@<sha>` works | same `parsed.ref` branch as test_add_sha_pinned_lands_on_pin (see Worker notes on hermeticity) |
| 2. URL `/tree/<sha>` works | `test_add_sha_pinned_lands_on_pin` |
| 3. branch/tag regression | existing `test_add_store_owned_clones_and_records` + suite green |
| 4. ref-less regression | existing add tests, suite green |
| 5. bad SHA: loud + no lock + no orphan | `test_add_bad_sha_fails_loud_no_orphans` |
| 6. lock records pin | assertions in `test_add_sha_pinned_lands_on_pin` |
| 7. doctor reclone pin | `test_doctor_reclone_sha_pinned_lands_on_pin` |
| 8. no schema/CLI change | diff touches only the two engines + tests |

- [ ] **Step 3 (optional, network + real GitHub): manual smoke**

```bash
HOME=$(mktemp -d) uv run agent-toolkit pi-extension add \
  ajanderson1/skills@22d0c764cd6c10ed06a7877e55a606d3435f1ec5
```

Expected: succeeds; `git -C $HOME/.agent-toolkit/pi-extensions/skills rev-parse HEAD` prints the pinned SHA. (Pre-fix this exact command produced `fatal: Remote branch ... not found`.)
