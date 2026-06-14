# CLI command-coverage completion + guard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the test suite exercise every registered CLI command cell, add a CI guard that keeps it that way, and deepen the thin cells (harness parametrization, project scope, error paths).

**Architecture:** Test-only change. A new meta-test enumerates registered command cells and asserts each is invoked; new/expanded test files close the one empty cell (`agent update`) and the depth gaps. No production code changes except a possible tiny enumeration helper kept inside the test.

**Tech Stack:** pytest, `click.testing.CliRunner`, existing `tests/conftest.py` fixtures (`git_sandbox`, `make_behind/ahead/diverged/conflict/dirty`, `installed_skill`).

**Issue:** #423 · **Spec:** `docs/superpowers/specs/2026-06-14-verb-asset-harness-coverage-design.md`

---

## File structure

- `tests/test_cli/test_command_coverage_guard.py` — **new** (G0/AC0). The invariant, via **Click introspection** (not glob) + **comment-stripped** scan. Honest docstring: invocation-presence, NOT behavior.
- `tests/test_cli/test_cli_agent_update.py` — **new** (G1/AC1). Clones the pi-extension update template.
- per-asset test files — **modify** (G0b/AC0b). Behavior assertions for cells the thin-cell audit flags.
- `tests/test_cli/test_cli_skill_install.py` — **modify** (G2/AC2). Add per-mechanism parametrization.
- `tests/test_cli_mcp.py` — **modify** (G2/AC2). Add 4-harness parametrization.
- `tests/test_cli/test_cli_agent_update.py` + existing instructions/mcp/pi-ext test files — **modify** (G3/AC3, G4/AC4). Scope (excl. `mcp update`) + error-path cases.

> **Ordering note:** Task 1 (G1) lands BEFORE Task 2 (G0). The guard goes red until `agent update` is tested, so write the agent-update tests first, then add the guard that codifies "every cell invoked". This keeps every commit green.

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
def test_agent_update_unknown_slug_reports_error(tmp_path, monkeypatch, git_sandbox):
    """A named slug not in the lock => '{slug}: not in lock' + exit 1.

    NOTE: this needs a lock that EXISTS but lacks the slug. With NO lock at all,
    read_lock returns an empty lock (it swallows FileNotFoundError, see
    skill_lock.read_lock) and `targets = slugs` => the loop hits 'not in lock'
    and exits 1 — but to make the lock-exists path explicit, seed one entry first.
    """
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    upstream = _make_agent_upstream(tmp_path, git_sandbox.env)
    CliRunner().invoke(main, ["agent", "add", str(upstream), "--slug", "demo"])

    r = CliRunner().invoke(main, ["agent", "update", "nope", "-g"])
    assert r.exit_code != 0
    assert "nope: not in lock" in r.output


def test_agent_update_no_lock_is_silent_noop(tmp_path, monkeypatch):
    """REVIEW FIX: read_lock swallows FileNotFoundError and returns an EMPTY lock,
    so `agent update -g` with no lock takes targets=() => the loop runs zero times
    => exit 0 with EMPTY output. The 'no agents lock found' branch in update_cmd.py
    is dead code (read_lock never raises). Assert the REAL behavior, not the message.
    """
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)
    r = CliRunner().invoke(main, ["agent", "update", "-g"])
    assert r.exit_code == 0, r.output
    assert r.output.strip() == "", f"expected empty output, got: {r.output!r}"


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
    """A lock entry whose canonical has no .git/ cannot update: message + exit 1.

    Seed directly at library_agent_path("plain") — the EXACT path update_cmd reads
    (update_cmd.py: `canonical = library_agent_path(slug)`). Review confirmed
    canonical_agent_dir("plain", scope="global") == library_agent_path("plain") at
    global scope, so either resolves the same dir; we use library_agent_path to make
    the intent unambiguous.
    """
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    (tmp_path / "fake-home").mkdir(parents=True, exist_ok=True)
    from agent_toolkit_cli.agent_lock import LockEntry, add_entry, read_lock, write_lock
    from agent_toolkit_cli.agent_paths import library_agent_path, library_lock_path
    # Seed a NON-git canonical at the path the command reads + a lock entry for it.
    canonical = library_agent_path("plain")
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

