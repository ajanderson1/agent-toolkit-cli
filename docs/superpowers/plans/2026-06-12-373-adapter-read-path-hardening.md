# Adapter Read-Path Hardening Implementation Plan (#373)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every data-dependent canonical/registry read in the agent adapters surfaces as a clean `InstallError` naming the slug — never a raw traceback.

**Architecture:** Hybrid per the spec (`docs/superpowers/specs/2026-06-12-373-adapter-read-path-hardening-design.md`): adapters guard their own reads (`(ValueError, OSError)` → `InstallError`, harness-prefixed); the facade seam in `agent_install.py` catches **only** `InstallError` and re-raises `type(exc)(f"{slug}: {exc}")` so the slug is named once for every mechanism and the `AgentProjectionConflictError` subtype survives. Fail-loud preserved: unexpected exception classes still traceback.

**Tech Stack:** Python 3.12, pytest, Click's `CliRunner`. Run everything with `uv run pytest …` from the repo root.

**Verified baseline (main @ dba6d20):** translate has the F8 missing-canonical guard but reads above its try; aider-desk/dexto/firebender/codex reads fully unguarded; firebender/codex are catalog-disabled (`subagent_mechanism: none`) so their tests construct adapters directly via `config_file_folder.adapter_for(...)`.

---

### Task 1: translate — read inside the wrap, slug out of the F8 messages

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/translate.py:396-409` (install(): F8 guard + read + try block)
- Modify: `src/agent_toolkit_cli/agent_adapters/standard.py:73` (F8 message slug-drop)
- Modify: `src/agent_toolkit_cli/agent_adapters/symlink.py:150` (F8 message slug-drop)
- Test: `tests/test_cli/test_agent_adapters/test_translate.py`

- [x] **Step 1: Write the failing test** (append near `test_install_missing_canonical_raises_install_error`):

```python
def test_install_non_utf8_canonical_raises_install_error(tmp_path):
    """#373 (gap 1): a non-UTF8 canonical must surface as InstallError,
    not a raw UnicodeDecodeError traceback (the read used to sit one line
    above the #370 wrap)."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("gemini-cli")
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True)
    content.write_bytes(b"---\nname: x\n---\n\xff\xfe invalid utf8")
    with pytest.raises(InstallError):
        adapter.install("test-agent", content, scope="global", home=tmp_path)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_translate.py::test_install_non_utf8_canonical_raises_install_error -v`
Expected: FAIL with `UnicodeDecodeError` (not `InstallError`).

- [x] **Step 3: Implement.** In `translate.py` `install()`, replace this block:

```python
        if not content_path.exists():
            raise InstallError(
                f"{self.harness}: {slug}: canonical content file missing: "
                f"{content_path} — re-run `agent add {slug}` to restore it"
            )
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

with (slug dropped from the F8 message — the facade seam adds it in Task 4;
read moved inside the try; except widened to catch `UnicodeDecodeError`
(a `ValueError` subclass) and environment failures like `PermissionError`):

```python
        if not content_path.exists():
            raise InstallError(
                f"{self.harness}: canonical content file missing: "
                f"{content_path} — re-run `agent add {slug}` to restore it"
            )
        try:
            raw = content_path.read_text()
            fm, body = _parse_frontmatter(raw)
            output = self._emitter(fm, body, slug)
        except (ValueError, OSError) as exc:
            # Data/environment-dependent translation failure (non-UTF8 or
            # unreadable canonical, missing/invalid frontmatter). Emitter
            # messages already name the harness and key; the facade seam
            # prefixes the slug; InstallError is what the CLI layer converts
            # to a clean ClickException.
            raise InstallError(str(exc)) from exc
```

- [x] **Step 4: Drop the slug from the standard + symlink F8 messages too.**
The Task-4 seam prefixes the slug for EVERY mechanism; these two adapters
carry the same `{slug}:`-embedding F8 message and would print it doubled
(`my-agent: standard: my-agent: canonical…`) — and standard is the default
fan-out's first adapter, so this is the most common path. The existing
tests (`test_symlink.py`, `test_translate.py`) match only the
`"canonical content file missing"` suffix, so this is test-safe.

In `src/agent_toolkit_cli/agent_adapters/standard.py:73`, change:

```python
                f"standard: {slug}: canonical content file missing: "
```
to:
```python
                f"standard: canonical content file missing: "
```

In `src/agent_toolkit_cli/agent_adapters/symlink.py:150`, change:

```python
                f"{self.harness}: {slug}: canonical content file missing: "
```
to:
```python
                f"{self.harness}: canonical content file missing: "
```

(Both keep the trailing ``re-run `agent add {slug}` to restore it`` hint.)

- [x] **Step 5: Run the adapter test files**

Run: `uv run pytest tests/test_cli/test_agent_adapters/ -v`
Expected: ALL PASS (the existing F8 tests match on `"canonical content file missing"`, which survives the message change).

- [x] **Step 6: Commit**

```bash
git commit --only tests/test_cli/test_agent_adapters/test_translate.py --only src/agent_toolkit_cli/agent_adapters/translate.py --only src/agent_toolkit_cli/agent_adapters/standard.py --only src/agent_toolkit_cli/agent_adapters/symlink.py -m "fix(agent): translate canonical read inside the InstallError wrap (#373)"
```

---

### Task 2: config_file_folder — shared guarded canonical read for all 4 adapters

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/config_file_folder.py` (new helper + 4 install() call sites)
- Test: `tests/test_cli/test_agent_adapters/test_config_file_folder.py`

- [x] **Step 1: Write the failing tests** (append to `test_config_file_folder.py`; module already imports `pytest` and `Path`):

```python
# ---------------------------------------------------------------------------
# #373: guarded canonical reads — InstallError, never a raw traceback
# ---------------------------------------------------------------------------

CFF_HARNESSES = ["aider-desk", "codex", "dexto", "firebender"]


@pytest.mark.parametrize("harness", CFF_HARNESSES)
def test_install_missing_canonical_raises_install_error(harness, tmp_path):
    """#373: missing canonical → InstallError (translate F8 parity), not
    FileNotFoundError. firebender/codex are catalog-disabled, so construct
    the adapter directly."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for(harness)
    missing = tmp_path / "canonical" / "test-agent.md"
    with pytest.raises(InstallError, match="canonical content file missing"):
        adapter.install("test-agent", missing, scope="global", home=tmp_path)


