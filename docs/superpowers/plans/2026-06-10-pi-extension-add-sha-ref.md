# Fix SHA-pinned `pi-extension add` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `pi-extension add <source>@<sha>` (and the doctor reclone of a SHA-pinned lock entry) land on the pinned commit instead of failing with `fatal: Remote branch <sha> not found`, and make `update`/`reset` skip pinned entries instead of failing on them.

**Architecture:** `git clone --branch` accepts only branch/tag names, never a raw SHA. The fix adapts the proven import pattern (`pi_extension/import_cmd.py:115-122`): when the parsed ref *looks like* a SHA, clone at default HEAD (no `--branch`), then `fetch_ref(<sha>)` (best-effort — it rescues only full-SHA wants and always fails for abbreviations) + `checkout(<sha>)` (the fail-loud authority — it resolves abbreviations locally against the full clone). A failed checkout cleans up the partial store directory (no lock entry per #283, no orphan dir per #313). Doctor reclone pins ONLY on a SHA-looking `ref` — never on `upstream_sha`, which for add-created entries is the observed tip, not a pin. `update`/`reset` skip pinned entries with an informational message (one pinned entry must not poison the whole batch). No shallow-clone is added (measured: no benefit — see spec).

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
| `src/agent_toolkit_cli/pi_extension_add.py` | `add()` core | Add public `looks_like_sha()` helper; branch the clone site on it; best-effort fetch + fail-loud checkout with cleanup |
| `src/agent_toolkit_cli/pi_extension_doctor.py` | doctor engine | `_make_reclone_action` pins ONLY on a SHA-looking `ref` (never `upstream_sha`) |
| `src/agent_toolkit_cli/commands/pi_extension/update_cmd.py` | update verb | Skip pinned entries with informational message |
| `src/agent_toolkit_cli/commands/pi_extension/reset_cmd.py` | reset verb | Same pinned skip |
| `tests/test_cli/test_pi_extension_add.py` | add tests | `looks_like_sha` unit table; SHA happy path (full + abbreviated); bad-SHA fail-loud; branch-ref regression |
| `tests/test_cli/test_cli_pi_extension_lifecycle.py` | doctor + verb tests (§ Task B5) | reclone SHA-pin test; branch-entry stale-`upstream_sha` regression; update/reset pinned-skip tests |

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
    # Lock records the pin; upstream_sha is None (no origin/<sha> remote ref).
    entry = read_lock(pep.library_lock_path(env={})).skills["pinned"]
    assert entry.ref == first_sha
    assert entry.local_sha == first_sha
    assert entry.upstream_sha is None


def test_add_abbreviated_sha_pin_expands(tmp_path, monkeypatch, git_sandbox):
    """A 7-char pin must land on the full commit: `git fetch origin <short>`
    always fails (best-effort), and checkout resolves it locally (#330)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    first_sha, second_sha = _push_second_commit(git_sandbox)

    pea.add(
        source=f"file://{git_sandbox.upstream}/tree/{first_sha[:7]}",
        slug="shortpin", env=git_sandbox.env,
    )

    canonical = pep.library_pi_extension_path("shortpin", env={})
    head = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert head == first_sha != second_sha
    assert not (canonical / "EXTRA.md").exists()
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
        # fetch_ref is BEST-EFFORT: a full clone already holds every
        # ref-reachable object, so the fetch only rescues full-SHA pins
        # not reachable from advertised tips — and it ALWAYS fails for
        # abbreviated pins (git fetch accepts only remote refs and full
        # object IDs, while checkout resolves abbreviations locally).
        try:
            skill_git.fetch_ref(canonical, ref=pin_sha, env=env)
        except skill_git.GitError:
            pass
        # checkout is the FAIL-LOUD authority. Deliberate divergence from
        # import's swallow-and-stay-at-HEAD: add is a single explicit pin —
        # silently landing on the wrong commit would violate fail-loud.
        # Clean up the clone so a failed pin leaves no orphaned store dir
        # (#313) and no lock entry (#283).
        try:
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
`src/agent_toolkit_cli/pi_extension_add.py`: in the **checkout** `except
skill_git.GitError:` block from Task 2 (the one that re-raises — not the
best-effort fetch block), replace `shutil.rmtree(canonical, ignore_errors=True)`
with `pass`. Run:

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
    # upstream_sha=None matches what a real SHA-pinned add records (the
    # post-checkout `rev-parse origin/<sha>` fails and is caught).
    from agent_toolkit_cli.pi_extension_lock import LockEntry, LockFile, write_lock
    from agent_toolkit_cli import pi_extension_paths as pep
    lock_path = pep.library_lock_path(env={})
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock(lock_path, LockFile(version=1, skills={
        "pinned": LockEntry(
            source=str(git_sandbox.upstream), source_type="git",
            ref=first_sha, pi_extension_path="pinned", upstream_sha=None,
        ),
    }))

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
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


def test_doctor_reclone_branch_entry_lands_on_current_tip(
    tmp_path, monkeypatch, git_sandbox,
):
    """Regression: a BRANCH entry whose upstream_sha is stale (one commit
    behind the pushed tip) must reclone onto the CURRENT tip, on the branch —
    upstream_sha is the observed tip at add time, NOT a pin (#330 review)."""
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
    second_sha = git("rev-parse", "HEAD")

    from agent_toolkit_cli.pi_extension_lock import LockEntry, LockFile, write_lock
    from agent_toolkit_cli import pi_extension_paths as pep
    lock_path = pep.library_lock_path(env={})
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock(lock_path, LockFile(version=1, skills={
        "tracking": LockEntry(
            source=str(git_sandbox.upstream), source_type="git",
            ref="main", pi_extension_path="tracking", upstream_sha=first_sha,
        ),
    }))

    from agent_toolkit_cli import pi_extension_doctor as ped
    findings = ped.diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    reclone = next(
        f for f in findings
        if f.fix_action is not None and "Re-clone" in f.fix_action.description
    )
    reclone.fix_action.apply()

    canonical = pep.library_pi_extension_path("tracking", env={})
    def store_git(*args):
        return subprocess.run(
            ["git", "-C", str(canonical), *args],
            check=True, env=git_sandbox.env, capture_output=True, text=True,
        ).stdout.strip()
    assert store_git("rev-parse", "HEAD") == second_sha  # CURRENT tip, not stale
    assert store_git("rev-parse", "--abbrev-ref", "HEAD") == "main"  # on branch
```

> `diagnose()` takes four keyword-only args, all required:
> `diagnose(*, slugs: tuple[str, ...] | None, scope: Scope, home: Path | None,
> project: Path | None)` (`pi_extension_doctor.py:71`). `slugs=None` scans
> every slug in the lock; `scope="global"` targets the global library.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py::test_doctor_reclone_sha_pinned_lands_on_pin tests/test_cli/test_cli_pi_extension_lifecycle.py::test_doctor_reclone_branch_entry_lands_on_current_tip -q`
Expected: the SHA-pin test FAILS — either `GitError` (`--branch <sha>` rejected) or `head == second commit` (landed on HEAD, pin ignored). The branch-regression test PASSES both before and after the fix — it exists to kill the tempting-but-wrong variant that pins on `upstream_sha` (under that variant it goes RED). Do not delete it for being green.

- [ ] **Step 3: Implement the fix in `_make_reclone_action`**

In `src/agent_toolkit_cli/pi_extension_doctor.py`, add two imports at the top of the file (the code block below does NOT repeat them — add them before pasting it):

```python
import shutil

from agent_toolkit_cli.pi_extension_add import looks_like_sha
```

Then replace the body of `_make_reclone_action` (`:337-353`):

```python
def _make_reclone_action(*, slug: str, entry: object) -> FixAction:
    """Re-clone the store copy from the lock entry's source.

    Pin ONLY when the entry's `ref` is a SHA — NEVER from `upstream_sha`,
    which add() records for every store-owned entry as the observed tip at
    add time; pinning on it would detach every branch-tracking entry at a
    stale SHA (#330 review). `git clone --branch` rejects raw SHAs, so a pin
    is applied post-clone: best-effort fetch_ref (rescues full-SHA wants;
    always fails for abbreviations), then checkout as the fail-loud
    authority. A failed checkout removes the partial clone and re-raises —
    fail loud, no orphan dir (#313).
    """
    source = getattr(entry, "source", "")
    ref = getattr(entry, "ref", None)
    canonical = library_pi_extension_path(slug)

    ref_is_sha = looks_like_sha(ref)
    pin_sha = ref if ref_is_sha else None
    clone_ref = None if ref_is_sha else ref

    def _apply() -> None:
        if canonical.exists():
            return  # idempotent
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone(source, canonical, ref=clone_ref, env=None)
        if pin_sha and skill_git.is_git_repo(canonical):
            try:
                skill_git.fetch_ref(canonical, ref=pin_sha, env=None)
            except skill_git.GitError:
                pass  # best-effort; checkout resolves locally
            try:
                skill_git.checkout(canonical, ref=pin_sha, env=None)
            except skill_git.GitError:
                shutil.rmtree(canonical, ignore_errors=True)
                raise

    return FixAction(
        description=f"Re-clone {slug} from {source}",
        shell_preview=(
            f"git clone{(' --branch ' + clone_ref) if clone_ref else ''} "
            f"{source} {canonical}"
            + (f" && git -C {canonical} checkout {pin_sha}" if pin_sha else "")
        ),
        apply=_apply,
    )
```

- [ ] **Step 4: Run the doctor tests**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -q`
Expected: all PASS. Branch and ref-less entries are genuinely unchanged
because the pin comes ONLY from a SHA-looking `ref` (`pin_sha = ref if
ref_is_sha else None`): for them `clone_ref == ref` and `pin_sha is None`
regardless of what `upstream_sha` holds. The
`test_doctor_reclone_branch_entry_lands_on_current_tip` regression test
proves it against a stale `upstream_sha`.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_doctor.py tests/test_cli/test_cli_pi_extension_lifecycle.py
git commit -m "fix(pi-extension): doctor reclone honours a SHA pin (#330)"
```

---

### Task 5: `update` / `reset` skip pinned entries

**Files:**
- Modify: `src/agent_toolkit_cli/commands/pi_extension/update_cmd.py:70` (before the `resolve_ref`/`merge` block)
- Modify: `src/agent_toolkit_cli/commands/pi_extension/reset_cmd.py:76` (before the dirty check)
- Test: `tests/test_cli/test_cli_pi_extension_lifecycle.py`

Without this, one SHA-pinned entry poisons every `pi-extension update` run:
`update` does `resolve_ref(entry.ref)` → the SHA verbatim → `merge(origin/<sha>)`
which git rejects, so the user sees a phantom "conflict during merge" and exit 1
for a healthy entry. `reset` hits the same wall at `reset_hard(origin/<sha>)`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli/test_cli_pi_extension_lifecycle.py` (near the existing
update tests; reuse the file's existing `CliRunner`/`main` imports):

```python
def _seed_pinned_entry(tmp_path, git_sandbox) -> str:
    """Store-owned entry pinned to a SHA, with a real clone on disk.
    Returns the pinned SHA."""
    import subprocess
    from agent_toolkit_cli import pi_extension_add as pea
    sha = subprocess.run(
        ["git", "-C", str(git_sandbox.clone), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    pea.add(
        source=f"file://{git_sandbox.upstream}/tree/{sha}",
        slug="pinned", env=git_sandbox.env,
    )
    return sha


def test_update_skips_pinned_entry(tmp_path, monkeypatch, git_sandbox):
    """A SHA-pinned entry must not poison `update`: skip + exit 0 (#330)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    sha = _seed_pinned_entry(tmp_path, git_sandbox)

    r = CliRunner().invoke(main, ["pi-extension", "update", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned" in r.output.lower()
    assert sha[:7] in r.output
    assert "conflict" not in r.output.lower()


def test_reset_skips_pinned_entry(tmp_path, monkeypatch, git_sandbox):
    """`reset` on a pinned entry: informational skip, exit 0 (#330)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    sha = _seed_pinned_entry(tmp_path, git_sandbox)

    r = CliRunner().invoke(main, ["pi-extension", "reset", "pinned", "-g"])
    assert r.exit_code == 0, r.output
    assert "pinned to" in r.output.lower()
    assert sha[:7] in r.output
```

> NOTE: these tests depend on Task 2 (SHA-pinned `add` working). Task order
> matters here — do not reorder Task 5 before Task 2.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py::test_update_skips_pinned_entry tests/test_cli/test_cli_pi_extension_lifecycle.py::test_reset_skips_pinned_entry -q`
Expected: both FAIL — update prints "conflict during merge" and exits 1; reset raises `ClickException` ("git failed during reset")

- [ ] **Step 3: Implement the skips**

In `src/agent_toolkit_cli/commands/pi_extension/update_cmd.py`, add the import
`from agent_toolkit_cli.pi_extension_add import looks_like_sha` at the top,
then insert immediately BEFORE the line `ref = skill_git.resolve_ref(entry.ref, canonical)` (`:70`):

```python
        if looks_like_sha(entry.ref):
            click.echo(
                f"{slug}: pinned to {entry.ref[:7]} — skipping "
                f"(remove and re-add to change the pin)"
            )
            continue
```

In `src/agent_toolkit_cli/commands/pi_extension/reset_cmd.py`, same import,
same block inserted after the copy-mode check (before the `if not force:`
dirty check at `:76`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -q`
Expected: all PASS (the new skip fires only when `entry.ref` is SHA-looking;
branch/ref-less/npm rows take their existing paths)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/pi_extension/update_cmd.py src/agent_toolkit_cli/commands/pi_extension/reset_cmd.py tests/test_cli/test_cli_pi_extension_lifecycle.py
git commit -m "fix(pi-extension): update/reset skip SHA-pinned entries (#330)"
```

---

### Task 6: full-suite verification

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
| 6. lock records pin in ref+local_sha, upstream_sha=None | assertions in `test_add_sha_pinned_lands_on_pin` |
| 7. doctor reclone: SHA-ref pin honoured, upstream_sha NEVER a pin | `test_doctor_reclone_sha_pinned_lands_on_pin` + `test_doctor_reclone_branch_entry_lands_on_current_tip` |
| 8. update/reset skip pinned entries, exit 0 | `test_update_skips_pinned_entry` + `test_reset_skips_pinned_entry` |
| 9. no schema change; CLI changes additive only | diff touches the two engines + two verb guards + tests |
| 10. abbreviated SHA pins work | `test_add_abbreviated_sha_pin_expands` |

- [ ] **Step 3 (optional, network + real GitHub): manual smoke**

```bash
HOME=$(mktemp -d) uv run agent-toolkit pi-extension add \
  ajanderson1/skills@22d0c764cd6c10ed06a7877e55a606d3435f1ec5
```

Expected: succeeds; `git -C $HOME/.agent-toolkit/pi-extensions/skills rev-parse HEAD` prints the pinned SHA. (Pre-fix this exact command produced `fatal: Remote branch ... not found`.)
