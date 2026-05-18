# Per-scope `is_supported` for pi project agents — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `is_supported(harness, kind, scope=...)` answer per-scope so we can remove the dead `_PROJECT_TARGETS[("pi","agent")]` row without violating SSOT invariants.

**Architecture:**
1. Relax the `_USER_TARGETS == _PROJECT_TARGETS` parity to `_PROJECT_TARGETS ⊆ _USER_TARGETS`.
2. Extend `is_supported` with an optional `scope` parameter; back-compat (no scope) keeps current behaviour.
3. Update the two iteration sites in the linker / unlinker to pass `scope=scope` so they pre-check per-scope support before calling `harness_target_dir`.
4. Remove `_PROJECT_TARGETS[("pi","agent")]`. The `_list_json._cell_status` "unsupported" branch already handles the resulting `slot_dir → None`.

**Tech Stack:** Python 3.12, click, pytest, uv. Source at `src/agent_toolkit_cli/`. Tests at `tests/`.

**Spec:** `docs/superpowers/specs/2026-05-05-per-scope-is-supported-pi-project-agents-design.md`

---

### Task 1: Pin acceptance criteria 1–4 with failing tests

**Files:**
- Modify: `tests/test_support.py`

- [ ] **Step 1: Add the new tests**

Append these tests to `tests/test_support.py` after the existing `test_is_supported_matches_set_membership` test:

```python
def test_is_supported_back_compat_no_scope_for_pi_agent():
    """Acceptance #1: is_supported('pi','agent') returns True without a scope arg."""
    assert is_supported("pi", "agent") is True


def test_is_supported_user_scope_for_pi_agent_is_true():
    """Acceptance #2: pi agents ARE supported at user scope (~/.pi/agent/agents)."""
    assert is_supported("pi", "agent", scope="user") is True


def test_is_supported_project_scope_for_pi_agent_is_false():
    """Acceptance #3: pi has no project-scope agent discovery — must report unsupported."""
    assert is_supported("pi", "agent", scope="project") is False


def test_is_supported_unknown_scope_returns_false():
    """Defensive: any scope string other than 'user' or 'project' returns False."""
    assert is_supported("claude", "skill", scope="bogus") is False


def test_slot_dir_pi_agent_project_returns_none(tmp_path):
    """Acceptance #4: project-scope slot for (pi, agent) is None after the row is removed."""
    from agent_toolkit_cli._support import slot_dir

    assert slot_dir("pi", "agent", "project", project_root=tmp_path) is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/test_support.py::test_is_supported_user_scope_for_pi_agent_is_true tests/test_support.py::test_is_supported_project_scope_for_pi_agent_is_false tests/test_support.py::test_is_supported_unknown_scope_returns_false tests/test_support.py::test_slot_dir_pi_agent_project_returns_none -v`

Expected: all four FAIL — `test_is_supported_user_scope_for_pi_agent_is_true` fails with `TypeError: is_supported() got an unexpected keyword argument 'scope'`. `test_slot_dir_pi_agent_project_returns_none` fails because the row is still present (returns a Path, not None).

The back-compat test `test_is_supported_back_compat_no_scope_for_pi_agent` should already PASS — pin only.

- [ ] **Step 3: Commit**

```bash
git add tests/test_support.py
git commit -m "test(#49): pin per-scope is_supported acceptance criteria"
```

---

### Task 2: Update parity test from equality to subset

**Files:**
- Modify: `tests/test_support.py:28-31`

- [ ] **Step 1: Replace the equality assertion with subset**

Find the existing test and rewrite line 31:

```python
def test_supported_pairs_match_target_keys():
    """SUPPORTED_PAIRS is derived from _USER_TARGETS — no second SSOT.

    _PROJECT_TARGETS is a subset of _USER_TARGETS: project scope can omit a
    pair the harness only reads at user scope (e.g. pi agents at user scope
    only — see issue #49).
    """
    assert SUPPORTED_PAIRS == frozenset(_USER_TARGETS.keys())
    assert frozenset(_PROJECT_TARGETS.keys()) <= frozenset(_USER_TARGETS.keys())
```

- [ ] **Step 2: Run the parity test — must still PASS now (unchanged tables)**

Run: `uv run pytest tests/test_support.py::test_supported_pairs_match_target_keys -v`

Expected: PASS. Tables haven't changed yet, so the subset relation holds trivially.

