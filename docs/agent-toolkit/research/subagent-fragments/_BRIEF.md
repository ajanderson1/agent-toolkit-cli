# Research brief — subagent support per harness (v3.0.0 Phase A)

You are researching whether a specific set of AI coding **harnesses** support
**subagents**, and if so exactly how they locate and load a subagent definition.

## Terminology (do not confuse these)

- **harness** = an AI coding tool (Claude Code, Cursor, Codex, Gemini CLI, Pi…).
  That is what you are researching.
- **subagent / agent kind** = a *spawnable, separately-defined assistant* with
  its own instructions/tools, dropped in as a file (e.g. Claude Code's
  `~/.claude/agents/<slug>.md`). This is the concept you are checking for.
- A subagent is NOT a skill, NOT a slash command, NOT an MCP server, NOT a
  "mode". If a harness only has skills/commands/MCPs and no separately-spawnable
  sub-assistant, its verdict is `unsupported (by design)`.

## Two-stage protocol, per harness

1. **Winnow (time-boxed, ~5 min/harness):** Does this harness have any subagent
   concept distinct from skills/commands/MCPs? Answer yes / no / unknown.
   - `no` with clear evidence → verdict `unsupported (by design)`, one-line reason, done.
   - `unknown` after a bounded search (no public docs, no source, dead project)
     → verdict `unknown — no public evidence found`, list what you checked, done.
   - `yes` → deep-dive.
2. **Deep-dive (only yes/unknown-leaning-yes):** capture the cell fields below
   from CURRENT upstream (re-verify; do not trust 3-week-old data).

## Cell fields to capture (per harness)

- **verdict:** one of `symlink` / `translate` / `config_file` / `config_file+folder`
  / `dual-symlink` (these imply "supported"), or `unsupported (gap)` /
  `unsupported (by design)` / `unknown — no public evidence found`.
  - Use `unsupported (gap)` when the harness *does* support subagents but the
    projection is non-trivial / not yet designed — note why.
- **mechanism:** same keyword as verdict when supported; blank otherwise.
- **user-scope target path** AND **project-scope target path** (e.g.
  `~/.claude/agents/<slug>.md` / `.claude/agents/<slug>.md`).
- **file format:** `markdown+frontmatter` / `TOML` / `JSON`, plus **required**
  and **forbidden** frontmatter fields (e.g. "zod .strict() rejects extra
  top-level keys" → only `name`+`description` allowed).
- **citation:** a CURRENT upstream `file:line` (loader/glob code) or an official
  doc URL. Re-verified this session. No citation copied from memory.

## Output contract (STRICT)

Return ONLY a markdown table fragment — one row per harness you were assigned —
in EXACTLY this column order, followed by a "What I checked" trail. Do NOT
write to any doc; the orchestrator assembles fragments.

```
| `<harness>` | <verdict> | <mechanism> | <user path> / <project path> | <format + required/forbidden fields> | <citation> |
```

Then:

```
## What I checked — <batch name>
- `<harness>`: <1-3 lines: what sources you hit, what you found / why unknown>
```

Hold the skill-vs-subagent line firmly. When in doubt whether a "mode" or
"profile" is a real subagent, describe it precisely in the trail and lean
`unsupported (gap)` with a note rather than over-claiming `supported`.
