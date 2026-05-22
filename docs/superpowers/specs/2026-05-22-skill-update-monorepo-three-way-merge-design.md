# Spec — Monorepo skills: editable like per-skill repos (`update` three-way merge + TUI state fix)

**Issue:** TBD (file alongside this spec)
**Branch:** `feat/skill-update-monorepo-three-way-merge`
**Mode:** `--auto`
**Supersedes:**
- the `update` paragraph of `2026-05-21-skill-add-monorepo-design.md`
  (which specified `git pull --ff-only` for monorepo entries);
- the implicit "monorepo skills are uneditable" model the `state: copy`
  TUI label currently broadcasts.

## Goal

Let users **edit a monorepo skill in place** inside its parent clone and still pull
upstream updates without forking. Two coupled changes deliver this:

1. **`skill update <slug>`** for a monorepo entry must perform a real **three-way
   merge** between the user's local commits in the parent clone and `origin/<ref>`
   — the same merge semantics that already work for per-skill repo entries
   (e.g. `journal`).
2. **The TUI state column** must report `clean` / `dirty` for monorepo skills —
   derived from the parent clone's working tree — just like it does for per-skill
   repo entries. The current blanket `copy` label misrepresents the model now
   that monorepo skills are locally editable.

The user model:

> "The parent clone at `<library>/_parents/<owner>/<repo>/` is **mine**. I can
> commit edits to its branch. `skill update` should merge upstream into my branch
> like any normal git workflow. I never have to fork unless I want to share my
> changes back."

`read_only: true` continues to gate **`skill push`** (sharing back upstream)
— it does **not** gate local divergence, and it does **not** drive the TUI
state column.

## Why this is a bug today

### Bug 1 — `update` refuses any local divergence

PR #177 shipped `skill update <monorepo-slug>` calling `skill_git.pull_ff_only(...)`
on the parent clone. `--ff-only` refuses any non-fast-forward, so the moment a user
commits a single local change to the parent's `main` branch the next `update` fails:

```
$ git -C <parent_clone> pull --ff-only origin main
fatal: Not possible to fast-forward, aborting.
```

The per-skill-repo branch of the same function uses `fetch` + `merge` and handles
divergence (and surfaces real conflicts as a non-zero exit). Two branches of the
same command path; only one supports the user's workflow.

PR #177's design doc explicitly chose ff-only ("the symlink stays valid"), but the
choice was driven by the symlink-vs-copy materialisation question, not by intent
to forbid local edits. This spec re-opens that decision and aligns the monorepo
branch with the per-skill-repo branch.

### Bug 2 — TUI shows `state: copy` for every monorepo skill, regardless of working-tree

`src/agent_toolkit_tui/skill_state.py:121` decides state by inspecting the **library
canonical** (`<library>/<slug>/`). For a monorepo skill that path is a symlink (or
copy) into `<library>/_parents/<owner>/<repo>/<subpath>/` — it has no `.git/`
directly. `is_git_repo(canonical)` returns False, so the cell falls into:

```python
elif not skill_git.is_git_repo(canonical):
    state = "copy"          # ← every monorepo skill lands here
```

…regardless of whether the parent clone is clean, dirty, or has local commits
ahead of upstream. That label communicates "you can't change this" to the user,
which contradicts Bug 1's fix. The two bugs must ship together or the UX stays
broken even after `update` works.

The correct discriminator is `entry.parent_url is not None` (already in the lock).
For monorepo entries the TUI must derive state from the **parent clone** at
`parent_clone_path(owner, repo, ref=entry.ref)`, using the same
`skill_git.status(...)` helper the per-skill-repo branch uses on its canonical.

## Anchor to the current code

