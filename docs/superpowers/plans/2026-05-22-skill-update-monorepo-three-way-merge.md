# skill update: monorepo three-way merge + TUI state fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-05-22-skill-update-monorepo-three-way-merge-design.md`

**Goal:** Make monorepo skills locally editable like per-skill repos. Two coupled fixes shipped together:
1. `skill update <slug>` for monorepo entries performs `git fetch` + `git merge --no-edit origin/<ref>` on the parent clone (was: `git pull --ff-only`).
2. The TUI's `state` column reports `clean` / `dirty` for monorepo skills with a healthy parent clone (was: blanket `copy` regardless of working-tree state).

**Architecture:** `update_cmd.py`'s monorepo branch swaps `pull_ff_only` for `fetch` + `merge`. Error message names the parent clone path. Copy-mode re-copy step stays but only fires on successful merge. `skill_state.py`'s `build_skill_rows` branches on `entry.parent_url is not None` before the existing `is_git_repo(canonical)` check, deriving state from `parent_clone_path(...)` for monorepo entries. The `copy` label narrows to "genuinely uneditable" (no parent clone, plain-file install). No lock schema changes.

**Tech Stack:** Python 3.12+, Click 8.x, pytest (existing test layout), uv (already running pre-commit pytest).

---

## Task 1: CLI — replace `pull_ff_only` with `fetch` + `merge` in monorepo update branch

The bug: PR #177 used `pull --ff-only` which refuses any local divergence in the parent clone. Per-skill-repo entries already do the right thing with `fetch` + `merge`. We align the two code paths.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/update_cmd.py`

- [ ] **Step 1: Locate the monorepo branch of `update_cmd`**

Open `src/agent_toolkit_cli/commands/skill/update_cmd.py`. Find the block guarded by `if entry.parent_url is not None:` (around lines 50–94 as of this writing). It currently:
1. Resolves `parent_dir = parent_clone_path(owner, repo, ref=entry.ref, env=None)`.
2. Checks `skill_git.is_git_repo(parent_dir)`.
3. Calls `skill_git.pull_ff_only(parent_dir, ref=ref, env=None)` inside a `try/except skill_git.GitError`.
4. On exception: prints `f"{slug}: parent pull failed (non-fast-forward?)"` + `exc.stderr`; sets `had_conflict = True`; `continue`s.
5. If `entry.extras.get("materialised") == "copy"`: removes `library_dir` and re-copies from `parent_dir / entry.skill_path`.
6. Updates `entry.upstream_sha = skill_git.head_sha(parent_dir, env=None)`; writes lock; echoes `"{slug}: updated (parent {entry.source} @ {ref})"`.

- [ ] **Step 2: Replace `pull_ff_only` with `fetch` + `merge`**

Change the `try/except` to call `skill_git.fetch` then `skill_git.merge` — same shape the per-skill-repo branch uses further down the function:

```python
try:
    skill_git.fetch(parent_dir, env=None)
    skill_git.merge(parent_dir, ref=ref, env=None)
except skill_git.GitError as exc:
    click.echo(
        f"{slug}: merge failed in parent clone at {parent_dir}.\n"
        f"  Resolve conflicts there (or commit/stash your changes), "
        f"then re-run `agent-toolkit-cli skill update {slug}`."
    )
    click.echo(exc.stderr)
    had_conflict = True
    continue
```

Key changes vs. the existing code:
- `pull_ff_only(parent_dir, ref=ref, env=None)` → `fetch(parent_dir, env=None)` + `merge(parent_dir, ref=ref, env=None)`.
- Error message names the **parent clone path** (so users know where to `cd`) and tells them to commit/stash for the dirty-tree case. The old message ("non-fast-forward?") becomes wrong now that we allow merges, so it's fully replaced.

- [ ] **Step 3: Keep the post-merge copy-mode re-copy on success only**

The existing block:

```python
if entry.extras.get("materialised") == "copy":
    library_dir = library_skill_path(slug)
    skill_root = parent_dir / entry.skill_path
    if library_dir.exists():
        shutil.rmtree(library_dir)
    shutil.copytree(skill_root, library_dir)
```

