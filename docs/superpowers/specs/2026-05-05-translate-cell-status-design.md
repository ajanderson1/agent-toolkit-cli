# Spec — fix bare-slug lookup for translate cells in status reporting (#40-A)

## Problem

Two status-reporting paths build slot lookup paths from a bare slug:

- `src/agent_toolkit/commands/_list_json.py:47` — `link_path = slot / slug`
- `src/agent_toolkit/doctor/symlinks.py:34` — `link_path = home / rel / asset.slug`

The `_link_lib._translated_slot_filename` helper (`_link_lib.py:79-86`) returns `<slug>.md` for OpenCode agents and commands. So when a user runs `link user opencode`, the slot lands at `~/.config/opencode/agents/<slug>.md`, but `_cell_status` and `doctor/symlinks` look for `~/.config/opencode/agents/<slug>` — and report "unlinked" or "missing" respectively, when the link is in fact present and healthy.

This is a **pre-existing latent bug** that today affects only OpenCode agent/command translate cells. It is not visible to most users because OpenCode translate is recent and the `list` JSON / `doctor` paths for these cells are not heavily exercised. It will become a much bigger problem when codex skills (#40 PR-C) and any future translate cells land on top of broken status reporting.

## Why fix this first

This PR is a clean, mechanical fix that:
- Improves status reporting for OpenCode agent/command translate cells **today**.
- Removes a confounder for #40 PR-C, where status assertions for codex skills will need to work correctly the first time.
- Has zero coupling to the directory-slot translate work in PR-B or the codex translator in PR-C — independently revertable.

## Out of scope

- The `inside_repo` check in `_cell_status` (`_list_json.py:62-69`) compares the symlink target against `toolkit_root_resolved`. For OpenCode translate cells, the symlink target is **inside the cache directory**, not inside the toolkit repo. The current code reports such cells as `"broken"` because `inside_repo == False`. **This is a real second-order bug** that PR-B will need to address (the cache root is "expected" for translate cells), but it is out of scope for PR-A. PR-A's regression test will assert the link is _at least_ found (i.e. the read returns something other than `"unlinked"`), without asserting the final `linked`-vs-`broken` verdict — that's PR-B territory.
- Changes to `harness_adapters/` or MCP code paths.
- The 4-glyph TUI rendering.

## Acceptance criteria

1. After `link user opencode` for an OpenCode-declared agent, `_cell_status(opencode, agent, …, scope=user, …)` returns a status that is NOT `"unlinked"` (it may be `"linked"` or `"broken"` — the bare-slug bug is fixed; the inside-repo bug is left for PR-B). The current code returns `"unlinked"`.
2. After `link user opencode` for an OpenCode-declared agent, `doctor symlinks --harness opencode` reports the link as found (no "expected symlink … missing" warning for that asset). The current code emits the warning.
3. A regression test pins both of the above behaviours.
4. `uv run pytest -q` passes.
5. No changes to file-slot kinds (skill/hook/plugin/pi-extension) or to MCPs.

## Solution sketch

Both call-sites already have access to `kind`, `slug`, and `harness`. Import and use `_link_lib._translated_slot_filename` (or a re-export of it) at each call-site:

- `_list_json._cell_status`: `link_path = slot / _translated_slot_filename(slug, kind, harness)`.
- `doctor/symlinks.py`: same substitution for `link_path` at line 34, and the symmetric stale-link sweep at line 63 (`for entry in user_kind_dir.iterdir()` already iterates real filenames, so that loop is fine — the lookup `declared_slugs.get((kind, entry.name))` is the symmetric bug, since `entry.name` for an OpenCode agent slot would be `foo.md`, not `foo`. Strip a `.md` suffix before the lookup, gated on the `_translated_slot_filename` shape.)

The helper does not need to be promoted out of `_link_lib`; a direct import from these two modules is the smallest possible change.