| Concept | Where today |
|---|---|
| Monorepo update branch | `commands/skill/update_cmd.py` lines ~50–94 (the `entry.parent_url is not None` block) |
| Per-skill-repo update branch | same file, lines ~96–122 (uses `fetch` + `merge`) |
| Parent clone path | `skill_paths.parent_clone_path(owner, repo, ref=…)` → `<library>/_parents/<owner>/<repo>[@<ref>]/` |
| Library canonical | `library_skill_path(slug)` — a symlink (or copy fallback) into the parent clone |
| `LockEntry.parent_url` / `LockEntry.read_only` | already plumbed (PR #177) |
| Existing git helpers | `skill_git.fetch`, `skill_git.merge`, `skill_git.pull_ff_only`, `skill_git.head_sha`, `skill_git.is_git_repo`, `skill_git.reset_hard` |
| Existing monorepo update tests | `tests/test_cli/test_skill_update_monorepo.py` (2 tests, both assume clean parent) |
| TUI state computation | `src/agent_toolkit_tui/skill_state.py:103-138` (`build_skill_rows`) |
| TUI state enum | `src/agent_toolkit_tui/skill_state.py:23` (`State = Literal["clean", "dirty", "missing", "copy", "library"]`) |
| TUI state styling | `src/agent_toolkit_tui/widgets/skill_grid.py:31` (`"copy": "[blue]copy[/]"`) |
| TUI install-button gate | `src/agent_toolkit_tui/app.py:306` (`if row.state in ("missing", "copy"):` — blocks installs for `copy` rows) |

## In scope

1. **`update_cmd.py` — monorepo branch.** Replace the `pull_ff_only` call with the
   same `fetch` + `merge` sequence the per-skill-repo branch uses:

   ```python
   skill_git.fetch(parent_dir, env=None)
   try:
       skill_git.merge(parent_dir, ref=ref, env=None)
   except skill_git.GitError as exc:
       click.echo(f"{slug}: conflict during merge in parent clone "
                  f"({parent_dir}) — resolve there, then re-run update")
       click.echo(exc.stderr)
       had_conflict = True
       continue
   ```

   The error message must name the parent clone path so the user knows **where**
   to resolve the conflict (the parent is a real git repo on their disk, not a
   hidden cache).

2. **Copy-mode re-copy stays.** When `entry.extras.get("materialised") == "copy"`,
   the post-merge `shutil.copytree` step is unchanged — it now copies the
   *merged* tree instead of the *fast-forwarded* tree. Same code path.

3. **`upstream_sha` semantics.** After merge, `upstream_sha` records the parent
   clone's `HEAD` (the local merge commit, or the unchanged remote tip if no
   local divergence existed). This matches the per-skill-repo branch's behaviour
   today — both record local HEAD, which after a successful merge points at code
   that includes upstream.

   We do **not** add a separate `remote_sha` field. Out of scope; the per-skill-repo
   branch doesn't track it either.

4. **Dirty working tree handling.** `git merge` refuses on a dirty working tree
   in the parent clone. Surface that as a conflict (same `GitError` path) with an
   error message naming the parent clone and instructing the user to commit or
   stash their working changes there. No auto-stash. No `--no-edit` override of
   that behaviour (the existing `merge` helper already passes `--no-edit`).

5. **TUI state column for monorepo skills** (`src/agent_toolkit_tui/skill_state.py`).
   In `build_skill_rows`, branch on `entry.parent_url is not None` **before** the
   existing `is_git_repo(canonical)` check:

   ```python
   if not canonical.exists():
       state = "library" if scope == "project" else "missing"
   elif entry.parent_url is not None:
       # Monorepo skill — state lives in the parent clone, not the symlinked subpath.
       owner, repo = entry.source.split("/", 1)
       parent_dir = parent_clone_path(owner, repo, ref=entry.ref, env=None)
       if not skill_git.is_git_repo(parent_dir):
           state = "copy"   # parent clone missing → genuinely uneditable
       else:
           wt = skill_git.status(parent_dir, env=None)
           state = "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY else "clean"
   elif not skill_git.is_git_repo(canonical):
       state = "copy"       # plain-file install (npx skills add --copy)
   else:
       wt = skill_git.status(canonical, env=None)
       state = "dirty" if wt == skill_git.GitWorkingTreeStatus.DIRTY else "clean"
   ```

   The `"copy"` literal stays in the enum and the styling map — it remains the
   correct label for the **genuine** copy-mode install (plain files, no `.git/`
   anywhere, used by `npx skills add --copy` consumers and as the
   symlink-fallback materialisation when the parent clone is missing/lost).
   Monorepo skills with a healthy parent clone now report `clean` / `dirty`.

   The `app.py:306` install-button gate (`if row.state in ("missing", "copy"):`)
   keeps working as-is: monorepo skills that used to appear as `copy` will now
   appear as `clean` or `dirty`, both of which are install-eligible — which is
   correct, since they have a real git history we can install from.