…lives **after** the try/except. Since we `continue` on `GitError`, this block only runs on a successful merge. No change needed — verify by reading the diff. The spec requires "on conflict, the library canonical is left at its prior state" — the `continue` already delivers that.

- [ ] **Step 4: Confirm the success-path log message still makes sense**

```python
click.echo(f"{slug}: updated (parent {entry.source} @ {ref})")
```

Still accurate. A merge result and a fast-forward result both produce "updated". Don't add merge-commit detail to the log — keep it terse, parity with the per-skill-repo branch.

- [ ] **Step 5: Verify nothing else in the file relies on `pull_ff_only`**

```bash
grep -n "pull_ff_only" src/agent_toolkit_cli/commands/skill/update_cmd.py
```
Expected: zero matches in this file after the edit.

```bash
grep -rn "pull_ff_only" src/agent_toolkit_cli/
```
Expected: only the definition in `skill_git.py`. The helper is left in place — it's tested and may be useful for future ff-only flows (e.g. `skill reset` — already shipped uses its own `reset_hard` though).

- [ ] **Step 6: Run the existing monorepo update tests**

```bash
uv run pytest tests/test_cli/test_skill_update_monorepo.py -q
```
Expected: both existing tests pass. A clean fast-forward goes through `merge` and produces the same result as `pull --ff-only`, so neither test should require changes.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/update_cmd.py
git commit -m "feat(update): three-way merge for monorepo skill update

Replace pull --ff-only with fetch + merge --no-edit on the parent
clone, matching per-skill-repo update semantics. Users can now
commit local edits to the parent clone's branch and pull upstream
without forking.

Conflicts surface as exit 1 with an error message naming the parent
clone path so the user knows where to resolve them.

