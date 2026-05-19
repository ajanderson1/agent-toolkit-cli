# Fix `(gemini, command)` symlink pruned — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `(gemini, command)` projection so `agent-toolkit-cli link user gemini command:<slug>` actually leaves a symlink at `~/.gemini/commands/<slug>.toml` (and project-scope equivalent), instead of writing and immediately pruning it.

**Architecture:** Two surgical changes in `src/agent_toolkit_cli/commands/_link_lib.py`. (1) `_render_to_cache` defers to `_slot_filename(slug, kind, harness)` for the cache filename instead of hardcoding `.md`. (2) The orphan sweep recognises any entry whose stem matches a discovered slug, instead of only stripping `.md`. Both fixes generalise existing logic that already worked for `.md` cells; no behavioural change for `(claude, *)` (raw symlinks — no translator) or `(opencode|gemini, *)` cells that happen to use `.md`.

**Tech Stack:** Python 3.13, pytest, uv. The codebase uses `pathlib.Path`. `_slot_filename` is the canonical filename decider; the bug is that two call sites bypass it. Linter/formatter: ruff via lefthook pre-commit hook (auto-runs on commit, also runs pytest).

**Spec:** `docs/superpowers/specs/2026-05-19-gemini-command-symlink-pruned-design.md`

---

## File Structure

- **Modify:** `src/agent_toolkit_cli/commands/_link_lib.py`
  - `_render_to_cache` (line 183 region): cache-file name derived from `_slot_filename`, not hardcoded `.md`.
  - Orphan sweep inside `project_from_file` (line 654 region): generalise slug recovery via `Path(name).stem`.
- **Modify:** `tests/test_link_lib.py`
  - Add `test_gemini_command_slot_uses_toml_suffix` (analogue of `test_claude_command_slot_uses_md_suffix`, but for a translated cell — asserts symlink target is the cache file, not the source).
  - Add `test_orphan_sweep_prunes_legacy_gemini_command_bare_slug` (analogue of `test_orphan_sweep_prunes_legacy_bare_slug_for_claude_command`).
  - Add `test_orphan_sweep_keeps_fresh_gemini_command_toml_link` — regression test specifically for the bug being fixed (the sweep must NOT prune a freshly-linked `<slug>.toml`).
- **Modify:** `audit/demos/command-gemini.sh`
  - Update `TARGET` to `<slug>.toml` and adjust `assert_symlink_target` to point at the cache file rather than the source asset.

No new files. No refactoring outside the two functions named above.

---

### Task 1: Failing test — fresh gemini command symlink survives the sweep

This test reproduces the exact bug. It will fail before the fix and pass after.

**Files:**
- Test: `tests/test_link_lib.py` (append at end of file)

- [ ] **Step 1: Add the test**

Append to `tests/test_link_lib.py`:

```python
def test_orphan_sweep_keeps_fresh_gemini_command_toml_link(tmp_path):
    """Regression for #137: a freshly-linked (gemini, command) slot must
    not be pruned by the same projection pass that just created it.

    Before the fix, _render_to_cache hardcodes `<slug>.md` while
    _slot_filename returns `<slug>.toml`, so the cache file and slot
    name disagree; and the orphan sweep only strips `.md` so the
    `<slug>.toml` entry is unrecognised and gets pruned.
    """
    toolkit = tmp_path / "toolkit"
    (toolkit / "commands" / "demo-cmd").mkdir(parents=True)
    asset = toolkit / "commands" / "demo-cmd" / "demo-cmd.md"
    asset.write_text(
        "---\nname: demo-cmd\ndescription: demo\n"
        "spec:\n  harnesses: [gemini]\n---\n# body\n",
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()
    allowlist = project / ".agent-toolkit.yaml"
    allowlist.write_text(
        "skills: []\nagents: []\ncommands:\n- demo-cmd\n"
        "hooks: []\nplugins: []\nmcps: []\npi_extensions: []\n",
        encoding="utf-8",
    )
    target_dir = project / ".gemini" / "commands"
    target_dir.mkdir(parents=True)

    from agent_toolkit_cli.commands._link_lib import project_from_file

    counters = LinkCounters()
    stdout = StringIO()
    project_from_file(
        scope="project",
        harness="gemini",
        toolkit_root=toolkit,
        project_root=project,
        allowlist_path=allowlist,
        dry_run=False,
        counters=counters,
        stdout=stdout,
    )

    expected = target_dir / "demo-cmd.toml"
    assert expected.is_symlink(), (
        f"expected fresh symlink at {expected}; "
        f"dir contents: {sorted(p.name for p in target_dir.iterdir())}; "
        f"counters: created={counters.created} removed={counters.removed}"
    )
    # The slot must point at the cache, not the source asset.
    cache_target = Path(os.readlink(expected))
    assert cache_target.name == "demo-cmd.toml", (
        f"slot target should end in .toml; got {cache_target}"
    )
    # And the bug-signature: link-then-prune is gone.
    assert counters.removed == 0, (
        f"sweep should not prune the slot it just created; "
        f"counters: created={counters.created} removed={counters.removed}"
    )
```

