# Relocate Project Canonical Out of the Project Tree — Design

**Date:** 2026-05-25
**Status:** Approved (Sections 1–3)
**Supersedes:** the project-canonical layout shipped in v2.9.0 (`docs/superpowers/plans/2026-05-24-project-monorepo-install.md`)

## Goal

Move a project-scope skill's canonical clone (and its monorepo `_parents/` cache)
out of the project tree into a per-project store under the user's home, so the
project tree holds **only** symlinks plus the lock file. This makes uninstall
non-destructive: removing a skill never deletes a clone the user may have edited.

## Motivation

In v2.9.0 the project canonical lives inside the project at
`<project>/.agents/skills/<slug>` — a real git clone for single-skill repos, or a
symlink into `<project>/.agents/skills/_parents/...` for monorepo skills. Two
problems follow from canonical-in-tree:

1. **Uninstall is destructive.** `uninstall()` ends with `shutil.rmtree(canonical)`.
   If the user edited the clone, that work is gone.
2. **The project tree carries git working trees** it shouldn't — clones nested
   under a (typically git-ignored) `.agents/` dir, which muddies the project's own
   VCS state and bloats the tree.

Relocating the canonical to `~/.agent-toolkit/projects/<id>/skills/<slug>` solves
both: uninstall only removes symlinks + the lock entry, and the project tree
contains nothing but symlinks. This mirrors how **global** scope already works
(canonical in the library, agents reach it via symlink) — the two scopes become
structurally uniform, differing only in *where* the canonical store lives.

---

## Section 1 — Path model

### Layout change

| Artifact | Old (v2.9.0) | New |
|---|---|---|
| Project canonical | `<project>/.agents/skills/<slug>` | `~/.agent-toolkit/projects/<id>/skills/<slug>` |
| Project `_parents/` cache | `<project>/.agents/skills/_parents/<owner>/<repo>[@ref]/` | `~/.agent-toolkit/projects/<id>/skills/_parents/<owner>/<repo>[@ref]/` |
| Project lock | `<project>/skills-lock.json` | **unchanged** |
| Per-agent projection symlinks | `<project>/<agent-dir>/skills/<slug>` → canonical | **unchanged location**, now always a real symlink (see Section 2) |

The result: the project tree contains only the lock file and projection symlinks.
The per-project store under `~/.agent-toolkit/projects/<id>/` is git-clone-bearing
and lives entirely outside the project's own VCS.

### `<id>` derivation — sanitized abs path + short hash

`<id>` names the per-project directory under `~/.agent-toolkit/projects/`. It must
be **stable** (same project path → same id across runs) and **collision-free**
(two different project paths must never map to the same id).

```
project_id(project) = "<sanitized-abs-path>-<hash6>"
  sanitized-abs-path = abs path with leading "/" stripped, every os.sep and any
                       character outside [A-Za-z0-9._-] replaced with "-"
  hash6              = sha256(str(project.resolve())).hexdigest()[:6]
```

Example: `/Users/ajanderson/GitHub/projects/ryanair_fares` →
`Users-ajanderson-GitHub-projects-ryanair_fares-a1b2c3`.

The sanitized prefix keeps `doctor` output and on-disk inspection human-readable;
the `hash6` suffix guarantees uniqueness even if two distinct paths sanitize to the
same string. The hash is taken over `project.resolve()` (the real absolute path) so
symlinked or relative invocations of the same project resolve to one id.

### New / changed helpers in `skill_paths.py`

```python
def project_id(project: Path) -> str:
    """Stable, collision-free directory name for a project's skill store.

    Sanitized absolute path + 6-hex-char sha256 suffix. Human-readable for
    doctor output; the hash disambiguates any sanitization collisions.
    """

def project_store_root(project: Path) -> Path:
    """Per-project skill store: ~/.agent-toolkit/projects/<id>/skills.

    Holds project canonical skill dirs AND the project's _parents/ cache.
    Lives under library_root().parent (i.e. ~/.agent-toolkit), OUTSIDE the
    project tree, so removing a skill never touches project files.
    """
    # ~/.agent-toolkit/projects/<id>/skills
    return library_root(env).parent / "projects" / project_id(project) / "skills"
```