Closes <ISSUE-NUMBER>."
```

(Replace `<ISSUE-NUMBER>` with the filed issue.)

---

## Task 2: CLI tests — three-way merge, conflict, dirty tree

The existing test file covers clean fast-forward and copy-mode re-copy. Add three new tests for the new behaviours.

**Files:**
- Modify: `tests/test_cli/test_skill_update_monorepo.py`

- [ ] **Step 1: Read the existing test helpers**

```bash
sed -n '1,30p' tests/test_cli/test_skill_update_monorepo.py
```

`_init_parent(tmp_path)` initialises a parent git repo from the `monorepo_skills` fixture with a single `init` commit on `main`. Re-use it. The helper uses `scrub_git_env()` from `tests/conftest.py` — keep that pattern (per `memory/feedback_git_env_leak.md`).

- [ ] **Step 2: Add test — local commit + non-conflicting upstream commit → exit 0, both present**

Append to the test file:

```python
def test_update_monorepo_merges_local_and_upstream_commits(
    tmp_path, monkeypatch,
):
    """User commits a local change to the parent clone, upstream gets a
    non-conflicting commit. `skill update` merges both."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    parent_clone = library / "skills" / "_parents" / "_" / parent.name
    # `_init_parent` produces an `owner/repo` of `_/parent` because
    # we cloned from a file:// URL; locate the clone by walking _parents/.
    candidates = list((library / "skills" / "_parents").glob("*/*"))
    assert len(candidates) == 1, candidates
    parent_clone = candidates[0]

    env = scrub_git_env()

    # 1. Local commit in the parent clone (the "I edited it" path).
    (parent_clone / "mkdocs" / "LOCAL.md").write_text("local change\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "local edit"],
    ):
        subprocess.run(cmd, cwd=parent_clone, check=True, env=env)

    # 2. Upstream commit on a different file.
    (parent / "mkdocs" / "UPSTREAM.md").write_text("upstream change\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream edit"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    # 3. Update — should merge.
    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code == 0, r2.output

    canonical = library / "skills" / "mkdocs"
    assert (canonical / "LOCAL.md").read_text() == "local change\n"
    assert (canonical / "UPSTREAM.md").read_text() == "upstream change\n"
```

> **Implementation note:** `_init_parent` clones from a `file://` URL; the
> `_parents/<owner>/<repo>` layout under the library uses an owner placeholder
> for non-`owner/repo` sources. The test discovers the clone path by globbing
> rather than guessing. If the actual layout differs after Task 1, adjust this
> discovery step but **don't** add a special-cased fixture — the goal is to
> test what users see in practice.

- [ ] **Step 3: Add test — conflicting edits surface real merge conflict**

```python
def test_update_monorepo_surfaces_real_merge_conflict(tmp_path, monkeypatch):
    """Both local and upstream change the same file → `skill update` exits
    non-zero, names the parent clone path, leaves the clone mid-merge."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    candidates = list((library / "skills" / "_parents").glob("*/*"))
    parent_clone = candidates[0]

    env = scrub_git_env()
    target = "mkdocs/SKILL.md"

    # Local change.
    (parent_clone / target).write_text("LOCAL VERSION\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "local"],
    ):
        subprocess.run(cmd, cwd=parent_clone, check=True, env=env)

    # Upstream change to the same file.
    (parent / target).write_text("UPSTREAM VERSION\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    # Update — should fail with a useful message.
    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code != 0, r2.output
    assert str(parent_clone) in r2.output, r2.output
    assert "mkdocs:" in r2.output, r2.output

    # The parent clone should be mid-merge (MERGE_HEAD present).
    assert (parent_clone / ".git" / "MERGE_HEAD").exists(), \
        "parent clone should be left mid-merge so user can resolve"
```

- [ ] **Step 4: Add test — dirty working tree refused**

```python
def test_update_monorepo_refuses_dirty_working_tree(tmp_path, monkeypatch):
    """Uncommitted change in the parent clone → `skill update` exits
    non-zero with a message telling the user to commit or stash."""
    parent = _init_parent(tmp_path)
    parent_url = f"file://{parent}"
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(cli, ["skill", "add", parent_url, "--skill", "mkdocs"])
    assert r1.exit_code == 0, r1.output

    candidates = list((library / "skills" / "_parents").glob("*/*"))
    parent_clone = candidates[0]

    # Leave an uncommitted change.
    (parent_clone / "mkdocs" / "SKILL.md").write_text("dirty\n")

    # Upstream change so the merge has actual work to do.
    env = scrub_git_env()
    (parent / "mkdocs" / "OTHER.md").write_text("upstream\n")
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "upstream"],
    ):
        subprocess.run(cmd, cwd=parent, check=True, env=env)

    r2 = runner.invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r2.exit_code != 0, r2.output
    assert str(parent_clone) in r2.output, r2.output
```

- [ ] **Step 5: Run the new + existing tests**

```bash
uv run pytest tests/test_cli/test_skill_update_monorepo.py -q
```
Expected: five tests pass (two existing + three new).

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli/test_skill_update_monorepo.py
git commit -m "test(update): three-way merge, conflict, dirty-tree cases"
```

---

## Task 3: TUI — derive monorepo state from parent clone

The bug: `build_skill_rows` checks `is_git_repo(canonical)` — but for monorepo skills `canonical` is a symlink (or copy) into a parent subpath that has no `.git/` of its own. The result is a blanket `copy` label regardless of working-tree state. Fix: branch on `entry.parent_url is not None` and derive state from the **parent clone**.

**Files:**
- Modify: `src/agent_toolkit_tui/skill_state.py`

- [ ] **Step 1: Add the import**

At the top of `skill_state.py`, add `parent_clone_path` to the imports from `agent_toolkit_cli.skill_paths`:

```python
from agent_toolkit_cli.skill_paths import (
    ...  # existing imports
    parent_clone_path,
)
```

- [ ] **Step 2: Branch on `parent_url` in `build_skill_rows`**

Replace the state-derivation block in `build_skill_rows` (currently lines 117–128):

```python
        if not canonical.exists():
            # Project scope: slug is in the library but not yet installed here.
            # Global scope: library entry recorded but directory was deleted.
            state: State = "library" if scope == "project" else "missing"
        elif not skill_git.is_git_repo(canonical):
            state = "copy"
        else:
            wt = skill_git.status(canonical, env=None)
            state = (
                "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY
                else "clean"
            )
```

With:

```python
        if not canonical.exists():
            # Project scope: slug is in the library but not yet installed here.
            # Global scope: library entry recorded but directory was deleted.
            state: State = "library" if scope == "project" else "missing"
        elif entry.parent_url is not None:
            # Monorepo skill — state lives in the parent clone, not the
            # symlinked subpath (which has no `.git/` of its own).
            owner, repo = entry.source.split("/", 1)
            parent_dir = parent_clone_path(
                owner, repo, ref=entry.ref, env=None,
            )
            if not skill_git.is_git_repo(parent_dir):
                # Parent clone missing — user `rm -rf`'d it, or
                # materialised: copy with no parent available.
                state = "copy"
            else:
                wt = skill_git.status(parent_dir, env=None)
                state = (
                    "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY
                    else "clean"
                )
        elif not skill_git.is_git_repo(canonical):
            # Plain-file install (e.g. `npx skills add --copy`).
            state = "copy"
        else:
            wt = skill_git.status(canonical, env=None)
            state = (
                "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY
                else "clean"
            )
```

The `parent_url is not None` branch sits **between** the `not canonical.exists()` check and the `not is_git_repo(canonical)` check — so a missing canonical still goes to `missing`/`library`, and the legacy plain-file case still maps to `copy`.

- [ ] **Step 3: Verify no other call site in the TUI assumes `copy` means monorepo**

```bash
grep -rn '"copy"\|state == .copy.\|state.copy' src/agent_toolkit_tui/
```
Expected matches (all benign):
- `skill_state.py:23` — `State` enum literal definition (untouched).
- `skill_state.py:121` and the new branch — the two places we just edited.
- `widgets/skill_grid.py:31` — styling map entry (untouched; `copy` still renders blue).
- `app.py:306` — `if row.state in ("missing", "copy"):` gating the install button.