- [ ] **Step 3: Commit**

```bash
git add tests/test_support.py
git commit -m "test(#49): relax _USER/_PROJECT key-set invariant to subset"
```

---

### Task 3: Implement per-scope `is_supported`

**Files:**
- Modify: `src/agent_toolkit_cli/_support.py:81-83`

- [ ] **Step 1: Replace `is_supported` with the per-scope version**

In `src/agent_toolkit_cli/_support.py`, replace the current `is_supported` definition:

```python
def is_supported(harness: str, kind: str, scope: str | None = None) -> bool:
    """True iff `(harness, kind)` has a real adapter slot in the matrix.

    With `scope=None` (default), returns True if the pair has a slot at *any*
    scope — i.e., membership in `SUPPORTED_PAIRS`. This is the back-compat
    answer used by allow-list/validate code paths that operate before a scope
    is in scope.

    With `scope="user"` or `scope="project"`, returns True only if the pair
    has a slot at *that* scope. Use this in projection-time code paths
    (linker iteration loops, etc.) so per-scope-only entries (e.g.
    `("pi","agent")` at user scope only) are skipped cleanly instead of
    falling through to a `harness_target_dir → None → RuntimeError`.

    Any other scope value returns False.
    """
    if scope is None:
        return (harness, kind) in SUPPORTED_PAIRS
    if scope == "user":
        return (harness, kind) in _USER_TARGETS
    if scope == "project":
        return (harness, kind) in _PROJECT_TARGETS
    return False
```

- [ ] **Step 2: Run the four scope-aware tests — three should PASS, one still fails**

Run: `uv run pytest tests/test_support.py::test_is_supported_back_compat_no_scope_for_pi_agent tests/test_support.py::test_is_supported_user_scope_for_pi_agent_is_true tests/test_support.py::test_is_supported_project_scope_for_pi_agent_is_false tests/test_support.py::test_is_supported_unknown_scope_returns_false -v`

Expected: `test_is_supported_back_compat_no_scope_for_pi_agent` PASS, `test_is_supported_user_scope_for_pi_agent_is_true` PASS, `test_is_supported_unknown_scope_returns_false` PASS, `test_is_supported_project_scope_for_pi_agent_is_false` **FAIL** — the `_PROJECT_TARGETS` row is still there. That's expected; Task 4 removes it.

- [ ] **Step 3: Commit**

```bash
git add src/agent_toolkit_cli/_support.py
git commit -m "feat(#49): add scope parameter to is_supported"
```

---

### Task 4: Remove the dead `_PROJECT_TARGETS[("pi","agent")]` row

**Files:**
- Modify: `src/agent_toolkit_cli/_support.py:51-56`

- [ ] **Step 1: Delete the row and its multi-line comment**

In `src/agent_toolkit_cli/_support.py`, remove the `("pi", "agent")` entry from `_PROJECT_TARGETS` and the explanatory comment block above it. After this edit the dict's pi rows look like:

```python
    # Pi project-scope: pi reads from <cwd>/.pi/{skills,extensions} (no /agent/
    # infix at project scope). User-scope keeps the .pi/agent/ prefix because
    # pi's globalBaseDir == ~/.pi/agent. See package-manager.js:669-686.
    # Pi has no project-scope `agents` discovery (package-manager.js:1788-1794
    # — only extensions, skills, prompts, themes are auto-discovered at
    # project scope), so ("pi","agent") is intentionally absent here. Per-
    # scope `is_supported(..., scope="project")` answers False for this pair.
    ("pi", "skill"):           ".pi/skills",
    ("pi", "pi-extension"):    ".pi/extensions",
```

(The comment is collapsed to one block that explains both the `.pi/{skills,extensions}` layout and the deliberate absence of `("pi","agent")`.)

- [ ] **Step 2: Run the project-scope tests — should now PASS**

Run: `uv run pytest tests/test_support.py::test_is_supported_project_scope_for_pi_agent_is_false tests/test_support.py::test_slot_dir_pi_agent_project_returns_none tests/test_support.py::test_supported_pairs_match_target_keys -v`

Expected: all three PASS.

- [ ] **Step 3: Run the full `test_support.py` suite — must still all PASS**

Run: `uv run pytest tests/test_support.py -v`