> Review verified (by running the command): seeding a non-git dir at `library_agent_path("plain")` reaches the `no .git` branch (`exit 1`, message `"plain: no .git/ in canonical — cannot update; ..."`). No reachability hedge needed — `canonical_agent_dir(global) == library_agent_path`.

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

Enumerate every registered CLI command cell **via Click introspection** (not a filesystem glob — review finding: the glob missed `skill remove`/`skill uninstall`, which are inline `@skill.command()` in `commands/skill/__init__.py`), and assert each is *named* by ≥1 live test invocation. Scan the test corpus **with comments stripped** so a commented-out/dead invocation cannot satisfy the guard (review finding). After Task 1 this passes; a future un-invoked cell fails it.

**Honest-framing requirement (review):** the guard's docstring MUST state it asserts *invocation presence*, NOT behavioral coverage — it guarantees "no cell ships completely untested", not "every cell is effectively tested" (that is G0b's job).

**Files:**
- Create: `tests/test_cli/test_command_coverage_guard.py`

- [ ] **Step 1: Write the guard test (Click-introspection enumeration)**

```python
"""Coverage guard (#423 / AC0): every registered CLI command cell must be NAMED
by at least one live test invocation.

WHAT THIS GUARANTEES (and what it does NOT):
- Guarantees: no (group, verb) command ships *completely un-invoked* by any test.
  This is a regression FLOOR — the lowest bar worth enforcing.
- Does NOT guarantee the command's behavior is effectively asserted. A --help or
  bare exit-code smoke satisfies this guard. Assertion DEPTH is a reviewer / G0b
  concern, NOT enforced here. Do not read a green guard as "comprehensive coverage".

Mechanism: enumerate cells from Click's own command tree (so inline @group.command()
verbs and aliases are caught automatically), then scan the comment-stripped test
corpus for a literal ["<group-or-alias>", "<verb>"] invocation.
"""
from __future__ import annotations

import io
import re
import tokenize
from pathlib import Path

import pytest

from agent_toolkit_cli.cli import main

_TESTS = Path(__file__).resolve().parents[1]

# Click registers each group under its canonical name AND any aliases (skills,
# mcps). Map canonical group-name -> all first-token spellings tests may use.
_GROUP_ALIASES = {
    "skill": ("skill", "skills"),
    "agent": ("agent", "agents"),
    "instructions": ("instructions",),
    "mcp": ("mcp", "mcps"),
    "pi-extension": ("pi-extension", "pi_extension"),
    "bundle": ("bundle",),
}


def _registered_cells() -> set[tuple[str, str]]:
    """(group, verb) for every command Click actually exposes.

    Walk main.commands; for each sub-group, walk its .commands. This catches
    verbs defined inline in __init__.py (skill remove/uninstall) AND those in
    *_cmd.py, with zero filesystem assumptions. De-aliases group names so
    `skills`/`mcps` don't double-count.
    """
    canonical = set(_GROUP_ALIASES)
    cells: set[tuple[str, str]] = set()
    for gname, gcmd in main.commands.items():
        if gname not in canonical:
            continue  # skip the alias registrations (skills, mcps)
        subcmds = getattr(gcmd, "commands", {})
        for vname in subcmds:
            cells.add((gname, vname))
    return cells


def _strip_comments(src: str) -> str:
    """Remove Python comments so a commented-out invocation can't satisfy the guard."""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                continue
            out.append(tok)
        return tokenize.untokenize(out)
    except (tokenize.TokenError, IndentationError):
        # Fall back to a regex strip if a file won't tokenize cleanly.
        return re.sub(r"#.*", "", src)


def _scannable_test_source() -> str:
    parts = []
    for p in _TESTS.rglob("*.py"):
        if p.name == Path(__file__).name:
            continue  # don't let this guard self-satisfy
        parts.append(_strip_comments(p.read_text(encoding="utf-8", errors="ignore")))
    return "\n".join(parts)


@pytest.fixture(scope="module")
def test_src() -> str:
    return _scannable_test_source()


@pytest.mark.parametrize("group, verb", sorted(_registered_cells()))
def test_command_cell_is_invoked_by_a_test(group, verb, test_src):
    aliases = _GROUP_ALIASES[group]
    # Match an invoke list opening: ["agent", "update"  or  ('agents', 'update'
    pattern = re.compile(
        r"""["'](?:%s)["']\s*,\s*["']%s["']"""
        % ("|".join(re.escape(a) for a in aliases), re.escape(verb))
    )
    assert pattern.search(test_src), (
        f"command cell ({group} {verb}) is named by no test. Add a test that "
        f'invokes CliRunner().invoke(main, ["{aliases[0]}", "{verb}", ...]) and '
        f"asserts its behavior (not just exit_code == 0)."
    )
```

