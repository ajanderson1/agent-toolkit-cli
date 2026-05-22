# Doctor: classify dying-bundle-target as drift — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When `skill doctor` follows a per-harness symlink that resolves to `~/.agents/skills/<slug>` (the v2.1 bundle target), classify it as `drifted_symlink` (fixable) instead of `foreign_symlink` (report-only). The existing `drifted_symlink` re-link action is reused unchanged.

**Architecture:** A single private predicate `_is_universal_bundle_target(target)` added to `src/agent_toolkit_cli/skill_doctor.py`. Inside `_check_slug`, the existing `foreign_symlink` branch checks the predicate first; if it fires we instead emit `drifted_symlink` pointing at the canonical library path. No new public API, no engine restructure, no changes to `_expected_target_root`.

**Tech Stack:** Python 3.13, pytest, `uv run pytest -q`.

---

## File Structure

| File | Role |
|---|---|
| `src/agent_toolkit_cli/skill_doctor.py` | Add `_is_universal_bundle_target`; reorder `foreign_symlink` branch. |
| `tests/test_cli/test_skill_doctor.py` | Add new test: v2.1-style bundle target → `drifted_symlink`. |
| `tests/test_cli/test_cli_skill_doctor.py` | Update `test_doctor_journal_v21_to_v22_repro` to reflect new classification. |

No new files. No public-API additions.

---

## Task 1: Add failing test — v2.1 bundle target classifies as drift

**Files:**
- Test: `tests/test_cli/test_skill_doctor.py` (append after `test_diagnose_foreign_symlink_repair_foreign`, around line 415)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cli/test_skill_doctor.py`:

```python
def test_diagnose_v21_bundle_target_is_drift(
    git_sandbox, tmp_path: Path, monkeypatch,
):
    """A claude-code symlink that points at ~/.agents/skills/<slug>
    (the v2.1 bundle layout) must classify as drifted_symlink, not
    foreign_symlink — the user can apply the fix to relink to the library.
    """
    library_root = tmp_path / "lib" / "skills"
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library_root))
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(fake_home / ".claude"))
    _patch_claude_global_skills_dir(monkeypatch, fake_home / ".claude" / "skills")

    runner = CliRunner()
    _seed_library(runner, git_sandbox.upstream)

    # Plant the v2.1 layout: a real dir at ~/.agents/skills/demo and a
    # claude-code symlink pointing at it.
    bundle = fake_home / ".agents" / "skills" / "demo"
    bundle.mkdir(parents=True)
    (bundle / "SKILL.md").write_text("v2.1 leftover\n")
    claude_skills = fake_home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    link = claude_skills / "demo"
    link.symlink_to(bundle)

    from agent_toolkit_cli.skill_doctor import diagnose
    findings = diagnose(
        slugs=None, scope="global", home=fake_home, project=None,
    )
    drift = [f for f in findings if f.kind == "drifted_symlink" and f.path == link]
    foreign = [f for f in findings if f.kind == "foreign_symlink" and f.path == link]
    assert len(drift) == 1, [f.kind for f in findings]
    assert len(foreign) == 0
    # Fix action present and idempotent: relinks at library canonical.
    assert drift[0].fix_action is not None
    drift[0].fix_action.apply()
    assert link.is_symlink()
    assert link.resolve() == (library_root / "demo").resolve()
    drift[0].fix_action.apply()  # idempotent
    assert link.resolve() == (library_root / "demo").resolve()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_v21_bundle_target_is_drift -v`

Expected: FAIL — `len(drift) == 1` assertion fails because the finding is `foreign_symlink` (and is filtered out of `drift`); `len(foreign) == 0` likewise fails.

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/test_cli/test_skill_doctor.py
git commit -m "test(doctor): v2.1 bundle target should classify as drift (#192)"
```

---

## Task 2: Implement the predicate + reclassify in `_check_slug`

**Files:**
- Modify: `src/agent_toolkit_cli/skill_doctor.py:145-160` (helpers area) — add predicate
- Modify: `src/agent_toolkit_cli/skill_doctor.py:281-294` (the `foreign_symlink` branch inside `_check_slug`)

- [ ] **Step 1: Add the predicate next to `_is_inside`**

Edit `src/agent_toolkit_cli/skill_doctor.py`. Locate the existing helper:

```python
def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False
```

Insert immediately after it:

```python
def _universal_bundle_root() -> Path:
    """Root of the v2.1 universal-bundle layout: ~/.agents/skills.

    Mirrors `skill_install._universal_bundle_link` (which is `<root>/<slug>`).
    """
    return Path.home() / ".agents" / "skills"


def _is_universal_bundle_target(target: Path) -> bool:
    """True when `target` lives inside the universal-bundle root.

    On a v2.1 → v2.2 migration the per-harness symlinks point at
    `~/.agents/skills/<slug>` (a real dir or a transitional symlink). The
    classification should be `drifted_symlink` (re-link to library) rather
    than `foreign_symlink` (report-only).
    """
    return _is_inside(target, _universal_bundle_root())
```

- [ ] **Step 2: Reclassify inside `_check_slug`**

In the same file, locate the existing `foreign_symlink` branch (around lines 281–294):

```python
        expected_root = _expected_target_root(scope=scope, project=project)
        if not _is_inside(target, expected_root):
            findings.append(Finding(
                kind="foreign_symlink", slug=slug, scope=scope,
                path=link,
                detail=(
                    f"{agent_name} symlink at {link} points to {target}, "
                    f"which is outside {expected_root}"
                ),
                fix_action=(
                    _make_unlink_action(link=link) if repair_foreign else None
                ),
            ))
            continue
```

Replace it with:

```python
        expected_root = _expected_target_root(scope=scope, project=project)
        if not _is_inside(target, expected_root):
            if _is_universal_bundle_target(target):
                findings.append(Finding(
                    kind="drifted_symlink", slug=slug, scope=scope,
                    path=link,
                    detail=(
                        f"{agent_name} symlink at {link} points to {target} "
                        f"(v2.1 bundle layout), expected {canonical}"
                    ),
                    fix_action=_make_relink_action(
                        link=link, canonical=canonical,
                    ),
                ))
                continue
            findings.append(Finding(
                kind="foreign_symlink", slug=slug, scope=scope,
                path=link,
                detail=(
                    f"{agent_name} symlink at {link} points to {target}, "
                    f"which is outside {expected_root}"
                ),
                fix_action=(
                    _make_unlink_action(link=link) if repair_foreign else None
                ),
            ))
            continue
```

- [ ] **Step 3: Run the new test — should now pass**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_v21_bundle_target_is_drift -v`

Expected: PASS.

- [ ] **Step 4: Run the foreign-symlink regression tests — should still pass**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py::test_diagnose_foreign_symlink_report_only tests/test_cli/test_skill_doctor.py::test_diagnose_foreign_symlink_repair_foreign -v`

Expected: PASS — those tests plant the foreign dir at `tmp_path / "user-handrolled-skill"`, which is **not** under `Path.home() / ".agents" / "skills"` (`HOME` is monkeypatched to `tmp_path / "home"`), so `_is_universal_bundle_target` returns False and the foreign-classification branch fires as before.

- [ ] **Step 5: Commit**

```bash
git add src/agent_toolkit_cli/skill_doctor.py
git commit -m "fix(doctor): classify v2.1 bundle target as drift (#192)

When a per-harness symlink resolves to ~/.agents/skills/<slug>
(the v2.1 universal-bundle layout), classify it as drifted_symlink
with a fixable re-link action instead of report-only foreign_symlink."
```

---

## Task 3: Update the v2.1 → v2.2 end-to-end repro test

**Files:**
- Modify: `tests/test_cli/test_cli_skill_doctor.py:122-207` (`test_doctor_journal_v21_to_v22_repro`)

The test currently asserts the claude link is reported as `foreign_symlink` (report-only, skipped). After Task 2 it is reported as `drifted_symlink` (prompted). The user now answers `'y'` twice and the run exits clean.

- [ ] **Step 1: Update the test docstring + ordering comments**

Edit `tests/test_cli/test_cli_skill_doctor.py`. Locate the multi-line comment block from line 183 (`# The engine diagnoses two findings in this order:`) through line 199 (`assert "1 skipped" in r.output`).

Replace lines 183–199 with:

```python
    # The engine diagnoses two findings:
    #   1. drifted_symlink (fixable): the claude link points at the v2.1
    #      bundle path (~/.agents/skills/journal). The new
    #      _is_universal_bundle_target predicate triggers drift instead
    #      of foreign_symlink, so this is now a prompted fix rather than
    #      a skipped report.
    #   2. wrong_type_bundle (fixable): bundle is a real dir, not a symlink.
    # Two 'y' answers apply both fixes. Exit code is 0 — nothing skipped.
    r = runner.invoke(
        main, ["skill", "doctor", "journal", "-g"], input="y\ny\n",
    )
    assert r.exit_code == 0, r.output
    assert "drifted_symlink" in r.output
    assert "wrong_type_bundle" in r.output
    assert "fixed." in r.output
    assert "foreign_symlink" not in r.output
```

- [ ] **Step 2: Run the updated test**

Run: `uv run pytest tests/test_cli/test_cli_skill_doctor.py::test_doctor_journal_v21_to_v22_repro -v`

Expected: PASS.

Note: the post-fix assertions on lines 201–207 (`bundle.is_symlink()`, `bundle.resolve() == library_journal.resolve()`, `claude_link.resolve() == library_journal.resolve()`, backup file exists) still hold — applying the drift fix re-links the claude link to the library canonical (which exists), and applying the bundle fix backs up the real dir and creates the symlink. Both fixes are independent and idempotent.

- [ ] **Step 3: Run the full doctor test files**

Run: `uv run pytest tests/test_cli/test_skill_doctor.py tests/test_cli/test_cli_skill_doctor.py -v`

Expected: PASS — every test green. If anything else fails, stop and investigate before continuing.

- [ ] **Step 4: Run the full suite**

Run: `uv run pytest -q`

Expected: PASS — 305+ passed (304 baseline + 1 new), 2 skipped (the existing baseline skips).

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli/test_cli_skill_doctor.py
git commit -m "test(doctor): update v2.1→v2.2 repro for new drift classification (#192)"
```

---

## Self-Review (already performed)

**Spec coverage:**
- Predicate + reclassification: Task 2.
- v2.1 bundle → drift assertion: Task 1.
- `test_diagnose_foreign_symlink_report_only` still passes: Task 2 step 4 verifies.
- `test_diagnose_foreign_symlink_repair_foreign` still passes: Task 2 step 4 verifies.
- New v2.1-style drift test: Task 1.
- Update `test_doctor_journal_v21_to_v22_repro`: Task 3.

**Placeholders:** None. Every step contains exact code, file paths, or commands.

**Type consistency:** `_is_universal_bundle_target(target: Path) -> bool`, called once inside `_check_slug` with the local `target = link.resolve()`. No type drift.

**Out of scope but worth noting:** the new predicate could later be reused in the project-scope branch if a project ever symlinks at the bundle root — currently `_expected_target_root` for project scope is `project / ".agents" / "skills"` which is **different** from the user-home bundle root, so the predicate behaves correctly: a project-scope link pointing at `~/.agents/skills/<slug>` would (correctly) be flagged as drift rather than foreign. No code change needed for that case.