@pytest.mark.parametrize("harness", CFF_HARNESSES)
def test_install_non_utf8_canonical_raises_install_error(harness, tmp_path):
    """#373: non-UTF8 canonical → InstallError, not UnicodeDecodeError."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for(harness)
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True)
    content.write_bytes(b"\xff\xfe invalid utf8")
    with pytest.raises(InstallError):
        adapter.install("test-agent", content, scope="global", home=tmp_path)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_config_file_folder.py -k "test_install_missing_canonical or test_install_non_utf8" -v`
Expected: 8 FAIL — `FileNotFoundError` / `UnicodeDecodeError` escape raw.

- [x] **Step 3: Implement.** In `config_file_folder.py`:

(a) Add the import (after the existing `_guard_foreign` import; translate.py
already imports from `_install_core`, so no circularity):

```python
from agent_toolkit_cli._install_core import InstallError
```

(b) Add the helper below `_check_scope`:

```python
def _read_canonical(harness: str, slug: str, content_path: Path) -> str:
    """Read the canonical agent file, fail-louding as InstallError.

    Missing file and unreadable/non-UTF8 content are data/environment-
    dependent failures the CLI must surface cleanly (#373; translate F8
    parity). The message names the harness; the facade seam prefixes the
    slug."""
    if not content_path.exists():
        raise InstallError(
            f"{harness}: canonical content file missing: "
            f"{content_path} — re-run `agent add {slug}` to restore it"
        )
    try:
        return content_path.read_text()
    except (ValueError, OSError) as exc:
        raise InstallError(f"{harness}: {exc}") from exc
```

(c) Replace each adapter's raw canonical read in `install()`:
- aider-desk (`text = content_path.read_text()`, ~line 85) → `text = _read_canonical("aider-desk", slug, content_path)`
- dexto (`source_block = textwrap.indent(content_path.read_text().strip(), "  ")`, ~line 155) → `source_block = textwrap.indent(_read_canonical("dexto", slug, content_path).strip(), "  ")`
- firebender (`text = content_path.read_text()`, ~line 219) → `text = _read_canonical("firebender", slug, content_path)`
- codex (`source_text = content_path.read_text()`, ~line 317) → `source_text = _read_canonical("codex", slug, content_path)`

NOTE: do the read BEFORE each adapter's `_guard_foreign`/`mkdir` so a bad
canonical aborts before any directory is created. For aider-desk this means
moving the assignment above `_guard_foreign(cfg, ...)`; for dexto above
`_guard_foreign(yml, ...)`. (firebender/codex already guard a different
file first — moving the canonical read to the top of install() is correct
and harmless for all four.)

- [x] **Step 4: Run the cff test file**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_config_file_folder.py -v`
Expected: ALL PASS.

- [x] **Step 5: Commit**

```bash
git commit --only tests/test_cli/test_agent_adapters/test_config_file_folder.py --only src/agent_toolkit_cli/agent_adapters/config_file_folder.py -m "fix(agent): cff adapters guard canonical reads as InstallError (#373)"
```

---

### Task 3: firebender registry + codex config.toml reads

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/config_file_folder.py` (firebender install ~:233, firebender uninstall ~:270, codex install ~:327, codex uninstall ~:374)
- Test: `tests/test_cli/test_agent_adapters/test_config_file_folder.py`

- [x] **Step 1: Write the failing tests:**

```python
def _fb_content(tmp_path):
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text("---\nname: test-agent\n---\nbody\n")
    return content


def test_firebender_install_corrupt_registry_raises_install_error(tmp_path):
    """#373 (gap 4): corrupt firebender.json at install → InstallError,
    not a raw JSONDecodeError traceback."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    fb_dir = tmp_path / ".firebender"
    fb_dir.mkdir()
    (fb_dir / "firebender.json").write_text("{not json")
    with pytest.raises(InstallError, match="firebender"):
        adapter.install("test-agent", _fb_content(tmp_path),
                        scope="global", home=tmp_path)