`project_store_root` is rooted at `library_root(env).parent` (default
`~/.agent-toolkit`) so it honors `$AGENT_TOOLKIT_SKILLS_ROOT` overrides in tests
the same way the library does — when the env var points the library at a tmp dir,
the per-project store lands beside it under that tmp dir's parent.

**`canonical_skill_dir(scope="project")`** changes from
`project / ".agents" / "skills" / slug` to `project_store_root(project) / slug`.

**`project_parents_root(project)`** changes from `project / ".agents" / "skills"`
to `project_store_root(project)`. (Its callers — `ensure_project_canonical` and,
after the Section 3 fix, `status_cmd` — keep calling it unchanged; only its return
value moves.)

`lock_file_path(scope="project")` is **unchanged** (`<project>/skills-lock.json`).

---

## Section 2 — Symlink projection (universal inversion)

### The old skip rule

`_should_skip_symlink()` currently returns `(True, "universal-project")` for
project-scope **universal** agents (those whose `skills_dir == ".agents/skills"`).
The rationale was that the project canonical *was* `<project>/.agents/skills/<slug>`,
so a universal agent read it directly with no symlink needed.

### The inversion

With the canonical relocated out of the tree (Section 1), there is nothing at
`<project>/.agents/skills/<slug>` for a universal agent to read. So the skip rule
is **removed**: project-scope universal agents now get a per-slug symlink
`<project>/.agents/skills/<slug>` → `~/.agent-toolkit/projects/<id>/skills/<slug>`,
exactly like every non-universal agent already gets
`<project>/.claude/skills/<slug>` → canonical.

### Code touch points in `skill_install.py`

- **`_should_skip_symlink()`**: delete the
  `if cfg.is_universal: ... if scope == "project": return True, "universal-project"`
  branch. Project-universal now falls through to the normal not-skipped path. The
  global-universal behavior (`return True, "universal-global"`, handled via the
  universal bundle link in `apply()`) is **unchanged**.
- **`_linked_agents()`**: remove the special case that treated project-universal
  "linked" as "canonical exists" — it's now a real symlink-existence check like
  every other agent.
- **`apply()`**: no project-universal special path; the standard projection-symlink
  creation handles it.
- **Module header comment (lines 8–11)**: update the four-quadrant table so
  "Project + universal" reads "symlink → external canonical" instead of
  "no symlink (canonical IS the install)".

### Resulting uniform model

Every `(scope × agent)` combination is now **projection symlink → canonical**. The
only axis of variation is where the canonical lives: the library
(`~/.agent-toolkit/skills/<slug>`) for global scope, the per-project store
(`~/.agent-toolkit/projects/<id>/skills/<slug>`) for project scope.

---

## Section 3 — Uninstall semantics, auto-migration, orphan sweep, status fix

### 3a. Uninstall — non-destructive at project scope

Today `uninstall()` ends with an unconditional `shutil.rmtree(canonical)`. Under the
new model that would delete the external clone and any uncommitted work in it.

**Change:** at **project** scope, uninstall removes the projection symlinks and the
project lock entry **only** — it never touches the external canonical. **Global**
scope is unchanged (the library is the SSOT; `rmtree` stays).

```
uninstall(scope="project"):
    apply(plan with target_agents=())          # tears down projection symlinks
    remove slug from <project>/skills-lock.json # lock entry gone
    # external canonical at ~/.agent-toolkit/projects/<id>/skills/<slug> LEFT IN PLACE

uninstall(scope="global"):
    apply(plan with target_agents=())
    shutil.rmtree(canonical)                    # unchanged
```

The now-orphaned external clone is reclaimable by the doctor sweep (3c), but
uninstall itself never destroys it. This is the central payoff of the relocation.