6. **Tests** (`tests/test_cli/test_skill_update_monorepo.py` for `update`;
   `tests/test_tui/test_skill_state.py` for the TUI fix):
   - **New:** `test_update_monorepo_merges_local_and_upstream_commits` — commit
     a local change to the parent clone's `main`, commit a non-conflicting
     change upstream, run `skill update`, assert exit 0 and both changes
     present in the library canonical.
   - **New:** `test_update_monorepo_surfaces_real_merge_conflict` — commit
     conflicting changes locally and upstream to the same line, run `skill
     update`, assert non-zero exit, error names the parent clone path, and
     the parent clone is left mid-merge (so the user can resolve).
   - **New:** `test_update_monorepo_refuses_dirty_working_tree` — leave an
     uncommitted change in the parent clone, run `skill update`, assert
     non-zero exit and a message telling the user to commit/stash in the
     parent clone.
   - **Keep:** the two existing tests (clean fast-forward case, copy-mode
     re-copy case). Both should still pass — `merge` of a fast-forwardable
     branch produces the same result as `pull --ff-only`.
   - **New (TUI):** `test_build_rows_monorepo_clean_when_parent_clean` —
     add a monorepo skill via the CLI, run `build_skill_rows`, assert the
     row's `state == "clean"`.
   - **New (TUI):** `test_build_rows_monorepo_dirty_when_parent_has_uncommitted_change`
     — add a monorepo skill, write to a file in the parent clone, run
     `build_skill_rows`, assert `state == "dirty"`.
   - **New (TUI):** `test_build_rows_monorepo_dirty_when_parent_has_local_commit`
     — add a monorepo skill, commit a local change in the parent clone,
     run `build_skill_rows`, assert `state == "dirty"` (a clone ahead of
     upstream is considered dirty for our purposes — same convention as
     per-skill repos, which call `git status --porcelain` and treat any
     non-empty result as dirty; commits ahead don't show up there, so we
     match that existing behaviour exactly, and ahead-of-upstream surfacing
     is the open question in the §Open questions block).
   - **New (TUI):** `test_build_rows_monorepo_copy_when_parent_missing` —
     simulate a deleted `_parents/<owner>/<repo>/` directory (e.g. user
     `rm -rf`'d it), assert `state == "copy"` (the existing fallback label,
     used now only for genuinely uneditable installs).
   - **Keep:** existing TUI state tests for `clean` / `dirty` / `missing` /
     `library` rows. They run on per-skill-repo entries and must not regress.

## Out of scope

- **`skill push` for monorepo skills.** Still rejected per PR #177 (`read_only: true`).
  Sharing back upstream is a fork workflow; this spec doesn't change that.
- **A `--ff-only` opt-in flag** for users who want the old strict behaviour. If
  someone asks, a separate issue. Default is the more useful behaviour.
- **Tracking `remote_sha` independently of local HEAD.** Per-skill-repo update
  doesn't do this either; revisit holistically if needed.
- **Auto-stash of dirty working tree.** Surfacing the conflict is the right
  failure mode; auto-stashing hides intent and risks lost work.
- **Retiring `skill_git.pull_ff_only`**. The helper stays — it might be useful
  for `skill reset` or future ff-only flows. It just stops being called from
  `update_cmd.py`.
- **Lock file shape changes.** No new fields. `read_only`, `parent_url`,
  `skill_path`, `upstream_sha`, `extras.materialised` all stay as-is.

## Decisions (locked-in)

- **Three-way merge by default for monorepo entries.** Aligns with per-skill-repo
  semantics. The two `update` branches converge except for the symlink-vs-copy
  materialisation step at the end.
- **No new lock fields.** This is a behaviour fix, not a model change. Old lock
  files keep working; new behaviour is fully implicit from the existing
  `parent_url is not None` discriminator.
- **`read_only` continues to gate `push` only.** Not local edits, not merges,
  not the TUI state column.
- **TUI `state` column for monorepo skills reports `clean` / `dirty`.** Derived
  from the parent clone's `git status`, matching per-skill-repo semantics.
  The `"copy"` literal stays in the enum but its meaning narrows: it now means
  "genuinely uneditable — no git history available", which applies to
  plain-file installs (e.g. `npx skills add --copy`) and the edge case where a
  monorepo skill's parent clone has been deleted. Healthy monorepo skills
  never show `copy`.
- **Error messages name the parent clone path.** Users editing a monorepo skill
  are working in `<library>/_parents/<owner>/<repo>/...`; they need to know to
  cd there to resolve conflicts. Generic "merge conflict" messages are not
  enough.
- **No `git status --porcelain` precheck**. Let `git merge` itself refuse on a
  dirty tree — its error message is the authoritative one, and a precheck
  duplicates logic. We just translate the `GitError` into a user-friendly
  message.
