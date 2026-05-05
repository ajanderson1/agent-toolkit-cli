# Spec — project-scope skills work for opencode and pi (#41)

## Problem

Project-scope skill projection is filesystem-deep but not runtime-deep for OpenCode and Pi. The toolkit creates `.opencode/skills/<slug>/` and `.pi/agent/skills/<slug>/` symlinks, but neither runtime registers them. Only Claude works end-to-end at project scope.

Empirical investigation against installed `opencode 1.14.30` and `pi 0.70.6` reveals **two distinct root causes**, both fixable in this PR.

## Root cause 1 — Pi project paths use the wrong directory layout

Pi's source code (`@mariozechner/pi-coding-agent/dist/core/package-manager.js:669-686`):

```js
const globalBaseDir = this.agentDir;                       // ~/.pi/agent  (user)
const projectBaseDir = join(this.cwd, CONFIG_DIR_NAME);    // <cwd>/.pi    (project)
```

Both scopes then look up `<baseDir>/{skills,extensions,prompts,themes}`. Pi never reads project-scope from `<cwd>/.pi/agent/skills`. The user-scope convention `~/.pi/agent/<kind>/` does NOT extend to project scope; project scope is `.pi/<kind>/` directly.

Pi also has **no project-scope `agents` directory** at all — its source iterates `extensions/skills/prompts/themes`, never `agents`. The toolkit's `("pi", "agent") → .pi/agent/agents` for project scope is a dead drop.

## Root cause 2 — OpenCode silently drops skills missing top-level `name:` and won't follow directory symlinks

OpenCode's skill loader (sst/opencode `packages/opencode/src/skill/index.ts`) requires both `name:` and `description:` at the YAML top level — the toolkit's v1alpha2 wrapper has neither (`metadata.name`, `metadata.description`). Same root cause as #40 fixed for codex, plus an extra `name:` field.

Empirical: `opencode debug skill` from a project with a raw v1alpha2 SKILL.md returns nothing for that skill; with a translated shape (top-level `name` + `description`), opencode loads and registers it.

**Additional finding:** OpenCode's directory-walk glob does NOT follow directory symlinks. PR-B (#40) shipped a "slot dir symlinks to cache dir" shape that works for codex. Verified against opencode 1.14.30:

| Slot shape | OpenCode loads? |
|---|---|
| Real `<slug>/` + real `SKILL.md` | ✓ |
| `<slug>/` is symlink to cache dir | ✗ (silently dropped) |
| Real `<slug>/` + `SKILL.md` is file symlink to cache file | ✓ |

So opencode needs a **third slot shape**: real slot directory + file symlink to cache `SKILL.md`. Codex still uses the directory-symlink shape (verified working).

## What changes

### `_support.py` — pi project paths

| Pair | Before | After |
|---|---|---|
| `("pi", "skill")` project | `.pi/agent/skills` | `.pi/skills` |
| `("pi", "agent")` project | `.pi/agent/agents` | **removed** (unsupported pair, falls through `_PROJECT_TARGETS`) |
| `("pi", "pi-extension")` project | `.pi/agent/extensions` | `.pi/extensions` |

User-scope (`_USER_TARGETS`) entries are unchanged — they're correct.

Removing `("pi", "agent")` from `_PROJECT_TARGETS` means `slot_dir("pi", "agent", "project", _)` returns `None`, so attempts to project a pi agent at project scope will surface as `unsupported` cells in `list`/TUI rather than silently writing to a path pi never reads. This matches the issue #30 / PR #33 "fail loud on unsupported pairs" discipline.

Note: `("pi", "agent")` remains in `_USER_TARGETS`, so user-scope projection still works. The `SUPPORTED_PAIRS` derivation (line 54) reads from `_USER_TARGETS.keys()`, so the pair stays "supported" overall — only the project-scope cell becomes a no-op. This is the cleanest expression of "user yes, project no" given the current table shape.

### `_translators.py` — opencode skill translator

Add `_translate_opencode_skill` mirroring `_translate_codex_skill`, but emit BOTH `name:` AND `description:` at the top level. Register `("opencode", "skill")` in `TRANSLATORS`.

```python
def _translate_opencode_skill(record, body):
    fm = {
        "name": _name(record),
        "description": _description(record),
        "agent_toolkit": _wrapper_block(record),
    }
    return _render(fm, body)
```

Where `_name` is a new helper analogous to `_description`:

