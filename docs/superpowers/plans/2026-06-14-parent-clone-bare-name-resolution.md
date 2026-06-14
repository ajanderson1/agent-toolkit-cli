# Parent-Clone Bare-Name Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `skill update`/`status`/`push`/`reset`/`doctor` locate a monorepo parent clone whether it lives at the canonical `<repo>@<ref>` path or the legacy bare `<repo>` path, so they can no longer disagree (#412).

**Architecture:** A new shared resolver `resolve_existing_parent_clone` prefers the suffixed path and falls back to the bare path only when bare is a git repo whose remote matches `parentUrl`. The five read/update call sites switch to it; the create path (`skill_install`) stays on `parent_clone_path` so fresh clones remain canonical. URL comparison reuses doctor's `_normalise_git_url`, promoted to `skill_git`. Phase 2 adds a non-destructive doctor `legacy_bare_parent` finding whose fix creates a `<repo>@<ref> → <repo>` alias symlink.

**Tech Stack:** Python 3.9+, Click, pytest, `uv run`, ruff, mypy. Hermetic git via `file://` bare-clone fixtures (`tests/conftest.scrub_git_env`).

---

### Task 1: Promote `_normalise_git_url` to `skill_git`

Doctor already has a robust URL normaliser (`skill_doctor._normalise_git_url` + `_SSH_GIT_URL_RE`/`_HTTPS_GIT_URL_RE`/`_SSH_URL_RE`). Move it (and its regexes) into `skill_git.py` so the new resolver and doctor share one definition; re-export from `skill_doctor` so its existing callers are unbroken.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_git.py` (add `normalise_git_url` + regexes)
- Modify: `src/agent_toolkit_cli/skill_doctor.py:639` (replace body with re-export)
- Test: `tests/test_cli/test_skill_git.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli/test_skill_git.py`:

```python
def test_normalise_git_url_collapses_forms():
    from agent_toolkit_cli.skill_git import normalise_git_url
    a = normalise_git_url("https://github.com/foo/bar.git")
    b = normalise_git_url("git@github.com:foo/bar.git")
    c = normalise_git_url("https://github.com/foo/bar")
    assert a == b == c == "github.com/foo/bar"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_git.py::test_normalise_git_url_collapses_forms -v`
Expected: FAIL — `ImportError: cannot import name 'normalise_git_url'`

- [ ] **Step 3: Move the function into `skill_git.py`**

Copy `_normalise_git_url` and the three regexes (`_SSH_GIT_URL_RE`, `_HTTPS_GIT_URL_RE`, `_SSH_URL_RE`) from `skill_doctor.py` into `skill_git.py` (place near `remote_url`), renamed public as `normalise_git_url`. Keep the exact body — it already handles SSH/HTTPS/`ssh://`/local fallback.

