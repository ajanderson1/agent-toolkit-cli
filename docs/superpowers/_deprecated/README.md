# Deprecated superpowers docs

These specs and plans describe **superseded designs**. They are kept for
archaeology — to trace how a decision evolved — and must **never** be followed as
the design for current work. A live spec or plan will never link here as its
authority; if you arrived from a live doc, you took a wrong turn.

## v1 MCP design generation (retired 2026-06-12, issue #329)

The entire first-generation MCP design — written against the **v2.x architecture
that was deleted in the v2.3.0 refold (#160)**. It assumed a walker, an allow-list
as the authority on what we manage, a catalog repo at `<toolkit-repo>/mcps/`, the
verbs `link`/`unlink`/`diff`/`fix`/`new`, a plugin-folder strategy for Claude, and
a `v1alpha2` schema bump. **None of that survives** into the v3 library-model build.

Retired in favour of: `docs/superpowers/specs/2026-06-12-mcp-kind-v3-design.md`
(design) + `docs/superpowers/plans/2026-06-07-mcp-kind-v3-foundations.md` (plan).

Retired docs:

- `2026-05-04-mcp-management-design.md` — v1 spec (Plan A): the "five rules", four-harness strategy table.
- `2026-05-04-mcp-adapters-design.md` — v1 spec (Plan B): the adapter write/read path.
- `2026-05-04-mcp-foundations.md` — v1 plan: walker / sidecar / `_allowlist.py` foundations.
- `2026-05-04-mcp-adapters-codex.md` — v1 plan: Codex adapter detail.
- `2026-05-05-config-file-mcp-adapters-claude-opencode-design.md` + `…-claude-opencode.md` — v1 spec+plan: Claude/OpenCode config-file adapters.
- `2026-05-19-list-json-mcp-hook-unlinked-design.md` + `…-unlinked.md` — v1 spec+plan: `list --format=json` `unlinked` status (#141).
- `2026-05-19-mcp-link-creates-mcp-json-design.md` + `…-mcp-json.md` — v1 spec+plan: project-scope `link` absent-file bug (#125).

The mechanism *rules* that carried forward unchanged (manage-by-name, round-trip
parsers preserving neighbours, structural drift, loud atomic writes, the empty-`{}`
/ absent-`.mcp.json` failure-mode handling) are restated, cleanly, in the v3 spec —
read them there.