- [ ] **Step 2: Sanity-check the enumeration matches reality**

Run a throwaway probe to confirm Click introspection finds exactly the expected cells (skill should now include `remove` and `uninstall`):

Run: `uv run python -c "from tests.test_cli.test_command_coverage_guard import _registered_cells; import pprint; pprint.pprint(sorted(_registered_cells()))"`
Expected: includes `('skill', 'remove')`, `('skill', 'uninstall')`, `('skill', 'install')`, `('skill', 'add')`, `('agent', 'update')`, and NO `skills`/`mcps` alias duplicates.

- [ ] **Step 3: Run the guard, verify all parametrizations pass**

Run: `uv run pytest tests/test_cli/test_command_coverage_guard.py -v`
Expected: every cell PASS (Task 1 closed `agent update`; comment-stripping must not have removed a real invocation). If a cell fails that you believe IS tested, check whether its only invocation was inside a comment (correct fail) or whether an alias spelling is missing from `_GROUP_ALIASES` (extend it).

- [ ] **Step 4: Prove the guard guards — three negative checks**

(a) **Un-invoked new cell** — temporarily add `src/agent_toolkit_cli/commands/bundle/zzz_cmd.py` registering a `zzz` command on the bundle group (an empty file is NOT enough now — the guard reads Click, so the command must actually register). Simplest: append a trivial `@bundle.command("zzz")` in `commands/bundle/__init__.py`, run the guard, confirm `(bundle, zzz)` FAILS, then revert. Do NOT commit.

(b) **Comment-only invocation does NOT satisfy** — in a scratch test file add only `# CliRunner().invoke(main, ["bundle", "validate"])` as a comment and TEMPORARILY remove the real `bundle validate` test, confirm the guard FAILS for `(bundle, validate)`, then restore. (Confirms comment-stripping works.) Revert; do NOT commit.

Run (a): edit `commands/bundle/__init__.py` to add a `zzz` command, then `uv run pytest tests/test_cli/test_command_coverage_guard.py -k zzz`; then `git checkout src/agent_toolkit_cli/commands/bundle/__init__.py`
Expected: `zzz` FAILS, then is reverted.

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_command_coverage_guard.py
git commit -m "test: guard that every CLI command cell is named by a live test (Click-introspection, comment-stripped) (#423)"
```

---

## Task 2b: thin-cell assertion audit (G0b / AC0b) — addresses "effective"

The guard (Task 2) proves *invocation*, not *behavior*. This task answers the user's **"effective"** ask: find cells whose ONLY coverage is a `--help` invocation or a behaviorless `assert exit_code == 0` smoke, and add a real behavior-asserting test where one is genuinely missing. **Bounded:** only cells the audit flags thin — not a blanket rewrite.

**Files:**
- Create (audit output, temporary): a scratch list in the PR description — NOT a committed file.
- Modify: per-asset test files, adding behavior assertions only where flagged.

- [ ] **Step 1: Run the thin-cell audit**

For each registered cell (reuse `_registered_cells()` from Task 2), find the tests that invoke it and classify each invocation:
- **help-only:** the invoke list contains `"--help"` and the test asserts only help text.
- **smoke-only:** the only assertion on the result is `exit_code == 0` (or `!= 0`) with no check of output, files, or lock state.
- **behavioral:** asserts a message string, a created/removed file, a lock change, or projection path.

A cell is THIN if ALL its invocations are help-only or smoke-only. Produce the list:

```bash
# Starting point — list every test invocation per cell, then read the flagged ones:
uv run python - <<'PY'
import re, pathlib
from tests.test_cli.test_command_coverage_guard import _registered_cells, _GROUP_ALIASES
tests = pathlib.Path("tests")
src = {p: p.read_text() for p in tests.rglob("*.py")}
for group, verb in sorted(_registered_cells()):
    aliases = _GROUP_ALIASES[group]
    pat = re.compile(r'["\'](?:%s)["\']\s*,\s*["\']%s["\']' %
                     ("|".join(map(re.escape, aliases)), re.escape(verb)))
    hits = [p.name for p, t in src.items() if pat.search(t)]
    print(f"{group} {verb}: {hits}")
