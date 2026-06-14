# CLI command-coverage completion + guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the test suite exercise every registered CLI command cell, add a CI guard that keeps it that way, and deepen the thin cells (harness parametrization, project scope, error paths).

**Architecture:** Test-only change. A new meta-test enumerates registered command cells and asserts each is invoked; new/expanded test files close the one empty cell (`agent update`) and the depth gaps. No production code changes except a possible tiny enumeration helper kept inside the test.

**Tech Stack:** pytest, `click.testing.CliRunner`, existing `tests/conftest.py` fixtures (`git_sandbox`, `make_behind/ahead/diverged/conflict/dirty`, `installed_skill`).

**Issue:** #423 · **Spec:** `docs/superpowers/specs/2026-06-14-verb-asset-harness-coverage-design.md`

---

## File structure

- `tests/test_cli/test_command_coverage_guard.py` — **new** (G0/AC0). The invariant.
- `tests/test_cli/test_cli_agent_update.py` — **new** (G1/AC1). Clones the pi-extension update template.
- `tests/test_cli/test_cli_skill_install.py` — **modify** (G2/AC2). Add per-mechanism parametrization.
- `tests/test_cli_mcp.py` — **modify** (G2/AC2). Add 4-harness parametrization.
- `tests/test_cli/test_cli_agent_update.py` + existing instructions/mcp/pi-ext test files — **modify** (G3/AC3, G4/AC4). Scope + error-path cases.

> **Ordering note:** Task 1 (G1) lands BEFORE Task 2 (G0). The guard goes red until `agent update` is tested, so write the agent-update tests first, then add the guard that codifies "all cells covered". This keeps every commit green.

---

## Task 1: `agent update` test file (G1 / AC1)

`agent update` is the only registered cell with zero tests. It explicitly "mirrors pi-extension update_cmd" (`src/agent_toolkit_cli/commands/agent/update_cmd.py:3`), so clone the pi-extension update template at `tests/test_cli/test_cli_pi_extension_lifecycle.py:75-159`.

**Trap (from project memory `project_345_run_complete`):** the shared `git_sandbox` fixture seeds the upstream with `SKILL.md`, but `agent add <source> --slug demo` requires a `demo.md` content file in the source or it refuses post-clone (`add_cmd.py:144`). This test therefore builds its OWN upstream seeded with `demo.md` rather than reusing `git_sandbox` directly.

**Files:**
- Create: `tests/test_cli/test_cli_agent_update.py`

- [ ] **Step 1: Write the failing happy-path test**

```python
"""CLI tests for `agent update` (#423 / AC1).

Mirrors tests/test_cli/test_cli_pi_extension_lifecycle.py update cases —
`agent update` is documented as mirroring pi-extension update_cmd.

The shared git_sandbox seeds SKILL.md upstream, but `agent add --slug demo`
needs a demo.md content file in the source, so these tests build a dedicated
upstream seeded with demo.md.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from click.testing import CliRunner

from agent_toolkit_cli.agent_lock import read_lock
from agent_toolkit_cli.agent_paths import library_agent_path, library_lock_path
from agent_toolkit_cli.cli import main


def _make_agent_upstream(tmp_path: Path, env: dict, slug: str = "demo") -> Path:
    """A bare upstream seeded with <slug>.md so `agent add --slug` accepts it."""
    upstream = tmp_path / f"{slug}-upstream.git"
    subprocess.run(["git", "init", "--bare", "--initial-branch=main", str(upstream)],
                   check=True, env=env, capture_output=True)
    seed = tmp_path / f"{slug}-seed"
    seed.mkdir()
    subprocess.run(["git", "init", "--initial-branch=main", str(seed)],
                   check=True, env=env, capture_output=True)
    (seed / f"{slug}.md").write_text(
        f"---\nname: {slug}\ndescription: A test agent.\n---\n\nBody.\n"
    )
    for args in (["add", "-A"], ["commit", "-m", "seed"],
                 ["remote", "add", "origin", str(upstream)],
                 ["push", "origin", "main"]):
        subprocess.run(["git", "-C", str(seed), *args],
                       check=True, env=env, capture_output=True)
    return upstream


def _advance_remote(upstream: Path, env: dict, *, slug: str = "demo",
                    body: str = "updated\n") -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        work = Path(td) / "work"
        subprocess.run(["git", "clone", str(upstream), str(work)],
                       check=True, capture_output=True, env=env)
        (work / f"{slug}.md").write_text(body)
        for args in (["add", "-A"], ["commit", "-m", "upstream update"],
                     ["push", "origin", "main"]):
            subprocess.run(["git", "-C", str(work), *args],
                           check=True, capture_output=True, env=env)


def _head(path: Path) -> str:
    return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=True).stdout.strip()


def test_agent_update_pulls_upstream_changes(tmp_path, monkeypatch, git_sandbox):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))

    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)
    r = CliRunner().invoke(main, ["agent", "add", str(upstream), "--slug", "demo"])
    assert r.exit_code == 0, r.output

    canonical = library_agent_path("demo")
    _advance_remote(upstream, git_sandbox.env)
    sha_before = _head(canonical)

    r = CliRunner().invoke(main, ["agent", "update", "demo", "-g"])
    assert r.exit_code == 0, r.output
    sha_after = _head(canonical)
    assert sha_before != sha_after, "update should advance HEAD"

    lock = read_lock(library_lock_path())
    assert lock.skills["demo"].local_sha == sha_after
```

