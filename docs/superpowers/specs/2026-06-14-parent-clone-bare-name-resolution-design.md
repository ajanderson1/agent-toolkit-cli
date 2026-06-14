# Spec — #412: reconcile legacy bare-named parent-clone path resolution

**Issue:** #412 · **Size:** M · **Date:** 2026-06-14

## Problem

`agent-toolkit-cli skill update -g` reports `parent clone missing or not a git
repo at .../_parents/<owner>/<repo>@<ref>` for every monorepo parent that was
materialised on disk **without** the `@<ref>` suffix (~19 skills in a real run).
The clones are not missing — they are live git repos that the canonical
symlinks point into. `skill doctor -g` reports `✓ all clean` for the same
machine. The two surfaces disagree about where the parent clone lives.

### Root cause

`skill_paths.parent_clone_path(owner, repo, ref=ref)` computes the leaf as:

```python
leaf = repo if ref is None else f"{repo}@{ref}"   # skill_paths.py:163
```

The `@<ref>` suffix has been in the code since #177. What changed is the
**lock**: older entries were added when `ref` was unset (`None`), so the parent
was cloned to a **bare** `<repo>` dir. Later, `ref` was backfilled to `'main'`
(by `update`/`status` ref-detection). Lookup now computes `<repo>@main`, which
does not match the bare `<repo>` dir on disk → "missing or not a git repo".

This is incidental to clone *age*, not a first-vs-third-party distinction. Any
clone — first- or third-party — created before its `ref` was populated carries
the legacy bare name and fails the same way.

### Why doctor disagrees

Doctor's per-skill check validates that the **canonical symlink resolves** to a
real directory; for an existing canonical it never recomputes
`parent_clone_path` at validation time. Its reclone fix-action
(`_make_monorepo_reclone_action`) *does* compute the suffixed path, but is gated
behind `if canonical.exists(): return` — so it short-circuits before the path is
ever consulted. Update, by contrast, recomputes the suffixed path on every run
and fails. The resolvers must be reconciled so they cannot diverge again.

## Goal

Both first- and third-party monorepo parents must pull + merge regardless of
when they were cloned, and `doctor` + `update` (+ `status` / `push` / `reset`)
must resolve the parent **identically**.

## Design

Two phases, per the approved fix direction ("probe + doctor cleanup"). Phase 1
is the real fix; Phase 2 is optional non-destructive tidiness.

### Phase 1 — probe-both shared resolver

A new function reconciles resolution across every read/update surface.

**New helper — `skill_paths.resolve_existing_parent_clone`:**

```python
def resolve_existing_parent_clone(
    owner: str, repo: str, *, ref: str | None, parent_url: str,
    env: dict[str, str] | None = None, root: Path | None = None,
) -> Path:
    """Locate an existing monorepo parent clone, tolerating the legacy
    bare-named layout.

    Prefers the canonical suffixed path (`<repo>@<ref>`). Falls back to the
    bare `<repo>` path ONLY when the suffixed path is absent AND the bare dir
    is a git repo whose origin remote matches `parent_url`. When neither
    exists, returns the suffixed path — so a *fresh* clone still lands in the
    canonical scheme and behaviour is unchanged for new clones.
    """
    suffixed = parent_clone_path(owner, repo, ref=ref, env=env, root=root)
    if skill_git.is_git_repo(suffixed):
        return suffixed
    if ref is not None:  # a suffix was applied — a bare legacy dir may exist
        bare = parent_clone_path(owner, repo, ref=None, env=env, root=root)
        if skill_git.is_git_repo(bare) and _remote_matches(bare, parent_url, env):
            return bare
    return suffixed
```

Semantics:

- **Suffixed is the default and the preferred existing path.** Fresh clones
  target `<repo>@<ref>`; no behaviour change for new clones (confirmed intent).
- **Bare is a legacy-only fallback** — taken only when the suffixed path does
  not exist *and* the bare dir's `origin` remote matches `parent_url`. The
  remote-match guard prevents an unrelated `_parents/<owner>/<repo>` dir from
  being mistaken for this skill's parent.
- When `ref is None`, the suffixed and bare paths are identical, so the probe
  collapses to the single existing behaviour.

**URL comparison reuses doctor's normaliser.** `skill_doctor._normalise_git_url`
(and its `_SSH_GIT_URL_RE` / `_HTTPS_GIT_URL_RE` / `_SSH_URL_RE` regexes) already
collapses SSH/HTTPS/local forms to `host/path` for equality. To make the
resolver and doctor compare URLs the *same* way, promote `_normalise_git_url` +
its regexes to a shared module (`skill_git.py`, beside `remote_url`), re-export
the name from `skill_doctor` for its existing callers, and define:

```python
def _remote_matches(repo: Path, parent_url: str, env) -> bool:
    try:
        actual = skill_git.remote_url(repo, env=env)
    except skill_git.GitError:
        return False
    return normalise_git_url(actual) == normalise_git_url(parent_url)
```

`_remote_matches` lives in `skill_paths.py` (or `skill_git.py`) so all callers
share one definition. (`skill_git.remote_url` and `skill_git.is_git_repo`
already exist — no new git wrappers needed.)

**Call-site conversions** — these five surfaces switch from
`parent_clone_path(...)` to `resolve_existing_parent_clone(...)` for *locating*
an existing clone:

| Surface | File:line | Notes |
|---|---|---|
| update | `commands/skill/update_cmd.py:83` | the reported failure site |
| status | `commands/skill/status_cmd.py:90` | |
| push | `commands/skill/push_cmd.py:257` | returns the dir |
| reset | `commands/skill/reset_cmd.py:77` | |
| doctor reclone fix | `skill_doctor.py:387` | inside `_make_monorepo_reclone_action` |

Each passes `parent_url=entry.parent_url` and the same `ref` / `root` it
currently passes to `parent_clone_path`.

**Untouched — the create path stays canonical.** `skill_install.py:414`
(`ensure_*_canonical`) keeps `parent_clone_path(...)` as the **cache key /
clone target**: a fresh clone must materialise at the suffixed name, and the
existing comment there already documents the cache-key contract. `agent` /
`pi-extension` parent-clone paths (`agent_paths.agent_parent_clone_path`,
`pi_extension_paths`) are the create-path for those kinds and likewise stay on
`parent_clone_path`. (Agents/pi-extensions do not exhibit this bug — see Out of
scope for why their read paths can't diverge.)

### Phase 2 — doctor alias-symlink cleanup (optional tidiness)

A new `FindingType` `legacy_bare_parent`. During the doctor sweep, for each
monorepo lock entry whose `ref is not None`, if the **bare** `<repo>` dir is a
git repo whose remote matches `parent_url` AND the **suffixed** `<repo>@<ref>`
path does not yet exist, doctor emits a `legacy_bare_parent` finding. Its
fix-action creates a `<repo>@<ref> → <repo>` **alias symlink** (relative, in the
same `<owner>/` dir), mirroring the manual 2026-06-14 workaround:

- Non-destructive: the bare dir stays the real git repo; nothing re-clones.
- Reversible: `rm` the symlink.
- Idempotent: if the suffixed path already exists (alias or real), no finding.
- Low priority: ordered after the existing functional findings.

On a machine where the 15 manual aliases already exist, doctor reports nothing
to do. The probe-both resolver already makes `update` work without this; Phase 2
only normalises the on-disk layout for tidiness.

## Acceptance criteria

1. `resolve_existing_parent_clone` returns the **suffixed** path when it exists;
   the **bare** path when only the bare dir exists *and* its remote matches
   `parent_url`; and the **suffixed** path (as the fresh-clone target) when
   neither exists. RED-proven against the current single-path behaviour.
2. The remote-match guard rejects a bare dir whose `origin` does **not** match
   `parent_url` (returns the suffixed path instead) — proven with a colliding
   unrelated repo at the bare path.
3. `skill update -g` succeeds against a legacy bare-named parent clone (the #412
   repro) — no "parent clone missing" — and still pulls + merges correctly.
4. `status`, `push`, and `reset` locate a legacy bare-named parent clone
   identically (no "missing" / no divergent path).
5. Fresh clones still materialise at `<repo>@<ref>` — `skill_install` create
   path is unchanged; a new monorepo skill add lands in the suffixed scheme.
6. `_normalise_git_url` is promoted to a shared module and re-exported so
   doctor's existing callers are unbroken; resolver and doctor compare URLs via
   the same function (no second normaliser).
7. (Phase 2) doctor emits `legacy_bare_parent` for a bare-named parent with a
   matching remote and no suffixed path; its fix-action creates a
   `<repo>@<ref> → <repo>` alias symlink; idempotent when the alias/suffixed
   path already exists; no finding when remote does not match.
8. Full suite green (the 2 known whitelisted HOME-isolation env fails excepted);
   ruff net-0-new, mypy net-0-new.

## Test surface

- `tests/test_cli/test_skill_paths.py` — `resolve_existing_parent_clone`: suffixed-wins,
  bare-fallback-on-match, bare-rejected-on-mismatch, neither-exists-returns-suffixed,
  `ref is None` collapse. Hermetic temp `_parents/` git repos (init bare dir, set
  `origin` remote to match / mismatch `parent_url`).
- `tests/test_cli/` update/status/push/reset — legacy-bare repro resolves and the
  command succeeds (extend existing monorepo command tests; `test_skill_owned_monorepo.py`
  has the parent-clone fixtures to model from).
- doctor test — `legacy_bare_parent` finding emitted + alias-symlink fix applied +
  idempotency + remote-mismatch no-finding.
- A focused test asserting `skill_install` create path still targets the suffixed
  name (guards AC5 against regression).

## Out of scope

- **Renaming** bare dirs to suffixed (rejected: destructive, interrupt window).
  Phase 2 uses non-destructive alias symlinks only.
- **Agent / pi-extension** parent resolution. These kinds DO backfill `ref`
  (`entry.ref = ref` in their `update`/`reset` commands) and DO compute the
  suffixed parent path in their `add` command — so at first glance they look
  vulnerable. They are not: their `update`/`status`/`push`/`reset`/`doctor`
  read paths operate on the **canonical directory directly**
  (`skill_git.is_git_repo(canonical)`), because those kinds materialise the
  canonical as a per-slug git clone rather than a symlink into a shared
  `_parents/` parent. Only the skill kind recomputes `parent_clone_path` on its
  read path (symlink-into-shared-parent model), so only the skill kind can
  diverge. `agent_parent_clone_path` / `pi_extension_paths` are used solely as a
  create-time clone target, where the canonical suffixed name is correct. Left
  on `parent_clone_path`.
- **#413** (scope-opacity: surfacing which scope/lock was resolved when no
  `-g`/`-p` flag is given) — separate open enhancement, not this bug.
- Removing the manual alias symlinks already on AJ's machine — they are
  forward-compatible with the resolver and Phase 2 (idempotent).