def test_firebender_uninstall_corrupt_registry_raises_install_error(tmp_path):
    """#373 (gap 4): corrupt firebender.json at uninstall → InstallError."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    adapter.install("test-agent", _fb_content(tmp_path),
                    scope="global", home=tmp_path)
    (tmp_path / ".firebender" / "firebender.json").write_text("{not json")
    with pytest.raises(InstallError, match="firebender"):
        adapter.uninstall("test-agent", scope="global", home=tmp_path)


def test_codex_uninstall_corrupt_config_raises_install_error(tmp_path):
    """#373 (gap 4): corrupt config.toml at codex uninstall → InstallError
    (mirrors the firebender uninstall coverage)."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("codex")
    adapter.install("test-agent", _fb_content(tmp_path),
                    scope="global", home=tmp_path)
    # Make the read raise: read_text on a non-UTF8 config.toml.
    (tmp_path / ".codex" / "config.toml").write_bytes(b"\xff\xfe not utf8")
    with pytest.raises(InstallError, match="codex"):
        adapter.uninstall("test-agent", scope="global", home=tmp_path)
```

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_config_file_folder.py -k "corrupt_registry or corrupt_config" -v`
Expected: 3 FAIL with raw `json.decoder.JSONDecodeError` / `UnicodeDecodeError`.

- [x] **Step 3: Implement.** In `config_file_folder.py`, wrap the three
registry/config reads (JSONDecodeError is a ValueError subclass):

firebender `install()` — replace:

