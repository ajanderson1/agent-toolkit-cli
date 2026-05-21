# Spec — `skill add`: monorepo skills (`--skill`, subpath, skills.sh URLs)

**Issue:** #162
**Branch:** `feat/162-skill-add-monorepo`
**Mode:** `--auto`

> **Superseded in parts by:**
> [`2026-05-22-skill-update-monorepo-three-way-merge-design.md`](2026-05-22-skill-update-monorepo-three-way-merge-design.md)
> changes the `update` paragraph from `git pull --ff-only` to `fetch` + `merge`
> and fixes the TUI `state: copy` label for monorepo skills.

## Goal

Let one `skill add` invocation install a single skill from a parent repo that contains many. Three input shapes must work and produce the same lock entry:

```
agent-toolkit-cli skill add vamseeachanta/workspace-hub --skill mkdocs
agent-toolkit-cli skill add vamseeachanta/workspace-hub/mkdocs
agent-toolkit-cli skill add https://www.skills.sh/vamseeachanta/workspace-hub/mkdocs
```

All three install only the `mkdocs/` subfolder of the parent repo. The on-disk lock file is byte-compatible with `npx skills add` for these entries.

## Anchor to the v2.2 code shape

Issue #162 was drafted before the v2.2 library/install split landed in `1dfff61`. The spec re-anchors on the **current** code:

| Concept | Where today |
|---|---|
| Library canonical (global) | `library_skill_path(slug)` → `~/.agent-toolkit/skills/<slug>/` |
| Project canonical | `<project>/.agents/skills/<slug>/` |
| Per-agent symlinks | created by `skill_install.apply()` |
| `LockEntry.skill_path` | already exists, defaults to `"SKILL.md"` |
| `skill add` (current) | clones source into library, writes lock entry |
| `skill install` (current) | creates agent-visibility symlinks for a library skill |

So the work splits cleanly: **`skill add` learns about monorepos**, `skill install` is unchanged.

## In scope

1. **Parser** (`skill_source.py`) — accept three new input shapes that resolve to a parent repo + a subskill identifier:
   - `owner/repo/<subpath>` shorthand (third path segment).
   - `https://www.skills.sh/<owner>/<repo>/<skill>` URLs.
   - `--skill <name>` flag combined with `owner/repo` or any GitHub URL.
   - (`/tree/<ref>/<subpath>` URLs already parse; the new install path consumes them.)
2. **`skill add`** (`commands/skill/__init__.py`) — when the parsed source has a subpath or skill_name:
   - Clone the **parent** repo into `library_root() / "_parents" / "<owner>" / "<repo>"`. Re-use across multiple `skill add` calls into the same parent.
   - If `skill_name` was supplied without an explicit subpath, walk the clone for `SKILL.md` files and resolve the one whose frontmatter `name:` matches. Mismatch ⇒ error listing available names.
   - The skill's library canonical (`~/.agent-toolkit/skills/<slug>/`) is created as a **symlink** to `<parent_clone>/<subpath>/`. Fall back to copy if the platform refuses symlinks.
   - Default slug: `skill_name or basename(subpath)` (never the parent repo name — collides across monorepos).
3. **`LockEntry`** — two new fields (additive, byte-compat with vercel-labs keys on disk):
   - `parent_url: str | None` → `parentUrl` on disk. Set only when the parent repo differs from the skill's own repo (i.e. monorepo case).
   - `read_only: bool = False` → `readOnly` on disk. `skill push` rejects when true.
   - `skill_path` continues to record the subfolder (already plumbed; default `"SKILL.md"` for repo-root skills, `"<subpath>"` for monorepo skills).
4. **`skill update` / `skill push`** (`skill_git.py` + `commands/skill/update_cmd.py` + `commands/skill/push_cmd.py`):
   - `update <slug>` — if `parent_url` is set: `git -C <parent_clone> pull --ff-only`; the symlink stays valid. Otherwise the existing per-skill merge path.
   - `push <slug>` — if `read_only`: fail with a clear message naming `parent_url`. No silent success.
5. **README** — document `--skill` and skills.sh URL form in the Skills section.

## Out of scope

- `skill push` *into* a monorepo subpath. Monorepo entries are `read_only: true` and rejected at push. If the demand appears, a separate issue handles it.
- TUI skill-browsing surface against skills.sh.
- Treating parent repos as first-class library entries in `inventory`.

## Decisions (locked-in)

- **Symlink (with copy fallback)**, not a fresh per-skill clone. The parent clone is the single source of truth; the per-skill library entry is a thin view into it. Update is then `git pull` on the parent. `npx skills` copies; we accept the divergence for the perf/simplicity win and because our `update` semantics need the live parent.
- **`skill push` for monorepo skills is rejected** with a clear message. Pushing into a parent's subpath is a different code path; deferred.
- **Slug default**: `skill_name or basename(subpath)`. Not the parent repo name (would collide).
- **`--skill` together with `/tree/<ref>/<subpath>` is rejected** as ambiguous — subpath already pins the folder.
- **Parent cache lives under the library**, not in a separate hidden directory. `library_root() / "_parents" / "<owner>" / "<repo>"` keeps everything inside `AGENT_TOOLKIT_SKILLS_ROOT`'s blast radius, including for `--toolkit-repo` overrides.
- **Multiple skills from the same parent share one clone**. Each `skill add` from the same parent owner/repo into the same library reuses the existing parent clone (idempotent `git fetch` on second add).