The test imports `os` and `Path` — they're already imported at top of `test_link_lib.py` via `from io import StringIO` and existing test code; verify with `grep -n "^import os\|^from pathlib\|^import os, " tests/test_link_lib.py` and add the import if missing.

- [ ] **Step 2: Verify imports**

Run: `grep -nE "^import os$|^from pathlib import|^from io import StringIO" tests/test_link_lib.py`
If `os` is missing, add `import os` to the top of the file alongside other stdlib imports.
If `Path` is missing, add `from pathlib import Path`.

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/test_link_lib.py::test_orphan_sweep_keeps_fresh_gemini_command_toml_link -v`
Expected: **FAIL** — either no symlink at `demo-cmd.toml`, or `counters.removed == 1`. This is the bug.

- [ ] **Step 4: Commit the failing test**

```bash
git add tests/test_link_lib.py
git commit -m "test(link): #137 reproduce gemini command symlink prune"
```

---

### Task 2: Fix `_render_to_cache` to use `_slot_filename`

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py` (around lines 180-184)

- [ ] **Step 1: Apply the change**

In `_render_to_cache`, replace the file-layout branch. Current code:

```python
    if layout == "file":
        # Cache layout: <cache_root>/<kind>/<slug>.md; slot symlinks the file.
        cache_dir = cache_root
        cache_path = cache_dir / f"{slug}.md"
        slot_target = cache_path
```

New code:

```python
    if layout == "file":
        # Cache layout: <cache_root>/<kind>/<_slot_filename>; slot symlinks the
        # file. The cache filename must agree with the slot filename computed
        # in maybe_link (`_slot_filename(slug, kind, harness)`), otherwise the
        # orphan sweep will not recognise the slot. See #137.
        cache_dir = cache_root
        cache_path = cache_dir / _slot_filename(slug, kind, harness)
        slot_target = cache_path
```

- [ ] **Step 2: Run the failing test from Task 1**

Run: `uv run pytest tests/test_link_lib.py::test_orphan_sweep_keeps_fresh_gemini_command_toml_link -v`
Expected: still FAIL (the orphan-sweep half is still broken — the cache file is now `.toml` and the slot symlink path matches, but the sweep will still mis-recognise `.toml` entries and prune them).

