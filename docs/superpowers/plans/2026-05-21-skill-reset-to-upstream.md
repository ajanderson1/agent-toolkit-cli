# Plan: skill reset — force-sync to upstream

**Spec:** [`docs/superpowers/specs/2026-05-21-skill-reset-to-upstream-design.md`](../specs/2026-05-21-skill-reset-to-upstream-design.md)
**Issue:** #170 · **Branch:** `feat/170-skill-reset-to-upstream`

The plan is split into ordered phases. Each phase is small, has a clear DoD,
and ends with the tests that prove it works. Phases are sequential — no
parallel subagents required, since the work is tightly coupled (one new
command, one new git helper, one new test module).

---

## Phase 1 — `skill_git.reset_hard` helper

**Goal:** add the lowest-level building block so the command layer has a
clean, env-scrubbed entrypoint for `git reset --hard origin/<ref>`.

**Files:**
- `src/agent_toolkit_cli/skill_git.py` — add `reset_hard(repo, *, ref, env)`.

**Implementation:**

```python
def reset_hard(
    repo: Path, *, ref: str, env: dict[str, str] | None,
) -> GitResult:
    """Hard-reset `repo`'s working tree to `origin/<ref>`.

    Discards local commits and uncommitted changes. Goes through _run so
    GIT_* env vars are scrubbed identically to every other git call
    (see memory feedback_git_env_leak.md).
    """
    proc = _run(
        ["git", "-C", str(repo), "reset", "--hard", f"origin/{ref}"],
        env=env,
    )
    return GitResult(stdout=proc.stdout, stderr=proc.stderr)
```

**Tests added (TDD — write first, then implement):**

`tests/test_skill_git.py`:
- `test_reset_hard_snaps_working_tree_to_origin_ref` — seed repo, advance
  upstream via the helper pattern from `test_cli_skill_update.py`'s
  `_advance_upstream`, fetch in the clone, then call `reset_hard(clone,
  ref="main", env=…)`. Assert the advanced file exists and HEAD matches
  `origin/main`.
- `test_reset_hard_scrubs_git_env_leak` — set `GIT_DIR` / `GIT_INDEX_FILE`
  in the env passed in; `reset_hard` must not touch the leaked repo. This
  follows the same shape as the existing leak-regression tests for
  `push`/`commit_all`.

**DoD:** both new unit tests pass; existing `tests/test_skill_git.py` tests
still pass.

---

## Phase 2 — `reset_cmd` Click command

**Goal:** ship the user-facing `skill reset` command.

**Files:**
- `src/agent_toolkit_cli/commands/skill/reset_cmd.py` — new.
- `src/agent_toolkit_cli/commands/skill/__init__.py` — register.

**Implementation (`reset_cmd.py`):**

Mirrors `update_cmd.py`'s shape exactly — same imports, same
`scope_and_roots` helper, same loop-with-`had_error` pattern. Adds a
`--force` boolean.

```python
"""skill reset subcommand."""
from __future__ import annotations

import click

from agent_toolkit_cli import skill_git
from agent_toolkit_cli.skill_lock import read_lock, write_lock
from agent_toolkit_cli.skill_paths import canonical_skill_dir, lock_file_path

from ._common import scope_and_roots


@click.command("reset")
@click.argument("slugs", nargs=-1)
@click.option("-g", "--global", "global_", is_flag=True)
@click.option("-p", "--project", "project_flag", is_flag=True)
@click.option("--force", is_flag=True,
              help="Reset even if the working tree is dirty.")
@click.pass_context
def reset_cmd(
    ctx: click.Context,
    slugs: tuple[str, ...],
    global_: bool,
    project_flag: bool,
    force: bool,
) -> None:
    """Force-sync each named skill to upstream HEAD.

    Discards local commits and uncommitted edits. Refuses on a dirty tree
    unless --force is given. Updates `local_sha` and `upstream_sha` in the
    lock after a successful reset.
    """
    if not slugs:
        raise click.UsageError(
            "skill reset: at least one slug required. "
            "Run `skill list` to see installed skills."
        )

    scope, home, project_root = scope_and_roots(
        global_,
        project_flag,
        ctx.obj.get("project_root") if ctx.obj else None,
    )
    lock_path = lock_file_path(scope=scope, home=home, project=project_root)
    lock = read_lock(lock_path)

    had_error = False
    for slug in slugs:
        if slug not in lock.skills:
            click.echo(f"{slug}: not in lock")
            had_error = True
            continue

        entry = lock.skills[slug]
        canonical = canonical_skill_dir(
            slug, scope=scope, home=home, project=project_root,
        )

        if not skill_git.is_git_repo(canonical):
            click.echo(
                f"{slug}: copy-mode (no .git/) — cannot reset; remove "
                f"and re-add to switch to git-managed",
            )
            had_error = True
            continue

        if not force:
            if skill_git.status(canonical, env=None) == skill_git.GitWorkingTreeStatus.DIRTY:
                click.echo(
                    f"{slug}: dirty — commit, push, or use --force to discard"
                )
                had_error = True
                continue

        ref = entry.ref or "main"
        try:
            skill_git.fetch(canonical, env=None)
            skill_git.reset_hard(canonical, ref=ref, env=None)
        except skill_git.GitError as exc:
            raise click.ClickException(
                f"{slug}: git failed during reset\n{exc.stderr}"
            ) from exc

        entry.local_sha = skill_git.head_sha(canonical, env=None)
        entry.upstream_sha = skill_git.remote_head_sha(
            canonical, ref=ref, env=None,
        )
        write_lock(lock_path, lock)
        click.echo(f"{slug}: reset to {entry.local_sha[:7]}")

    if had_error:
        ctx.exit(1)
```

