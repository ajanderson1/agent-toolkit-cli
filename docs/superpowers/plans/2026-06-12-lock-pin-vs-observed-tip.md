# Lock pin-vs-observed-tip derived-reader Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop overloading `LockEntry.ref` by deciding "is this a user SHA-pin?" in one place — a derived in-memory reader — then repoint all six `looks_like_sha` call sites at it and fix the three skill/agent clone paths that reject SHA pins.

**Architecture:** Add `looks_like_sha` + `is_sha_pinned(entry)` to `skill_lock.py`, plus two pure read-only `LockEntry` properties (`ref_looks_pinned`, `ref_tracks_branch`). Extract the pi-extension clone→fetch→checkout dance into a shared `skill_git` helper so the three skill/agent reclone paths and pi-extension converge on one implementation. **No on-disk lock change** — the format stays byte-compatible with `vercel-labs/skills` (`npx skills`).

**Tech Stack:** Python 3, `uv run pytest`, dataclasses, `git_sandbox` test fixture (hermetic `file://` upstream).

**Spec:** `docs/superpowers/specs/2026-06-12-lock-pin-vs-observed-tip-design.md`

---

## File Structure

- `src/agent_toolkit_cli/skill_lock.py` — gains `looks_like_sha`, `is_sha_pinned`, and the two `LockEntry` properties. The discriminator's home.
- `src/agent_toolkit_cli/pi_extension_add.py` — `looks_like_sha` definition removed; re-imported from `skill_lock` so existing import paths still resolve.
- `src/agent_toolkit_cli/skill_git.py` — gains `clone_pinned_or_branch(...)`, the shared clone→fetch→checkout helper.
- `src/agent_toolkit_cli/skill_doctor.py` — `_make_reclone_action` + `_make_monorepo_reclone_action` use the shared helper.
- `src/agent_toolkit_cli/commands/agent/doctor_cmd.py` — `_make_readd_library_action` uses the shared helper.
- `src/agent_toolkit_cli/pi_extension_doctor.py` — reclone reads `entry.ref_looks_pinned`/`ref_tracks_branch`; clone body delegates to the shared helper.
- `src/agent_toolkit_cli/pi_extension_inventory.py`, `commands/pi_extension/{push,reset,update}_cmd.py` — repoint to `entry.ref_looks_pinned`.
- Tests: `tests/test_cli/test_skill_lock.py` (truth table), `tests/test_cli/test_cli_skill_doctor.py` + `tests/test_cli/test_agent_doctor.py` (clone red-green), `tests/test_cli/test_cli_pi_extension_lifecycle.py` (existing reclone tests stay green).

---

## Task 1: The discriminator — `looks_like_sha`, `is_sha_pinned`, and `LockEntry` properties

**Files:**
- Modify: `src/agent_toolkit_cli/skill_lock.py`
- Test: `tests/test_cli/test_skill_lock.py`

- [ ] **Step 1: Write the failing truth-table test**

Add to `tests/test_cli/test_skill_lock.py`:

```python
import pytest
from agent_toolkit_cli.skill_lock import LockEntry, is_sha_pinned, looks_like_sha

_SHA = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"  # 40-hex


@pytest.mark.parametrize(
    "source_type,ref,pinned,tracks_branch",
    [
        ("npm", _SHA, False, False),        # npm + hex ref: NOT a pin (#386 guard)
        ("npm", "main", False, False),      # npm + branch: neither (no clone)
        ("git", _SHA, True, False),         # store-owned + SHA: pinned
        ("git", "main", False, True),       # store-owned + branch: tracks branch
        ("git", None, False, True),         # store-owned + None: tracks default
        ("github", "abc1234", True, False), # short SHA on a git entry: pinned
    ],
)
def test_lockentry_pin_truth_table(source_type, ref, pinned, tracks_branch):
    entry = LockEntry(source="o/r", source_type=source_type, ref=ref)
    assert is_sha_pinned(entry) is pinned
    assert entry.ref_looks_pinned is pinned
    assert entry.ref_tracks_branch is tracks_branch


def test_looks_like_sha_unchanged():
    assert looks_like_sha(_SHA) is True
    assert looks_like_sha("abc1234") is True
    assert looks_like_sha("main") is False
    assert looks_like_sha(None) is False
    assert looks_like_sha("g" * 7) is False  # non-hex
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_lock.py::test_lockentry_pin_truth_table -v`
Expected: FAIL — `ImportError: cannot import name 'is_sha_pinned'` (and `ref_looks_pinned` attribute missing).

