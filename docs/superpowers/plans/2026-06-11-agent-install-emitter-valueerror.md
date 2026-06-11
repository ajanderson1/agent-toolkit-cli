# agent install: clean error for translate-emitter frontmatter failures — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Issue:** #370 · **Spec:** docs/superpowers/specs/2026-06-11-agent-install-emitter-valueerror-design.md

**Goal:** Translate-emitter data failures (missing/invalid frontmatter) surface as a clean Click error naming the harness and the key, instead of a raw `ValueError` traceback mid-fan-out.

**Architecture:** One seam change — `_TranslateAdapter.install` wraps the parse+emit step and re-raises `ValueError` as `InstallError` (the base class `install_cmd.py:143` already converts to `ClickException`). Emitters are untouched; their messages already name harness + key. No CLI change, no facade change.

**Tech Stack:** Python, pytest, CliRunner. Conventions from `tests/test_cli/test_agent_adapters/test_translate.py` (adapter level) and `tests/test_cli/test_cli_agent_group.py` (CLI level: `monkeypatch.setenv("HOME", str(tmp_path))`, `_seed_global_canonical`, `_write_global_lock`).

**Baseline note:** line numbers verified on main @ 7e503b0. Partial-install rollback is OUT of scope (spec §Decision).

---

### Task 1: Adapter seam — wrap emitter ValueError as InstallError

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/translate.py` (imports ~line 18; `_TranslateAdapter.install` ~lines 381-398)
- Modify (retype in place): `tests/test_cli/test_agent_adapters/test_translate.py:327-349`

- [x] **Step 1: Retype the two existing adapter tests to the new contract**

`test_translate.py` ALREADY covers both scenarios (critical-review finding):
`test_github_copilot_install_raises_when_description_missing` (line 327) and
`test_mistral_vibe_install_raises_on_invalid_safety` (line 338) assert
`pytest.raises(ValueError)`. Do NOT append duplicate tests — retype these two
in place to pin the #370 contract:

```python
def test_github_copilot_install_raises_when_description_missing(tmp_path):
    """github-copilot REQUIRES `description` in frontmatter; data-dependent
    emitter failures surface as InstallError at the adapter boundary (#370)
    so the CLI layer converts them to a clean ClickException."""
    content = tmp_path / "no-desc.md"
    content.write_text("---\nname: test-agent\n---\n\nBody.\n")
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("github-copilot")
    with pytest.raises(InstallError, match="description"):
        adapter.install("test-agent", content, scope="global", home=tmp_path)


def test_mistral_vibe_install_raises_on_invalid_safety(tmp_path):
    """mistral-vibe `safety` must be one of safe|neutral|destructive|yolo.
    Anything else surfaces as InstallError at the adapter boundary (#370)
    rather than a raw ValueError traceback mid-fan-out."""
    content = tmp_path / "bad-safety.md"
    content.write_text(
        "---\nname: test\ndescription: test\nsafety: tornado\n---\n\nBody.\n"
    )
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("mistral-vibe")
    with pytest.raises(InstallError, match="safety"):
        adapter.install("test", content, scope="global", home=tmp_path)
```

**Leave untouched** the adjacent `requires home=` test (~line 320): that one
asserts a *contract* ValueError from `_resolve_dest`, which runs BEFORE the
wrap added in Step 3 and must stay a ValueError.

- [x] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_translate.py -k "description_missing or invalid_safety" -v`
Expected: 2 FAILED on the unfixed baseline — the emitters still raise `ValueError`, which is not an `InstallError` (`InstallError` subclasses `RuntimeError`), so `pytest.raises(InstallError)` does not catch it and pytest reports the escaping ValueError. (The `InstallError` import succeeds on the baseline — `_install_core.py:28` already defines it; the red state is the wrong exception type, not an ImportError.)

- [x] **Step 3: Implement the wrap**

In `src/agent_toolkit_cli/agent_adapters/translate.py`, add to the imports block:

```python
from agent_toolkit_cli._install_core import InstallError
```

(No circularity: `translate.py` already imports from `agent_toolkit_cli.agent_adapters`, and `_install_core` is a leaf module.)

Then in `_TranslateAdapter.install`, replace:

```python
        raw = content_path.read_text()
        fm, body = _parse_frontmatter(raw)
        output = self._emitter(fm, body, slug)
```