**Registration (`__init__.py`):**

Add `from .reset_cmd import reset_cmd` near the other imports and
`skill.add_command(reset_cmd)` near the other `add_command` calls.

**DoD:** `agent-toolkit-cli skill reset --help` renders without error and
shows the `--force` flag.

---

## Phase 3 — CLI integration tests

**Goal:** prove the user-facing surface against the DoD bullets.

**Files:**
- `tests/test_cli/test_cli_skill_reset.py` — new.

**Test inventory (all named `test_reset_*`, mapped to DoD bullets in the
spec):**

1. `test_reset_clean_snaps_to_upstream` — happy path. Add + install,
   advance upstream, run `skill reset demo -p`, assert advanced file
   exists in the canonical.
2. `test_reset_refuses_dirty_without_force` — write an uncommitted edit
   to the canonical, run `skill reset demo -p`, assert exit ≠ 0 *and*
   the edited file still contains the local edit (i.e. the reset did
   *not* fire).
3. `test_reset_force_discards_dirty_tree` — same dirty setup, but pass
   `--force`; assert the edit is gone and tree matches upstream.
4. `test_reset_updates_lock_shas` — after a successful reset, read the
   project's `skills-lock.json`, assert `lock.skills["demo"].local_sha ==
   lock.skills["demo"].upstream_sha` and both equal the upstream's HEAD
   SHA.
5. `test_reset_missing_slug_errors` — `skill reset bogus -p` exits
   non-zero with "not in lock" in the output. Lock file is untouched.
6. `test_reset_multi_slug` — add + install *two* slugs (demo + demo2),
   advance upstream for both, run `skill reset demo demo2 -p`, assert
   both updated.

**Shared helpers:** copy `_add_and_install_project` and `_advance_upstream`
from `test_cli_skill_update.py` into the new file (local copies, not a
conftest extraction — minimises blast radius and matches what
`test_cli_skill_push.py` already does).

**DoD:** all six tests pass under `uv run pytest tests/test_cli/test_cli_skill_reset.py -v`.

---

## Phase 4 — full-suite gate

**Goal:** make sure nothing else broke.

**Commands:**
- `uv run ruff check .` — must be clean.
- `uv run pytest` — must be green.

If ruff or pytest surface real issues, fix in this phase. The
`test_cli_help.py` snapshot might need refreshing if a help listing test
exists.

**DoD:** both commands exit 0.

---

## Phase 5 — manual smoke (verify.sh or terminal recipe)

**Goal:** confirm the command shows up in `--help` output.

Run `uv run agent-toolkit-cli skill --help` and `uv run agent-toolkit-cli
skill reset --help`. Capture both to `assets/verification/170/`. This is
the Step 9 verify recipe — terminal/CLI shape per `flow.md` § Step 9.

---

## Risks (per spec)

- **#169 lands first** → `commands/skill/__init__.py` conflict. Surface
  area is one import line + one `skill.add_command(reset_cmd)` line.
  Resolution: rebase, add both imports/commands, re-test.
- **GIT_* env leak** → mitigated by going through `_run` (existing scrub).
  Phase 1 test #2 enforces this.

## Acceptance — top-level DoD mapping

| DoD bullet | Phase | Test |
|---|---|---|
| `skill reset <slug>` runs fetch + reset --hard | 2 | Phase 3 #1 |
| Refuses dirty without `--force` | 2 | Phase 3 #2 |
| Updates `local_sha` + `upstream_sha` | 2 | Phase 3 #4 |
| Multi-slug form | 2 | Phase 3 #6 |
| Errors loudly if slug not in lock | 2 | Phase 3 #5 |
| Tests cover clean/dirty/dirty-force/lock/missing | 3 | Phase 3 (#1–#6) |

Plan complete.