- [ ] **Step 3: Add `looks_like_sha` + `is_sha_pinned` to `skill_lock.py`**

At the top of `src/agent_toolkit_cli/skill_lock.py`, add `import re` (near the other stdlib imports). Add these module-level functions just below the `LockEntry`/`LockFile` dataclass definitions:

```python
def looks_like_sha(ref: str | None) -> bool:
    """True when `ref` can only sensibly be a commit SHA (lowercase hex,
    7-40 chars — git's abbreviated-to-full range).

    Why a heuristic is safe both ways: `git clone --branch` rejects a 40-hex
    *branch name* anyway, so classifying one as a SHA is strictly more correct;
    and a short all-hex *tag* classified as a SHA still resolves — fetch_ref +
    checkout accept tag names too. (Moved verbatim from pi_extension_add, #345.)
    """
    return bool(ref) and re.fullmatch(r"[0-9a-f]{7,40}", ref) is not None


def is_sha_pinned(entry: "LockEntry") -> bool:
    """True when the entry's `ref` is a user SHA-pin: a SHA-shaped ref on a
    store-owned (git-cloned) entry. An npm entry carrying a hex `ref`
    (hand-edited / future-schema) is NOT a pin — gating on source_type
    preserves the #386 phantom-pin fix. `upstream_sha` is NEVER consulted:
    it is the observed tip at add time, not a pin (#330 review)."""
    return entry.source_type != "npm" and looks_like_sha(entry.ref)
```

- [ ] **Step 4: Add the two read-only properties to `LockEntry`**

Inside the `@dataclass class LockEntry:` body (after the fields, before the class ends), add:

```python
    @property
    def ref_looks_pinned(self) -> bool:
        """Derived: does `ref` read as a user SHA-pin? Never a persisted
        field — the lock format is the vercel-labs/skills interop format and
        we do not add fields to it (#345)."""
        return is_sha_pinned(self)

    @property
    def ref_tracks_branch(self) -> bool:
        """Derived: does this store-owned entry follow a moving branch/tag
        (or the remote default when ref is None) rather than a fixed SHA?
        npm entries track nothing here (no clone)."""
        return self.source_type != "npm" and not looks_like_sha(self.ref)
```

(`is_sha_pinned` is defined at module scope above the class but referenced via forward-quote in its own signature; the property calls it at runtime after the module is fully loaded, so ordering is fine. If the linter objects to using `is_sha_pinned` before its textual definition, move the two functions above the `LockEntry` dataclass — both orderings are valid since the property body runs lazily.)

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_skill_lock.py -v`
Expected: PASS (truth table + `looks_like_sha_unchanged`).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_lock.py tests/test_cli/test_skill_lock.py
git commit -m "feat(lock): derive SHA-pin from ref in one place (#345)

Add looks_like_sha + is_sha_pinned + LockEntry.ref_looks_pinned /
.ref_tracks_branch. origin-aware (npm+hex is not a pin, #386 guard);
upstream_sha never consulted. No on-disk change.

Device: $(hostname -s)"
```

---

## Task 2: Re-home `looks_like_sha` import in `pi_extension_add`

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_add.py:36` (the `def looks_like_sha`), `:116` (call site)
- Test: existing `tests/test_cli/test_pi_extension_add.py` (must stay green)

- [ ] **Step 1: Remove the local definition, re-import from skill_lock**

In `src/agent_toolkit_cli/pi_extension_add.py`, delete the `def looks_like_sha(...)` function body (lines ~36-46) and add to the existing `from agent_toolkit_cli.skill_lock import (...)` block:

```python
from agent_toolkit_cli.skill_lock import (
    LockEntry,
    looks_like_sha,   # re-exported here so `from pi_extension_add import looks_like_sha` still resolves
    # ...existing names...
)
```

If `re` is now unused in `pi_extension_add.py`, remove its import.

The call site at `:116` stays as-is — it classifies a freshly-`parse_source`d `ParsedSource.ref` *before* a `LockEntry` exists, so it legitimately calls the bare helper:

```python
    pin_sha = parsed.ref if looks_like_sha(parsed.ref) else None