Confirm `app.py:306` keeps making sense: monorepo skills no longer hit this branch (they're `clean`/`dirty` instead), which is correct — they're install-eligible. Plain-file `copy` rows still get gated, also correct.

- [ ] **Step 4: Smoke-test build_skill_rows by hand**

```bash
uv run python -c "
from pathlib import Path
from agent_toolkit_tui.skill_state import build_skill_rows
rows = build_skill_rows(scope='global', home=Path.home(), project=None)
for r in rows:
    print(f'{r.slug:20s} state={r.state}')
"
```
Expected: any monorepo skill installed via PR #177 (e.g. `find-skills`) now reports `clean` (or `dirty` if you've edited its parent clone). Per-skill-repo entries like `journal` are unaffected.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_tui/skill_state.py
git commit -m "fix(tui): derive monorepo skill state from parent clone

Monorepo skills' library canonical is a symlink into a parent subpath
with no .git/, so the previous is_git_repo(canonical) check
classified them all as 'copy' regardless of working-tree state. The
'copy' label implied 'uneditable' — wrong now that update does a
three-way merge.

Branch on entry.parent_url and run git status against the parent
clone instead. 'copy' now means what it should: plain-file install
or parent clone missing."
```

---

## Task 4: TUI tests — clean / dirty / parent-missing states for monorepo

**Files:**
- Locate or create the test module (the existing test layout for TUI state should make this obvious; if no test currently calls `build_skill_rows`, add `tests/test_tui/test_skill_state.py`).

- [ ] **Step 1: Find the existing TUI state tests (if any)**

```bash
grep -rn "build_skill_rows\|SkillRow\b" tests/ | head -20
```
If a test file exists, append the new tests there. If not, create `tests/test_tui/test_skill_state.py` with the standard test harness (CliRunner is not needed here — `build_skill_rows` is a pure function).

- [ ] **Step 2: Add fixture helper to install a monorepo skill into a tmp library**

Re-use the `_init_parent` pattern from `test_skill_update_monorepo.py`. Extract it to a shared `tests/conftest.py` helper if both modules import it, or duplicate it locally — duplication is fine if the helper is < 20 lines.

- [ ] **Step 3: Test — monorepo with clean parent reports `clean`**

```python
def test_build_rows_monorepo_clean_when_parent_clean(
    tmp_path, monkeypatch,
):
    parent = _init_parent(tmp_path)
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(
        cli, ["skill", "add", f"file://{parent}", "--skill", "mkdocs"]
    )
    assert r1.exit_code == 0, r1.output

    rows = build_skill_rows(
        scope="global", home=Path.home(), project=None,
    )
    row = next(r for r in rows if r.slug == "mkdocs")
    assert row.state == "clean", row
```

> The `home=Path.home()` is fine here because we've redirected
> `AGENT_TOOLKIT_SKILLS_ROOT` and the library lock follows it. If
> `build_skill_rows` reads other paths from `home`, mock them.

- [ ] **Step 4: Test — dirty working tree in parent reports `dirty`**

```python
def test_build_rows_monorepo_dirty_when_parent_has_uncommitted_change(
    tmp_path, monkeypatch,
):
    parent = _init_parent(tmp_path)
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(
        cli, ["skill", "add", f"file://{parent}", "--skill", "mkdocs"]
    )
    assert r1.exit_code == 0, r1.output

    candidates = list((library / "skills" / "_parents").glob("*/*"))
    parent_clone = candidates[0]
    (parent_clone / "mkdocs" / "SKILL.md").write_text("dirty\n")

    rows = build_skill_rows(
        scope="global", home=Path.home(), project=None,
    )
    row = next(r for r in rows if r.slug == "mkdocs")
    assert row.state == "dirty", row
```

- [ ] **Step 5: Test — local commit in parent reports `dirty`**

> **Decision check:** `skill_git.status(...)` uses `git status --porcelain`, which lists uncommitted changes but **does not** flag commits ahead of upstream. So a local commit on a clean working tree reports `clean` from this helper. The spec acknowledges this — we match per-skill-repo semantics exactly, even though it's a slight gap (resolved as an open question for `skill status` enhancement). Adjust the test accordingly to reflect actual behaviour:

```python
def test_build_rows_monorepo_clean_when_parent_has_only_committed_changes(
    tmp_path, monkeypatch,
):
    """Local commits with no uncommitted changes → `clean`. This matches the
    per-skill-repo branch's behaviour (git status --porcelain doesn't surface
    ahead-of-upstream). Documented gap; addressed separately if needed."""
    parent = _init_parent(tmp_path)
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(
        cli, ["skill", "add", f"file://{parent}", "--skill", "mkdocs"]
    )
    assert r1.exit_code == 0, r1.output

    candidates = list((library / "skills" / "_parents").glob("*/*"))
    parent_clone = candidates[0]
    (parent_clone / "mkdocs" / "LOCAL.md").write_text("local\n")
    env = scrub_git_env()
    for cmd in (
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        ["git", "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-q", "-m", "local"],
    ):
        subprocess.run(cmd, cwd=parent_clone, check=True, env=env)

    rows = build_skill_rows(
        scope="global", home=Path.home(), project=None,
    )
    row = next(r for r in rows if r.slug == "mkdocs")
    assert row.state == "clean", row
```

- [ ] **Step 6: Test — parent clone missing falls back to `copy`**

```python
def test_build_rows_monorepo_copy_when_parent_missing(
    tmp_path, monkeypatch,
):
    parent = _init_parent(tmp_path)
    library = tmp_path / "library"
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library / "skills"))

    runner = CliRunner()
    r1 = runner.invoke(
        cli, ["skill", "add", f"file://{parent}", "--skill", "mkdocs"]
    )
    assert r1.exit_code == 0, r1.output

    # User rm -rf'd the parent clone.
    parents_dir = library / "skills" / "_parents"
    shutil.rmtree(parents_dir)
    # Library canonical (symlink) now dangles — recreate as a plain dir
    # so the existence check still passes but is_git_repo fails.
    canonical = library / "skills" / "mkdocs"
    if canonical.is_symlink():
        canonical.unlink()
    canonical.mkdir(parents=True, exist_ok=True)

    rows = build_skill_rows(
        scope="global", home=Path.home(), project=None,
    )
    row = next(r for r in rows if r.slug == "mkdocs")
    assert row.state == "copy", row