- **Conflicts leave the parent clone mid-merge.** Standard git workflow: user
  resolves with `git mergetool` / edits / `git commit`, then re-runs
  `skill update <slug>` (which on a clean tree post-resolve is a no-op fetch +
  fast-forward of the merge commit). Document this in the conflict message.
- **Copy-mode behaviour for conflicts.** If the parent merge fails, we **do not**
  re-copy. The library canonical stays pointing at the pre-merge state, which
  is the safer outcome (last known good copy). The user resolves in the parent
  clone; the next successful `update` will re-copy.

## Sequencing (single PR)

| Step | File(s) | Risk | Lands alone? |
|---|---|---|---|
| 1. Replace `pull_ff_only` with `fetch` + `merge` in monorepo branch | `commands/skill/update_cmd.py` | low | yes |
| 2. Refine error message to name parent clone path | same file | trivial | with step 1 |
| 3. Add three new CLI tests | `tests/test_cli/test_skill_update_monorepo.py` | low | with step 1 |
| 4. Branch TUI `build_skill_rows` on `parent_url`; derive state from parent clone | `src/agent_toolkit_tui/skill_state.py` | low | yes (independent of step 1, but ship together) |
| 5. Add four new TUI state tests | `tests/test_tui/test_skill_state.py` (or wherever build_skill_rows tests live) | low | with step 4 |
| 6. Update README / cli.md to note monorepo skills are locally editable; TUI column documents `clean`/`dirty` for monorepo entries | docs | trivial | last |
| 7. Note the spec supersession at the top of `2026-05-21-skill-add-monorepo-design.md` | docs | trivial | last |

One PR, two coupled fixes. Each step is one commit on the branch for review
legibility. Steps 1–3 (CLI update) and steps 4–5 (TUI state) are technically
independent, but they MUST ship together — landing only the CLI fix leaves the
TUI lying about whether your edits are visible; landing only the TUI fix
exposes a `dirty` state that the user can't actually clear with `update`.

## Architecture / data flow (after)

```
skill update find-skills              (entry.parent_url is not None)
       │
       ▼
resolve parent clone:
  <library>/_parents/vercel-labs/skills/
       │
       ├─► git fetch origin --prune
       │
       ├─► git merge --no-edit origin/main
       │     │
       │     ├─ clean fast-forward (no local commits) ───┐
       │     ├─ real three-way merge (local commits,    │
       │     │   non-conflicting upstream) ─────────────┤── proceed
       │     ├─ merge conflict ──► error: name parent  │
       │     │   clone path, exit 1, leave mid-merge   │
       │     └─ dirty working tree ──► error: name    │
       │         parent clone path, exit 1            │
       │                                              ▼
       ├─► if materialised == "copy":  re-copy <subpath> → library canonical
       │   (symlink case: no-op, library auto-sees new content)
       │
       └─► entry.upstream_sha = head_sha(parent_dir)
           write_lock(...)
           echo "<slug>: updated (parent <source> @ <ref>)"
```

Compare with the **per-skill-repo** branch — same shape, no materialisation step:

```
skill update journal                  (entry.parent_url is None)
       │
       ▼
resolve canonical:
  <library>/journal/
       │
       ├─► git fetch
       ├─► git merge --no-edit origin/main
       │     (conflict surfaced same way)
       └─► entry.local_sha + upstream_sha updated
           write_lock(...)
```

The two branches converge. That's the point.

## Definition of done

- `skill update <slug>` for a monorepo skill performs `git fetch` + `git merge
  --no-edit origin/<ref>` on the parent clone instead of `git pull --ff-only`.
- A user can commit local edits to the parent clone's `main` branch and
  `skill update <slug>` will merge upstream into their branch — exit 0 on a
  clean three-way merge, exit 1 on a real conflict.
- On conflict, the error message names the parent clone path
  (`<library>/_parents/<owner>/<repo>/`) and tells the user to resolve there.
- On a dirty working tree, `skill update` fails with a message naming the parent
  clone and instructing the user to commit/stash.
- Copy-mode entries (`extras.materialised == "copy"`) re-copy from the
  parent only after a successful merge; on conflict, the library canonical is
  left at its prior state.
- Existing tests in `test_skill_update_monorepo.py` continue to pass.
- Three new CLI tests cover: local+upstream merge, real conflict, dirty tree.
- TUI `build_skill_rows` reports `clean` / `dirty` for monorepo entries with a
  healthy parent clone, derived from `git status` on the parent — same
  semantics as per-skill repo entries. The `copy` label is only emitted when
  the parent clone is genuinely missing or for plain-file installs.