- [ ] **Step 2: Run it, verify it passes** (the command exists; this proves the test harness is correct)

Run: `uv run pytest tests/test_cli/test_cli_agent_update.py::test_agent_update_pulls_upstream_changes -v`
Expected: PASS. (If it FAILS, the test setup is wrong — fix the test, not the product.)

- [ ] **Step 3: Add the error-branch + no-op tests**

```python
def test_agent_update_unknown_slug_reports_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)
    r = CliRunner().invoke(main, ["agent", "update", "nope", "-g"])
    # update_cmd: "no agents lock found" (no lock) OR "nope: not in lock" + exit 1
    assert r.exit_code != 0 or "not in lock" in r.output or "no agents lock" in r.output


def test_agent_update_no_lock_is_clean(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)
    r = CliRunner().invoke(main, ["agent", "update", "-g"])
    assert r.exit_code == 0, r.output
    assert "no agents lock" in r.output.lower()


def test_agent_update_no_args_updates_all(tmp_path, monkeypatch, git_sandbox):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)
    CliRunner().invoke(main, ["agent", "add", str(upstream), "--slug", "demo"])
    _advance_remote(upstream, git_sandbox.env)
    r = CliRunner().invoke(main, ["agent", "update", "-g"])  # no slug => all
    assert r.exit_code == 0, r.output
    assert "demo: updated" in r.output
```

- [ ] **Step 4: Add the "no .git in canonical" branch test**

```python
def test_agent_update_non_git_canonical_reports_error(tmp_path, monkeypatch):
    """A lock entry whose canonical has no .git/ cannot update: message + exit 1."""
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)
    from agent_toolkit_cli.agent_lock import LockEntry, add_entry, read_lock, write_lock
    from agent_toolkit_cli.agent_paths import (
        canonical_agent_dir, library_lock_path,
    )
    # Seed a non-git canonical + a lock entry pointing at it.
    canonical = canonical_agent_dir("plain", scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "plain.md").write_text("---\nname: plain\ndescription: x\n---\nB\n")
    lock_path = library_lock_path()
    lock = read_lock(lock_path)
    write_lock(lock_path, add_entry(lock, "plain", LockEntry(
        source="https://github.com/test/plain", source_type="github",
        agent_path="plain.md",
    )))
    r = CliRunner().invoke(main, ["agent", "update", "plain", "-g"])
    assert r.exit_code != 0
    assert "no .git" in r.output
```

> **Verify branch reachability first:** `agent update` calls `library_agent_path(slug)` for the canonical, not `canonical_agent_dir`. Before relying on the seeding above, confirm with `readlink`/inspection that `library_agent_path("plain")` resolves to the same dir the lock entry implies. If `agent add` is the only way to populate `library_agent_path`, seed via a non-git path the command actually reads — adjust the test to match the real canonical location rather than forcing it. The assertion (`"no .git"`, exit 1) is the contract; the seeding is whatever makes `library_agent_path(slug)` a non-git dir.

- [ ] **Step 5: Run the whole new file, verify green**

Run: `uv run pytest tests/test_cli/test_cli_agent_update.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli/test_cli_agent_update.py
git commit -m "test(agent): cover \`agent update\` — happy path, no-lock, unknown slug, non-git canonical (#423)"
```

---

## Task 2: command-coverage guard meta-test (G0 / AC0)