## Sequencing (independently landable)

| Step | File(s) | Risk | Lands alone? |
|---|---|---|---|
| 1. Parser changes | `skill_source.py` + tests | low | yes (no behaviour change) |
| 2. Lock fields | `skill_lock.py` + tests | low (additive) | yes |
| 3. `skill add` monorepo path | `commands/skill/__init__.py`, new `skill_install` helper, fixtures + tests | medium | needs Step 1 + Step 2 |
| 4. `update`/`push` branch | `skill_git.py`, `update_cmd.py`, `push_cmd.py` + tests | low | needs Step 3 |
| 5. README + cli.md | docs | trivial | last |

This PR ships 1+2+3+4+5 together since the issue's "definition of done" requires the full path. Each step is a separate commit on the branch for review legibility.

## Architecture / data flow

```
skill add vamseeachanta/workspace-hub --skill mkdocs
       │
       ▼
ParsedSource(type='github', url='https://github.com/vamseeachanta/workspace-hub',
             owner_repo='vamseeachanta/workspace-hub', ref=None,
             subpath=None, skill_name='mkdocs')   ← new field
       │
       ▼
skill add (monorepo branch):
       │
       ├─► parent clone:  library_root()/_parents/vamseeachanta/workspace-hub/
       │       (git clone if absent; git fetch if present)
       │
       ├─► resolve subpath:  walk *.toolkit.yaml + SKILL.md frontmatter
       │       for `name: mkdocs` → returns subpath 'mkdocs'
       │
       ├─► library canonical:  library_root()/mkdocs/ → symlink to
       │       library_root()/_parents/vamseeachanta/workspace-hub/mkdocs/
       │
       └─► lock entry (library lock):
              source         = 'vamseeachanta/workspace-hub'
              sourceType     = 'github'
              skillPath      = 'mkdocs'
              parentUrl      = 'https://github.com/vamseeachanta/workspace-hub'
              readOnly       = true
              upstreamSha    = <head sha of parent clone>
```

`skill install <slug>` is unchanged: it sees a library canonical (which happens to be a symlink) and creates per-agent symlinks pointing at it.

## Lock file shape (round-trip with npx skills)

`vercel-labs/skills`'s lock includes `skillPath` (already supported). It does not currently emit `parentUrl` or `readOnly` — these are our additive extras. The lock reader preserves unknown keys, so a lock file written by us is readable by `npx skills` with degraded fidelity (it loses the `read_only` guard) — and a lock written by `npx skills` is readable by us (we infer `parent_url` from `sourceUrl` when `skillPath != 'SKILL.md'`, and `read_only` defaults to `false`).

Migration of an existing lock file: none required. Old entries (`skillPath = "SKILL.md"`, no `parentUrl`) behave exactly as today — `update` uses the existing merge path, `push` is allowed.

## Definition of done

- `skill add owner/repo --skill <name>` installs the named subfolder; library lock has `skillPath=<subpath>` and `readOnly=true`.
- `skill add owner/repo/<subpath>` works (explicit form).
- `skill add https://www.skills.sh/<owner>/<repo>/<skill>` works (URL form, equivalent result).
- `skill add <repo>/tree/<ref>/<subpath>` works (URL with ref form).
- `skill update <slug>` for monorepo skills pulls the parent and refreshes the symlinked content without touching unrelated skills.
- `skill push <slug>` for monorepo skills fails with a message naming the parent URL.
- Lock file is round-trip compatible with `npx skills` for monorepo entries.
- New tests pass:
  - `tests/test_cli/test_skill_source_monorepo.py`
  - `tests/test_cli/test_skill_add_monorepo.py` (fixture parent repo with two `SKILL.md` files)
  - `tests/test_cli/test_skill_update_monorepo.py`
- README "Skills" section documents `--skill` and the skills.sh URL form.

## Risks / known gotchas

- **Symlinks on Windows.** `Path.symlink_to` requires either elevated privileges or developer mode. Fallback path: copy + record `materialized: 'copy'` extra so `update` knows to re-copy instead of re-pointing. Out of scope to test on Windows, but the fallback exists.
- **Concurrent parent clones.** Two `skill add` calls into the same parent could race. Acceptable: the second one finds the dir present and skips the clone, then `fetch`s. `fetch` is idempotent. No lock file.
- **Parent ref vs skill ref.** A monorepo skill currently has only one `ref` (the parent's). Users wanting "skill at a specific commit" need the parent-cache key to include ref. Use `library_root()/_parents/<owner>/<repo>@<ref>/` when `ref` is set, else `library_root()/_parents/<owner>/<repo>/`.
- **skills.sh URL might 3xx-redirect.** No HTTP fetch at parse time — we parse the URL pattern only. The clone hits GitHub. If skills.sh ever serves skills outside GitHub, we'll add then.
- **Issue text drift.** The issue's "context" paragraph describes the pre-v2.2 model. The plan in this spec supersedes it.