```

- [ ] **Step 2: Confirm downstream importers still resolve**

These modules do `from agent_toolkit_cli.pi_extension_add import looks_like_sha` and must keep working via the re-export: `pi_extension_doctor.py:31`, `pi_extension_inventory.py:13`, `commands/pi_extension/{push,reset,update}_cmd.py`. (They get repointed in Task 3, but the re-export keeps them green in the meantime.)

Run: `uv run pytest tests/test_cli/test_pi_extension_add.py -v`
Expected: PASS (no behaviour change; `looks_like_sha` is the same function).

- [ ] **Step 3: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_add.py
git commit -m "refactor(pi-extension): import looks_like_sha from skill_lock (#345)

Device: $(hostname -s)"
```

---

## Task 3: Collapse the five `LockEntry`-holding call sites onto `ref_looks_pinned`

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_inventory.py:117`, `commands/pi_extension/push_cmd.py:84`, `commands/pi_extension/reset_cmd.py:77`, `commands/pi_extension/update_cmd.py:71`, `pi_extension_doctor.py:370`
- Test: existing pi-extension suites must stay green (behaviour-preserving)

- [ ] **Step 1: Repoint inventory (absorbs the origin gate)**

`pi_extension_inventory.py:108-120` currently:

```python
            pinned_sha = (
                entry.ref
                if origin == "store-owned" and looks_like_sha(entry.ref)
                else None
            )
```

becomes (the `origin == "store-owned"` gate now lives inside the property):

```python
            pinned_sha = entry.ref if entry.ref_looks_pinned else None
```

Remove the now-unused `from agent_toolkit_cli.pi_extension_add import looks_like_sha` import at `:13` if nothing else in the file uses it.

- [ ] **Step 2: Repoint push / reset / update**

In each of `commands/pi_extension/push_cmd.py:84`, `reset_cmd.py:77`, `update_cmd.py:71`:

```python
        if looks_like_sha(entry.ref):
```

becomes:

```python
        if entry.ref_looks_pinned:
```

Remove each file's `from agent_toolkit_cli.pi_extension_add import looks_like_sha` import (`:19`/`:13`/`:13`) if unused afterward.

- [ ] **Step 3: Repoint pi_extension_doctor's reclone classification**

In `pi_extension_doctor.py:368-372`:

```python
    ref_is_sha = looks_like_sha(ref)
    pin_sha = ref if ref_is_sha else None
    clone_ref = None if ref_is_sha else ref
```

becomes (read from the entry directly):

```python
    pin_sha = ref if entry.ref_looks_pinned else None
    clone_ref = None if entry.ref_looks_pinned else ref
```

Note `entry` is the `_make_reclone_action` param; `ref = getattr(entry, "ref", None)` a few lines above stays. Remove the `from ...pi_extension_add import looks_like_sha` import at `:31` if unused (the clone body in Task 5 may still reference it indirectly via the helper — verify before deleting).

- [ ] **Step 4: Run the pi-extension suites**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py tests/test_cli/test_pi_extension_add.py tests/test_cli/test_cli_pi_extension_write.py -v`
Expected: PASS — behaviour is identical; `entry.ref_looks_pinned` returns exactly what `origin=="store-owned" and looks_like_sha(entry.ref)` did.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_inventory.py \
        src/agent_toolkit_cli/commands/pi_extension/push_cmd.py \
        src/agent_toolkit_cli/commands/pi_extension/reset_cmd.py \
        src/agent_toolkit_cli/commands/pi_extension/update_cmd.py \
        src/agent_toolkit_cli/pi_extension_doctor.py
git commit -m "refactor: read entry.ref_looks_pinned at the five LockEntry sites (#345)

