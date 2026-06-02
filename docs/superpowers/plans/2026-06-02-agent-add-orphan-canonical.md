# Plan: agent add orphan-canonical fix (#313)

**Date:** 2026-06-02
**Spec:** `docs/superpowers/specs/2026-06-02-agent-add-orphan-canonical-design.md`

---

## Task list

### Task 1 — add_cmd.py: track fresh clone and clean up on failure

File: `src/agent_toolkit_cli/commands/agent/add_cmd.py`

1. Add `import shutil` at the top of the file (after existing imports).
2. In `add_cmd()`, just before the `if not canonical.exists()` guard,
   declare `fresh_clone = False`.
3. Inside the `if not canonical.exists()` block (after `canonical.parent.mkdir`
   and before `skill_git.clone`), set `fresh_clone = True`.
4. After the `clone()` call, wrap the content-file check in a try/except so
   that on failure we can clean up:

   ```python
   content_file = canonical / f"{final_slug}.md"
   if not content_file.exists():
       if fresh_clone:
           import shutil
           shutil.rmtree(canonical, ignore_errors=True)
       raise click.ClickException(
           f"{final_slug}: content file {final_slug}.md absent in source "
           f"{parsed.url!r}; expected <slug>.md at the repo root. "
           f"Pass --slug to match the source's content file."
       )
   ```

   The `shutil` import is at module level; the inline reference above is
   for clarity — the actual `import shutil` goes at the top.

5. `ignore_errors=True` on rmtree handles edge cases where the directory was
   partially created or a concurrent process is touching it. The important
   thing is the clone doesn't linger; if rmtree itself fails we surface the
   original ClickException regardless.

### Task 2 — doctor_cmd.py: orphan-canonical detection

File: `src/agent_toolkit_cli/commands/agent/doctor_cmd.py`

1. Add `import shutil` at the top (it's not currently imported).
2. In `_diagnose()`, after the `for slug, entry in sorted(targets.items()):`
   loop, add a second pass:

   ```python
   # 4. Orphan canonicals — directories in the library with no lock entry.
   # Only run when no slugs filter is active (targeted run won't see orphans).
   if not slugs:
       library_base = library_agent_path("dummy").parent
       if library_base.is_dir():
           lock_slugs = set(lock.skills.keys())
           for child in library_base.iterdir():
               if not child.is_dir():
                   continue
               if child.name not in lock_slugs:
                   orphan = child
                   findings.append(Finding(
                       slug=child.name,
                       kind="orphan-canonical",
                       scope=scope,
                       path=orphan,
                       detail="canonical directory has no lock entry",
                       fix_action=FixAction(
                           shell_preview=f"rm -rf {orphan}",
                           apply=lambda p=orphan: shutil.rmtree(p),
                       ),
                   ))
   ```

   Note: `library_agent_path("dummy").parent` gives us the library base
   without introducing new path helpers. The `dummy` slug argument does not
   need to correspond to anything real.

### Task 3 — tests: test_cli_agent_group.py

File: `tests/test_cli/test_cli_agent_group.py`

Add two new test functions in the `add content-file validation` section:

**Test A — `test_add_no_slug_leaves_no_orphan`**

Verifies fix from Task 1:
1. Build a local git repo (using `_local_agent_repo`) that has `actual-name.md`
   (not matching the repo name `agent-src`).
2. Run `agent add <src>` (no `--slug`).
3. Assert `r.exit_code != 0` (fails as expected).
4. Assert the library has no stray directory for the derived slug (repo name).
   Use `library_agent_path(derived_slug)` to find the expected path and assert
   `not path.exists()`.

**Test B — `test_doctor_detects_and_fixes_orphan_canonical`**

Verifies fix from Task 2:
1. Create a stray directory in the library (no lock entry): manually create
   `canonical_agent_dir("stray-orphan", scope="global")` and write a dummy
   `.md` inside it.
2. Run `agent doctor -g --no-fix`.
3. Assert `r.exit_code != 0` (findings exist).
4. Assert `"orphan-canonical"` in `r.output` and `"stray-orphan"` in `r.output`.
5. Run `agent doctor -g` (with fix prompt answered "y" via `input="y\n"`).
6. Assert the stray directory is gone afterward.

---

## Order of execution

1. Task 1 (add_cmd.py) — smallest change, most critical fix
2. Task 2 (doctor_cmd.py) — complementary self-healing
3. Task 3 (tests) — validate both fixes

---

## Risk notes

- `shutil.rmtree(canonical, ignore_errors=True)` is safe because we only
  reach it when `fresh_clone is True`, meaning this invocation created the
  directory in this call. The `ignore_errors` flag prevents a secondary
  failure from masking the original ClickException.
- The `library_agent_path("dummy").parent` trick is pragmatic; if the path
  helper signature changes in a future refactor, this will need updating.
  Alternative: export a `library_base_path()` helper, but that's extra scope.
- Lambda closure in `FixAction.apply` captures `p=orphan` to avoid the
  late-binding loop variable issue in Python.