```python
        if fb_json.exists():
            body = json.loads(fb_json.read_text())
        else:
            body = {"agents": []}
```

with:

```python
        if fb_json.exists():
            try:
                body = json.loads(fb_json.read_text())
            except (ValueError, OSError) as exc:
                raise InstallError(f"firebender: {fb_json}: {exc}") from exc
        else:
            body = {"agents": []}
```

firebender `uninstall()` — replace:

```python
        if fb_json.exists():
            body = json.loads(fb_json.read_text())
```

with:

```python
        if fb_json.exists():
            try:
                body = json.loads(fb_json.read_text())
            except (ValueError, OSError) as exc:
                raise InstallError(f"firebender: {fb_json}: {exc}") from exc
```

codex `install()` — replace:

```python
        if config_toml.exists():
            existing = config_toml.read_text()
        else:
            existing = ""
```

with:

```python
        if config_toml.exists():
            try:
                existing = config_toml.read_text()
            except (ValueError, OSError) as exc:
                raise InstallError(f"codex: {config_toml}: {exc}") from exc
        else:
            existing = ""
```

codex `uninstall()` (~:374) — uninstall must not raw-traceback either; replace:

```python
        if config_toml.exists():
            existing = config_toml.read_text()
```

with:

```python
        if config_toml.exists():
            try:
                existing = config_toml.read_text()
            except (ValueError, OSError) as exc:
                raise InstallError(f"codex: {config_toml}: {exc}") from exc
```