Device: $(hostname -s)"
```

---

## Task 4: Shared `clone_pinned_or_branch` helper in `skill_git`

**Files:**
- Modify: `src/agent_toolkit_cli/skill_git.py`
- Test: `tests/test_cli/test_skill_git_clone_pin.py` (new) — direct unit test of the helper

- [ ] **Step 1: Write the failing helper test**

Create `tests/test_cli/test_skill_git_clone_pin.py`:

```python
import subprocess

from agent_toolkit_cli import skill_git


def _git(env, cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        check=True, env=env, capture_output=True, text=True,
    ).stdout.strip()


def test_clone_pinned_lands_on_sha(tmp_path, git_sandbox):
    """A SHA pin must NOT go through `git clone --branch <sha>` (git rejects
    it) — clone at HEAD, then checkout the pin."""
    first_sha = _git(git_sandbox.env, git_sandbox.clone, "rev-parse", "HEAD")
    (git_sandbox.clone / "EXTRA.md").write_text("second\n")
    _git(git_sandbox.env, git_sandbox.clone, "add", "-A")
    _git(git_sandbox.env, git_sandbox.clone, "commit", "-m", "second")
    _git(git_sandbox.env, git_sandbox.clone, "push", "origin", "main")

    dest = tmp_path / "pinned"
    skill_git.clone_pinned_or_branch(
        str(git_sandbox.upstream), dest, ref=first_sha, env=git_sandbox.env,
    )
    assert _git(git_sandbox.env, dest, "rev-parse", "HEAD") == first_sha
    assert not (dest / "EXTRA.md").exists()


def test_clone_branch_lands_on_tip(tmp_path, git_sandbox):
    """A branch ref clones --branch and lands on the current tip."""
    dest = tmp_path / "tracking"
    skill_git.clone_pinned_or_branch(
        str(git_sandbox.upstream), dest, ref="main", env=git_sandbox.env,
    )
    tip = _git(git_sandbox.env, git_sandbox.clone, "rev-parse", "HEAD")
    assert _git(git_sandbox.env, dest, "rev-parse", "HEAD") == tip
    assert _git(git_sandbox.env, dest, "rev-parse", "--abbrev-ref", "HEAD") == "main"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_git_clone_pin.py -v`
Expected: FAIL — `AttributeError: module 'agent_toolkit_cli.skill_git' has no attribute 'clone_pinned_or_branch'`.

- [ ] **Step 3: Implement the helper**

Add to `src/agent_toolkit_cli/skill_git.py` (needs `import shutil` at top if absent):

```python
def clone_pinned_or_branch(
    url: str, dest: Path, *, ref: str | None, env: dict[str, str] | None,
) -> None:
    """Clone `url` into `dest`, honouring a possible SHA pin.

    `git clone --branch <sha>` is rejected by git, so a SHA `ref` is applied
    post-clone: clone at HEAD (ref=None), best-effort fetch_ref (rescues
    full-SHA wants not reachable from advertised tips; always fails for
    abbreviations, which checkout resolves locally), then checkout as the
    fail-loud authority. A branch/tag `ref` (or None → remote default) clones
    `--branch` directly. A failed checkout removes the partial clone and
    re-raises — fail loud, no orphan dir (#313, #345)."""
    pin = ref if looks_like_sha(ref) else None
    clone(url, dest, ref=None if pin else ref, env=env)
    if pin and is_git_repo(dest):
        try:
            fetch_ref(dest, ref=pin, env=env)
        except GitError:
            pass  # best-effort; checkout resolves locally
        try:
            checkout(dest, ref=pin, env=env)
        except GitError:
            shutil.rmtree(dest, ignore_errors=True)
            raise
```

Add `from agent_toolkit_cli.skill_lock import looks_like_sha` to `skill_git.py`. **Watch for an import cycle:** `skill_lock` must not import `skill_git` at module top for this to be safe. `skill_lock.py` calls `subprocess` for `_apply_insteadof` but does **not** import `skill_git` — so the edge `skill_git → skill_lock` is acyclic. Verify with `uv run python -c "import agent_toolkit_cli.skill_git"` after the edit; if a cycle appears, do a function-local `from agent_toolkit_cli.skill_lock import looks_like_sha` inside `clone_pinned_or_branch` instead.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_cli/test_skill_git_clone_pin.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_git.py tests/test_cli/test_skill_git_clone_pin.py
git commit -m "feat(git): clone_pinned_or_branch — SHA-aware clone helper (#345)

Device: $(hostname -s)"
```