```

> If the dangling-symlink handling differs in `build_skill_rows.canonical.exists()`
> (a dangling symlink's `.exists()` returns False), this test instead exercises
> the `missing` branch. Inspect actual behaviour during Step 7 and adjust the
> setup or the assertion — the **intent** is to cover the "parent gone" case,
> not to enforce a specific state literal.

- [ ] **Step 7: Run the TUI state tests**

```bash
uv run pytest tests/test_tui/test_skill_state.py -q
```
Expected: four new tests pass; any pre-existing TUI state tests continue to pass.

- [ ] **Step 8: Commit**

```bash
git add tests/test_tui/test_skill_state.py
git commit -m "test(tui): monorepo state reports clean/dirty/copy correctly"
```

---

## Task 5: Docs — README, cli.md, and spec supersession note

**Files:**
- Modify: `README.md`
- Modify: `docs/cli.md` (if it exists; otherwise skip and note in PR)
- Modify: `docs/superpowers/specs/2026-05-21-skill-add-monorepo-design.md`

- [ ] **Step 1: Locate the Skills section in README**

```bash
grep -n "^## \|^### " README.md | head -30
```
Find the section that documents `skill add` for monorepo skills (added by PR #177). Update or extend it to cover the new semantics.

- [ ] **Step 2: Add an "Editing monorepo skills" subsection**

Add a paragraph (concise — don't pad) under the existing monorepo-add docs. Key points to communicate:
1. The parent clone at `<library>/_parents/<owner>/<repo>/` is yours to edit; commit changes on its branch as you would any git repo.
2. `agent-toolkit-cli skill update <slug>` runs `git fetch` + `git merge` on the parent clone, so local commits and upstream commits merge cleanly.
3. On conflict, the parent clone is left mid-merge; resolve there, then re-run `skill update <slug>`.
4. `skill push` still refuses monorepo skills — sharing back upstream requires forking the parent.
5. The TUI's `state` column now reports `clean` / `dirty` for monorepo skills, the same as per-skill repos.

Aim for 4–6 lines of prose plus one short example block. Don't repeat the spec.

- [ ] **Step 3: If `docs/cli.md` exists, sync its `skill update` description**

```bash
test -f docs/cli.md && grep -n "skill update\|monorepo" docs/cli.md
```
If found, update the `skill update` entry to say "three-way merge for monorepo skills (was: fast-forward only)". One line, no more.

- [ ] **Step 4: Add the supersession note to the 2026-05-21 spec**

Open `docs/superpowers/specs/2026-05-21-skill-add-monorepo-design.md`. Insert a block right after the front-matter header (the `**Issue:** #162` / `**Branch:**` block), something like:

```markdown
> **Superseded in parts by:**
> [`2026-05-22-skill-update-monorepo-three-way-merge-design.md`](2026-05-22-skill-update-monorepo-three-way-merge-design.md)
> changes the `update` paragraph from `git pull --ff-only` to `fetch` + `merge`
> and fixes the TUI `state: copy` label for monorepo skills.
```

- [ ] **Step 5: Run the docs lints (if any)**

```bash
# repo may have a docs check; otherwise skip
ls .github/workflows/ | grep -i doc
```
If a docs workflow exists, run it locally per its definition. If not, eyeball.

- [ ] **Step 6: Commit**

```bash
git add README.md docs/superpowers/specs/2026-05-21-skill-add-monorepo-design.md
test -f docs/cli.md && git add docs/cli.md
git commit -m "docs: monorepo skills are locally editable

- README: editing-monorepo-skills subsection covers merge semantics,
  conflict resolution, and the TUI state column.
- cli.md: skill update entry notes three-way merge for monorepo.
- 2026-05-21 spec: supersession note pointing at the 2026-05-22 spec."
```

---

## Task 6: Full suite + integration sanity check

- [ ] **Step 1: Run the full test suite**

```bash
uv run pytest -q
```
Expected: all green. Snapshot count should match prior baseline + 7 (3 CLI + 4 TUI new tests).

- [ ] **Step 2: Mypy --strict (per user convention)**

```bash
uv run mypy --strict src/agent_toolkit_cli src/agent_toolkit_tui
```
Per `memory/feedback_python_mypy_strict.md` — mypy strict is the pre-commit bar. Fix any new errors (most likely missing type annotations on the new `parent_dir` line in `skill_state.py`).