Note: `apply()` only ever *adds/updates* the lock entry (it calls `add_entry` when
`target_agents` is non-empty and never removes), so the lock-entry removal must be
wired into `uninstall()` explicitly via `remove_entry` + `write_lock`
(both already exist in `skill_lock.py`). Global-scope uninstall does not currently
prune the lock either, but that is pre-existing behavior and out of scope here — this
change adds project-scope lock pruning only.

### 3b. Auto-migration — on next `install -p` or `doctor -p`

Existing projects have an in-tree canonical at `<project>/.agents/skills/<slug>`:
a **real clone** (single-skill repos) or a **symlink** into the in-tree `_parents/`
(v2.9.0 monorepo skills). A `migrate_project_canonical(project, slug)` step runs
before normal install/doctor logic for each locked slug:

1. `dest = project_store_root(project) / slug`. `old = project / ".agents" / "skills" / slug`.
2. **If `old` is already a symlink whose target is under `dest`** (or `dest`'s store):
   no-op — already migrated. (Idempotency.)
3. **If `old` is a symlink** (v2.9.0 monorepo projection, holds no work): remove it.
   The subsequent install/doctor logic recreates the new-layout projection symlink
   and re-clones the parent into the new store's `_parents/` (cheaper and safer than
   moving a shared cache mid-flight). The old in-tree `_parents/` cache is left for
   the orphan sweep / can be removed once no in-tree symlink references it.
4. **If `old` is a real directory** (single-skill clone, possibly dirty):
   - If `dest` already exists, rename `dest` → `dest.bak-<UTC-timestamp>` first
     (never overwrite — fail-safe; backups are swept by 3c).
   - `shutil.move(old, dest)` — git history and any dirty working tree travel intact.
   - Recreate `old` as a symlink → `dest` (so any stale references still resolve
     until projections are rebuilt).
5. Migration is **silent on the happy path**, **loud** only when it creates a
   `.bak-` dir (`click.echo` a warning naming the backup).

Migration is idempotent and safe to run on every install/doctor invocation.

### 3c. Orphan sweep in `doctor -p`

`skill doctor -p` gains a pass over `project_store_root(project)`:

- Any `<slug>` dir with **no matching entry** in `<project>/skills-lock.json` is an
  orphan (left by a non-destructive uninstall) → reported and removed.
- Any `*.bak-*` dir (from migration collisions) → reported and removed.
- Honors the existing doctor `--dry-run`/report convention: in dry-run, list what
  *would* be removed without removing; otherwise remove and report counts.

This keeps the per-project store from growing unbounded as skills are
installed/uninstalled over a project's life.

### 3d. `status -p` mislabel fix (folded in)