Expected: PASS. `SUPPORTED_PAIRS` is still derived from `_USER_TARGETS.keys()`, so removing a `_PROJECT_TARGETS` row doesn't change `SUPPORTED_PAIRS`. `is_supported("pi","agent")` (no scope) still returns True via the user-scope row.

- [ ] **Step 4: Run the full test suite — see what breaks**

Run: `uv run pytest -q`

Expected: at least one failure related to `harness_target_dir(pi, agent, "project", ...) → None → RuntimeError`. Specifically: any test that exercises `_link_lib.project_from_file` or `unlink._do_all` against `harness=pi, scope=project` with an allow-listed agent will now hit the `RuntimeError("is_supported(...) is True but harness_target_dir returned None — SSOT invariant broken")` at `src/agent_toolkit_cli/commands/_link_lib.py:495-499`. If no existing test exercises that path, the suite passes — Task 5's new test will surface it.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/_support.py
git commit -m "feat(#49): remove dead _PROJECT_TARGETS[(pi, agent)] row"
```

---

### Task 5: Add a failing test for the linker `RuntimeError` exposure

**Files:**
- Modify: `tests/test_link_lib.py`

- [ ] **Step 1: Add the test exposing the RuntimeError**

Append this test after the existing `test_project_from_file_skips_unsupported_kinds_silently` test in `tests/test_link_lib.py`:

```python
def test_project_from_file_skips_pi_agent_at_project_scope_cleanly(tmp_path, monkeypatch):
    """Acceptance #5: project_from_file with harness=pi, scope=project must
    NOT raise when an `agent` asset is allow-listed.

    Pi has no project-scope agent discovery (issue #49). With the per-scope
    is_supported check at _link_lib.py:488 we skip cleanly; without it we'd
    fall through to harness_target_dir(pi, agent, "project", ...) → None →
    RuntimeError("SSOT invariant broken").
    """
    import io
    from agent_toolkit_cli.commands._link_lib import LinkCounters, project_from_file

    monkeypatch.setenv("HOME", str(tmp_path))
    project_root = tmp_path / "project"
    project_root.mkdir()
    allowlist_path = project_root / ".agent-toolkit.yaml"
    allowlist_path.write_text("agents: [foo-agent]\n")

    toolkit_root = tmp_path / "toolkit"
    agents_dir = toolkit_root / "agents"
    agents_dir.mkdir(parents=True)
    asset_path = agents_dir / "foo-agent.md"
    asset_path.write_text(
        "---\n"
        "kind: agent\n"
        "slug: foo-agent\n"
        "spec:\n"
        "  harnesses: [pi]\n"
        "---\n"
        "body\n"
    )

    counters = LinkCounters()
    out = io.StringIO()

    project_from_file(
        scope="project",
        harness="pi",
        toolkit_root=toolkit_root,
        project_root=project_root,
        allowlist_path=allowlist_path,
        dry_run=True,
        counters=counters,
        stdout=out,
    )
    # No symlinks created/would-be-created, no RuntimeError.
    assert counters.created == 0
    assert counters.would_link == 0
    assert counters.removed == 0
    assert counters.would_unlink == 0
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `uv run pytest tests/test_link_lib.py::test_project_from_file_skips_pi_agent_at_project_scope_cleanly -v`

Expected: FAIL with `RuntimeError: is_supported('pi', 'agent') is True but harness_target_dir returned None — SSOT invariant broken`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_link_lib.py
git commit -m "test(#49): pin pi/agent project-scope clean-skip behaviour"
```

---

### Task 6: Update linker iteration to use per-scope `is_supported`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py:488-499`
- Modify: `src/agent_toolkit_cli/commands/unlink.py:160`

- [ ] **Step 1: Update `_link_lib.project_from_file` filter and rewrite the RuntimeError guard**

In `src/agent_toolkit_cli/commands/_link_lib.py`, find lines 488-499 (the loop body inside `project_from_file` that filters by support and resolves `target_dir`). Replace:

```python
        if not is_supported(harness, kind):
            # Boundary: caller asked for a harness/kind pair we have no slot
            # for. Silent-skip is wrong (#30) but non-MCP kinds reach here
            # from a discovery loop, not user input — we honour the filter
            # rather than raise. Direct entrypoints (maybe_link) raise.
            continue
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if target_dir is None:
            raise RuntimeError(
                f"is_supported({harness!r}, {kind!r}) is True but "
                f"harness_target_dir returned None — SSOT invariant broken"
            )
```