---

## Task 5: Fix the skill-doctor reclone paths (single + monorepo)

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py:331-345` (`_make_reclone_action`), `:379+` (`_make_monorepo_reclone_action`)
- Test: `tests/test_cli/test_cli_skill_doctor.py`

- [ ] **Step 1: Write the failing red-green test**

Add to `tests/test_cli/test_cli_skill_doctor.py` (model on the existing `_seed`/`git_sandbox` helpers already in the file; if the file lacks a direct `diagnose`+`fix_action.apply` test, follow the pi-extension lifecycle pattern):

```python
def test_skill_doctor_reclone_sha_pinned_lands_on_pin(
    git_sandbox, tmp_path, monkeypatch,
):
    """A SHA-pinned skill entry whose canonical is missing must reclone onto
    the pin — not be rejected by `git clone --branch <sha>` (#345)."""
    from agent_toolkit_cli import skill_doctor
    from agent_toolkit_cli.skill_lock import LockEntry, LockFile, write_lock

    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(git_sandbox.clone), *args],
            check=True, env=git_sandbox.env, capture_output=True, text=True,
        ).stdout.strip()

    first_sha = git("rev-parse", "HEAD")
    (git_sandbox.clone / "EXTRA.md").write_text("second\n")
    git("add", "-A"); git("commit", "-m", "second"); git("push", "origin", "main")

    # Global library lock: store-owned skill pinned to first_sha, canonical MISSING.
    from agent_toolkit_cli.skill_paths import library_lock_path
    lock_path = library_lock_path(home=tmp_path)  # adjust to the real signature
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    write_lock(lock_path, LockFile(version=1, skills={
        "demo": LockEntry(
            source=str(git_sandbox.upstream), source_type="git",
            ref=first_sha, upstream_sha=None,
        ),
    }))

    findings = skill_doctor.diagnose(
        slugs=None, scope="global", home=tmp_path, project=None,
    )
    reclone = next(
        f for f in findings
        if f.fix_action is not None and "Re-clone" in f.fix_action.description
    )
    reclone.fix_action.apply()

    from agent_toolkit_cli.skill_paths import canonical_skill_dir
    canonical = canonical_skill_dir("demo", scope="global", home=tmp_path, project=None)
    head = subprocess.run(
        ["git", "-C", str(canonical), "rev-parse", "HEAD"],
        check=True, env=git_sandbox.env, capture_output=True, text=True,
    ).stdout.strip()
    assert head == first_sha
```

> **Worker note:** confirm `library_lock_path` / `canonical_skill_dir` exact signatures and the `diagnose` parameter names against `skill_doctor.py:56` before running — the file's existing `_seed` helper is the canonical reference for how the global library is laid out in tests. Adjust the seeding to match (the existing drift tests in this file already seed a global library; reuse that machinery).

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli/test_cli_skill_doctor.py::test_skill_doctor_reclone_sha_pinned_lands_on_pin -v`
Expected: FAIL — the reclone raises `GitError` because `git clone --branch <first_sha>` is rejected (`fatal: Remote branch <sha> not found`).

- [ ] **Step 3: Fix `_make_reclone_action`**

In `skill_doctor.py:341-345`, replace the `_apply` clone line. The `ref = entry.ref` line at `:331` and the `preview_ref` at `:347` stay for the shell preview, but the actual clone delegates to the helper:

```python
    def _apply() -> None:
        if canonical.exists():
            return  # idempotent
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone_pinned_or_branch(url, canonical, ref=ref, env=None)
```

Update the `shell_preview` to reflect the post-clone checkout when `ref` is a SHA (mirror the pi-extension preview format):