- [ ] **Step 3: Ruff / lint**

```bash
uv run ruff check src tests
```
Expected: zero new findings.

- [ ] **Step 4: End-to-end smoke against a real monorepo skill**

```bash
# Working from a clean tmp library
export TMP_LIB=$(mktemp -d)
uv run --project . agent-toolkit-cli skill add vercel-labs/skills --skill find-skills

# Verify state shows clean in the TUI (or via build_skill_rows)
uv run --project . python -c "
from pathlib import Path
from agent_toolkit_tui.skill_state import build_skill_rows
for r in build_skill_rows(scope='global', home=Path.home(), project=None):
    if r.slug == 'find-skills':
        print(r.state)
"

# Edit + commit in the parent clone
PARENT=~/.agent-toolkit/skills/_parents/vercel-labs/skills
(cd "$PARENT" && echo "# local note" >> skills/find-skills/SKILL.md \
  && git -c user.email=t@t -c user.name=t commit -am "local note")

# update should merge (no conflict since upstream is unchanged in this smoke)
uv run --project . agent-toolkit-cli skill update find-skills
```
Expected: `state: clean` initially → `state: clean` (or `dirty` if uncommitted) after edit → `skill update` exits 0 and the local commit survives.

> **Note:** Don't commit the smoke-test edit to the real `~/.agent-toolkit/skills/_parents/vercel-labs/skills` — reset it after the smoke (`git -C "$PARENT" reset --hard origin/main`) or run the smoke in a tmp library by overriding `AGENT_TOOLKIT_SKILLS_ROOT`.

- [ ] **Step 5: Verify with TUI by eyeball**

```bash
uv run --project . agent-toolkit-tui
```
Check that `find-skills` appears with `state: clean` (not `copy`) — and after the smoke-test edit, `state: dirty`. Take a screenshot for the PR description.

- [ ] **Step 6: Commit any final fixes from steps 1–5**

If mypy/ruff/smoke surfaced anything, fix and commit per the conventions
(small commits, conventional-commit style).

---

## Definition of done

- [ ] Task 1: `update_cmd.py` calls `fetch` + `merge` instead of `pull_ff_only` for monorepo entries.
- [ ] Task 2: Three new CLI tests pass (merge, conflict, dirty tree).
- [ ] Task 3: `skill_state.py` derives monorepo state from the parent clone.
- [ ] Task 4: Four new TUI state tests pass.
- [ ] Task 5: README, cli.md (if present), and 2026-05-21 spec note all updated.
- [ ] Task 6: Full pytest + mypy --strict + ruff all green; end-to-end smoke passes; TUI screenshot taken.
- [ ] PR description references the spec, lists the two coupled fixes, and includes the TUI before/after screenshot.

---

## Risks during execution

- **Helper duplication between test modules.** If both `test_skill_update_monorepo.py` and `test_skill_state.py` need `_init_parent`, extract it to `tests/conftest.py`. Pick one home; don't ship the same helper twice.
- **`build_skill_rows` reads paths from `home=`.** The test passes `Path.home()`, but if `build_skill_rows` uses `home` to find the library lock path on top of `AGENT_TOOLKIT_SKILLS_ROOT`, this could leak the user's real library into the test. Mock or monkeypatch as needed; the existing test conventions in this repo should already cover the pattern.
- **`parent_clone_path` returns a path without `env=`.** Confirm during Task 3 — the existing call site in `update_cmd.py` passes `env=None`. The TUI call should match.
- **TUI install-button gate at `app.py:306`.** Verify by hand (or test) that a `clean` monorepo skill is still install-eligible. The gate already only blocks `missing` and `copy`, so this should be a no-op — but worth confirming.
- **Mypy --strict on the new branch in `skill_state.py`.** `entry.source.split("/", 1)` returns `list[str]` which mypy may flag if `entry.source` is typed as `str | None` somewhere. Add an `assert` or type-narrow if needed.
- **`docs/cli.md` may not exist.** Don't create it just for this; the README is the canonical reference.