(Don't commit yet — wait until both fixes are in and the test passes.)

---

### Task 3: Fix orphan sweep to recognise any-extension stem matches

**Files:**
- Modify: `src/agent_toolkit_cli/commands/_link_lib.py` (around lines 651-655)

- [ ] **Step 1: Apply the change**

In `project_from_file`'s orphan sweep, replace the slug-recovery branch. Current code:

```python
                    canonical_slug: str | None = None
                    if bare_name in discovered_slugs:
                        canonical_slug = bare_name
                    elif bare_name.endswith(".md") and bare_name[:-3] in discovered_slugs:
                        canonical_slug = bare_name[:-3]
```

New code:

```python
                    canonical_slug: str | None = None
                    if bare_name in discovered_slugs:
                        canonical_slug = bare_name
                    else:
                        # Any single-extension stem that matches a known slug
                        # (e.g. `<slug>.md`, `<slug>.toml`) is a valid slot
                        # filename for some (harness, kind). The downstream
                        # `expected_name` check below will still prune entries
                        # whose extension doesn't match _slot_filename for this
                        # cell. See #137.
                        stem = Path(bare_name).stem
                        if stem and stem in discovered_slugs:
                            canonical_slug = stem
```

(`Path` is already imported at the top of `_link_lib.py`. Verify: `grep -n "from pathlib import Path" src/agent_toolkit_cli/commands/_link_lib.py` — should be a hit.)

- [ ] **Step 2: Run the previously-failing test**

Run: `uv run pytest tests/test_link_lib.py::test_orphan_sweep_keeps_fresh_gemini_command_toml_link -v`
Expected: **PASS**.

- [ ] **Step 3: Run the full test file**

Run: `uv run pytest tests/test_link_lib.py -v`
Expected: all pass, including the existing `test_orphan_sweep_prunes_legacy_bare_slug_for_claude_command` and `test_claude_command_slot_uses_md_suffix` (the fixes must not regress claude / opencode behaviour).

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -x`
Expected: 889 passed, 1 skipped (matches the pre-flight from the spec commit). If anything else fails, stop and investigate before continuing.

- [ ] **Step 5: Commit the fix**

```bash
git add src/agent_toolkit_cli/commands/_link_lib.py
git commit -m "fix(link): #137 (gemini, command) slot pruned by its own sweep

_render_to_cache hardcoded <slug>.md for every file-layout cell, but
_slot_filename returns <slug>.toml for (gemini, command). The cache
file and slot filename disagreed, so the orphan sweep — which only
stripped .md suffixes — treated the .toml slot as unknown and pruned
it inside the same pass that wrote it. Fix both call sites:

- _render_to_cache: derive cache filename from _slot_filename.
- Orphan sweep: recognise any entry whose stem matches a discovered
  slug, not only .md-suffixed entries."
```

---

### Task 4: Add slot-suffix test for `(gemini, command)`

This test pins the slot-shape behaviour (analogue of the existing
`test_claude_command_slot_uses_md_suffix`, but for a translated cell so
the slot targets the cache, not the source).

**Files:**
- Test: `tests/test_link_lib.py`

- [ ] **Step 1: Add the test**

Insert after `test_claude_command_slot_uses_md_suffix` (≈ line 537):

```python
def test_gemini_command_slot_uses_toml_suffix(tmp_path):
    """(gemini, command) is a translated cell: slot is <slug>.toml
    pointing at the per-scope cache file, NOT at the source asset.
    Regression for #137 (cache filename must match slot filename).
    """
    toolkit = tmp_path / "toolkit"
    (toolkit / "commands" / "demo-cmd").mkdir(parents=True)
    asset = toolkit / "commands" / "demo-cmd" / "demo-cmd.md"
    asset.write_text(
        "---\nname: demo-cmd\ndescription: demo\n"
        "spec:\n  harnesses: [gemini]\n---\n# body\n",
        encoding="utf-8",
    )
    target_dir = tmp_path / ".gemini" / "commands"
    target_dir.mkdir(parents=True)
    counters = LinkCounters()
    stdout = StringIO()

    maybe_link(
        harness="gemini",
        kind="command",
        slug="demo-cmd",
        asset_path=asset,
        target_dir=target_dir,
        toolkit_root=toolkit,
        dry_run=False,
        counters=counters,
        stdout=stdout,
        scope="project",
        project_root=tmp_path,
    )

    expected = target_dir / "demo-cmd.toml"
    assert expected.is_symlink(), (
        f"expected {expected} to exist as a symlink; "
        f"dir contents: {sorted(p.name for p in target_dir.iterdir())}"
    )
    # Translated cell: target is the cache file, with a .toml extension.
    cache_target = Path(os.readlink(expected))
    assert cache_target.name == "demo-cmd.toml"
    assert cache_target.is_file()
    # And the legacy/bug-shape (.md slot) must NOT exist.
    assert not (target_dir / "demo-cmd.md").exists()
    assert not (target_dir / "demo-cmd").exists()
    assert counters.created == 1
    assert counters.removed == 0
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_link_lib.py::test_gemini_command_slot_uses_toml_suffix -v`
Expected: **PASS** (the bug is already fixed by Tasks 2-3).

- [ ] **Step 3: Commit**

```bash
git add tests/test_link_lib.py
git commit -m "test(link): pin (gemini, command) slot suffix and cache target"
```

---

### Task 5: Add orphan-sweep prune test for legacy gemini command shapes

Mirror of `test_orphan_sweep_prunes_legacy_bare_slug_for_claude_command`, ensuring legacy bare-slug or `.md`-shaped slots under `.gemini/commands/` are pruned when upgrading.

**Files:**
- Test: `tests/test_link_lib.py`

- [ ] **Step 1: Add the test**

Insert after `test_orphan_sweep_prunes_legacy_bare_slug_for_claude_command` (≈ line 646):

```python
def test_orphan_sweep_prunes_legacy_gemini_command_bare_slug(tmp_path):
    """After upgrading from a pre-#137 layout, an existing bare-slug
    `<slug>` (or `<slug>.md`) symlink for a gemini command must be
    pruned on the next projection — superseded by the correct
    `<slug>.toml` slot pointing into the translation cache.
    """
    toolkit = tmp_path / "toolkit"
    (toolkit / "commands" / "legacy-cmd").mkdir(parents=True)
    asset = toolkit / "commands" / "legacy-cmd" / "legacy-cmd.md"
    asset.write_text(
        "---\nname: legacy-cmd\ndescription: legacy\n"
        "spec:\n  harnesses: [gemini]\n---\n# body\n",
        encoding="utf-8",
    )
    project = tmp_path / "project"
    project.mkdir()
    allowlist = project / ".agent-toolkit.yaml"
    allowlist.write_text(
        "skills: []\nagents: []\ncommands:\n- legacy-cmd\n"
        "hooks: []\nplugins: []\nmcps: []\npi_extensions: []\n",
        encoding="utf-8",
    )
    target_dir = project / ".gemini" / "commands"
    target_dir.mkdir(parents=True)
    # Pre-existing legacy slot: bare-slug raw symlink to the source asset
    # (shape produced by versions before the translation cache existed).
    legacy = target_dir / "legacy-cmd"
    legacy.symlink_to(asset)

    from agent_toolkit_cli.commands._link_lib import project_from_file

    counters = LinkCounters()
    stdout = StringIO()
    project_from_file(
        scope="project",
        harness="gemini",
        toolkit_root=toolkit,
        project_root=project,
        allowlist_path=allowlist,
        dry_run=False,
        counters=counters,
        stdout=stdout,
    )

    assert (target_dir / "legacy-cmd.toml").is_symlink()
    assert not (target_dir / "legacy-cmd").exists(), (
        "legacy bare-slug symlink should have been pruned on upgrade; "
        f"dir contents: {sorted(p.name for p in target_dir.iterdir())}"
    )
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_link_lib.py::test_orphan_sweep_prunes_legacy_gemini_command_bare_slug -v`
Expected: **PASS**.

- [ ] **Step 3: Run all gemini-related tests for safety**

Run: `uv run pytest tests/test_link_lib.py -k gemini -v`
Expected: all pass (the three new gemini tests + any pre-existing gemini coverage).

- [ ] **Step 4: Commit**

```bash
git add tests/test_link_lib.py
git commit -m "test(link): orphan sweep prunes legacy (gemini, command) shapes"
```

---

### Task 6: Update the gemini command audit demo

The audit demo currently asserts a *raw* symlink target at
`$AGENT_TOOLKIT_REPO/commands/demo-command.md`. The correct shape for a
translated cell is a symlink at `<TARGET_DIR>/<slug>.toml` pointing at
the per-scope cache file under `~/.gemini/.agent-toolkit-cache/command/<slug>.toml`.

**Files:**
- Modify: `audit/demos/command-gemini.sh`

- [ ] **Step 1: Inspect the current assertions**

Run: `sed -n '25,80p' audit/demos/command-gemini.sh`
Note the lines that set `TARGET`, `EXPECTED_TARGET`, and the calls to
`assert_symlink_target`. Verify they match what the spec describes;
adjust the line numbers in Step 2 if the file has drifted.

- [ ] **Step 2: Apply the changes**

Two substitutions:

1. Header comment block — update the projection-shape comment:

   Current:
   ```bash
   # Projection shape for (gemini, command) — per _support.py:
   #   User target:    ~/.gemini/commands/<slug>.md   (raw file symlink)
   #   Project target: .gemini/commands/<slug>.md     (raw file symlink)
   ```

   New:
   ```bash
   # Projection shape for (gemini, command) — translated cell:
   #   User target:    ~/.gemini/commands/<slug>.toml   (symlink → cache)
   #   Project target: .gemini/commands/<slug>.toml     (symlink → cache)
   # The cache lives under ~/.gemini/.agent-toolkit-cache/command/<slug>.toml
   # (project scope: .gemini/.agent-toolkit-cache/command/<slug>.toml).
   ```

2. `TARGET` and `EXPECTED_TARGET`:

   Current:
   ```bash
   TARGET="$HOME/.gemini/commands/demo-command.md"
   EXPECTED_TARGET="$AGENT_TOOLKIT_REPO/commands/demo-command.md"
   ```

   New:
   ```bash
   TARGET="$HOME/.gemini/commands/demo-command.toml"
   EXPECTED_TARGET="$HOME/.gemini/.agent-toolkit-cache/command/demo-command.toml"
   ```

3. Project-scope counterpart (search the file for the `Lifecycle 4/4` /
   `proj` section; same substitution — `.md` → `.toml`, and update
   `EXPECTED_TARGET` to the project-scope cache path
   `$PWD/.gemini/.agent-toolkit-cache/command/demo-command.toml`).

- [ ] **Step 3: Run the demo**

The demo can be invoked outside tmux for the in-process assertions:

Run: `AUDIT_INSIDE_TMUX=1 bash audit/demos/command-gemini.sh`
Expected: exit 0, all `[PASS]` lines.

If anything fails, read the failure message — `assert_symlink_target`
prints both observed and expected, which is the fastest way to diagnose
a path discrepancy.

- [ ] **Step 4: Commit**

```bash
git add audit/demos/command-gemini.sh
git commit -m "audit(command-gemini): assert translated-slot shape (#137)"
```

---

### Task 7: Final full-suite verification

- [ ] **Step 1: Run the full pytest suite**

Run: `uv run pytest -x`
Expected: pre-flight count + 3 (one regression + two coverage tests added in Tasks 1, 4, 5). Roughly `892 passed, 1 skipped`.

- [ ] **Step 2: Run all gemini audit demos**

Run: `AUDIT_INSIDE_TMUX=1 bash audit/demos/command-gemini.sh && echo OK`
Expected: `OK` on stdout, exit 0.

- [ ] **Step 3: Sanity-check the adjacent green cells still pass**

Run: `AUDIT_INSIDE_TMUX=1 bash audit/demos/command-claude.sh && AUDIT_INSIDE_TMUX=1 bash audit/demos/command-opencode.sh 2>/dev/null || true`
Expected: both exit 0 (or, if `command-opencode.sh` doesn't exist, the `|| true` keeps the line green and that's fine — claude is the must-pass).

- [ ] **Step 4: No commit**

This task is verification-only — nothing to commit. If any check failed, return to the relevant Task above and fix.

---

## Self-Review

- **Spec coverage:**
  - Spec § "Fix" 1 (`_render_to_cache`) → Task 2.
  - Spec § "Fix" 2 (orphan sweep) → Task 3.
  - Spec § "Fix" 3.a (slot-suffix test) → Task 4.
  - Spec § "Fix" 3.b (orphan-sweep test) → Task 5.
  - Plus an extra regression test (Task 1) directly exercising the
    bug — explicitly belt-and-braces because the link-then-prune
    interaction is exactly what the two fixes have to address.
  - Spec § "Fix" 4 (audit demo) → Task 6.
  - Spec § "Acceptance criteria" 1-2 → Tasks 1, 4 (unit-level) and
    Task 6 (audit-level).
  - Spec § "Acceptance criteria" 3 → Task 6 Step 3 / Task 7 Step 2.
  - Spec § "Acceptance criteria" 4 → Task 3 Step 4 + Task 7 Step 1.
  - Spec § "Acceptance criteria" 5 → Task 3 Step 3 (existing claude
    tests must still pass) + Task 7 Step 3.

- **Placeholder scan:** every code step has actual code. No TBDs, no
  "implement appropriate error handling". The only sed-substitution
  command is gated on inspection in Task 6 Step 1 to handle file
  drift.

- **Type consistency:** `_slot_filename(slug, kind, harness)` is the
  same signature in both Task 2 and Task 3 — confirmed against
  `src/agent_toolkit_cli/commands/_link_lib.py:101`.
  `Path(bare_name).stem` in Task 3 — `Path` is already imported at
  the top of `_link_lib.py`; verified in Task 3 Step 1.
