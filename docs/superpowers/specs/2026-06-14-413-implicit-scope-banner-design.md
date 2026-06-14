# #413 — surface which scope/lock was resolved when no `-g`/`-p` is given

**Issue:** #413 · **Size:** M · **Date:** 2026-06-14

## Problem

When a `skill` read-only verb runs with no `-g`/`-p`, `scope_and_roots`
(`commands/skill/_common.py`) resolves scope **implicitly**: a `skills-lock.json`
in `cwd` silently selects **project** scope; otherwise it falls back to
**global** (the documented #210 read-only default). The resolution is invisible —
nothing tells the user which lock was picked.

Combined with `update_cmd.py` refusing all monorepo entries at project scope
(`monorepo update only supported at global scope`), a bare `skill update` from a
directory whose project lock is all monorepo-backed (the common case — e.g.
`~/Journal`, a 6-skill project lock) is a **guaranteed `exit 1` no-op** with a
misleading message. The user reasonably reads it as "these need `-g`", but `-g`
does not re-scope those 6 entries — it switches to the **global** lock, a
different ~64-skill universe. Nothing surfaces (a) that they were in project
scope, (b) that the project lock holds 6 skills, (c) that `-g` targets a
different set.

This is a **transparency / UX fix**, not a behaviour change. The scope
resolution itself is correct and stays as-is.

## Decisions (settled in brainstorm)

1. **Scope: `skill` only.** The identical implicit-resolution pattern exists in
   `agent`, `mcp`, and `pi_extension` `_common.py`. Those get **follow-up
   issues**, not this change.
2. **Signal lives in `scope_and_roots`.** It returns a 4th element, `implicit`
   (`True` iff neither `-g` nor `-p` was passed). All 6 skill call sites unpack
   it. Only the `skill` helper changes; agent/mcp/pi stay 3-tuple.
3. **Banner on implicit-project only.** When scope was resolved implicitly *and*
   landed on project, print a one-line reminder. Implicit-**global** stays quiet
   (it is the documented default and was not the reported pain).
4. **Improve the monorepo refusal message** in `update` to explain what `-g`
   actually does (switches to the global library set), not just state the
   constraint.

## Approach

### `scope_and_roots` → 4-tuple

```python
def scope_and_roots(global_, project, ctx_project, *, read_only=False):
    if global_ and project:
        raise click.UsageError("use either -g/--global or -p/--project, not both")
    if global_:
        return "global", Path.home(), None, False        # explicit
    if project:
        return "project", None, (ctx_project or Path.cwd()), False  # explicit
    project_root = ctx_project or Path.cwd()
    if read_only and not (project_root / "skills-lock.json").exists():
        return "global", Path.home(), None, True          # implicit → global
    return "project", None, project_root, True            # implicit → project
```

`implicit` is `True` on both fallthrough branches and `False` on both
explicit-flag branches. The two write-path verbs that pass `read_only=False`
still fall through to implicit-project with `implicit=True`; they may ignore it.

### `scope_banner` helper (`commands/skill/_common.py`)

```python
def scope_banner(scope, *, implicit, lock_path, count):
    """Emit a one-line scope reminder to stderr on implicit-project resolution.

    Best-effort and informational: never raises, never affects exit codes.
    Silent unless scope was resolved implicitly AND landed on project — the
    one case (#413) where the user got no signal about which lock was picked.
    """
    if not (implicit and scope == "project"):
        return
    noun = "skill" if count == 1 else "skills"
    click.echo(
        f"Operating on project scope — {lock_path} ({count} {noun}). "
        f"Pass -g to target the global library.",
        err=True,
    )
```

**stderr, deliberately.** The banner is metadata about *where* the verb is
operating, never part of the data stream. Routing it to stderr keeps
`skill list --json` stdout valid JSON and keeps it out of any piped stdout.
There is existing `err=True` precedent in `commands/skill/__init__.py`.

### Wiring

Each of the **six** read verbs sharing `scope_and_roots`
(`list`, `status`, `update`, `reset`, `push`, `doctor`) unpacks the 4-tuple,
reads its lock, then calls `scope_banner(scope, implicit=implicit,
lock_path=lock_path, count=len(lock.skills))` **before** its main output.

- `list`: banner goes to stderr regardless of `--json`, so JSON stdout is
  untouched. Call it before both `_emit_json` and `_emit_table`.
- `status`/`list` already print an *explicit*-`-p`-empty hint; that path has
  `implicit=False`, so no double message.

### `update` monorepo refusal message

Rewrite (current → new):

```
{slug}: monorepo update only supported at global scope
```
→
```
{slug}: monorepo skill — update it at global scope. Note: -g switches to the
  global library (a different set), it does not update this project entry.
```

The banner (above) already tells the user they are in project scope and how
many skills are here; this message clears up the specific `-g` misconception
for monorepo entries.

## Components & boundaries

| Unit | Change | Depends on |
|---|---|---|
| `scope_and_roots` | returns 4-tuple `(scope, home, project_root, implicit)` | nothing new |
| `scope_banner` | new helper, stderr, implicit-project only | `click` |
| 6 read verbs | unpack 4th element, call `scope_banner` pre-output | the two above |
| `update_cmd` refusal | reworded string only | — |

## Error handling

- Banner never raises and never changes exit codes — it is advisory output.
- Empty project lock (`count == 0`) still banners on the implicit path; that is
  still the surprising implicit-project case. It does not collide with the
  existing explicit-`-p`-empty hint, which only fires when `project_flag` is set
  (i.e. `implicit=False`).

## Out of scope

- `agent`, `mcp`, `pi_extension` (follow-up issues — same pattern, same fix).
- Changing the scope-resolution rules themselves (#210 behaviour stands).
- Banner on implicit-**global** resolution.

## Test surface

- `scope_and_roots` returns the correct `implicit` across all four branches
  (explicit `-g`, explicit `-p`, implicit→project, implicit→global).
- `scope_banner`: prints on implicit-project; silent on implicit-global,
  explicit `-p`, explicit `-g`; singular/plural noun; `count == 0` still prints.
- Banner is written to **stderr** — `skill list --json` stdout parses as JSON
  with the banner present on stderr.
- New `update` monorepo-refusal wording asserted.
- End-to-end: bare `skill update` from a cwd with a monorepo-backed project lock
  prints the project banner before the per-skill lines.
```