with:

```python
        raw = content_path.read_text()
        try:
            fm, body = _parse_frontmatter(raw)
            output = self._emitter(fm, body, slug)
        except ValueError as exc:
            # Data-dependent translation failure (missing/invalid frontmatter).
            # Emitter messages already name the harness and key; InstallError
            # is what the CLI layer converts to a clean ClickException.
            raise InstallError(str(exc)) from exc
```

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_translate.py -v`
Expected: ALL PASS — the two retyped tests now catch `InstallError`, and the
rest of the translate suite (including the `requires home=` contract test) is
unaffected because the wrap covers only the parse+emit step.

- [x] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/agent_adapters/translate.py tests/test_cli/test_agent_adapters/test_translate.py
git commit -m "fix(agent): surface translate-emitter frontmatter failures as InstallError (#370)"
```

(Remember the `Device:` trailer per conventions — `git interpret-trailers` or the repo hook handles it; if committing manually add `Device: $(hostname -s)`.)

---

### Task 2: CLI regression — default fan-out over a frontmatter-less agent

**Files:**
- Test: `tests/test_cli/test_cli_agent_group.py`

- [x] **Step 1: Write the failing CLI regression test**

Append to `tests/test_cli/test_cli_agent_group.py` (reuses the module's existing helpers `_seed_global_canonical` / `_write_global_lock` and the autouse `_clean_env` fixture):

```python
# ---------------------------------------------------------------------------
# #370: default fan-out over frontmatter-less agent → clean error, no traceback
# ---------------------------------------------------------------------------


def test_default_fanout_missing_description_clean_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path, slug="no-fm")
    (canonical / "no-fm.md").write_text("Body only, no frontmatter.\n")
    _write_global_lock(tmp_path, slug="no-fm")

    r = CliRunner().invoke(main, ["agent", "install", "no-fm", "-g"])

    assert r.exit_code != 0
    # The failure must be a handled ClickException, not an escaped ValueError.
    assert not isinstance(r.exception, ValueError), (
        f"raw ValueError escaped the CLI layer:\n{r.output}"
    )
    # Clean message names the harness and the missing key, with no traceback.
    assert "github-copilot" in r.output
    assert "description" in r.output
    assert "Traceback" not in r.output, (
        f"raw Traceback leaked into output:\n{r.output}"
    )
```

- [x] **Step 2: Run it to verify it fails on current main**

Run: `uv run pytest tests/test_cli/test_cli_agent_group.py::test_default_fanout_missing_description_clean_error -v`
Expected on the unfixed baseline: FAIL — `r.exception` is the escaped `ValueError` and `r.output` lacks the message. After Task 1 it must PASS; if executing tasks in order, verify the red state by running this test from a throwaway worktree of the pre-fix commit (`git worktree add .worktrees/370-baseline <pre-fix-sha>`), per the repo convention — do NOT `git stash` live edits to peek the baseline (recorded learning: a blocked stash pop has stranded work before). The red-green cycle is required, not optional.

- [x] **Step 3: Run the test to verify it passes with Task 1 applied**

Run: `uv run pytest tests/test_cli/test_cli_agent_group.py::test_default_fanout_missing_description_clean_error -v`
Expected: PASS

- [x] **Step 4: Full suite + commit**

Run: `uv run pytest -q`
Expected: green. Known local-only failure exempt per memory: `test_empty_machine_is_empty` (global pi inventory ignores `home=`); if it is the ONLY failure, proceed (it is green on CI).

```bash
git add tests/test_cli/test_cli_agent_group.py
git commit -m "test(agent): regression — default fan-out over frontmatter-less agent exits clean (#370)"
```

---

### Verification (whole-issue)

- [x] `uv run pytest -q` green (modulo the known local-only `test_empty_machine_is_empty`).
- [x] Manual smoke in a HOME-isolated sandbox: `agent add` a hermetic repo whose `demo-agent.md` has no frontmatter, then `agent install demo-agent -g` with no `--harnesses` → one-line `Error: github-copilot: 'description' is required in frontmatter but was not found`, exit 1, no traceback.
- [x] Note in the PR body that partially-written harness files before the failure remain on disk (out-of-scope follow-up: rollback or partial-set reporting).