`status_cmd.py:67` calls `parent_clone_path(owner, repo, ref=entry.ref, env=None)`
with **no `root=`**. At project scope that probes the *global* `_parents` path, finds
nothing, and mislabels every project monorepo skill as `copy`. (Flagged as a
follow-up in PR #233.)

**Fix:** when `scope == "project"`, pass `root=project_parents_root(project)`:

```python
parent_dir = parent_clone_path(
    owner, repo, ref=entry.ref, env=None,
    root=project_parents_root(project_root) if scope == "project" else None,
)
```

`update_cmd` and `reset_cmd` only run their monorepo branch at **global** scope
(they `echo "... only supported at global scope"` and skip otherwise), so they are
correct as-is and out of scope for this change. Enabling project-scope
update/reset against the relocated `_parents` remains a separate future follow-up.

---

## Components and boundaries

| Unit | Responsibility | Depends on |
|---|---|---|
| `project_id` / `project_store_root` (`skill_paths.py`) | Pure path math: map a project path → its external store | `library_root`, `hashlib` |
| `canonical_skill_dir` / `project_parents_root` (`skill_paths.py`) | Resolve project canonical + parents under the new store | `project_store_root` |
| `_should_skip_symlink` / `_linked_agents` / `apply` (`skill_install.py`) | Projection symlink creation; now uniform across scopes | `skill_paths`, `skill_agents` |
| `migrate_project_canonical` (`skill_install.py`) | Idempotent in-tree → external migration, backup-on-collision | `skill_paths`, `shutil` |
| `ensure_project_canonical` (`skill_install.py`) | Calls migration, then clones/symlinks into the new store | `skill_paths`, `skill_git` |
| `uninstall` (`skill_install.py`) | Non-destructive at project scope; rmtree only at global | `skill_paths`, `apply`, lock |
| doctor orphan sweep (`skill_doctor.py` / `doctor_cmd.py`) | Reclaim unreferenced canonicals + `.bak-` dirs | `skill_paths`, project lock |
| `status_cmd` parent-path fix | Probe project `_parents` at project scope | `project_parents_root` |

## Data flow

```
skill install <slug> -p
  → ensure_project_canonical(slug, project)
      → migrate_project_canonical(project, slug)         # idempotent
      → clone/symlink canonical into project_store_root  # new layout
      → write project lock entry (parentUrl/skillPath/read_only)
  → apply(plan)
      → projection symlink <project>/<agent-dir>/skills/<slug> → external canonical
        (universal agents now included — Section 2)

skill uninstall <slug> -p
  → apply(plan, target_agents=())   # remove projection symlinks
  → remove slug from project lock
  # external canonical preserved

skill doctor -p
  → migrate_project_canonical(project, slug) for each locked slug
  → orphan sweep over project_store_root (unreferenced slugs + *.bak-*)

skill status -p
  → for monorepo entries, probe project _parents (root= fix)
```

## Error handling

- **Migration collision** (`dest` exists): back up, never overwrite. Loud warning.
- **Migration of a dirty clone**: moved as-is; git history + uncommitted changes
  preserved. No data loss path.
- **Broken in-tree symlink** during migration: treated as "symlink, holds no work"
  → removed; install logic recreates. (No raise.)
- **Orphan sweep**: dry-run lists, never deletes; live run removes only entries with
  no lock match and `.bak-*` dirs.
- General principle (per project conventions): fail loud on bad state, never
  silently degrade.

## Testing strategy

- **Path math** (`test_skill_paths.py`): `project_id` stability + collision
  resistance (two paths sanitizing alike get different ids via hash); `project_store_root`
  honors `$AGENT_TOOLKIT_SKILLS_ROOT`; `canonical_skill_dir`/`project_parents_root`
  resolve under the new store. Falsifiable literal RHS, not recomputation.
- **Install** (`test_skill_install_project_monorepo.py` + engine tests): canonical
  lands in the external store; project tree holds only symlinks; both single-skill
  and monorepo paths; universal agent now gets a real symlink.
- **Migration**: in-tree real clone → moved to store + symlink left behind; dirty
  clone history survives; `dest`-exists → `.bak-` created; idempotent re-run is a
  no-op; v2.9.0 monorepo in-tree symlink → removed + recreated in new layout.
- **Uninstall**: project-scope uninstall removes symlinks + lock entry, leaves the
  external canonical; global-scope still rmtree's.
- **Doctor orphan sweep**: orphaned canonical + `.bak-` dir detected; `--dry-run`
  reports without deleting.
- **status -p**: project monorepo skill reports `clean`/`dirty` (not `copy`).
- Fixtures: `tests/fixtures/monorepo_skills/`, `scrub_git_env()` from conftest.

## Out of scope (separate future follow-ups)

- Project-scope `skill update` / `skill reset` against the relocated `_parents`
  (still global-only; not required here).
- A standalone `skill gc` / `skill migrate` command (auto-migration + doctor sweep
  cover the need; revisit only if a real second case demands an explicit command).

## Post-ship verification

Renormalize the user's `ryanair_fares` project (mirrors the v2.9.0 step): after
installing the new build, run `skill install -p` (triggers auto-migration), confirm
the canonical now lives under `~/.agent-toolkit/projects/<id>/skills/`, the project
tree holds only symlinks, both skills' `SKILL.md` resolve through `.claude/skills/`,
and the lock still carries `parentUrl`.