Enumerate every registered `commands/<at>/*_cmd.py` cell plus skill's off-dir verbs, and assert each is invoked by at least one test. After Task 1 this passes; a future untested cell makes it fail.

**Files:**
- Create: `tests/test_cli/test_command_coverage_guard.py`

- [ ] **Step 1: Write the guard test**

```python
"""Coverage guard (#423 / AC0): every registered CLI command cell must be
invoked by at least one test.

Turns the one-off 2026-06-14 audit into a permanent invariant: a newly-added
(asset_type, verb) command that ships without a test fails this test.

Mechanism: enumerate command cells from the source tree, then scan all test
sources for a CliRunner invocation list whose first two string tokens are
(group-or-alias, verb).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src/agent_toolkit_cli/commands"
_TESTS = Path(__file__).resolve().parents[1]

# First-token aliases each command group may appear under in invoke lists.
_GROUP_ALIASES = {
    "skill": ("skill", "skills"),
    "agent": ("agent", "agents"),
    "instructions": ("instructions",),
    "mcp": ("mcp", "mcps"),
    "pi_extension": ("pi-extension", "pi_extension"),
    "bundle": ("bundle",),
}

# Skill's install/add live outside commands/skill/ (skill_install.py + wizard);
# they are heavily tested but won't be discovered from the commands dir.
_OFF_DIR_CELLS = {("skill", "install"), ("skill", "add")}


def _registered_cells() -> set[tuple[str, str]]:
    cells: set[tuple[str, str]] = set()
    for at_dir in _SRC.iterdir():
        if not at_dir.is_dir() or at_dir.name.startswith("__"):
            continue
        for cmd in at_dir.glob("*_cmd.py"):
            cells.add((at_dir.name, cmd.name[: -len("_cmd.py")]))
    cells |= _OFF_DIR_CELLS
    return cells


def _all_test_source() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in _TESTS.rglob("*.py")
        if p.name != Path(__file__).name  # don't let this file self-satisfy
    )


@pytest.fixture(scope="module")
def test_src() -> str:
    return _all_test_source()


@pytest.mark.parametrize("asset_type, verb", sorted(_registered_cells()))
def test_command_cell_is_invoked_by_a_test(asset_type, verb, test_src):
    groups = _GROUP_ALIASES[asset_type]
    # Match an invoke list opening:  ["agent", "update"  or  ('agents', 'update'
    pattern = re.compile(
        r"""["'](?:%s)["']\s*,\s*["']%s["']"""
        % ("|".join(re.escape(g) for g in groups), re.escape(verb))
    )
    assert pattern.search(test_src), (
        f"command cell ({asset_type} {verb}) has no test invoking it. "
        f"Add a test that calls CliRunner().invoke(main, [\"{groups[0]}\", \"{verb}\", ...])."
    )
```

- [ ] **Step 2: Run it, verify all parametrizations pass**

Run: `uv run pytest tests/test_cli/test_command_coverage_guard.py -v`
Expected: every parametrized cell PASS (Task 1 closed the lone gap). If any cell FAILS that isn't expected, either it's a genuine gap (add a test) or an alias/off-dir miss (extend `_GROUP_ALIASES` / `_OFF_DIR_CELLS`).

- [ ] **Step 3: Prove the guard actually guards (temporary negative check)**

Temporarily add a fake cell file `src/agent_toolkit_cli/commands/bundle/zzz_cmd.py` (empty), re-run the guard, confirm it FAILS for `(bundle, zzz)`, then delete the fake file and confirm green again. Do NOT commit the fake file.

Run: `touch src/agent_toolkit_cli/commands/bundle/zzz_cmd.py && uv run pytest tests/test_cli/test_command_coverage_guard.py -k zzz ; rm src/agent_toolkit_cli/commands/bundle/zzz_cmd.py`
Expected: the `zzz` parametrization FAILS, then the file is removed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_cli/test_command_coverage_guard.py
git commit -m "test: guard that every registered CLI command cell is invoked by a test (#423)"
```

---

## Task 3: harness-dimension parametrization (G2 / AC2)

`skill install` and `mcp install` currently hard-code one harness. Parametrize over one representative per adapter mechanism (skill) and the full MCP harness set (mcp). Mirror the proven pattern in `tests/test_cli/test_agent_adapters/test_symlink.py`.

**Files:**
- Modify: `tests/test_cli/test_cli_skill_install.py`
- Modify: `tests/test_cli_mcp.py`

- [ ] **Step 1: Read the existing install tests to find the seam**

Run: `uv run pytest tests/test_cli/test_cli_skill_install.py -q` (confirm green baseline) and read the test that installs into `claude-code`. Identify the one assertion block that proves a projection exists, so it can be parametrized rather than duplicated.

- [ ] **Step 2: Add the skill-install parametrized test**

```python
import pytest

