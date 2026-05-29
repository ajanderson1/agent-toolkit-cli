# Research brief — instruction-file support per harness (v3.0.0 Phase A)

You are researching whether — and how — a specific set of AI coding **harnesses**
load a single **instruction file** (a root-level prompt-context file like
`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`) **by default**, with no config changes
and no flags, at both **project** and **global/user** scope.

This is the contract that decides whether the `instructions` asset kind can
satisfy the harness with a per-harness pointer symlink to a single canonical
`AGENTS.md`.

## Terminology (do not confuse these)

- **harness** = an AI coding tool (Claude Code, Cursor, Codex, Gemini CLI, Pi…).
  That is what you are researching.
- **instruction file** = the *one* root-level prompt-context file the harness
  loads by default for project/global guidance. Examples: `AGENTS.md`,
  `CLAUDE.md`, `GEMINI.md`. **This is the asset this kind manages.**
- **pointer** = the per-harness symlink the toolkit creates (e.g.
  `CLAUDE.md` → `AGENTS.md`). Creating pointers is the only action the
  `instructions` kind ever takes.
- An instruction file is NOT a skill, NOT a subagent, NOT a slash command,
  NOT an MCP server, NOT a runtime memory file written by the harness itself.
  If a harness has only those, its verdict is `unsupported (by design)`.

## Verdict-assignment rules (read carefully)

Pick exactly one verdict per harness. The rules below are strict — read them
before assigning.

| Verdict | Meaning | Action this kind would take |
|---|---|---|
| `native` | Reads `AGENTS.md` by default (no pointer needed) | **None** — already satisfied. This is the per-kind "general" column. |
| `symlink` | Reads a fixed own-name file by default (e.g. `CLAUDE.md`, `GEMINI.md`) | Create `<OWN-NAME>.md` symlink → `AGENTS.md` |
| `unsupported (gap)` | Reads only via config opt-in / explicit flag, OR reads a directory (not a single file), OR support is unshipped/defunct | **None** — a same-name symlink can't satisfy it and we don't mutate config |
| `unsupported (by design)` | No root instruction-file concept at all | **None** |
| `unknown — no public evidence found` | Bounded search surfaced no default instruction-file convention | **None** — revisit if the product publishes |

**Strict rules the verdict must obey:**

1. **Default behaviour only.** Verdict follows what the harness reads *out of
   the box* with no flags and no config. Gemini reads `GEMINI.md` by default
   (→ `symlink`) **even though** it *can* be pointed at `AGENTS.md` via
   `context.fileName` opt-in — that opt-in is **irrelevant** here, because we
   only satisfy defaults.
2. **Runtime-load, not seed-only.** Claude Code's `/init` *reads* `AGENTS.md`
   to *seed* `CLAUDE.md`, but does **not** load `AGENTS.md` at runtime →
   `symlink` (target `CLAUDE.md`), **NOT** `native`. Touching the file ≠
   loading it.
3. **File vs directory.** A harness that reads a *directory* (like Cline's
   `.clinerules/`) → `gap` (a same-name symlink to one file can't satisfy a
   directory loader). Even if `AGENTS.md` is one of the files inside that
   directory, it's still `gap` if the harness doesn't auto-load a single root
   file.
4. **Unshipped / defunct.** Record `gap` with the evidence trail; do not wire.
5. **Multiple files loaded by default.** If the harness loads several
   instruction files (e.g. `CLAUDE.md` AND nested ones AND `AGENTS.md`),
   the verdict is determined by the **top-level project-root** file the
   harness reads first/most-prominently. If that's `AGENTS.md` → `native`;
   if that's a fixed own-name file → `symlink`; document the rest in the
   trail.

## Two-stage protocol, per harness

1. **Winnow (time-boxed, ~5 min/harness):** Does this harness have a default
   root-level instruction file at all? Answer yes / no / unknown.
   - `no` with clear evidence → verdict `unsupported (by design)`, one-line
     reason, done.
   - `unknown` after a bounded search (no public docs, no source, dead
     project) → verdict `unknown — no public evidence found`, list what you
     checked, done.
   - `yes` → deep-dive.
2. **Deep-dive (only yes/unknown-leaning-yes):** capture the cell fields
   below from CURRENT upstream (re-verify; do not trust 3-week-old data).

## Cell fields to capture (per harness)

- **verdict:** one of the 5 from the table above.
- **default instruction file name:** e.g. `CLAUDE.md`, `GEMINI.md`,
  `AGENTS.md`, the directory `.clinerules/`, or `none`.
- **project-scope path** AND **global/user-scope path**. Both required.
  Examples: `./CLAUDE.md` (project) / `~/.claude/CLAUDE.md` (global).
  If a scope is not supported (e.g. project-only or global-only), say so
  explicitly: write `none (project-only)` or `none (global-only)`.
- **reads `AGENTS.md` natively by default?** yes / no. The bucket
  discriminator — must match the verdict (`native` ↔ yes; everything else ↔ no).
- **mechanism:** `symlink` if verdict is `symlink`, else blank. (There is no
  `translate` or `config_file` for this kind. Pointers only.)
- **citation:** a CURRENT upstream `file:line` (loader code that opens the
  file) OR an official doc URL. Re-verified this session. No citation copied
  from memory.
- **one-line reasoning** for the verdict.

## Reusable priors (re-verify, do not trust)

These are the spec's seed data — **priors to re-verify against current
upstream**, not trusted facts. Harnesses move fast.

- `claude-code` → `CLAUDE.md` (NOT `AGENTS.md` natively; `/init` only seeds).
- `gemini-cli` → `GEMINI.md` (default); `AGENTS.md` only via
  `context.fileName` opt-in.
- `aider`-family → `CONVENTIONS.md` by convention; auto-loads nothing
  without `--read` / `.aider.conf.yml`.
- `cline` → `.clinerules/` directory; native `AGENTS.md` proposed but
  unmerged (issue #5033).
- Native readers (from conventions doc): `codex`, `opencode`, `pi` read
  `AGENTS.md` natively.

Re-confirm each, in current upstream, this session. If a prior is wrong,
say so in the trail with the citation that overturned it.

## Output contract (STRICT)

Return ONLY a markdown table fragment — one row per harness you were
assigned — in EXACTLY this column order, followed by a "What I checked"
trail. Do NOT write to any doc; the orchestrator assembles fragments.

```
| `<harness>` | <verdict> | <default file> | <project path> / <global path> | <reads AGENTS.md natively?> | <mechanism> | <citation> | <one-line reasoning> |
```

Then:

```
## What I checked — <batch name>
- `<harness>`: <1-3 lines: what sources you hit, what loader/doc you found,
  any surprising upstream change vs the priors above>
```

Hold the line firmly on the `runtime-load vs seed-only` rule and the
`file vs directory` rule — they are the two most common ways to
over-claim `native`. When in doubt between `native` and `symlink`,
lean `symlink` and explain in the trail.