PY
```

Then READ each flagged cell's test(s) and decide thin-or-not by eye (the script locates; the judgment is human/agent).

- [ ] **Step 2: For each genuinely-thin cell, add ONE behavior-asserting test**

Reuse the asset's existing fixtures. Assert something real: the specific output message, a projected file's existence, or a lock-state change. Do NOT add a test for a cell that already has a behavioral assertion elsewhere.

- [ ] **Step 3: Record the audit result in the PR description**

List every cell audited, its verdict (behavioral / was-thin-now-fixed), so the reviewer can see *effectiveness* was checked, not just invocation. This is the artifact that answers "comprehensive AND effective".

- [ ] **Step 4: Run new behavior tests + commit**

Run: `uv run pytest tests/ -k "behavior or effective" -v` (or the specific new test names)
Expected: all PASS.

```bash
git add tests/
git commit -m "test: deepen thin cells flagged by the assertion audit (#423)"
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

> **EXCLUDE `mcp update` (review finding):** `mcp update` is **global-only by design — it has NO `-p` flag** (`commands/mcp/update_cmd.py` docstring: "NO scope flag"; `test_cli_mcp.py` confirms `["mcp","update",...]` with no `-p`). Do NOT write a project-scope test for it — it would fail on an unknown option. Skip it when listing gaps.

Run: `grep -rn '"-p"\|"--project"' tests/ | grep -iE "install|uninstall|status|update"`
Then for each candidate, confirm the verb actually HAS a `-p` option before writing the test: `uv run agent-toolkit-cli <asset> <verb> --help | grep -- '-p'`

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

## Task 5: error-path tests (G4 / AC4) — BOUNDED, specific-message assertions

Add **bounded** error-condition tests for mutating verbs. **Review finding:** production has ~95 raise sites — this task is NOT "cover them all". It covers two cheap-and-high-value categories (not-in-lock, invalid-slug) across the four core asset types, plus dirty-canonical ONLY where a real guard exists. **Every assertion checks the SPECIFIC production message** — no permissive `exit≠0 OR "no" in output` disjunctions (that is the "green checkmark without substance" failure mode).

**Files:**
- Modify: the relevant per-asset test files (skill / agent / mcp / pi-extension), adding focused error cases.

- [ ] **Step 1: Enumerate the EXACT error strings per verb (so tests assert real text)**

Grep production for the literal messages. Record the exact string each verb prints for not-in-lock / invalid-slug so the test asserts THAT string, not a guess.

Run: `grep -rn "not in lock\|no .git\|InstallError\|raise \|ctx.exit(1)\|DirtyCanonical\|LockMismatch\|UsageError" src/agent_toolkit_cli/ | grep -iE "install|update|reset|push|uninstall"`

Produce a small table: `(asset, verb) → exact not-in-lock message`. (e.g. agent update prints `"{slug}: not in lock"`.)

- [ ] **Step 2: Add not-in-lock cases asserting the SPECIFIC message**

For each asset with `update`/`push`/`reset`/`uninstall`, seed a lock that EXISTS but lacks the queried slug (so the not-in-lock branch — not the empty-lock no-op — fires), then assert the exact recorded string:

