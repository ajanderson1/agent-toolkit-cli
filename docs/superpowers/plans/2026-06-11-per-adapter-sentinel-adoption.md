# Per-Adapter Sentinel Adoption Implementation Plan (#368)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the standard adapter's ownership contract (sentinel on install, adopt-if-identical, sentinel-only overwrite authority, guarded uninstall with structured refusal) to the symlink and translate adapters, plus sentinel write+cleanup for codex/firebender; re-enable the doctor's cursor-shadow fix sentinel-gated.

**Architecture:** Per-destination `.{name}.attk` sidecars (existing `_sentinel_path` convention) become the sole clobber authority in symlink/translate — the facade's lock-derived `overwrite=` flag is ignored, exactly as `standard.py` does. The `AgentAdapter.uninstall` Protocol unifies on `canonical_content: Path | None = None` → `Path | None` (refusal), collapsing the facade's `name == "standard"` special-casing. Spec: `docs/superpowers/specs/2026-06-11-per-adapter-sentinel-adoption-design.md`.

**Tech Stack:** Python 3.11+, pytest, Click. Run tests with `uv run pytest`.

**Known environment caveat:** two HOME-isolation test failures are local-only and pre-existing (`test_empty_machine_is_empty`-family); they are NOT caused by this work. Pre-commit `--no-verify` is justified only when they are the sole failures.

**Conventions:** every commit message carries a `Device: $(hostname -s)` trailer. Work happens in a worktree branch per `git.md` (the runner creates it; commands below show `git add`/`git commit` only).

---

### Task 1: Symlink adapter — install-side ownership contract

The symlink adapter must: write the sidecar on install, adopt a byte-identical pre-existing file, ignore the facade `overwrite=` flag (sentinel-only authority), replace (never write through) a symlink at the destination, and fail loud on a missing canonical.

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/symlink.py:132-146` (install)
- Test: `tests/test_cli/test_agent_adapters/test_symlink.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_agent_adapters/test_symlink.py` (the file already has `fake_content` and `_expand` fixtures/helpers; `SYMLINK_CELLS` rows are `(harness, global_tpl, project_tpl)`):

```python
# ── #368: install-side ownership contract ────────────────────────────────

@pytest.mark.parametrize("harness, global_tpl, project_tpl", SYMLINK_CELLS)
def test_install_writes_sentinel(harness, global_tpl, project_tpl, tmp_path, fake_content):
    """#368: every symlink-cell install writes the .attk ownership sidecar."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, symlink
    adapter = symlink.adapter_for(harness)
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert _sentinel_path(dest).exists(), f"{harness}: no sentinel beside {dest}"


def test_install_adopts_identical_sentinel_less_file(tmp_path, fake_content):
    """#368 (F3): a pre-existing byte-identical file is adopted — sentinel
    written, no error, file untouched."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, symlink
    adapter = symlink.adapter_for("cursor")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text(fake_content.read_text())  # identical, no sentinel
    out = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert out == dest
    assert _sentinel_path(dest).exists()


def test_install_ignores_facade_overwrite_flag(tmp_path, fake_content):
    """#368 (G5, waived from #362): a divergent sentinel-less file at the
    destination refuses install EVEN WITH overwrite=True — lock-derived
    per-slug ownership must not clobber a user file at a destination the
    tool never projected."""
    from agent_toolkit_cli.agent_adapters import AgentProjectionConflictError, symlink
    adapter = symlink.adapter_for("cursor")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("# user-authored, divergent\n")
    with pytest.raises(AgentProjectionConflictError):
        adapter.install("test-agent", fake_content, scope="global",
                        home=tmp_path, overwrite=True)
    assert dest.read_text() == "# user-authored, divergent\n"  # untouched


def test_install_with_sentinel_overwrites_divergent_file(tmp_path, fake_content):
    """#368: the sentinel authorizes refreshing our own (even drifted) file."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, symlink
    adapter = symlink.adapter_for("cursor")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("stale projection\n")
    _sentinel_path(dest).write_text("")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert dest.read_text() == fake_content.read_text()


def test_install_replaces_symlink_at_destination(tmp_path, fake_content):
    """#368 (F6 parity): a symlink at the destination is REPLACED — copy2
    through it would write into its target."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, symlink
    adapter = symlink.adapter_for("cursor")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    target = tmp_path / "users-dotfile.md"
    target.write_text("user dotfile source\n")
    dest.symlink_to(target)
    _sentinel_path(dest).write_text("")  # stale sentinel scenario
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert not dest.is_symlink()
    assert dest.read_text() == fake_content.read_text()
    assert target.read_text() == "user dotfile source\n"  # NOT written through