```python
    from agent_toolkit_cli.skill_lock import looks_like_sha
    if looks_like_sha(ref):
        preview = (f"git clone {url} {canonical} && "
                   f"git -C {canonical} checkout {ref}")
    else:
        preview = f"git clone{(' --branch ' + ref) if ref else ''} {url} {canonical}"
    return FixAction(
        description=f"Re-clone {slug} from {url}",
        shell_preview=preview,
        apply=_apply,
    )
```

- [ ] **Step 4: Fix `_make_monorepo_reclone_action`**

The monorepo path clones the **parent** repo into the `_parents/` cache. Locate its `skill_git.clone(parent_url, parent_dir, ref=...)` call (around `:379-400`) and the `ref` it passes. A monorepo skill's pin is still on `entry.ref`, so replace that `clone(...)` with `clone_pinned_or_branch(parent_url, parent_dir, ref=ref, env=None)`. Keep the subsequent symlink-to-subpath logic unchanged. (Read the full function body before editing — only the clone call changes.)

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_cli/test_cli_skill_doctor.py -v`
Expected: PASS (new SHA test + all existing doctor tests).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_cli_skill_doctor.py
git commit -m "fix(skill): doctor reclone honours SHA pins (#345)

git clone --branch <sha> is rejected; route both single + monorepo
reclone through clone_pinned_or_branch (clone-at-HEAD + checkout).

Device: $(hostname -s)"
```

---

## Task 6: Fix the agent-doctor re-add clone path

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/doctor_cmd.py:99`
- Test: `tests/test_cli/test_agent_doctor.py`

- [ ] **Step 1: Write the failing red-green test**

Add to `tests/test_cli/test_agent_doctor.py` a test that seeds a SHA-pinned agent library entry with a missing canonical, runs the doctor's re-add fix action, and asserts the recloned canonical's `HEAD == pinned_sha`. Model it on the existing agent-doctor tests in that file (they already build a library + lock via the file's helpers) and on Task 5's structure. Selector: the re-add `FixAction` (its description mentions re-add / re-clone — confirm the exact string from `_make_readd_library_action` and match on it).

```python
def test_agent_doctor_readd_sha_pinned_lands_on_pin(
    git_sandbox, tmp_path, monkeypatch,
):
    """An unlisted SHA-pinned agent re-added by doctor must land on the pin,
    not be rejected by `git clone --branch <sha>` (#345)."""
    # ... seed library lock with LockEntry(source=upstream, source_type="git",
    #     ref=first_sha, agent_path=..., upstream_sha=None), canonical missing ...
    # ... run doctor diagnose, find the re-add fix_action, apply it ...
    # ... assert HEAD of the recloned canonical == first_sha ...
```

> **Worker note:** fill in the seeding from the existing helpers in `test_agent_doctor.py` (it already exercises `_make_readd_library_action` for the #360 unlisted case — reuse that setup, just set `ref` to a SHA and assert the landed commit).

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_cli/test_agent_doctor.py::test_agent_doctor_readd_sha_pinned_lands_on_pin -v`
Expected: FAIL — `GitError`, `git clone --branch <sha>` rejected.

- [ ] **Step 3: Fix the clone call**

In `commands/agent/doctor_cmd.py:99`, inside `_make_readd_library_action._apply`:

```python
        if not canonical.exists():
            canonical.parent.mkdir(parents=True, exist_ok=True)
            skill_git.clone(url, canonical, ref=entry.ref, env=None)
```

becomes:

```python
        if not canonical.exists():
            canonical.parent.mkdir(parents=True, exist_ok=True)
            skill_git.clone_pinned_or_branch(url, canonical, ref=entry.ref, env=None)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_cli/test_agent_doctor.py -v`
Expected: PASS (new test + existing agent-doctor tests).

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/doctor_cmd.py tests/test_cli/test_agent_doctor.py
git commit -m "fix(agent): doctor re-add honours SHA pins (#345)