- Four new TUI state tests cover: clean monorepo, dirty (uncommitted),
  dirty-on-local-commit (matches existing `git status --porcelain` convention),
  and parent-missing fallback to `copy`.
- The TUI install-button gate (`app.py:306`) continues to behave correctly:
  monorepo skills no longer get blocked by a spurious `copy` state.
- `2026-05-21-skill-add-monorepo-design.md` carries a top-of-file note pointing
  at this spec as the superseding decision for both `update` and the TUI state
  column.
- README / `cli.md` note that monorepo skills are locally editable, that
  `skill update` performs a three-way merge, and that the TUI's `state` column
  for monorepo skills means the same thing it does for per-skill repos.

## Lock file / migration

- **No lock schema changes.** No fields added, none removed, none renamed.
- **No migration.** Existing locks work unchanged. Old `find-skills` entries
  with `upstream_sha` set from a prior `pull --ff-only` continue to work; the
  next `update` simply produces a merge commit (or remains a fast-forward) and
  updates `upstream_sha` to the new HEAD.
- **Round-trip with `npx skills`.** Unchanged. We still emit the same keys.
  Behaviour difference is invisible to the lock format.

## Risks / known gotchas

- **User confusion about "where do I edit?"** The library canonical is a symlink
  (`<library>/find-skills`); the **real files** live in
  `<library>/_parents/<owner>/<repo>/<subpath>/`. Editing through either path
  hits the same inodes, but git operations only make sense from inside the
  parent clone. The conflict error message is the primary teaching moment;
  README is the secondary one.
- **Merge commits in the parent clone.** Users who don't want merge commits can
  rebase manually (`git -C <parent_clone> rebase origin/main`) before
  `skill update`. We don't offer `--rebase` — keep one path. Document.
- **Copy-mode (Windows / symlink-refusing platforms).** After a merge, we
  `shutil.rmtree(library_dir)` + `shutil.copytree(...)`. If the user was
  editing files through the **library** path (not the parent clone), those
  edits were already being written to the copy — and they get clobbered by
  the re-copy. This is a pre-existing gotcha from PR #177; the new merge
  semantics don't change it. Document: in copy mode, edit in the parent clone,
  not the library.
- **`materialised: "copy"` + conflict.** New decision: don't re-copy on
  conflict. This is a behaviour change in one edge case — previously
  `pull_ff_only` would either succeed or fail; now `merge` can fail
  mid-conflict and leave the parent dirty. Library canonical must stay at
  last-known-good. Tests cover this.
- **`git merge` opens an editor by default.** The existing `skill_git.merge`
  helper passes `--no-edit`; no editor will open in CI or scripted use. Good.
- **Detached HEAD in parent clone.** If a user `git checkout <sha>` inside the
  parent clone, `merge origin/<ref>` will succeed but they're now on a
  detached branch. Out of scope to defend against; it's their working tree.
- **Reflog as safety net.** The parent clone is a real git repo with reflog;
  users who mess up a merge can `git reset --hard ORIG_HEAD`. Mention in
  README troubleshooting.
- **TUI `copy` label semantics narrow, not removed.** Pre-fix: any skill
  without `.git/` in its canonical → `copy`. Post-fix: only plain-file
  installs (no parent clone, no canonical `.git/`) and the
  parent-clone-missing edge case → `copy`. Anyone scripting against
  `SkillRow.state == "copy"` keeps working — they were asking about
  uneditability, and we now return that more accurately. No `State` enum
  member is removed; the styling map in `widgets/skill_grid.py:31` keeps
  rendering `copy` in blue.
- **TUI state for monorepo with `materialised: "copy"`.** Same rule as
  symlink-mode: derive from the **parent clone**, not the library canonical.
  Even when the library canonical is a plain-file copy, the parent clone
  still exists at `<library>/_parents/<owner>/<repo>/` and is the authoritative
  source of truth for "have I edited this?" / "is this in sync with upstream?".

## Open questions (decide in plan, not here)

- Should `skill status <slug>` for monorepo entries surface "local commits
  ahead of upstream" the way it does for per-skill repos? Probably yes,
  but separate work — file as follow-up if not already covered.
- Should the TUI introduce a separate `monorepo` badge or column to indicate
  the skill's parent-shared nature (orthogonal to `clean`/`dirty`)? The
  current spec doesn't add one — `parent_url` is already in the lock and
  could drive a future column. File separate UX spec if useful.