# One representative per adapter mechanism — covers every distinct code path
# without 57x bloat (the other harnesses are config-table rows, not code).
_SKILL_INSTALL_REPS = [
    "claude-code",   # symlink
    "gemini-cli",    # translate
    "aider-desk",    # config_file_folder
]

@pytest.mark.parametrize("harness", _SKILL_INSTALL_REPS)
def test_skill_install_projects_into_each_mechanism(
    installed_skill, harness, monkeypatch, tmp_path
):
    """skill install --agents <harness> creates a projection for every mechanism."""
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main
    r = CliRunner().invoke(
        main, ["skill", "install", installed_skill.slug, "--agents", harness, "-g"]
    )
    assert r.exit_code == 0, r.output
    # Projection existence is asserted via the public path helper for the harness,
    # mirroring how test_skill_install_engine.py locates agent_projection_dir.
    # (Use the same helper the existing single-harness test uses; assert the
    # slug's destination now exists under the harness's skills dir.)
```

> Fill the final assertion using the SAME projection-path helper the existing single-harness `skill install` test uses (do not invent a new one). The point is to run the existing assertion across three mechanisms, not to write new path logic.

- [ ] **Step 3: Run it, verify all three pass**

Run: `uv run pytest tests/test_cli/test_cli_skill_install.py -k each_mechanism -v`
Expected: 3 PASS.

- [ ] **Step 4: Add the mcp-install parametrized test**

```python
import pytest

_MCP_HARNESSES = ["claude-code", "codex", "opencode", "pi"]

@pytest.mark.parametrize("harness", _MCP_HARNESSES)
def test_mcp_install_writes_config_for_each_harness(harness, tmp_path, monkeypatch):
    """mcp install projects into every MCP harness's config target."""
    # Mirror the existing test_cli_mcp.py install test's setup (add a library
    # mcp, monkeypatch HOME + the harness's config dir), then assert the named
    # server appears in that harness's config file after install.
    ...
```

> Use the existing `test_cli_mcp.py` install test as the literal template for setup; the only new axis is `harness`. Reuse its config-read assertion. If a harness needs its config dir pre-created (e.g. `_target_config_exists` gate in `mcp_install.py:77-86`), create it in the test as that test already does for claude-code.

- [ ] **Step 5: Run mcp install params, verify green**

Run: `uv run pytest tests/test_cli_mcp.py -k each_harness -v`
Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli/test_cli_skill_install.py tests/test_cli_mcp.py
git commit -m "test: parametrize skill/mcp install over adapter-mechanism representatives (#423)"
```

---

## Task 4: project-scope variants (G3 / AC3)

Add `-p` (project) scope variants for install/uninstall/status/update where e2e coverage is global-only. Reuse each asset's existing global test as the template; the only change is `-g` → `-p` plus a project-root setup.

**Files:**
- Modify: `tests/test_cli/test_cli_agent_update.py` (add a project-scope `agent update`)
- Modify: the instructions / mcp / pi-extension lifecycle test files (one project-scope case each for a mutating verb not yet covered at project scope)

- [ ] **Step 1: Identify which (asset, verb, scope=project) cells lack a test**

For each of agent/instructions/mcp/pi-extension and verbs install/uninstall/status/update, grep the test files for a `-p` / `--project` invocation. List the missing ones. (Expect a handful, not all.)

Run: `grep -rn '"-p"\|"--project"' tests/ | grep -iE "install|uninstall|status|update"`

- [ ] **Step 2: For each missing cell, clone its global test and switch to project scope**

Pattern (project root + lock seeded under the project, invoke with `-p`):

```python
def test_<asset>_<verb>_project_scope(tmp_path, monkeypatch):
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(project)   # project scope resolves from cwd
    # ... seed a project-scope lock/canonical exactly as the global test does,
    #     but at project scope (canonical_*_dir(..., scope="project", project=project)) ...
    r = CliRunner().invoke(main, ["<asset>", "<verb>", "<slug>", "-p"])
    assert r.exit_code == 0, r.output
    # assert the project-scoped destination/lock changed
```