In `skill_doctor.py`, replace the function definition (and the now-unused regexes if they're only used by it) with a re-export so existing references keep working:

```python
from agent_toolkit_cli.skill_git import normalise_git_url as _normalise_git_url
```

(Grep `skill_doctor.py` for `_normalise_git_url` / the regex names first; only delete a regex if no other doctor code uses it. Note `_normalise_git_url` is also used at `skill_doctor.py:765` for `lock_source_mismatch` — the re-export keeps it working.)

> **Promote the function UNCHANGED** (decision 2026-06-14). The body lowercases
> the whole URL, so `host/Foo/Bar` and `host/foo/bar` collide — a latent
> wrong-repo risk on *case-sensitive self-hosted* Git hosts (GitLab self-managed,
> Gitea, Bitbucket DC). It cannot misfire for github.com (case-insensitive) or
> `file://` parents, which is all this machine uses. Do NOT change the lowercase
> semantics here — that would also alter doctor's existing `lock_source_mismatch`
> behaviour for a case we don't hit. **PR body must carry this caveat**: "Shared
> `normalise_git_url` case-folds the whole URL; revisit if a case-sensitive
> self-hosted parent is ever added."

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_git.py::test_normalise_git_url_collapses_forms tests/test_cli/test_skill_doctor.py -q`
Expected: PASS (doctor's existing URL-comparison tests still green via the re-export)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_git.py src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_git.py
git commit -m "refactor(skill): promote normalise_git_url to skill_git for shared use (#412)"
```

---

### Task 2: Add `resolve_existing_parent_clone` resolver

The probe-both helper. Prefers the suffixed path; falls back to bare only when bare is a git repo whose remote matches `parent_url`; otherwise returns the suffixed path (fresh-clone target).

**Files:**
- Modify: `src/agent_toolkit_cli/skill_paths.py` (add resolver + `_remote_matches`, after `parent_clone_path`)
- Test: `tests/test_cli/test_skill_paths.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli/test_skill_paths.py`:

```python
import subprocess
from tests.conftest import scrub_git_env


def _init_repo_with_remote(path, remote_url):
    path.mkdir(parents=True)
    env = scrub_git_env()
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(path), "remote", "add", "origin", remote_url],
        check=True, env=env,
    )


def test_resolve_prefers_suffixed_when_present(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    url = "https://github.com/o/r"
    suffixed = parent_clone_path("o", "r", ref="main", env=env)
    _init_repo_with_remote(suffixed, url)
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url=url, env=env,
    )
    assert got == suffixed


def test_resolve_falls_back_to_bare_on_remote_match(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    url = "https://github.com/o/r"
    bare = parent_clone_path("o", "r", ref=None, env=env)  # legacy layout
    _init_repo_with_remote(bare, url + ".git")  # different form, same repo
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url=url, env=env,
    )
    assert got == bare


def test_resolve_rejects_bare_on_remote_mismatch(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    bare = parent_clone_path("o", "r", ref=None, env=env)
    _init_repo_with_remote(bare, "https://github.com/someone/else")
    suffixed = parent_clone_path("o", "r", ref="main", env=env)
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url="https://github.com/o/r", env=env,
    )
    assert got == suffixed  # mismatch => do NOT adopt bare


def test_resolve_returns_suffixed_when_neither_exists(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    suffixed = parent_clone_path("o", "r", ref="main", env=env)
    got = resolve_existing_parent_clone(
        "o", "r", ref="main", parent_url="https://github.com/o/r", env=env,
    )
    assert got == suffixed


def test_resolve_ref_none_collapses_to_bare(tmp_path):
    """With ref=None the suffixed and bare paths are identical, so the probe
    collapses to the single existing path (spec AC1 'ref is None collapse')."""
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    bare = parent_clone_path("o", "r", ref=None, env=env)
    _init_repo_with_remote(bare, "https://github.com/o/r")
    got = resolve_existing_parent_clone(
        "o", "r", ref=None, parent_url="https://github.com/o/r", env=env,
    )
    assert got == bare
    assert got == parent_clone_path("o", "r", ref=None, env=env)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_skill_paths.py -k resolve -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_existing_parent_clone'`

- [ ] **Step 3: Write the resolver**

In `skill_paths.py`, after `parent_clone_path`, add (import `skill_git` at module top if not already imported):

```python
def _remote_matches(
    repo: Path, parent_url: str, env: dict[str, str] | None,
) -> bool:
    """True if `repo`'s origin remote names the same repo as `parent_url`."""
    from agent_toolkit_cli import skill_git
    try:
        actual = skill_git.remote_url(repo, env=env)
    except skill_git.GitError:
        return False
    return skill_git.normalise_git_url(actual) == skill_git.normalise_git_url(
        parent_url
    )


def resolve_existing_parent_clone(
    owner: str, repo: str, *, ref: str | None, parent_url: str,
    env: dict[str, str] | None = None, root: Path | None = None,
) -> Path:
    """Locate an existing monorepo parent clone, tolerating the legacy
    bare-named layout (#412).

    Prefers the canonical suffixed path (`<repo>@<ref>`). Falls back to the
    bare `<repo>` path ONLY when the suffixed path is absent AND the bare dir
    is a git repo whose origin remote matches `parent_url`. When neither
    exists, returns the suffixed path so a fresh clone still lands in the
    canonical scheme.
    """
    from agent_toolkit_cli import skill_git
    suffixed = parent_clone_path(owner, repo, ref=ref, env=env, root=root)
    if skill_git.is_git_repo(suffixed):
        return suffixed
    if ref is not None:
        bare = parent_clone_path(owner, repo, ref=None, env=env, root=root)
        if skill_git.is_git_repo(bare) and _remote_matches(bare, parent_url, env):
            return bare
    return suffixed
```

`skill_paths.py` has no `__all__` (public symbols are plain module-level defs) and does NOT import `skill_git` at module level — keep the `from agent_toolkit_cli import skill_git` imports lazy inside these two functions (as written above) to avoid a circular import with the low-level git module. No facade-parity change is required: `test_skill_facade_parity.py` is a subset check (asserts no names are *lost*), so adding a new name is free; optionally add `"resolve_existing_parent_clone"` to `SKILL_PATHS_PUBLIC` for hygiene, but it is not load-bearing.

**Slash-containing refs (e.g. `feat/x`) — handled safely, no extra code.** For a
slash-ref, `parent_clone_path(repo, ref="feat/x")` is `<owner>/<repo>@feat/x`
(the slash nests it below `<owner>/`), while the bare probe computes the flat
`<owner>/<repo>`. These are different paths, so for a slash-ref the resolver's
bare-fallback simply won't find the nested clone at the flat bare path and falls
through to the suffixed path — identical to the fresh-clone case, never a wrong
adoption (the remote-match guard would also reject any unrelated flat dir). The
legacy bare/suffixed split is, by construction, a *flat-ref* phenomenon: a
slash-ref clone is always created at its nested path and never had a flat bare
form. Phase 2's `bare != suffixed` guard skips slash-refs for the same reason.
Add a resolver test pinning this:

```python
def test_resolve_slash_ref_falls_through_to_suffixed(tmp_path):
    from agent_toolkit_cli.skill_paths import (
        parent_clone_path, resolve_existing_parent_clone,
    )
    env = {"AGENT_TOOLKIT_SKILLS_ROOT": str(tmp_path / "skills")}
    # A flat bare <repo> exists with a matching remote, but ref has a slash —
    # the nested suffixed path is what a slash-ref clone uses, so the flat bare
    # must NOT be adopted.
    bare = parent_clone_path("o", "r", ref=None, env=env)
    _init_repo_with_remote(bare, "https://github.com/o/r")
    suffixed = parent_clone_path("o", "r", ref="feat/x", env=env)
    got = resolve_existing_parent_clone(
        "o", "r", ref="feat/x", parent_url="https://github.com/o/r", env=env,
    )
    assert got == suffixed
    assert got != bare
```

(Confirm with `bare.is_dir()` that the flat bare exists yet is not adopted — the
slash-ref's real clone would live at the nested `r@feat/x`, not the flat `r`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_paths.py -k resolve -v`
Expected: PASS (all four)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_paths.py tests/test_cli/test_skill_paths.py
git commit -m "feat(skill): add resolve_existing_parent_clone probe-both resolver (#412)"
```

---

### Task 3: Wire `update` to the resolver (the #412 repro)

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/update_cmd.py:82-85`
- Test: `tests/test_cli/test_skill_owned_monorepo.py` (new test; reuses `_setup_parent` + the new `_add_owned_ref`)

> **Do NOT touch the create-path `parent_clone_path` calls.** A `grep
> parent_clone_path` sweep will also surface the *add* create-sites
> (`commands/skill/__init__.py:101` and `:354`) and `skill_install.py:414`.
> These are create-time clone targets that MUST stay on `parent_clone_path` so a
> fresh clone lands at the canonical `<repo>@<ref>` name (AC5). Only the five
> read/locate sites in the spec's table convert to the resolver.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli/test_skill_owned_monorepo.py`.

> **CRITICAL fixture note (feasibility review):** the existing `_add_owned`
> (`skill add file://{parent} --skill mkdocs --owned`) records **`ref=None`**
> — `_add_monorepo` sets the lock ref to `parsed.ref`, which is `None` for a
> bare `file://` URL. With `ref=None`, `parent_clone_path(..., ref=None)` ==
> the bare path, so there is no suffixed clone to rename and the whole
> legacy-bare reproduction collapses. To get a non-None ref, add via the
> `file://{parent}/tree/<ref>/<subpath>` form, which the source parser
> (`skill_source.py`) honours and which records `ref="main"`. Use this
> ref-bearing helper for all #412 tests:

```python
def _add_owned_ref(parent_url: str, skill: str = "mkdocs", ref: str = "main") -> None:
    """Like _add_owned but records a non-None ref via the /tree/<ref>/ form,
    so a suffixed <repo>@<ref> clone is materialised (#412 needs this)."""
    src = f"{parent_url}/tree/{ref}/{skill}"
    r = CliRunner().invoke(cli, ["skill", "add", src, "--owned"])
    assert r.exit_code == 0, r.output


def _make_legacy_bare(entry: dict) -> Path:
    """Rename the suffixed parent clone to the legacy bare `<repo>` name,
    reproducing the pre-ref-backfill on-disk layout (#412)."""
    from agent_toolkit_cli.skill_paths import parent_clone_path
    ref = entry["ref"]
    owner, repo = entry["source"].split("/", 1)
    suffixed = parent_clone_path(owner, repo, ref=ref, env=None)
    assert suffixed.name == f"{repo}@{ref}", suffixed
    bare = parent_clone_path(owner, repo, ref=None, env=None)
    suffixed.rename(bare)
    return bare


def test_update_finds_legacy_bare_named_parent(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    assert entry.get("ref") == "main", entry  # /tree/main/ form records a ref
    bare = _make_legacy_bare(entry)
    assert bare.exists()

    r = CliRunner().invoke(cli, ["skill", "update", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    assert "parent clone missing" not in r.output
```

(Verify the `/tree/<ref>/<subpath>` add records `ref="main"` and a suffixed
clone before writing the dependent tests — a quick `_lock()` print confirms it.
If the `--owned` flag rejects the `/tree/` form, drop `--owned`: the tests below
don't depend on ownership, only on a materialised suffixed clone.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_owned_monorepo.py::test_update_finds_legacy_bare_named_parent -v`
Expected: FAIL — output contains "parent clone missing or not a git repo".

- [ ] **Step 3: Switch update to the resolver**

In `update_cmd.py`, replace the `parent_clone_path(...)` call (currently lines 82-85) with:

```python
            owner, repo = entry.source.split("/", 1)
            parent_dir = resolve_existing_parent_clone(
                owner, repo, ref=entry.ref, parent_url=entry.parent_url,
                env=None,
            )
```

Update the import at the top of `update_cmd.py`: replace `parent_clone_path` with `resolve_existing_parent_clone` (or add the latter alongside).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_skill_owned_monorepo.py::test_update_finds_legacy_bare_named_parent -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/update_cmd.py tests/test_cli/test_skill_owned_monorepo.py
git commit -m "fix(skill update): locate legacy bare-named parent clone via resolver (#412)"
```

---

### Task 4: Wire `status`, `push`, `reset` to the resolver

Same swap at three more sites. They locate the same clone for the same `entry`.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/skill/status_cmd.py:90`
- Modify: `src/agent_toolkit_cli/commands/skill/push_cmd.py:257`
- Modify: `src/agent_toolkit_cli/commands/skill/reset_cmd.py:77`
- Test: `tests/test_cli/test_skill_owned_monorepo.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli/test_skill_owned_monorepo.py`:

```python
def test_status_finds_legacy_bare_named_parent(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    _make_legacy_bare(entry)
    r = CliRunner().invoke(cli, ["skill", "status", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    assert "missing" not in r.output.lower()


def test_reset_finds_legacy_bare_named_parent(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    _make_legacy_bare(entry)
    r = CliRunner().invoke(cli, ["skill", "reset", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    assert "missing" not in r.output.lower()


def test_push_finds_legacy_bare_named_parent(tmp_path, monkeypatch):
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    _make_legacy_bare(entry)
    r = CliRunner().invoke(cli, ["skill", "push", "--direct", "mkdocs", "-g"])
    assert r.exit_code == 0, r.output
    assert "missing" not in r.output.lower()
```

(If a command's clean-tree path prints "nothing to push"/"up to date" that's fine — the assertion only rejects a "missing" path-resolution failure. Adjust the exact non-"missing" assertion to the command's actual clean output if needed.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_skill_owned_monorepo.py -k "legacy_bare" -v`
Expected: status/reset/push FAIL on a "missing" path (the update test from Task 3 still passes).

- [ ] **Step 3: Switch the three sites**

At each site, replace the `parent_clone_path(owner, repo, ref=..., ...)` call with `resolve_existing_parent_clone(owner, repo, ref=..., parent_url=entry.parent_url, ...)`, preserving the existing `env`/`root` arguments each site already passes. Update each file's import. (push_cmd's helper returns the dir — change its return expression.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_owned_monorepo.py -k "legacy_bare" -v`
Expected: PASS (all four legacy_bare tests)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/skill/status_cmd.py src/agent_toolkit_cli/commands/skill/push_cmd.py src/agent_toolkit_cli/commands/skill/reset_cmd.py tests/test_cli/test_skill_owned_monorepo.py
git commit -m "fix(skill): status/push/reset locate legacy bare-named parent via resolver (#412)"
```

---

### Task 5: Wire doctor's reclone fix-action to the resolver

`_make_monorepo_reclone_action` (`skill_doctor.py:387`) computes the suffixed path. When it fires (canonical missing) against a legacy bare parent, it should reuse the existing bare clone rather than re-clone to a divergent suffixed path.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py:386-387`
- Test: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli/test_skill_doctor.py` (model the parent setup on the file's existing monorepo doctor tests; if none, reuse `tests/test_cli/test_skill_owned_monorepo.py::_setup_parent` via import):

```python
def test_doctor_reclone_reuses_legacy_bare_parent(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from agent_toolkit_cli import skill_doctor
    from agent_toolkit_cli.skill_paths import (
        canonical_skill_dir, parent_clone_path,
    )

    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    bare = _make_legacy_bare(entry)

    # Break the canonical so the reclone fix-action fires.
    canonical = canonical_skill_dir("mkdocs", scope="global", home=None, project=None)
    if canonical.is_symlink() or canonical.exists():
        canonical.unlink()

    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    fix = next(f.fix_action for f in findings if f.fix_action)
    fix.apply()

    # It re-linked against the EXISTING bare clone, not a new suffixed clone.
    owner, repo = entry["source"].split("/", 1)
    suffixed = parent_clone_path(owner, repo, ref=entry["ref"], env=None)
    assert bare.exists()
    assert not suffixed.exists()  # no divergent re-clone
    assert canonical.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py::test_doctor_reclone_reuses_legacy_bare_parent -v`
Expected: FAIL — `suffixed.exists()` is True (fix re-cloned to the suffixed path).

- [ ] **Step 3: Switch doctor's reclone to the resolver**

In `_make_monorepo_reclone_action`, replace:

```python
    parents_root = None if scope == "global" else project_parents_root(project)
    parent_dir = parent_clone_path(owner, repo, ref=entry.ref, root=parents_root)
```

with:

```python
    from agent_toolkit_cli.skill_paths import resolve_existing_parent_clone
    parents_root = None if scope == "global" else project_parents_root(project)
    parent_dir = resolve_existing_parent_clone(
        owner, repo, ref=entry.ref, parent_url=parent_url, root=parents_root,
    )
```

(`parent_url` is already bound earlier in the function. The doctor site passes
`root=parents_root` and **no** `env` — mirroring its current `parent_clone_path`
call exactly; the resolver defaults `env=None`, so this is correct. Do not add a
spurious `env=` here. The `_apply` inner closure clones to `parent_dir` only when
it doesn't exist, so an existing bare dir is reused.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py::test_doctor_reclone_reuses_legacy_bare_parent -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "fix(skill doctor): reclone reuses legacy bare-named parent via resolver (#412)"
```

---

### Task 6: Guard the create path stays canonical (AC5)

Lock in that a *fresh* add still materialises at `<repo>@<ref>`, so the resolver change never silently moves new clones to the bare scheme.

**Files:**
- Test: `tests/test_cli/test_skill_owned_monorepo.py`

- [ ] **Step 1: Write the test**

```python
def test_fresh_add_materialises_suffixed_clone(tmp_path, monkeypatch):
    from agent_toolkit_cli.skill_paths import parent_clone_path
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    assert entry.get("ref") == "main"
    owner, repo = entry["source"].split("/", 1)
    suffixed = parent_clone_path(owner, repo, ref=entry["ref"], env=None)
    bare = parent_clone_path(owner, repo, ref=None, env=None)
    assert suffixed.exists() and suffixed.name == f"{repo}@{entry['ref']}"
    assert not bare.exists()  # fresh add never used the bare name
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_cli/test_skill_owned_monorepo.py::test_fresh_add_materialises_suffixed_clone -v`
Expected: PASS immediately (this is a regression guard, not RED-first — the create path was untouched).

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_skill_owned_monorepo.py
git commit -m "test(skill): guard fresh monorepo add stays on suffixed clone path (#412)"
```

---

### Task 7: Phase 2 — doctor `legacy_bare_parent` finding + alias-symlink fix

A non-destructive cleanup: when a bare-named parent exists (remote matches) and the suffixed path is absent, doctor offers to create the `<repo>@<ref> → <repo>` alias symlink.

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py` (add to `FindingType` union; emit in `_check_slug`; fix-action)
- Test: `tests/test_cli/test_skill_doctor.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_doctor_flags_legacy_bare_parent(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from agent_toolkit_cli import skill_doctor
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    _make_legacy_bare(entry)
    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    legacy = [f for f in findings if f.finding_type == "legacy_bare_parent"]
    assert legacy, [f.finding_type for f in findings]


def test_doctor_legacy_bare_fix_creates_alias_symlink(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from agent_toolkit_cli import skill_doctor
    from agent_toolkit_cli.skill_paths import parent_clone_path
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    bare = _make_legacy_bare(entry)
    owner, repo = entry["source"].split("/", 1)
    suffixed = parent_clone_path(owner, repo, ref=entry["ref"], env=None)

    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    fix = next(
        f.fix_action for f in findings
        if f.finding_type == "legacy_bare_parent" and f.fix_action
    )
    fix.apply()
    assert suffixed.is_symlink()
    assert suffixed.resolve() == bare.resolve()
    # idempotent: re-applying with the alias present is a no-op, no raise.
    fix.apply()


def test_doctor_no_legacy_finding_when_suffixed_present(tmp_path, monkeypatch):
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock,
    )
    from agent_toolkit_cli import skill_doctor
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")  # leaves the suffixed clone in place
    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    assert not [f for f in findings if f.finding_type == "legacy_bare_parent"]


def test_doctor_no_legacy_finding_when_remote_mismatch(tmp_path, monkeypatch):
    """A bare dir whose origin does NOT match parentUrl must not be flagged —
    exercises the _remote_matches GitError/mismatch guard."""
    import subprocess
    from tests.test_cli.test_skill_owned_monorepo import (
        _setup_parent, _add_owned_ref, _lock, _make_legacy_bare,
    )
    from tests.conftest import scrub_git_env
    from agent_toolkit_cli import skill_doctor
    parent_url, _ = _setup_parent(tmp_path, monkeypatch)
    _add_owned_ref(parent_url, "mkdocs")
    entry = _lock()["skills"]["mkdocs"]
    bare = _make_legacy_bare(entry)
    # Repoint origin to an unrelated URL so the remote-match guard rejects it.
    subprocess.run(
        ["git", "-C", str(bare), "remote", "set-url", "origin",
         "https://github.com/someone/else"],
        check=True, env=scrub_git_env(),
    )
    findings = skill_doctor.diagnose(
        slugs=("mkdocs",), scope="global", home=None, project=None,
    )
    assert not [f for f in findings if f.finding_type == "legacy_bare_parent"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py -k legacy_bare -v`
Expected: the two positive tests FAIL (no `legacy_bare_parent` finding yet); the two negative tests PASS.

- [ ] **Step 3: Add the finding type + emission + fix-action**

In `skill_doctor.py`:

1. Add `"legacy_bare_parent"` to the `FindingType` `Literal` union (line ~31).

2. In `_check_slug`, after the existing per-slug checks, for a monorepo entry add.
   **Reuse `_remote_matches`** from Task 2 rather than inlining the URL compare —
   it carries the `try/except GitError: return False` guard, so a corrupt bare
   clone yields no-finding instead of crashing the doctor sweep (scope-guardian
   + coherence flagged the inlined version as missing this guard):

```python
    if entry.parent_url is not None and entry.ref is not None:
        from agent_toolkit_cli.skill_paths import (
            parent_clone_path, project_parents_root, _remote_matches,
        )
        from agent_toolkit_cli import skill_git
        owner_repo = entry.source.split("/", 1)
        if len(owner_repo) == 2:
            owner, repo = owner_repo
            parents_root = (
                None if scope == "global" else project_parents_root(project)
            )
            suffixed = parent_clone_path(
                owner, repo, ref=entry.ref, root=parents_root,
            )
            bare = parent_clone_path(owner, repo, ref=None, root=parents_root)
            if (
                bare != suffixed              # slash-ref / ref=None: no flat bare
                and not suffixed.exists()
                and skill_git.is_git_repo(bare)
                and _remote_matches(bare, entry.parent_url, None)
                and _bare_ref_matches(bare, entry.ref)   # multi-ref safety (see below)
            ):
                findings.append(Finding(
                    finding_type="legacy_bare_parent", slug=slug, scope=scope,
                    path=bare,
                    detail=(
                        f"parent clone uses legacy bare name {bare.name}; "
                        f"alias to {suffixed.name} for canonical resolution"
                    ),
                    fix_action=_make_legacy_bare_alias_action(suffixed, bare),
                ))
```

The `bare != suffixed` guard makes the block a no-op for `ref=None` and for
slash-containing refs (where `<repo>@feat/x` nests below `<owner>/` and has no
flat-`<repo>` sibling) — see Task 2's slash-ref note. `_bare_ref_matches` is the
multi-ref safety guard added below.

3. Add the multi-ref safety guard + the fix-action factory near the other
   `_make_*_action` helpers:

```python
def _bare_ref_matches(bare: Path, ref: str) -> bool:
    """True if the bare clone's current branch is `ref`.

    Multi-ref safety (#412 adversarial review): when several skills share one
    monorepo at DIFFERENT refs, a single bare clone is checked out at exactly
    one ref. Aliasing `<repo>@<other-ref> -> <repo>` would lie about that other
    skill's ref and a later `update` could flip the shared tree. Only alias when
    the bare clone is actually on `ref`, so the alias never misrepresents it.
    """
    from agent_toolkit_cli import skill_git
    try:
        return skill_git.current_branch(bare, env=None) == ref
    except skill_git.GitError:
        return False


def _make_legacy_bare_alias_action(suffixed: Path, bare: Path) -> FixAction:
    def _apply() -> None:
        if suffixed.exists() or suffixed.is_symlink():
            return  # idempotent
        suffixed.parent.mkdir(parents=True, exist_ok=True)
        suffixed.symlink_to(bare.name)  # relative alias within <owner>/
    return FixAction(
        description=f"Alias {suffixed.name} -> {bare.name} (legacy parent clone)",
        shell_preview=f"ln -s {bare.name} {suffixed}",
        apply=_apply,
    )
```

(`skill_git.current_branch(repo, *, env)` exists — `skill_git.py:289`.)

Note: `_check_slug`'s signature has `project` and `scope` available (parameters).
`project_parents_root` is NOT yet imported in `_check_slug`'s namespace
(`_make_monorepo_reclone_action`'s import is function-local to that helper), so
add `project_parents_root` to the `from agent_toolkit_cli.skill_paths import ...`
line in the new block.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py -k legacy_bare -v`
Expected: PASS (all three)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py tests/test_cli/test_skill_doctor.py
git commit -m "feat(skill doctor): legacy_bare_parent finding + alias-symlink fix (#412)"
```

---

### Task 8: Full-suite green + lint/type gate

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -q 2>&1 | tail -20`
Expected: all pass except the 2 known whitelisted HOME-isolation env fails (`test_empty_machine_is_empty` and the instruction empty-lock test). If any NEW failure appears, fix it before proceeding. (Per memory, those 2 are now fixed — expect a fully green 1650+ run; if so, even better.)

- [ ] **Step 2: Lint + type check (net-zero-new)**

Run: `uv run ruff check src/ tests/ 2>&1 | tail -5 && uv run mypy src/ 2>&1 | tail -5`
Expected: no NEW ruff or mypy errors. **Base counts on `main` at 2026-06-14: ruff = 17 errors, mypy = 53 errors** (all pre-existing, in unrelated files — `agent_toolkit_tui/app.py` etc.). This change must not raise either count. Common traps: `E402` (imports inside functions are fine; module-level import ordering matters), and an unused `parent_clone_path` import left behind after a swap (ruff `F401`) — when a call site no longer uses `parent_clone_path`, drop it from that file's imports.

- [ ] **Step 3: Manual repro sanity check (R0+)**

The real-machine repro is `skill update -g` over a legacy bare clone; the Task 3 test reproduces it hermetically. Optionally confirm against the live machine state described in the issue is NOT needed (the manual aliases already make it clean) — the hermetic tests are the evidence. Capture the green suite output under `assets/verification/` per the testing convention.

- [ ] **Step 4: Final commit if any fixups were needed**

```bash
git add -A && git commit -m "chore(skill): suite + lint green for parent-clone resolver (#412)"
```

---

## Self-Review

**Spec coverage:**
- AC1 (resolver prefers suffixed / falls back / default / `ref=None` collapse / slash-ref) → Task 2 (6 tests, incl. `test_resolve_ref_none_collapses_to_bare`, `test_resolve_slash_ref_falls_through_to_suffixed`). ✓
- AC2 (remote-mismatch rejects bare) → Task 2 `test_resolve_rejects_bare_on_remote_mismatch`. ✓
- AC3 (`update` succeeds on legacy bare) → Task 3. ✓
- AC4 (status/push/reset) → Task 4. ✓
- AC5 (fresh clones stay suffixed) → Task 6. ✓
- AC6 (`normalise_git_url` promoted + shared, semantics unchanged) → Task 1. ✓
- AC7 (doctor `legacy_bare_parent` + alias + idempotent + mismatch-no-finding + multi-ref guard) → Task 7 (4 tests: flag, alias-creates+idempotent re-apply, suffixed-present-no-finding, remote-mismatch-no-finding; `_bare_ref_matches` guards the multi-ref case). ✓
- AC8 (suite + lint/mypy net-0) → Task 8. ✓

**Placeholder scan:** No TBD/TODO; every code step shows code; every test shows assertions. ✓

**Type consistency:** `resolve_existing_parent_clone(owner, repo, *, ref, parent_url, env=None, root=None)` used identically in Tasks 2–5. `_remote_matches(repo, parent_url, env)` defined in Task 2 and reused (not re-inlined) in Task 7. `_make_legacy_bare(entry)`, `_add_owned_ref(parent_url, skill, ref)`, `_bare_ref_matches(bare, ref)`, and `_make_legacy_bare_alias_action(suffixed, bare)` named consistently. `normalise_git_url` (public) used in Tasks 1, 2 (via `_remote_matches`), 7 (via `_remote_matches`). ✓

**Critical-review fixes folded in (2026-06-14):** fixture `ref=None` blocker → `_add_owned_ref` via `/tree/<ref>/`; Task 7 inline remote-match missing `GitError` guard → reuse `_remote_matches`; slash-ref symmetry → skip+document+test; Phase 2 multi-ref lie → `_bare_ref_matches` guard; normaliser case-fold → leave-as-is + PR-body caveat; AC1 `ref=None` + AC7 mismatch now tested.

**Note for the executor:** Tasks 3–7 each swap a call site; before each commit, run `git diff --cached --name-only` to confirm only the intended files are staged (this repo's shared-main checkout has been a source of cross-session leakage — see project memory). Doctor's `_check_slug` adds the new check at the END of the per-slug block so it doesn't reorder existing findings.

**Suggested follow-up (do NOT file as part of this issue):** the adversarial review found `~/.agent-toolkit/skills/_parents/ajanderson1/skills-workflow` (bare) and `skills-workflow@main` exist as TWO independent clones (not an alias) — the canonical symlink points into `@main`, leaving the bare dir as orphaned dead disk that Phase 2 never cleans (it only fires when suffixed is *absent*). A future doctor `orphan_bare_parent` finding could detect a bare dir whose suffixed sibling is already a real clone and offer to remove it. Out of scope for #412.