```python
def test_<asset>_<verb>_not_in_lock_reports_specific_error(tmp_path, monkeypatch, git_sandbox):
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fake-home"))
    # Seed ONE real entry so the lock is non-empty (mirror the asset's add helper),
    # then query a different, absent slug.
    ... seed "demo" via the asset's `add` ...
    r = CliRunner().invoke(main, ["<asset>", "<verb>", "ghost", "-g"])
    assert r.exit_code != 0
    assert "ghost: not in lock" in r.output   # EXACT string from Step 1, not a disjunction
```

> Per-asset the message differs — use the string recorded in Step 1 for that asset. If an asset's verb has no "not in lock" concept (check Step 1), skip it rather than forcing a generic assertion.

- [ ] **Step 3: Add invalid-slug cases (UsageError / refusal) asserting the specific message**

For verbs that validate slug shape (path traversal, empty, dots), assert the exact rejection message recorded in Step 1. Skip verbs that have no slug validation.

- [ ] **Step 4: Add a dirty-canonical case ONLY where a real guard exists**

Use the `make_dirty` fixture (uncommitted edit in the clone). Assert the verb refuses with its specific message. **Confirm the guard exists first** (Step 1 grep) — e.g. `agent update` has NO dirty-tree guard, so do NOT write one for it. If no mutating verb in scope guards on dirt, SKIP this step and note "no dirty-canonical guard in scope" in the PR — do not invent a guard or a test for a branch that can't fire.

- [ ] **Step 5: Run all new error-path tests, verify green**

Run: `uv run pytest tests/ -k "not_in_lock or invalid_slug or dirty or missing_canonical or lock_mismatch" -v`
Expected: all PASS, each asserting a SPECIFIC message.

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: bounded error-path coverage with specific-message assertions (#423)"
```

---

## Task 6: full-suite green + guard final check

- [ ] **Step 1: Run the complete suite**

Run: `uv run pytest -q 2>&1 | tail -20`
Expected: all pass (baseline ~1,527 `def test_` functions as of 2026-06-14, + ~45–65 new + guard cells). Note any pre-existing whitelisted env failures from project memory and confirm they're unchanged, not newly introduced.

- [ ] **Step 2: Confirm the guard sees zero gaps**

Run: `uv run pytest tests/test_cli/test_command_coverage_guard.py -q`
Expected: all parametrized cells PASS — the matrix is complete and enforced.

- [ ] **Step 3: Lint/type gate (match the repo's pre-commit)**

Run: `uv run ruff check tests/ && uv run ruff format --check tests/`
Expected: clean. (Note: per project memory the repo does NOT enforce mypy in pre-commit; do not add type churn.)

---

## Self-review

- **Spec coverage:** AC0→Task 2, AC0b→Task 2b, AC1→Task 1, AC2→Task 3, AC3→Task 4, AC4→Task 5. **Five acceptance criteria mapped; Task 6 is verification, not an AC** (coherence-review fix: an earlier draft falsely claimed an "AC5"). ✓
- **Ordering:** Task 1 before Task 2 so the guard is never committed red. ✓
- **Placeholders:** Tasks 3–5 intentionally say "use the existing test's helper/assertion" rather than inventing path logic — a deliberate reuse instruction, not a TBD. Task 5 now mandates the SPECIFIC production message (recorded in its Step 1), removing the permissive disjunction the product-review flagged.
- **Type consistency:** lock fields used (`local_sha`, `upstream_sha`, `ref`) match `update_cmd.py`; `library_agent_path` / `library_lock_path` / `canonical_agent_dir` match `agent_paths.py`. The guard enumerates via `main.commands[...].commands` (Click), de-aliasing `skills`/`mcps`.
- **Trap coverage:** SKILL.md-vs-`<slug>.md` seeding trap (Task 1); read_lock-swallows-FileNotFoundError dead-code trap (Task 1 no-lock test — feasibility-review fix); guard-misses-inline-verbs trap solved by Click introspection (scope-guardian fix); guard-passes-on-dead-code solved by comment-stripping (adversarial fix); `mcp update` has no `-p` (Task 4 — scope-guardian fix); `$HOME`-read-at-project-scope trap (Task 4); specific-message assertions (Task 5 — product-review fix); don't-add-mypy-churn (Task 6). All carried from project memory or critical review.
- **Critical-review findings:** all 10 resolved inline (see the spec's "Critical review" section for the ledger).