with:

```python
        if not is_supported(harness, kind, scope=scope):
            # Boundary: caller asked for a (harness, kind) pair that has no
            # slot at this scope. Silent-skip is wrong (#30) but non-MCP
            # kinds reach here from a discovery loop, not user input — we
            # honour the filter rather than raise. Direct entrypoints
            # (maybe_link) raise. Per-scope check (#49) lets us cleanly skip
            # pairs like (pi, agent) at project scope where the user-scope
            # entry exists but the project-scope one doesn't.
            continue
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if target_dir is None:
            raise RuntimeError(
                f"is_supported({harness!r}, {kind!r}, scope={scope!r}) is True"
                f" but harness_target_dir returned None — SSOT invariant broken"
            )
```

- [ ] **Step 2: Update `unlink._do_all` filter**

In `src/agent_toolkit_cli/commands/unlink.py`, find line 160 inside `_do_all`:

```python
    for kind in KINDS_FOR_PROJECTION:
        if not is_supported(harness, kind):
            continue
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if not target_dir.is_dir():
            continue
```

Change `is_supported(harness, kind)` to `is_supported(harness, kind, scope=scope)`. The body and `target_dir` handling are unchanged.

```python
    for kind in KINDS_FOR_PROJECTION:
        if not is_supported(harness, kind, scope=scope):
            continue
        target_dir = harness_target_dir(harness, kind, scope, project_root)
        if not target_dir.is_dir():
            continue
```

- [ ] **Step 3: Run the new pinning test — should PASS now**

Run: `uv run pytest tests/test_link_lib.py::test_project_from_file_skips_pi_agent_at_project_scope_cleanly -v`

Expected: PASS.

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -q`

Expected: 545+ tests, all PASS. (We've added 5 new tests in Task 1 + 1 in Task 5 = 6 new; baseline was 544 → 550.)

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py src/agent_toolkit_cli/commands/unlink.py
git commit -m "fix(#49): linker iteration uses per-scope is_supported"
```

---

### Task 7: Verify list/TUI cell rendering — acceptance #7

**Files:**
- Modify: `tests/test_list_json.py` (if missing the case) or add a new test file

- [ ] **Step 1: Locate or add a test pinning the (pi, agent) project-scope cell**

Run: `grep -n "pi.*agent\|unsupported" tests/test_list_json.py 2>/dev/null || echo "no test file"`

If `tests/test_list_json.py` does not have a case asserting `(pi, agent)` at project scope renders `unsupported`, add one. The `_cell_status` function already returns `("unsupported", None)` when `_slot_dir` returns `None` — this test pins that behaviour for our specific pair.

If the file exists, append:

```python
def test_cell_status_pi_agent_project_scope_is_unsupported(tmp_path):
    """Acceptance #7: the (pi, agent) project-scope cell reports 'unsupported'
    after _PROJECT_TARGETS row removal (#49)."""
    from agent_toolkit_cli.commands._list_json import _cell_status

    status, target = _cell_status(
        harness="pi",
        kind="agent",
        slug="any-slug",
        scope="project",
        expected_src=tmp_path / "ignored",
        toolkit_root_resolved=tmp_path / "ignored-toolkit",
        project_root=tmp_path,
    )
    assert status == "unsupported"
    assert target is None
```

If the file does not exist, create `tests/test_list_json.py` with this single test plus the required `from __future__ import annotations` / module docstring.

- [ ] **Step 2: Run the new test**

Run: `uv run pytest tests/test_list_json.py::test_cell_status_pi_agent_project_scope_is_unsupported -v`

Expected: PASS — the existing `slot is None → ("unsupported", None)` branch handles the case for free.

- [ ] **Step 3: Commit**

```bash
git add tests/test_list_json.py
git commit -m "test(#49): pin pi/agent project-scope cell renders 'unsupported'"
```

---

### Task 8: Update the test_link_lib docstring referencing the old guard

**Files:**
- Modify: `tests/test_link_lib.py:240-294` (the existing `test_project_from_file_skips_unsupported_kinds_silently` test)

- [ ] **Step 1: Update the docstring to reflect the per-scope variant**

The existing test pins the `(codex, agent)` case — codex has no agent slot at *any* scope, so behaviour is unchanged after Task 6, but the rationale in the docstring still references the old single-scope filter. Update it:

In `tests/test_link_lib.py`, find the docstring block of `test_project_from_file_skips_unsupported_kinds_silently` (lines 244-249 in the current file). Replace:

```python
    """project_from_file iterates only supported kinds for the given harness.

    Pin: an agent asset declaring `codex` is allow-listed; running
    project_from_file with harness=codex must NOT touch it (codex/agent
    is unsupported). Removing the is_supported filter would surface the
    pair to harness_target_dir → None → RuntimeError; the filter is the
    only reason this test passes silently.
    """
```

with:

```python
    """project_from_file iterates only supported kinds for the given (harness, scope).

    Pin: an agent asset declaring `codex` is allow-listed; running
    project_from_file with harness=codex must NOT touch it (codex/agent
    is unsupported at every scope). Removing the per-scope is_supported
    filter would surface the pair to harness_target_dir → None →
    RuntimeError; the filter is the only reason this test passes silently.
    """
```

Also update the comment block at lines 288-289:

```python
    # Filter is the line that prevents the loop from reaching
    # harness_target_dir(codex, agent) → None → RuntimeError.
```

becomes:

```python
    # The per-scope is_supported filter (#49) is the line that prevents the
    # loop from reaching harness_target_dir(codex, agent, ...) → None →
    # RuntimeError.
```

- [ ] **Step 2: Run that test — must still PASS**

Run: `uv run pytest tests/test_link_lib.py::test_project_from_file_skips_unsupported_kinds_silently -v`

Expected: PASS (no behavioural change for codex/agent — both `_USER_TARGETS` and `_PROJECT_TARGETS` lack the row, so per-scope and no-scope checks both return False).

- [ ] **Step 3: Commit**

```bash
git add tests/test_link_lib.py
git commit -m "docs(#49): update test_link_lib comment for per-scope filter"
```

---

### Task 9: Final verification — full suite + manual `agent-toolkit list pi`

**Files:**
- None modified — verification only

- [ ] **Step 1: Run the complete test suite**

Run: `uv run pytest -q`

Expected: 550 tests pass (544 baseline + 6 new).

- [ ] **Step 2: Manual smoke — list shows pi/agent project as unsupported**

Build a minimal JSON inventory and grep for the cell.

Run:

```bash
uv run agent-toolkit list pi --format=json 2>/dev/null | python -c "
import json, sys
inv = json.load(sys.stdin)
hits = [c for c in inv.get('cells', []) if c.get('harness')=='pi' and c.get('kind')=='agent' and c.get('scope')=='project']
print(f'pi/agent project cells: {len(hits)}')
for h in hits[:5]:
    print(f\"  {h['slug']:<20} status={h['status']}\")
print('all unsupported' if all(h['status']=='unsupported' for h in hits) else 'MIXED — investigate')
"
```

Expected: every pi/agent project cell shows `status=unsupported` (or no cells if no agent assets declare pi).

- [ ] **Step 3: Final commit (no-op safety net)**

If the manual smoke surfaced anything unexpected, fix and recommit. Otherwise nothing to commit — the smoke is for forensic reassurance only.

```bash
git status   # expect "nothing to commit, working tree clean"
```

---

## Self-Review Checklist

**Spec coverage:**
- Acceptance #1 (back-compat) → Task 1 Step 1 (`test_is_supported_back_compat_no_scope_for_pi_agent`).
- Acceptance #2 (user scope) → Task 1 Step 1 (`test_is_supported_user_scope_for_pi_agent_is_true`).
- Acceptance #3 (project scope) → Task 1 Step 1 + Task 4 (row removal makes it pass).
- Acceptance #4 (`slot_dir(...) → None`) → Task 1 Step 1 + Task 4.
- Acceptance #5 (linker pre-check, no RuntimeError) → Tasks 5 + 6.
- Acceptance #6 (subset, not equal) → Task 2.
- Acceptance #7 (list/TUI cell `unsupported`) → Task 7.

All seven acceptance criteria covered.

**Type & symbol consistency:**
- `is_supported(harness, kind, scope=...)` — same signature in Task 3 (definition) and Tasks 6, 8 (callers).
- `slot_dir`, `harness_target_dir` — same names everywhere.
- `_PROJECT_TARGETS`, `_USER_TARGETS`, `SUPPORTED_PAIRS` — all consistent with `_support.py` source.

**Placeholder scan:** no TBDs, no "implement later", every code step has actual code, every command has expected output. ✓