Device: $(hostname -s)"
```

---

## Task 7: Refactor pi-extension reclone onto the shared helper + full-suite green

**Files:**
- Modify: `src/agent_toolkit_cli/pi_extension_doctor.py:375-400` (the `_apply` clone dance)
- Test: `tests/test_cli/test_cli_pi_extension_lifecycle.py` (existing `test_doctor_reclone_sha_pinned_lands_on_pin` + `test_doctor_reclone_branch_entry_lands_on_current_tip` must stay green)

- [ ] **Step 1: Replace the inline clone→fetch→checkout with the shared helper**

In `pi_extension_doctor.py`, the `_apply` body (currently lines ~375-391) does the clone, fetch_ref, checkout inline. Replace the clone+pin block with:

```python
        if canonical.exists():
            if not force:
                return  # idempotent (missing_canonical: a race re-created it)
            shutil.rmtree(canonical, ignore_errors=True)  # half_dir (#347)
        canonical.parent.mkdir(parents=True, exist_ok=True)
        skill_git.clone_pinned_or_branch(source, canonical, ref=ref, env=None)
```

where `ref` is the entry's ref (already in scope as `ref = getattr(entry, "ref", None)`). The helper internally re-derives `pin` via `looks_like_sha`, so `pin_sha`/`clone_ref` locals computed in Task 3 are now only needed for the `shell_preview`. Keep them for the preview string; the `_apply` no longer uses them.

- [ ] **Step 2: Run the existing reclone regression tests**

Run: `uv run pytest tests/test_cli/test_cli_pi_extension_lifecycle.py -k reclone -v`
Expected: PASS — `test_doctor_reclone_sha_pinned_lands_on_pin`, `test_doctor_reclone_branch_entry_lands_on_current_tip`, `test_reclone_force_replaces_non_repo_dir` all green (behaviour identical; the helper is a verbatim extraction of the same dance).

- [ ] **Step 3: Run the full suite (changed-surface first, then whole)**

Run: `uv run pytest tests/test_cli/test_skill_lock.py tests/test_cli/test_cli_skill_doctor.py tests/test_cli/test_agent_doctor.py tests/test_cli/test_cli_pi_extension_lifecycle.py tests/test_cli/test_skill_git_clone_pin.py -v`
Expected: PASS.

Then the whole suite:
Run: `uv run pytest -q 2>&1 | tail -15`
Expected: all pass **except** the two known whitelisted env-isolation failures — `test_pi_extension_inventory.py::test_empty_machine_is_empty` and `test_tui/test_instruction_state.py::test_build_instruction_rows_empty_lock_no_canonical` — which fail identically on a clean base (verify by checking they are unrelated to this change). If any OTHER test fails, stop and investigate.

- [ ] **Step 4: Run linters**

Run: `uv run ruff check src/ tests/ && uv run mypy src/`
Expected: no NEW errors vs base (the repo carries pre-existing mypy/ruff baseline counts — compare, don't assume zero). The new property/helper must be clean.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/pi_extension_doctor.py
git commit -m "refactor(pi-extension): reclone via shared clone_pinned_or_branch (#345)

Three reclone paths (skill+agent+pi-extension) now share one SHA-aware
clone implementation. No behaviour change here — the helper is a verbatim
extraction of the pi-extension dance.

Device: $(hostname -s)"
```

---

## Self-Review notes (author)

- **Spec coverage:** discriminator (Task 1), six-site collapse (Tasks 2-3, with `add.py` as the documented exception in Task 2), three clone-path fixes (Tasks 4-6), pi-extension convergence (Task 7), persisted-field-B rejection (recorded in spec, no task needed — it's a non-action). Truth-table npm+hex row → Task 1 Step 1. ✓
- **Naming consistency:** `is_sha_pinned` (helper), `ref_looks_pinned` / `ref_tracks_branch` (properties), `clone_pinned_or_branch` (git helper) used identically across all tasks. ✓
- **No regex change:** confirmed — `looks_like_sha` is moved verbatim, never edited. ✓
- **Import-cycle risk** flagged in Task 4 Step 3 with a function-local fallback. ✓
- **Whitelisted failures** named explicitly in Task 7 Step 3 so the worker does not chase them. ✓
- **Open verification points** (test-helper signatures for skill/agent doctor seeding) are flagged inline as worker notes rather than guessed — the worker confirms against the existing tests in each file before running.