- [x] **Step 4: Run the cff test file**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_config_file_folder.py -v`
Expected: ALL PASS.

- [x] **Step 5: Commit**

```bash
git commit --only tests/test_cli/test_agent_adapters/test_config_file_folder.py --only src/agent_toolkit_cli/agent_adapters/config_file_folder.py -m "fix(agent): firebender/codex registry reads guard as InstallError (#373)"
```

---

### Task 4: facade-seam slug enrichment (apply + uninstall) and CLI conversion

**Files:**
- Modify: `src/agent_toolkit_cli/agent_install.py:311` (apply() install loop), `:336` (apply() remove loop), `uninstall()` adapter loop (~:485)
- Modify: `src/agent_toolkit_cli/commands/agent/uninstall_cmd.py` (wrap the `agent_install.uninstall(...)` call)
- Test: `tests/test_cli/test_agent_install.py` (seam tests); `tests/test_cli/test_cli_agent_group.py` (CLI assertion)

- [x] **Step 1: Write the failing seam tests** (append to `tests/test_cli/test_agent_install.py`; follow that file's existing fixture style for plan construction — it already builds `InstallPlan` objects and calls `agent_install.apply`):

```python
def test_apply_install_error_names_slug(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """#373 (gap 2): an adapter InstallError surfaces through apply() with
    the slug prefixed exactly once."""
    import pytest
    from agent_toolkit_cli import agent_install
    from agent_toolkit_cli._install_core import InstallError, InstallPlan
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    # canonical_agent_dir IGNORES home= at global scope (resolves via
    # Path.home()) — without this the test writes to the REAL home dir.
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = canonical_agent_dir("my-agent", scope="global", home=tmp_path)
    canonical.mkdir(parents=True)
    # No description → the github-copilot emitter raises (the #370 path).
    (canonical / "my-agent.md").write_text("Body only, no frontmatter.\n")

    plan = InstallPlan(
        slug="my-agent", scope="global", source=None, ref=None,
        add_agents=("github-copilot",), remove_agents=(),
    )
    with pytest.raises(InstallError, match=r"^my-agent: github-copilot"):
        agent_install.apply(plan, home=tmp_path, project=None)


def test_apply_conflict_error_keeps_subtype_through_seam(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """#373: the seam's slug enrichment must preserve
    AgentProjectionConflictError (the existing #368 G5 pin asserts the
    subtype through apply())."""
    import pytest
    from agent_toolkit_cli import agent_install
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_adapters import (
        AgentProjectionConflictError, translate,
    )
    from agent_toolkit_cli.agent_paths import canonical_agent_dir

    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = canonical_agent_dir("my-agent", scope="global", home=tmp_path)
    canonical.mkdir(parents=True)
    (canonical / "my-agent.md").write_text(
        "---\nname: my-agent\ndescription: d\n---\nbody\n"
    )
    # Plant a divergent foreign file at the gemini-cli destination.
    dest = translate.adapter_for("gemini-cli").destination(
        "my-agent", scope="global", home=tmp_path,
    )
    dest.parent.mkdir(parents=True)
    dest.write_text("# user-authored\n")

    plan = InstallPlan(
        slug="my-agent", scope="global", source=None, ref=None,
        add_agents=("gemini-cli",), remove_agents=(),
    )
    with pytest.raises(AgentProjectionConflictError, match=r"^my-agent: "):
        agent_install.apply(plan, home=tmp_path, project=None)
```

NOTE for the implementer: if `InstallPlan` requires other kwargs, copy the
construction shape from the existing tests in `test_agent_install.py` —
the assertion contract (slug prefix + subtype) is what matters.

- [x] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_install.py -k "names_slug or keeps_subtype" -v`
Expected: 2 FAIL — message lacks the `my-agent: ` prefix.

- [x] **Step 3: Implement the seam.** In `agent_install.py` `apply()`, wrap the install call (`:311`):

```python
        try:
            out = adapter.install(
                plan.slug, content_path,
                scope=plan.scope, home=home, project=project,
                overwrite=overwrite,
            )
        except InstallError as exc:
            # #373: name the failing slug exactly once, for every mechanism.
            # type(exc) keeps AgentProjectionConflictError discriminable.
            raise type(exc)(f"{plan.slug}: {exc}") from exc
        created.append(out)
```

and the remove call (`:336`):

```python
        try:
            adapter.uninstall(
                plan.slug,
                scope=plan.scope, home=home, project=project,
                canonical_content=content_path,
            )
        except InstallError as exc:
            raise type(exc)(f"{plan.slug}: {exc}") from exc
```

In `agent_install.uninstall()` (the direct loop the CLI uses), apply the same
wrap around its `adapter.uninstall(...)` call. NOTE: that loop already has
exception handling around the adapter call (an existing
`except ValueError: continue`) — INTEGRATE the new `except InstallError`
clause into the existing try (InstallError is not a ValueError, so the
clauses are disjoint; order them InstallError-first for clarity). Do not
paste a nested try.

In `commands/agent/uninstall_cmd.py`, import `InstallError` from
`agent_toolkit_cli._install_core` and wrap the `agent_install.uninstall(...)`
call exactly as `install_cmd.py:162-164` does:

```python
    try:
        refusals = agent_install.uninstall(
            slug=slug, scope=scope, home=effective_home, project=project,
            harnesses=target_harnesses,
        )
    except InstallError as exc:
        raise click.ClickException(str(exc)) from exc
```

(Adjust to the actual call shape in the file — only the try/except is new;
keep whatever the result variable is currently named.)

- [x] **Step 4: Write the CLI regression test** (it was RED before Step 3 and
passes on the Step-3 tree — do NOT expect to prove RED here; the seam tests
in Steps 1–2 carried the RED proof). Append to
`tests/test_cli/test_cli_agent_group.py`, next to
`test_default_fanout_missing_description_clean_error`, reusing its helpers:

```python
def test_install_error_output_names_slug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#373 (gap 2): the clean CLI error names WHICH agent failed."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path, slug="no-fm")
    (canonical / "no-fm.md").write_text("Body only, no frontmatter.\n")
    _write_global_lock(tmp_path, slug="no-fm")

    r = CliRunner().invoke(main, ["agent", "install", "no-fm", "-g"])

    assert r.exit_code != 0
    assert "no-fm" in r.output, f"slug missing from error:\n{r.output}"
    assert "Traceback" not in r.output
```

- [x] **Step 5: Run the touched test files**

Run: `uv run pytest tests/test_cli/test_agent_install.py tests/test_cli/test_cli_agent_group.py -v`
Expected: ALL PASS (incl. the existing #370 test — its `github-copilot`/`description` assertions still hold with the slug prefix added).

- [x] **Step 6: Commit**

```bash
git commit --only tests/test_cli/test_agent_install.py --only tests/test_cli/test_cli_agent_group.py --only src/agent_toolkit_cli/agent_install.py --only src/agent_toolkit_cli/commands/agent/uninstall_cmd.py -m "fix(agent): facade seam prefixes the slug on InstallError, uninstall CLI converts cleanly (#373)"
```

---

### Task 5: gap-3 regression test — failed fan-out retries cleanly (pins #368)

**Files:**
- Test: `tests/test_cli/test_cli_agent_group.py`

- [x] **Step 1: Write the test** (this should pass on the Task-4 tree — it pins behavior #368 already ships; if it FAILS, stop and raise, because the retry wedge is back):

```python
def test_failed_fanout_retry_succeeds_after_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#373 (gap 3, dissolved by #368): a fan-out that fails on one harness
    leaves sentineled projections behind; fixing the canonical and re-running
    must succeed — no AgentProjectionConflictError on our own leftovers."""
    monkeypatch.setenv("HOME", str(tmp_path))
    canonical = _seed_global_canonical(tmp_path, slug="retry-agent")
    # gemini-cli succeeds without a description; github-copilot requires one
    # and fails AFTER gemini-cli's file is already on disk.
    (canonical / "retry-agent.md").write_text(
        "---\nname: retry-agent\n---\nbody\n"
    )
    _write_global_lock(tmp_path, slug="retry-agent")

    r1 = CliRunner().invoke(
        main,
        ["agent", "install", "retry-agent", "-g",
         "--harnesses", "gemini-cli,github-copilot"],
    )
    assert r1.exit_code != 0
    assert "description" in r1.output

    # Fix the canonical, retry the same fan-out.
    (canonical / "retry-agent.md").write_text(
        "---\nname: retry-agent\ndescription: now valid\n---\nbody\n"
    )
    r2 = CliRunner().invoke(
        main,
        ["agent", "install", "retry-agent", "-g",
         "--harnesses", "gemini-cli,github-copilot"],
    )
    assert r2.exit_code == 0, f"retry wedged:\n{r2.output}"
```

NOTE: if the `--harnesses` token spelling differs (check `parse_harness_tokens`
in `commands/agent/_common.py`), use the catalog names exactly as
`AGENTS` keys them: `gemini-cli`, `github-copilot`.

- [x] **Step 2: Run it**

Run: `uv run pytest tests/test_cli/test_cli_agent_group.py::test_failed_fanout_retry_succeeds_after_fix -v`
Expected: PASS. (If FAIL with `AgentProjectionConflictError`: the #368 sentinel/adopt contract regressed — stop and raise, do not patch around it.)

- [x] **Step 3: Commit**

```bash
git commit --only tests/test_cli/test_cli_agent_group.py -m "test(agent): pin #368's dissolution of the failed-fan-out retry wedge (#373)"
```

---

### Task 6: full verification

- [x] **Step 1: Full suite**

Run: `uv run pytest -q`
Expected: everything green except (possibly) the 2 known HOME-isolation env failures (`test_empty_machine_is_empty`, `test_build_instruction_rows_empty_lock_no_canonical`) — both pre-existing on main; reproduce on a clean checkout before whitelisting anything else.

- [x] **Step 2: Lint/type checks**

Run: `uv run ruff check src tests && uv run mypy src`
Expected: no NEW errors versus main (main carries pre-existing counts; compare if non-zero).

- [x] **Step 3: CLI smoke** (sandbox HOME, no real installs):

```bash
HOME=$(mktemp -d) uv run agent-toolkit-cli agent install nonexistent -g 2>&1 | tail -3
```
Expected: clean one-line error (no traceback) — exact message depends on the lock-missing path, which precedes the adapter layer.