def test_install_missing_canonical_raises_install_error(tmp_path):
    """#368 (F8 parity): a missing canonical content file raises InstallError,
    not a raw OSError from filecmp/copy2."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("cursor")
    missing = tmp_path / "canonical" / "test-agent.md"
    with pytest.raises(InstallError, match="canonical content file missing"):
        adapter.install("test-agent", missing, scope="global", home=tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_symlink.py -v -k "sentinel or adopts or overwrite or replaces or missing_canonical"`
Expected: the 6 new test groups FAIL (no sentinel written; conflict not raised with overwrite=True; InstallError not raised). Pre-existing tests still PASS.

- [ ] **Step 3: Implement install**

In `src/agent_toolkit_cli/agent_adapters/symlink.py`: add `import filecmp` and `from agent_toolkit_cli._install_core import InstallError` to the imports, then replace the `install` method body:

```python
    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        # Fail loud on a missing canonical content file (standard-adapter F8
        # parity) BEFORE filecmp/copy2 raises a raw OSError mid-fan-out.
        if not content_path.exists():
            raise InstallError(
                f"{self.harness}: {slug}: canonical content file missing: "
                f"{content_path} — re-run `agent add {slug}` to restore it"
            )
        # Adopt-if-identical (#368): a pre-existing byte-identical file (e.g.
        # a pre-sentinel install by this tool) becomes tool-owned.
        if dest.exists() and not dest.is_symlink() and filecmp.cmp(
            content_path, dest, shallow=False,
        ):
            _sentinel_path(dest).write_text("")
            return dest
        # Ownership = SENTINEL, not lock (#368, standard-adapter parity): the
        # facade passes overwrite=True for any locked slug, but a lock entry
        # is per-slug, not per-destination — it is not evidence we own THIS
        # file (G5 harness-expansion clobber, waived from #362 to #368).
        _guard_foreign(dest, harness=self.harness, overwrite=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # A symlink at the slot must be REPLACED, never written through —
        # copy2 over a symlink would write into its target (F6 parity).
        if dest.is_symlink():
            dest.unlink()
        shutil.copy2(content_path, dest)
        _sentinel_path(dest).write_text("")
        return dest
```

- [ ] **Step 4: Run the adapter test file**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_symlink.py -v`
Expected: all PASS. (`test_symlink_uninstall_idempotent` still passes: uninstall already removes the sentinel via the #366 cleanup.)

- [ ] **Step 5: Flip the now-false doctor-test premise**

`tests/test_cli/test_agent_doctor.py::test_doctor_cursor_shadow_via_real_adapter_is_report_only` (line ~391) asserts the real cursor adapter writes NO sentinel:

```python
    assert not _sentinel_path(cursor_dest).exists(), (
        "premise: the real cursor adapter writes no ownership sentinel"
    )
```

That premise is false as of this task. Flip it now (the rest of the test — `fix_action is None`, exit-0 — stays TRUE until Task 8 adds the sentinel-gated fix, which then updates this test again):

```python
    assert _sentinel_path(cursor_dest).exists(), (
        "premise (#368): the real cursor adapter writes the ownership sentinel"
    )
```

- [ ] **Step 6: Run the facade + CLI agent suites for collateral**

Run: `uv run pytest tests/test_cli/ -q -k "agent"`
(No `-x`: let the full collateral surface.) Expected: PASS. If a facade test relied on lock-flag-authorized clobber of a divergent sentinel-less file, STOP and re-read it — the G5 semantics change is intentional; update that test's expectation to `AgentProjectionConflictError` only if it manufactures a foreign file (not a tool projection).

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/agent_adapters/symlink.py tests/test_cli/test_agent_adapters/test_symlink.py tests/test_cli/test_agent_doctor.py
git commit -m "feat(agent): symlink adapter writes ownership sidecars, sentinel-only overwrite

Adopt-if-identical + ignore the lock-derived overwrite flag (G5 expansion-
clobber fix waived from #362) + F6/F8 parity with the standard adapter.

Refs #368

Device: $(hostname -s)"
```

---

### Task 2: Symlink adapter — guarded uninstall with structured refusal

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/symlink.py:148-164` (uninstall)
- Test: `tests/test_cli/test_agent_adapters/test_symlink.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_agent_adapters/test_symlink.py`:

```python
# ── #368: guarded uninstall ──────────────────────────────────────────────

def test_uninstall_with_sentinel_removes_even_if_edited(tmp_path, fake_content):
    """Sentinel present → we own the path; remove even a user-edited copy."""
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("cursor")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    dest.write_text("user edited this projection\n")
    refused = adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert refused is None
    assert not dest.exists()


def test_uninstall_content_match_detaches_sentinel_less_file(tmp_path, fake_content):
    """#368 migration: a pre-sentinel projection byte-matching the canonical
    is detached via canonical_content (content-match detach)."""
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("cursor")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text(fake_content.read_text())  # no sentinel
    refused = adapter.uninstall(
        "test-agent", scope="global", home=tmp_path,
        canonical_content=fake_content,
    )
    assert refused is None
    assert not dest.exists()


def test_uninstall_refuses_foreign_file(tmp_path, fake_content, capsys):
    """Sentinel-less + divergent = the user's file: leave it, return the
    path (structured refusal), say so on stderr."""
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("cursor")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("# hand-authored\n")
    refused = adapter.uninstall(
        "test-agent", scope="global", home=tmp_path,
        canonical_content=fake_content,
    )
    assert refused == dest
    assert dest.exists()
    assert "left in place" in capsys.readouterr().err


def test_uninstall_without_canonical_content_still_guarded(tmp_path, fake_content):
    """canonical_content=None (default) → only the sentinel authorizes."""
    from agent_toolkit_cli.agent_adapters import symlink
    adapter = symlink.adapter_for("cursor")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("# hand-authored\n")
    refused = adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert refused == dest
    assert dest.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_symlink.py -v -k "uninstall"`
Expected: the new tests FAIL (`canonical_content` is an unexpected kwarg; foreign file deleted instead of refused). `test_symlink_uninstall_idempotent` and `test_symlink_uninstall_removes_orphan_sentinel` may also fail at this point — see Step 3 note.

- [ ] **Step 3: Implement guarded uninstall**

In `symlink.py`, add `import sys` to the imports and replace the `uninstall` method (mirror `standard.py:99-135`):

```python
    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        """Ownership-guarded detach (#368, standard-adapter parity): unlink
        only when the sentinel exists OR the file byte-matches
        `canonical_content` (covers pre-sentinel installs). A sentinel-less,
        content-divergent file is the user's — leave it, return its path as
        a structured refusal. The sidecar is removed whenever the file is
        gone (orphan hygiene, #361/#366)."""
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        sentinel = _sentinel_path(dest)
        refused: Path | None = None
        if dest.exists() or dest.is_symlink():
            owned = sentinel.exists() or (
                canonical_content is not None
                and canonical_content.exists()
                and not dest.is_symlink()
                and filecmp.cmp(canonical_content, dest, shallow=False)
            )
            if owned:
                dest.unlink()
            else:
                refused = dest
                print(
                    f"{self.harness}: {dest} not managed by this tool "
                    f"(no sentinel, content differs) — left in place",
                    file=sys.stderr,
                )
        if sentinel.exists() and not dest.exists():
            sentinel.unlink()
        return refused
```

NOTE: `test_symlink_uninstall_idempotent` installs via the adapter (which now writes a sentinel) so its uninstall stays authorized — it must keep passing unchanged. `test_symlink_uninstall_removes_orphan_sentinel` hand-writes a sentinel after install, so the file is owned and removed, then the sentinel is cleaned — also unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_symlink.py -v`
Expected: all PASS.

- [ ] **Step 5: Check direct callers still typecheck/pass**

Run: `uv run pytest tests/test_cli/ -q -k "agent" && uv run mypy src/agent_toolkit_cli/agent_adapters/symlink.py`
Expected: tests PASS; mypy reports no NEW errors in this file (repo has pre-existing errors elsewhere — compare against `main` if unsure).

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/agent_adapters/symlink.py tests/test_cli/test_agent_adapters/test_symlink.py
git commit -m "feat(agent): symlink adapter uninstall is ownership-guarded with structured refusal

Sentinel-or-content-match detach; foreign files left in place and returned
as refusals (standard-adapter F5 shape).

Refs #368

Device: $(hostname -s)"
```

---

### Task 3: Translate adapter — install-side ownership contract

Same contract as Task 1, except "identical" means **emission-identical**: compare the destination text against the emitter's output over the parsed canonical.

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/translate.py:382-405` (install)
- Test: `tests/test_cli/test_agent_adapters/test_translate.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_agent_adapters/test_translate.py` (the file already has the rich `fake_content` fixture and `_clean_xdg_env` autouse fixture):

```python
# ── #368: install-side ownership contract ────────────────────────────────

# All 10 translate cells; gemini-cli exercises the strict filter, codex the
# TOML emitter, kiro-cli the JSON emitter — the sentinel must appear for all.
TRANSLATE_HARNESSES = [
    "codex", "devin", "gemini-cli", "github-copilot", "kilo",
    "kiro-cli", "mistral-vibe", "mux", "opencode", "qwen-code",
]


@pytest.mark.parametrize("harness", TRANSLATE_HARNESSES)
def test_install_writes_sentinel(harness, tmp_path, fake_content):
    """#368: every translate-cell install writes the .attk ownership sidecar."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for(harness)
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert _sentinel_path(dest).exists(), f"{harness}: no sentinel beside {dest}"


def test_install_adopts_emission_identical_file(tmp_path, fake_content):
    """#368 (F3): a pre-existing file matching the EMITTER OUTPUT (not the
    canonical bytes) is adopted — sentinel written, no error."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for("gemini-cli")
    # First install produces the emitted shape; strip the sentinel to fake
    # a pre-#368 projection.
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    _sentinel_path(dest).unlink()
    out = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert out == dest
    assert _sentinel_path(dest).exists()


def test_install_ignores_facade_overwrite_flag(tmp_path, fake_content):
    """#368 (G5): divergent sentinel-less file refuses even with overwrite=True."""
    from agent_toolkit_cli.agent_adapters import AgentProjectionConflictError, translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("# user-authored, divergent\n")
    with pytest.raises(AgentProjectionConflictError):
        adapter.install("test-agent", fake_content, scope="global",
                        home=tmp_path, overwrite=True)
    assert dest.read_text() == "# user-authored, divergent\n"


def test_install_with_sentinel_overwrites_divergent_file(tmp_path, fake_content):
    """#368: the sentinel authorizes refreshing our own drifted projection."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("stale projection\n")
    _sentinel_path(dest).write_text("")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert "name: test-agent" in dest.read_text()


def test_install_replaces_symlink_at_destination(tmp_path, fake_content):
    """#368 (F6 parity): write_text through a symlink would land in its target."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    target = tmp_path / "users-dotfile.md"
    target.write_text("user dotfile source\n")
    dest.symlink_to(target)
    _sentinel_path(dest).write_text("")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert not dest.is_symlink()
    assert target.read_text() == "user dotfile source\n"


def test_install_missing_canonical_raises_install_error(tmp_path):
    """#368 (F8 parity): missing canonical → InstallError, not raw OSError."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("gemini-cli")
    missing = tmp_path / "canonical" / "test-agent.md"
    with pytest.raises(InstallError, match="canonical content file missing"):
        adapter.install("test-agent", missing, scope="global", home=tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_translate.py -v -k "sentinel or adopts or overwrite or replaces or missing_canonical"`
Expected: new tests FAIL.

- [ ] **Step 3: Implement install**

In `translate.py`, replace the `install` method (the emit now happens BEFORE the guard so the adopt check can compare against it; an emitter `ValueError` still becomes `InstallError` exactly as today):

```python
    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        # Fail loud on a missing canonical content file (standard-adapter F8
        # parity) BEFORE read_text raises a raw OSError mid-fan-out.
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
        # Adopt-if-identical (#368): "identical" for translate means the file
        # matches what the emitter would write NOW (emission-identical) — the
        # destination never holds the canonical bytes. Compare BYTES, not
        # decoded text: a foreign non-UTF8 file at the destination must route
        # to the conflict branch below, not raise UnicodeDecodeError.
        if dest.exists() and not dest.is_symlink() and dest.read_bytes() == output.encode():
            _sentinel_path(dest).write_text("")
            return dest
        # Ownership = SENTINEL, not lock (#368, standard-adapter parity; G5).
        _guard_foreign(dest, harness=self.harness, overwrite=False)
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Replace, never write through, a symlink at the slot (F6 parity).
        if dest.is_symlink():
            dest.unlink()
        dest.write_text(output)
        _sentinel_path(dest).write_text("")
        return dest
```

Also add `from agent_toolkit_cli.agent_adapters import _guard_foreign, _sentinel_path` (the module currently imports only `_guard_foreign` at line 19).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_translate.py -v`
Expected: all PASS. The pre-existing per-cell emitter tests must pass unchanged — if one fails on the new `InstallError` for missing canonical, it was relying on a raw `FileNotFoundError`; update only its expected exception type.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/agent_adapters/translate.py tests/test_cli/test_agent_adapters/test_translate.py
git commit -m "feat(agent): translate adapter writes ownership sidecars, emission-identical adopt

Sentinel-only overwrite authority (G5) + F6/F8 parity; adopt compares
against the emitter output, not the canonical bytes.

Refs #368

Device: $(hostname -s)"
```

---

### Task 4: Translate adapter — guarded uninstall (re-emit compare, never crash)

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/translate.py:407-417` (uninstall)
- Test: `tests/test_cli/test_agent_adapters/test_translate.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_translate.py`:

```python
# ── #368: guarded uninstall ──────────────────────────────────────────────

def test_uninstall_with_sentinel_removes(tmp_path, fake_content):
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    refused = adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert refused is None
    assert not dest.exists()
    assert not _sentinel_path(dest).exists(), "orphaned .attk after uninstall"


def test_uninstall_emission_match_detaches_sentinel_less_file(tmp_path, fake_content):
    """#368 migration: a pre-sentinel projection matching the re-run emitter
    output is detached via canonical_content."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    _sentinel_path(dest).unlink()  # fake a pre-#368 projection
    refused = adapter.uninstall(
        "test-agent", scope="global", home=tmp_path,
        canonical_content=fake_content,
    )
    assert refused is None
    assert not dest.exists()


def test_uninstall_refuses_foreign_file(tmp_path, fake_content, capsys):
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("# hand-authored\n")
    refused = adapter.uninstall(
        "test-agent", scope="global", home=tmp_path,
        canonical_content=fake_content,
    )
    assert refused == dest
    assert dest.exists()
    assert "left in place" in capsys.readouterr().err


def test_uninstall_emitter_failure_treated_as_no_match(tmp_path):
    """#368: a canonical that no longer emits (e.g. github-copilot without
    description) must NOT crash uninstall — it just can't authorize, so a
    sentinel-less file is refused, not an exception."""
    from agent_toolkit_cli.agent_adapters import translate
    bad_canonical = tmp_path / "canonical" / "test-agent.md"
    bad_canonical.parent.mkdir(parents=True)
    bad_canonical.write_text("---\nname: test-agent\n---\nNo description.\n")
    adapter = translate.adapter_for("github-copilot")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("whatever was projected long ago\n")
    refused = adapter.uninstall(
        "test-agent", scope="global", home=tmp_path,
        canonical_content=bad_canonical,
    )
    assert refused == dest
    assert dest.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_translate.py -v -k "uninstall"`
Expected: new tests FAIL (unexpected kwarg `canonical_content`; sentinel orphaned; foreign file deleted).

- [ ] **Step 3: Implement guarded uninstall**

In `translate.py`, add `import sys` to the imports, then replace `uninstall` and add the helper:

```python
    def _emitted_or_none(
        self, canonical_content: Path | None, slug: str,
    ) -> str | None:
        """Re-run the emitter over the canonical for content-match detach.
        Any failure (absent file, unreadable, emitter ValueError) returns
        None — uninstall must never crash computing ownership; the sidecar
        alone then decides."""
        if canonical_content is None or not canonical_content.exists():
            return None
        try:
            fm, body = _parse_frontmatter(canonical_content.read_text())
            return self._emitter(fm, body, slug)
        except (ValueError, OSError):
            return None

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        """Ownership-guarded detach (#368): unlink when the sentinel exists
        OR the file matches what the emitter would write now (covers
        pre-sentinel installs). Foreign files are left in place and returned
        as a structured refusal. The sidecar is removed whenever the file is
        gone (orphan hygiene — translate previously cleaned nothing)."""
        dest = self._resolve_dest(slug, scope=scope, home=home, project=project)
        sentinel = _sentinel_path(dest)
        refused: Path | None = None
        if dest.exists() or dest.is_symlink():
            owned = sentinel.exists()
            if not owned and not dest.is_symlink():
                expected = self._emitted_or_none(canonical_content, slug)
                # Bytes compare + OSError guard: a foreign non-UTF8 or
                # unreadable file must refuse, never crash the detach.
                try:
                    owned = (expected is not None
                             and dest.read_bytes() == expected.encode())
                except OSError:
                    owned = False
            if owned:
                dest.unlink()
            else:
                refused = dest
                print(
                    f"{self.harness}: {dest} not managed by this tool "
                    f"(no sentinel, content differs) — left in place",
                    file=sys.stderr,
                )
        if sentinel.exists() and not dest.exists():
            sentinel.unlink()
        return refused
```

NOTE: pre-existing translate uninstall tests (if any assert unconditional removal of a file the test wrote by hand without a sentinel) now see a refusal — fix the TEST by installing through the adapter first; the new semantics are the spec.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_translate.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/agent_adapters/translate.py tests/test_cli/test_agent_adapters/test_translate.py
git commit -m "feat(agent): translate adapter uninstall is ownership-guarded with structured refusal

Re-emit-and-compare content-match detach; emitter failure = no-match, never
a crash; gains the orphan-sentinel cleanup symlink got in #366.

Refs #368

Device: $(hostname -s)"
```

---

### Task 5: config_file_folder — codex/firebender sentinel write + cleanup, uniform uninstall signature

Codex and firebender guard their per-slug file but never write the sidecar (re-install conflicts on our own files). Aider-desk/dexto already write it. All four adapters additionally accept (and ignore) `canonical_content=` so Task 6 can thread it uniformly. Shared-registry mutation and unconditional removal semantics are UNCHANGED.

NOTE: codex and firebender are **catalog-disabled** (`subagent_mechanism="none"` in `skill_agents.py`, intentionally, pending PR5a) — `get_adapter()` never dispatches to them, so this contract is exercised via direct `config_file_folder.adapter_for()` calls only and becomes facade-reachable when the cells are enabled. This is forward-provisioning, not a live-path fix; do not be surprised that `agent install` reports these harnesses as skipped.

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/config_file_folder.py`
- Test: `tests/test_cli/test_agent_adapters/test_config_file_folder.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli/test_agent_adapters/test_config_file_folder.py` (reuse its existing content-file fixture if one exists — check the top of the file; otherwise this local fixture):

```python
@pytest.fixture
def sentinel_content(tmp_path):
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text("---\nname: test-agent\ndescription: testing\n---\n\nBody.\n")
    return content


def test_codex_install_writes_sentinel_and_uninstall_cleans_it(tmp_path, sentinel_content):
    """#368: codex's per-slug .toml gets the .attk sidecar; uninstall removes it."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, config_file_folder
    adapter = config_file_folder.adapter_for("codex")
    dest = adapter.install("test-agent", sentinel_content, scope="global", home=tmp_path)
    sidecar = _sentinel_path(dest)
    assert sidecar.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not dest.exists()
    assert not sidecar.exists(), "orphaned .attk after codex uninstall"


def test_codex_reinstall_self_authorizes_via_sentinel(tmp_path, sentinel_content):
    """#368 (F3): a second install over our own .toml succeeds with
    overwrite=False — the sidecar authorizes it."""
    from agent_toolkit_cli.agent_adapters import config_file_folder
    adapter = config_file_folder.adapter_for("codex")
    adapter.install("test-agent", sentinel_content, scope="global", home=tmp_path)
    # No lock, no overwrite flag — must not raise:
    adapter.install("test-agent", sentinel_content, scope="global", home=tmp_path)


def test_firebender_install_writes_sentinel_and_uninstall_cleans_it(tmp_path, sentinel_content):
    """#368: firebender's per-slug .md gets the .attk sidecar; uninstall removes it."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, config_file_folder
    adapter = config_file_folder.adapter_for("firebender")
    dest = adapter.install("test-agent", sentinel_content, scope="global", home=tmp_path)
    sidecar = _sentinel_path(dest)
    assert sidecar.exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not dest.exists()
    assert not sidecar.exists(), "orphaned .attk after firebender uninstall"


def test_codex_uninstall_cleans_orphan_sidecar(tmp_path, sentinel_content):
    """#368 review F3: the per-slug file deleted out-of-band must not strand
    its sidecar — an orphan .attk would authorize a future silent clobber."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, config_file_folder
    adapter = config_file_folder.adapter_for("codex")
    dest = adapter.install("test-agent", sentinel_content, scope="global", home=tmp_path)
    dest.unlink()  # user removes the projection by hand
    assert _sentinel_path(dest).exists()
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    assert not _sentinel_path(dest).exists(), "orphan sidecar survived uninstall"


def test_cff_uninstall_accepts_canonical_content_kwarg(tmp_path, sentinel_content):
    """#368 Protocol uniformity: all four cff adapters tolerate the kwarg
    (and ignore it — their removal semantics are out of scope)."""
    from agent_toolkit_cli.agent_adapters import config_file_folder
    for harness in ("aider-desk", "codex", "dexto", "firebender"):
        adapter = config_file_folder.adapter_for(harness)
        adapter.install("test-agent", sentinel_content, scope="global", home=tmp_path)
        result = adapter.uninstall(
            "test-agent", scope="global", home=tmp_path,
            canonical_content=sentinel_content,
        )
        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_config_file_folder.py -v -k "sentinel or canonical_content or self_authorizes"`
Expected: FAIL (no sidecar for codex/firebender; unexpected kwarg).

- [ ] **Step 3: Implement**

In `config_file_folder.py`:

1. `_CodexAdapter.install` — after `toml_path.write_text(...)` (line ~306), add:
```python
        _sentinel_path(toml_path).write_text("")
```
2. `_CodexAdapter.uninstall` — OUTSIDE (after) the `if toml_path.exists():` block, add:
```python
        # Unconditional: clean the sidecar even when the .toml was already
        # deleted out-of-band — an orphan sidecar would later authorize a
        # silent clobber via _guard_foreign (#361 hazard, #368 review F3).
        _sentinel_path(toml_path).unlink(missing_ok=True)
```
3. `_FirebenderAdapter.install` — after `md.write_text(text)` (line ~220), add:
```python
        _sentinel_path(md).write_text("")
```
4. `_FirebenderAdapter.uninstall` — OUTSIDE (after) the `if md.exists():` block, add:
```python
        # Unconditional: clean the sidecar even when the .md was already
        # deleted out-of-band (orphan-sidecar hygiene, as in codex above).
        _sentinel_path(md).unlink(missing_ok=True)
```
5. All four adapters' `uninstall` signatures gain the trailing parameter and explicit return type:
```python
    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
```
   Each body ends with `return None` (aider-desk/dexto/codex/firebender keep their unconditional removal — `canonical_content` is deliberately unused here; add the comment `# canonical_content accepted for Protocol uniformity (#368); cff removal semantics unchanged.` at the top of each changed signature).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli/test_agent_adapters/test_config_file_folder.py tests/test_cli/test_aider_desk_dexto_cells.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/agent_adapters/config_file_folder.py tests/test_cli/test_agent_adapters/test_config_file_folder.py
git commit -m "feat(agent): codex/firebender per-slug files get ownership sidecars

Sentinel write on install + cleanup on uninstall; registry mutation
unchanged. All cff uninstalls accept canonical_content for Protocol
uniformity.

Refs #368

Device: $(hostname -s)"
```

---

### Task 6: Facade + Protocol — thread canonical_content everywhere, collect all refusals

**Files:**
- Modify: `src/agent_toolkit_cli/agent_adapters/__init__.py:148-171` (Protocol docstring + signature)
- Modify: `src/agent_toolkit_cli/agent_install.py:294-319` (apply remove-loop), `:440-471` (uninstall loop)
- Test: `tests/test_cli/test_agent_install.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_agent_install.py` (check the top of the file for its existing home/project fixture pattern and reuse it; the test below assumes plain `tmp_path`):

```python
def test_uninstall_collects_refusals_from_symlink_adapters(tmp_path):
    """#368: facade uninstall() returns refusals from EVERY adapter, not just
    standard — a hand-authored file at a symlink-cell destination is left in
    place and reported."""
    from agent_toolkit_cli import agent_install
    from agent_toolkit_cli.agent_adapters import symlink
    home = tmp_path / "home"
    # A foreign file at cursor's GLOBAL destination (never installed by us).
    dest = symlink.adapter_for("cursor").destination(
        "test-agent", scope="global", home=home,
    )
    dest.parent.mkdir(parents=True)
    dest.write_text("# hand-authored\n")
    refusals = agent_install.uninstall(
        slug="test-agent", scope="global", home=home, project=None,
        harnesses=("cursor",),
    )
    assert refusals == (("cursor", dest),)
    assert dest.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_agent_install.py -v -k "collects_refusals"`
Expected: FAIL — the Task-2 adapter already refuses (the file is left in place and the stderr notice prints), but the facade's non-standard branch ignores the return value, so `refusals` comes back `()` instead of `(("cursor", dest),)`.

- [ ] **Step 3: Update the Protocol**

In `agent_adapters/__init__.py`, change `AgentAdapter.uninstall` to:

```python
    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        """Remove the projection. Idempotent.

        Ownership-guarded for the standard/symlink/translate mechanisms
        (#361/#368): the projection is unlinked only when its `.attk`
        sidecar exists OR the file matches what install would write from
        `canonical_content` (content-match detach for pre-sentinel
        installs). A foreign file is left in place and its path returned
        as a structured refusal; None means removed or absent.

        config_file_folder adapters accept `canonical_content` for Protocol
        uniformity but ignore it — their removal semantics (per-slug
        subdir/registry cleanup) are unchanged and always return None.
        """
        ...
```

- [ ] **Step 4: Collapse the facade special-casing**

In `agent_install.py` `apply()` (lines 294-319), replace the remove loop's dispatch:

```python
        try:
            adapter = agent_adapters.get_adapter(name)
        except UnsupportedMechanismError:
            continue
        # #368: every adapter takes canonical_content for ownership-guarded
        # detach (content-match authorizes removing pre-sentinel projections);
        # refusals print their own stderr notice inside the adapter.
        adapter.uninstall(
            plan.slug,
            scope=plan.scope, home=home, project=project,
            canonical_content=content_path,
        )
```

In `uninstall()` (lines 440-471), replace the per-name dispatch:

```python
        try:
            refused = adapter.uninstall(
                slug, scope=scope, home=home, project=project,
                canonical_content=canonical_content,
            )
            if refused is not None:
                refusals.append((name, refused))
        except ValueError:
            # Adapter can't resolve a destination for these args (e.g. a
            # {HOME}-template harness called with home=None, or dexto at
            # project scope). There is nothing to remove there — treat as a
            # no-op rather than crashing the uninstall.
            continue
```

(The `if name == "standard":` branches disappear in both loops. Update `uninstall()`'s docstring sentence "the standard adapter REFUSES..." to "standard/symlink/translate adapters REFUSE..." and drop the now-false "other adapters always return None" sentence from the module docstrings.)

- [ ] **Step 5: Run the facade + full agent suites**

Run: `uv run pytest tests/test_cli/test_agent_install.py tests/test_cli/ -q -k "agent"`
Expected: all PASS, including the new refusal test. WATCH FOR: any existing facade round-trip test that hand-places files at destinations without installing through adapters — those now refuse; fix the TEST to install through the facade (the new semantics are the spec).

- [ ] **Step 6: Run the TUI suite (refusal consumer)**

Run: `uv run pytest tests/test_tui/ -q`
Expected: PASS — `app.py:932-940` already consumes `(harness, dest)` tuples generically; new refusal sources need no TUI change.

- [ ] **Step 7: Commit**

```bash
git add src/agent_toolkit_cli/agent_adapters/__init__.py src/agent_toolkit_cli/agent_install.py tests/test_cli/test_agent_install.py
git commit -m "feat(agent): facade threads canonical_content to every adapter, collects all refusals

AgentAdapter.uninstall Protocol unified (canonical_content kwarg, Path|None
refusal return); name=='standard' special-casing collapsed in apply() and
uninstall().

Refs #368

Device: $(hostname -s)"
```

---

### Task 7: Facade-level pins — F3 self-authorizing re-install + G5 expansion-clobber

These are the issue's two motivating defects, pinned through the REAL facade (`apply()`), not adapter unit calls.

**Files:**
- Test: `tests/test_cli/test_agent_install.py`

- [ ] **Step 1: Write the tests**

Build the plans by constructing `InstallPlan` DIRECTLY (the file's existing idiom — see `test_agent_install.py:49` and `:303`; `from agent_toolkit_cli._install_core import InstallPlan`). Do NOT use `agent_install.plan()` here: its adapter-aware linked scan treats ANY existing file at a destination as "currently linked" (`dest.exists()`, no ownership check) and computes `add = target - current`, so a pre-existing foreign file would silently drop the harness from `add_agents` and `apply()` would never reach the adapter — the G5 test would fail with DID-NOT-RAISE for the wrong reason, and the F3 test could pass vacuously. Direct `InstallPlan` is also the TUI's real apply path (`app.py:909-914`). Mirror the file's canonical-seeding idiom (see its existing `apply()` tests around line 45: `canonical_agent_dir(...)` + write `<slug>.md`; the file's HOME-isolation fixtures apply). Then add:

```python
def test_reinstall_self_authorizes_without_lock_entry(tmp_path):
    """#368 F3 pin: apply() twice with NO lock entry (overwrite=False both
    times) — the second run succeeds because the first run's sentinels
    authorize the refresh. Before #368 this raised
    AgentProjectionConflictError on the tool's own files."""
    from agent_toolkit_cli import agent_install
    from agent_toolkit_cli._install_core import InstallPlan
    home = tmp_path / "home"
    home.mkdir()
    # Seed the canonical <slug>.md per the file's existing idiom (see the
    # apply() tests near line 45 — canonical_agent_dir + write test-agent.md).
    p = InstallPlan(
        slug="test-agent", scope="global", source=None, ref=None,
        add_agents=("cursor", "gemini-cli"), remove_agents=(),
    )
    agent_install.apply(p, home=home, project=None)
    agent_install.apply(p, home=home, project=None)  # must not raise


def test_expansion_does_not_clobber_foreign_file(tmp_path):
    """#368 G5 pin (waived from #362): with a lock entry present
    (overwrite=True from the facade), expanding to a harness whose
    destination holds a user-authored file still REFUSES."""
    import pytest
    from agent_toolkit_cli import agent_install
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_adapters import (
        AgentProjectionConflictError, symlink,
    )
    home = tmp_path / "home"
    home.mkdir()
    # Seed the canonical <slug>.md per the file's existing idiom, THEN seed a
    # lock entry so apply() derives overwrite=True (mirror the file's
    # lock-seeding idiom: agent_lock.add_entry + write_lock with a
    # LockEntry(source=..., agent_path="test-agent.md")).
    # User-authored file at a destination we never projected:
    dest = symlink.adapter_for("cursor").destination(
        "test-agent", scope="global", home=home,
    )
    dest.parent.mkdir(parents=True)
    dest.write_text("# the user's own cursor agent\n")
    p = InstallPlan(
        slug="test-agent", scope="global", source=None, ref=None,
        add_agents=("cursor",), remove_agents=(),
    )
    with pytest.raises(AgentProjectionConflictError):
        agent_install.apply(p, home=home, project=None)
    assert dest.read_text() == "# the user's own cursor agent\n"
```

IMPORTANT for the implementer: the seeding comments above defer to the file's EXISTING idioms (canonical seeding near line 45; lock seeding via `LockEntry` — check the exact field values its other lock tests use). The ASSERTIONS (second apply must not raise; expansion must raise and leave the file untouched) are the contract and may not be weakened. Keep the direct-`InstallPlan` construction — that requirement is load-bearing, not stylistic.

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_cli/test_agent_install.py -v -k "self_authorizes or expansion"`
Expected: PASS (Tasks 1–6 already landed the behavior). If `test_expansion_does_not_clobber_foreign_file` fails with DID-NOT-RAISE, first check the test still constructs `InstallPlan` directly (a `plan()` call would have dropped cursor from add_agents via the linked scan); only if the adapter genuinely overwrote the file is it a Task 1/3 regression.

- [ ] **Step 3: Commit**

```bash
git add tests/test_cli/test_agent_install.py
git commit -m "test(agent): pin F3 self-authorizing re-install and G5 expansion-clobber refusal

Refs #368, #362

Device: $(hostname -s)"
```

---

### Task 8: Doctor — sentinel-gated cursor-shadow fix

Restore F2's intent now the gate can fire: shadowing file WITH sidecar → offer removal fix; sentinel-less → today's report-only message. `cursor-shadow` stays informational for exit semantics, so the fix-offer must not route through the `skipped` counter.

**Files:**
- Modify: `src/agent_toolkit_cli/commands/agent/doctor_cmd.py:221-252` (finding), `:413-453` (prompt loop)
- Test: `tests/test_cli/test_agent_doctor.py`

- [ ] **Step 1: Update the two now-inverted existing tests**

`tests/test_cli/test_agent_doctor.py` has two tests whose premises FLIP under #368 — update them first (they are currently RED or about to be after Tasks 1–6):

1. `test_doctor_cursor_shadow_sentineled_no_longer_special` (line ~375) asserted a hand-made sentinel "changes nothing" (no fix). Under #368 a sentinel **does** gate the fix. Replace the whole test with:

```python
def test_doctor_cursor_shadow_with_sentinel_offers_removal_fix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#368: the .attk sidecar proves the tool wrote the cursor copy — the
    finding now carries a fix_action that removes file AND sidecar."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_locked_slug_with_matching_slot(tmp_path)
    cursor_dest = _write_cursor_file(tmp_path, _DIVERGED, sentinel=True)

    findings = _diagnose(slugs=None, scope="global", home=tmp_path, project=None)
    shadows = _by_type(findings, "cursor-shadow")
    assert len(shadows) == 1, [f.finding_type for f in findings]
    f = shadows[0]
    assert f.fix_action is not None
    assert "tool-installed" in f.detail
    f.fix_action.apply()
    assert not cursor_dest.exists()
    assert not _sentinel_path(cursor_dest).exists()
```

2. `test_doctor_cursor_shadow_via_real_adapter_is_report_only` (line ~391; its no-sentinel premise was already flipped in Task 1 Step 5) — now its `fix_action is None` assertions invert too. Rename it to `test_doctor_cursor_shadow_via_real_adapter_offers_fix` and update: assert `f.fix_action is not None`, and keep the exit-code block asserting `--no-fix` still exits 0 (informational semantics).

- [ ] **Step 2: Write the new failing tests**

Append to the cursor-shadow section of `test_agent_doctor.py` (helpers `_seed_locked_slug_with_matching_slot`, `_write_cursor_file`, `_by_type`, `_diagnose`, `_CONTENT`, `_DIVERGED`, `CliRunner`, `main` all exist in the file):

```python
def test_doctor_cursor_shadow_fix_applies_on_y(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#368 end-to-end: answering y removes the shadowing file + sidecar,
    and the run still exits 0 (informational, no actionable findings)."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_locked_slug_with_matching_slot(tmp_path)
    cursor_dest = _write_cursor_file(tmp_path, _DIVERGED, sentinel=True)

    r = CliRunner().invoke(main, ["agent", "doctor", "-g"], input="y\n")
    assert r.exit_code == 0, r.output
    assert not cursor_dest.exists()
    assert not _sentinel_path(cursor_dest).exists()


def test_doctor_cursor_shadow_fix_decline_keeps_exit_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#368 (F1 guard): declining the informational fix must NOT count as
    'skipped' (which drives exit 1) — doctor exits 0 and prints the clean
    verdict when no actionable findings exist."""
    monkeypatch.setenv("HOME", str(tmp_path))
    _seed_locked_slug_with_matching_slot(tmp_path)
    cursor_dest = _write_cursor_file(tmp_path, _DIVERGED, sentinel=True)

    r = CliRunner().invoke(main, ["agent", "doctor", "-g"], input="N\n")
    assert r.exit_code == 0, r.output
    assert "all clean" in r.output
    assert cursor_dest.exists()
```

`test_doctor_cursor_shadow_divergent_copy_report_only` (sentinel=False) keeps pinning the sentinel-less report-only branch, but its MESSAGE assertions change with the detail text: replace the `assert "agent uninstall" in f.detail` / `assert "--harnesses cursor" in f.detail` pair with:

```python
    assert "remove the file manually" in f.detail
    assert "--harnesses cursor" not in f.detail  # the old dead-end suggestion
```

Keep `fix_action is None` and the file-still-exists assertions unchanged.

- [ ] **Step 2b: Run to verify they fail**

Run: `uv run pytest tests/test_cli/test_agent_doctor.py -v -k "cursor_shadow"`
Expected: the updated + new tests FAIL (no fix offered; prompt never appears); `..._divergent_copy_report_only` PASSES.

- [ ] **Step 3: Implement the finding split**

In `doctor_cmd.py` section 4b (lines 237-252), replace the single `findings.append` with:

```python
            if (
                cursor_dest is not None
                and cursor_dest.exists()
                and not filecmp.cmp(scope_content, cursor_dest, shallow=False)
            ):
                if _sentinel_path(cursor_dest).exists():
                    # #368: the sidecar proves the tool wrote this file — a
                    # stale projection shadowing the slot; offer removal.
                    findings.append(Finding(
                        slug=slug, finding_type="cursor-shadow", scope=scope,
                        path=cursor_dest,
                        detail=(
                            "cursor reads its own .cursor/agents first, so "
                            f"this tool-installed file shadows the standard "
                            f"slot at {slot}"
                        ),
                        fix_action=FixAction(
                            shell_preview=(
                                f"rm {cursor_dest} {_sentinel_path(cursor_dest)}"
                            ),
                            apply=lambda d=cursor_dest: _rm_file_and_sidecar(d),
                        ),
                    ))
                else:
                    findings.append(Finding(
                        slug=slug, finding_type="cursor-shadow", scope=scope,
                        path=cursor_dest,
                        detail=(
                            "cursor reads its own .cursor/agents first, so this "
                            f"file shadows the standard slot at {slot} — if the "
                            "shadowing is unintended, remove the file manually "
                            "(it may be hand-authored; `agent uninstall` would "
                            "refuse it for the same reason no fix is offered)"
                        ),
                        fix_action=None,
                    ))
```

Review F4 (#368 critical review): the OLD detail suggested `agent uninstall <slug> --harnesses cursor`, but in this branch the file is sentinel-less AND divergent — exactly the class the new guarded uninstall refuses — so the suggested command was a guaranteed dead end. Manual removal is the only honest remediation here.

Also update the stale comment block above it (lines 221-228): the "ALWAYS report-only (PM review F2)" rationale is superseded — replace with "Report-only UNLESS the shadowing file carries our .attk sidecar (#368): sentinel-less files may equally be user-authored."

- [ ] **Step 4: Restructure the prompt loop**

In the loop (lines 418-423), the informational branch currently `continue`s before the fix-offer. Replace:

```python
        if f.finding_type in _INFORMATIONAL_TYPES:
            # Report-only notice about a file we do not manage — visible,
            # but never fails the exit code or the clean verdict (F1).
            informational += 1
            click.echo("  (informational — no automatic fix)")
            continue
```

with:

```python
        if f.finding_type in _INFORMATIONAL_TYPES:
            # Never fails the exit code or the clean verdict (F1) — but a
            # sentinel-backed informational finding MAY carry a fix (#368
            # cursor-shadow). Declining must not count as 'skipped' (which
            # drives exit 1); applying counts as fixed.
            informational += 1
            if f.fix_action is None or no_fix or quit_loop:
                click.echo("  (informational — no automatic fix)")
                continue
            click.echo(f"  fix:    {f.fix_action.shell_preview}")
            try:
                ans = click.prompt(
                    "  apply?", default="N", show_default=False,
                    type=click.Choice(["y", "N", "q"], case_sensitive=False),
                )
            except (click.Abort, EOFError, OSError):
                click.echo("\n  (no input available — leaving as-is)")
                quit_loop = True
                continue
            ans = ans.lower()
            if ans == "y":
                try:
                    f.fix_action.apply()
                    click.echo("  fixed.")
                    fixed += 1
                except Exception as exc:
                    click.echo(f"  fix failed: {exc}")
            elif ans == "q":
                quit_loop = True
            continue
```

(`fixed` inflation is harmless for the exit check: any unfixed ACTIONABLE finding increments `skipped`, which exits 1 on its own; and an informational-only run returns at the `actionable_total == 0` gate before the exit-1 line.)

- [ ] **Step 5: Run the doctor suite**

Run: `uv run pytest tests/test_cli/test_agent_doctor.py -v`
Expected: all PASS — including F1's exit-0 pin (`doctor -g` exit 0 with only hand-authored agents) and the pre-existing report-only cursor-shadow test.

- [ ] **Step 6: Commit**

```bash
git add src/agent_toolkit_cli/commands/agent/doctor_cmd.py tests/test_cli/test_agent_doctor.py
git commit -m "feat(agent): doctor cursor-shadow offers sentinel-gated removal fix

Sidecar present -> fix removes file + sidecar; sentinel-less stays
report-only; informational exit semantics unchanged (F1 preserved).

Refs #368

Device: $(hostname -s)"
```

---

### Task 9: Docs + full verification

**Files:**
- Modify: `docs/agent-toolkit/cli.md:47`
- Possibly modify: `docs/` how-it-works pages if any describe agent projection ownership (grep first)

- [ ] **Step 1: Update cli.md's cursor-shadow paragraph**

Line 47 currently says cursor-shadow is "report-only, since cursor installs carry no ownership sentinel". Replace that clause with:

```markdown
`cursor-shadow` (a divergent pre-existing `.cursor/agents/<slug>.md` file — cursor's own dir **wins** name conflicts, so it shadows the slot; when the file carries the tool's `.attk` ownership sidecar the doctor offers to remove it, otherwise it is report-only — a sentinel-less divergent file may equally be hand-authored, and `agent uninstall` refuses exactly that class, so remove it manually if the shadowing is unintended)
```

Then check for other stale ownership claims:

Run: `grep -rn "sentinel\|attk\|ownership" docs/agent-toolkit/*.md docs/how-it-works/*.md 2>/dev/null`
Update any line claiming only the standard adapter (or only some adapters) write sidecars: as of #368 ALL file-writing agent adapters (standard, symlink ×15, translate ×10, codex/firebender per-slug files) write `.attk` sidecars; aider-desk/dexto already did.

- [ ] **Step 2: Full suite + lint**

Run: `uv run pytest -q 2>&1 | tail -15 && uv run ruff check src tests`
Expected: suite green EXCEPT the two known HOME-isolation local-only failures (`test_empty_machine_is_empty`-family); ruff introduces no NEW findings vs main (`git stash` is FORBIDDEN for baseline comparison — use `git show main:<path>` if needed).

- [ ] **Step 3: Commit**

```bash
git add docs/agent-toolkit/cli.md
git commit -m "docs(agent): cursor-shadow fix is sentinel-gated; all adapters write sidecars

Refs #368

Device: $(hostname -s)"
```

---

## Acceptance-criteria → task map (spec §AC)

| AC | Pinned by |
|---|---|
| 1. sidecars everywhere | Task 1 (15 cells), Task 3 (10 cells), Task 5 (codex/firebender) |
| 2. F3 adopt/self-authorize | Tasks 1/3 (adapter), Task 5 (codex), Task 7 (facade pin) |
| 3. G5 overwrite-flag inert | Tasks 1/3 (adapter), Task 7 (facade pin) |
| 4. F6 symlink-replace | Tasks 1/3 |
| 5. guarded uninstall + refusal surfacing | Tasks 2/4 (adapter), Task 6 (facade collection; TUI free) |
| 6. no orphan sidecars | Task 2 (symlink, pre-existing test), Task 4 (translate), Task 5 (codex/firebender) |
| 7. doctor sentinel-gated fix, exit unchanged | Task 8 |
| 8. standard untouched, suite green | Task 9 (plus `test_agent_standard_adapter.py` untouched throughout) |