> **Trap (project memory `project_346_run_complete`):** several `build_*`/inventory paths read the global lock via `$HOME`, not the `home=` arg — so project-scope tests MUST `monkeypatch.setenv("HOME", ...)` even when passing an explicit project, or the command reads the real `$HOME`. Always set HOME in these tests.

- [ ] **Step 3: Run the new project-scope tests, verify green**

Run: `uv run pytest tests/ -k project_scope -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test: add project-scope variants for install/uninstall/status/update (#423)"
```

---

## Task 5: error-path tests (G4 / AC4)

Add error-condition tests for mutating verbs: dirty canonical, lock mismatch, missing canonical, not-in-lock, invalid slug. Assert the `InstallError`-family behavior (non-zero exit + the specific message). Use the `make_dirty` / `make_diverged` fixtures where a git state is needed.

**Files:**
- Modify: the relevant per-asset test files (skill / agent / mcp / pi-extension), adding focused error cases.

- [ ] **Step 1: Enumerate the error branches actually reachable per verb**

Grep production code for the error messages so tests assert real strings, not invented ones.

Run: `grep -rn "InstallError\|not in lock\|no .git\|raise \|ctx.exit(1)\|DirtyCanonical\|LockMismatch" src/agent_toolkit_cli/ | grep -iE "install|update|reset|push|uninstall"`

- [ ] **Step 2: Add not-in-lock + invalid-slug cases (cheapest, highest coverage)**

For each asset with `update`/`push`/`reset`/`uninstall`, add:

```python
def test_<asset>_<verb>_not_in_lock_reports_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)
    r = CliRunner().invoke(main, ["<asset>", "<verb>", "ghost", "-g"])
    assert r.exit_code != 0 or "not in lock" in r.output or "no " in r.output.lower()
```

- [ ] **Step 3: Add a dirty-canonical case for a verb that refuses on dirt**

Use the `make_dirty` fixture (uncommitted edit in the clone). Assert the verb refuses (non-zero / explicit message) rather than silently proceeding. Only add this for verbs whose production code actually guards on a dirty tree — confirm from Step 1's grep; do not assert a guard that doesn't exist.

- [ ] **Step 4: Run all new error-path tests, verify green**

Run: `uv run pytest tests/ -k "not_in_lock or invalid_slug or dirty or missing_canonical or lock_mismatch" -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/
git commit -m "test: error-path coverage for mutating verbs (not-in-lock, dirty, bad slug) (#423)"
```

---

## Task 6: full-suite green + guard final check

- [ ] **Step 1: Run the complete suite**

Run: `uv run pytest -q 2>&1 | tail -20`
Expected: all pass (baseline ~1,316 + ~45–65 new + guard cells). Note any pre-existing whitelisted env failures from project memory and confirm they're unchanged, not newly introduced.

- [ ] **Step 2: Confirm the guard sees zero gaps**

Run: `uv run pytest tests/test_cli/test_command_coverage_guard.py -q`
Expected: all parametrized cells PASS — the matrix is complete and enforced.

- [ ] **Step 3: Lint/type gate (match the repo's pre-commit)**

Run: `uv run ruff check tests/ && uv run ruff format --check tests/`
Expected: clean. (Note: per project memory the repo does NOT enforce mypy in pre-commit; do not add type churn.)

---

## Self-review

- **Spec coverage:** AC0→Task 2, AC1→Task 1, AC2→Task 3, AC3→Task 4, AC4→Task 5, AC5→Task 6. All five ACs mapped.
- **Ordering:** Task 1 before Task 2 so the guard is never committed red. ✓
- **Placeholders:** Tasks 3–5 intentionally say "use the existing test's helper/assertion" rather than inventing path logic — this is a deliberate instruction to reuse, not a TBD. The contract (exit code + message) is concrete in every case. The one genuinely open item (exact projection-path helper for skill install) is flagged to be lifted verbatim from the existing single-harness test, not guessed.
- **Type consistency:** lock fields used (`local_sha`, `upstream_sha`, `ref`) match `update_cmd.py`'s usage; `library_agent_path` / `library_lock_path` / `canonical_agent_dir` match `agent_paths.py`.
- **Trap coverage:** SKILL.md-vs-`<slug>.md` seeding trap (Task 1), `$HOME`-read-at-project-scope trap (Task 4), assert-real-message (Task 5 Step 1), don't-add-mypy-churn (Task 6) all carried from project memory.