```python
def _name(record):
    return (record.metadata.get("metadata") or {}).get("name") or ""
```

### `_link_lib.py` — third slot shape for `(opencode, skill)`

Today there are two slot shapes:
- **File-slot** (`opencode` agent/command): cache file → slot symlink → cache file. Slot filename ends with `.md`.
- **Dir-slot** (`codex` skill from PR-B): cache dir contains `SKILL.md`; slot symlink → cache dir. Slot filename is bare slug.

Add a third:
- **Slot-dir-with-file-symlink** (`opencode` skill, new): real slot directory `<slot>/<slug>/`, real cache directory `<cache>/<slug>/`, and a file symlink `<slot>/<slug>/<frontmatter-name>` → `<cache>/<slug>/<frontmatter-name>`.

Keying off harness/kind: `(opencode, skill)` uses the new shape. `(codex, skill)` keeps the directory-symlink shape (verified working). The detection lives in one helper `_translate_slot_layout(harness, kind)` returning an enum-ish string `"file" | "dir-symlink" | "dir-with-file-symlink"`.

### `_prune_translated_slot` — clean up the new shape

For the new shape, unlinking removes the file symlink, the cache file, the cache `<slug>/` directory (if empty), and the slot `<slug>/` directory (if empty). Same OSError-tolerant cleanup as PR-B.

### `_cell_status` — recognise the new shape

The current `_cell_status` checks `link_path.is_symlink()`. For the new shape the slot is a real directory; the **file inside** the slot directory is a symlink. The check needs to be:
- Existing flow for non-translate cells: unchanged.
- For translate cells: derive the expected slot-shape; if dir-with-file-symlink, check `(slot / <slug> / <frontmatter-name>).is_symlink()` and that its resolved target falls under the cache root.

`_translated_slot_filename` keeps returning `<slug>` for `(opencode, skill)` (the slot name is bare slug, same as codex), so the existing `link_path = slot / _translated_slot_filename(...)` computation gives the slot directory; we extend `_cell_status` to look one level deeper for the new shape's file symlink.

### `harness-matrix.md`

Update the `(opencode, skill)` cell from `symlink → ~/.config/opencode/skills/<slug>/` to `translate → ~/.config/opencode/skills/<slug>/SKILL.md` (cache: `~/.config/opencode/.agent-toolkit-cache/skill/<slug>/SKILL.md`).

`_TRANSLATE_PATH_RE` (PR-C widened to `(agents|commands)/<slug>\.md|skills/<slug>/SKILL\.md`) already matches `skills/<slug>/SKILL.md`, so no regex change.

Project-scope path table further down in the same doc (line 60+) needs updating to reflect the pi changes.

## Acceptance criteria

1. After `agent-toolkit link project pi <slug>` for a skill, `pi --print "list available skills"` from the project root finds `<slug>`. Empirical: ✓ verified the path `.pi/skills/<slug>/SKILL.md` is what pi reads.
2. After `agent-toolkit link project opencode <slug>` for a skill, `opencode debug skill` from the project root returns the skill (with name + description matching the toolkit asset). Empirical: ✓ verified the file-symlink shape works.
3. `agent-toolkit link project pi <slug>` for an `agent` kind raises `UnsupportedPair` (or list/TUI shows the cell as `unsupported`). Hand-tested via `slot_dir`.
4. PR-B/PR-C tests still pass — codex skill translation continues to work via the directory-symlink shape.
5. `uv run pytest -q` passes.

## Empirical verification (already done)

| Probe | Result |
|---|---|
| pi: project skills found at `<cwd>/.pi/skills/` | ✓ scout-verified |
| pi: no project agents discovery | ✓ scout-verified (source code) |
| opencode: drops raw v1alpha2 SKILL.md (no top-level name/description) | ✓ verified locally |
| opencode: loads translated shape (top-level name + description) | ✓ verified locally |
| opencode: silently misses dir-symlink-to-cache-dir slot | ✓ verified locally |
| opencode: loads file-symlink SKILL.md inside real slot dir | ✓ verified locally |
| codex: loads dir-symlink-to-cache-dir slot (PR-B unchanged) | ✓ verified locally |

## Out of scope

- The `(pi, agent)` user-scope path stays. The toolkit only loses the project-scope cell.
- No changes to claude (works), or to non-skill kinds for opencode/codex/pi.
- The `_TRANSLATE_PATH_RE` regex already covers the new opencode skill path because PR-C widened it for codex skills (same path shape).
