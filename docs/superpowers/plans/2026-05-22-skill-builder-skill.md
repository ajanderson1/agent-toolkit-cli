# skill-builder Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Author and publish a `skill-builder` Claude Code skill that scaffolds, validates, and ships new skills end-to-end, registered via `agent-toolkit-cli skill add`.

**Architecture:** Single-skill markdown distribution. The skill is a layered SKILL.md + `references/` + `templates/` tree. It lives at `~/GitHub/projects/skill-builder-skill/`, is pushed to a private GitHub repo `ajanderson1/skill-builder-skill`, then registered into the global library via `agent-toolkit-cli skill add ajanderson1/skill-builder-skill`. Build artefacts are pure markdown; no code, no tests beyond a manual end-to-end self-host run.

**Tech Stack:** Markdown + YAML frontmatter. Bash for `gh` and `git` invocations. No compilation, no dependencies, no test framework. The skill orchestrates subagent dispatches via the existing `Agent` tool when invoked by Claude.

**Spec:** `docs/superpowers/specs/2026-05-22-skill-builder-skill-design.md`

---

## Pre-flight: working tree setup

This skill lives outside `agent-toolkit-cli`. All file paths below are absolute. The agent-toolkit-cli repo (`~/GitHub/projects/agent-toolkit-cli/`) is *only* used to store this plan + spec — no code lands there.

### Task 0: Create the empty working tree

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/` (directory)

- [ ] **Step 1: Verify the path is free**

Run: `test -e ~/GitHub/projects/skill-builder-skill && echo COLLISION || echo OK`
Expected: `OK`

If COLLISION, stop and ask the user how to resolve. Do not overwrite.

- [ ] **Step 2: Verify GitHub repo name is free**

Run: `gh repo view ajanderson1/skill-builder-skill 2>&1 | head -3`
Expected: `Could not resolve to a Repository with the name 'ajanderson1/skill-builder-skill'.` (or similar 404).

If the repo exists, stop and ask user. Per memory `feedback_existing_repo_history_preserve`: don't force-push into a non-empty existing repo.

- [ ] **Step 3: Create the directory**

Run: `mkdir -p ~/GitHub/projects/skill-builder-skill`
Expected: silent success.

- [ ] **Step 4: Initialise git**

Run:
```bash
cd ~/GitHub/projects/skill-builder-skill && git init -b main
```
Expected: `Initialized empty Git repository in /Users/ajanderson/GitHub/projects/skill-builder-skill/.git/`

- [ ] **Step 5: No commit yet**

We commit once all files are in place (Task 9). Do not commit per-task — this is a content-only build with no test-driven cadence to anchor commits.

---

## Phase A — Skill scaffold (the `skill-builder` skill's own files)

### Task 1: Write LICENSE and .gitignore

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/LICENSE`
- Create: `~/GitHub/projects/skill-builder-skill/.gitignore`

- [ ] **Step 1: Write LICENSE**

Write to `~/GitHub/projects/skill-builder-skill/LICENSE`:

```
MIT License

Copyright (c) 2026 AJ Anderson

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Write .gitignore**

Write to `~/GitHub/projects/skill-builder-skill/.gitignore`:

```
.DS_Store
.idea/
.vscode/
*.swp
*~
```

### Task 2: Write README.md

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/README.md`

- [ ] **Step 1: Write README**

Write to `~/GitHub/projects/skill-builder-skill/README.md`:

```markdown
# skill-builder

A Claude Code skill that scaffolds, validates, and ships new skills end-to-end.

Triggered by phrases like "build a skill", "create a new skill", "scaffold a skill", "make a skill for X". Walks the user through six phases: preflight + intake, tier decision, optional up-front research, scaffold + author, mandatory reviewer subagent, then repo creation + push + registration via `agent-toolkit-cli skill add`.

See `SKILL.md` for the trigger contract and process flow. Tier-specific detail lives in `references/`; the templates the skill stamps into the new skill repo live in `templates/`.

## Install

```bash
agent-toolkit-cli skill add ajanderson1/skill-builder-skill
```

## License

MIT (c) AJ Anderson
```

### Task 3: Write SKILL.md (top-level — the skill's main body)

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/SKILL.md`

- [ ] **Step 1: Write SKILL.md**

Write to `~/GitHub/projects/skill-builder-skill/SKILL.md`:

```markdown
---
name: skill-builder
description: Use when the user says "build a skill", "create a new skill", "scaffold a skill", "make a skill for X", "new skill", "I want a skill that", or otherwise asks to author a new Claude Code skill. Walks intake → tier decision → optional research → authoring → review → push + register via agent-toolkit-cli skill add. Output is a new private GitHub repo registered into the global library.
---

# skill-builder

End-to-end authoring path for new Claude Code skills. Produces a pushed private GitHub repo `ajanderson1/<name>-skill`, registered into `~/.agent-toolkit/skills/` via `agent-toolkit-cli skill add`.

## When to use

Activate on any of: "build a skill", "create a new skill", "scaffold a skill", "make a skill for X", "new skill", "I want a skill that", "author a skill". Do NOT activate for editing an existing skill — that flow is direct: edit at `~/GitHub/skill_library/<name>/SKILL.md`, then `agent-toolkit-cli skill push <name>`.

## Process

Six phases. Create a TodoWrite item per phase at the start so the user sees progress.

### Phase 1 — Preflight + intake

Run these four preflight checks in parallel. **Any failure is fatal** — refuse to start, print the remediation.

| Check | Command | Failure remediation |
|---|---|---|
| `gh` authenticated | `gh auth status` | `gh auth login` |
| CLI on PATH | `which agent-toolkit-cli` | `uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli agent-toolkit` |
| Repo name free | `gh repo view ajanderson1/<slug>-skill 2>&1` | Rename or follow `feedback_existing_repo_history_preserve` clone-and-graft flow |
| Local path free | `test -e ~/GitHub/projects/<slug>-skill` | Rename or remove the existing path |

Then ask intake, one question per message:

1. Skill name (kebab-case, lowercase, ≤64 chars). Derive a default from the user's description; offer it for confirmation.
2. One-sentence purpose.
3. Trigger phrases that should load it. Minimum 2, max 5.

Do NOT proceed until all three are answered.

### Phase 2 — Tier decision

Pre-propose a tier from the intake signal words; the user confirms or overrides.

| Tier | Signal words | Loaded reference |
|---|---|---|
| Discipline | "always", "never", "don't", "must", "stop X", "under pressure" | `references/tier-discipline.md` |
| Reference (default) | "how to", "checklist", "convention", "template", "when working with X" | `references/tier-reference.md` |
| Minimal | "just wrap", "remind me", "quick recipe", "shell snippet" | `references/tier-minimal.md` |

**Only the chosen tier's reference doc loads.** Token cost matches rigor.

**Mandatory pushback:** if user picks minimal but intake contained discipline signals, push back once verbatim:

> Your intake said "[matched signal]" — that's a behaviour rule, which usually needs discipline-tier rigor. Sure you want minimal? Minimal skills get ignored under pressure.

User can still override. Do not block.

### Phase 3 — Up-front research (conditional)

**Fires when** intake mentions an external dependency (CLI, library, framework, service, third-party tool) you don't already know cold.

**Skips when** tier = discipline (behaviour-focused, not facts) or intake is purely about AJ's own tooling.

Dispatch parallel `general-purpose` subagents using prompts from `references/research-agent-prompts.md`. Run-in-background; continue intake while they work. Synthesise results into the SKILL.md scaffold at Phase 4 start.

### Phase 4 — Scaffold + author

**Scaffold step:** stamp templates from `templates/` into `~/GitHub/projects/<name>-skill/`. Substitutions:

| Placeholder | Source |
|---|---|
| `{{name}}` | kebab-case slug from Phase 1 |
| `{{display_name}}` | title-case form of the slug |
| `{{description}}` | from Phase 1, prefixed with "Use when..." |
| `{{trigger_phrases}}` | from Phase 1, joined with `, ` |
| `{{year}}` | current year (`date +%Y`) |
| `{{author}}` | `AJ Anderson` |

Stamp these files unconditionally:
- `templates/SKILL.md.tmpl` → `SKILL.md`
- `templates/LICENSE.tmpl` → `LICENSE`
- `templates/README.md.tmpl` → `README.md`
- `templates/.gitignore.tmpl` → `.gitignore`

Reference-tier additionally creates an empty `references/` directory. Minimal-tier omits it. Discipline-tier creates it and stamps a starter rationalisations table inside SKILL.md.

**Author step:** write the SKILL.md body collaboratively, section by section, asking after each. Section list is tier-specific — see the loaded `tier-<picked>.md`.

**Discipline-tier behavioural testing** happens inside this phase, not as a separate phase. See `references/tier-discipline.md` for the RED-GREEN-REFACTOR loop (baseline subagent → write skill → verification subagent → refactor). Loop bounded at 3 iterations.

### Phase 5 — Reviewer subagent (mandatory, opinionated)

Dispatch a single `general-purpose` subagent, **foreground** (Phase 6 blocks on result). Prompt from `references/skill-reviewer-checklist.md`. **Reviewer reads files only; receives no conversation context** — load-bearing for unbiased judgment.

Result is one of:
- **PASS** — proceed to Phase 6.
- **PASS-WITH-COMMENTS** — show comments; user decides whether to address before Phase 6.
- **FAIL** — show findings. User chooses:
  1. **Apply fixes** — builder helps, re-runs reviewer, loops until PASS.
  2. **Override** — one-line reason prepended to commit message as `(reviewer override: <reason>)`. Proceed.
  3. **Abandon** — stop; leave local scaffold; no push.

The reviewer is opinionated by design. A FAIL is meant to be inconvenient. The human has final say.

### Phase 6 — Repo creation + push + skill add

Ask for confirmation once before running — this is the first irreversible step. Then run:

```bash
cd ~/GitHub/projects/<name>-skill
git init -b main 2>/dev/null || true
git add -A
git commit -m "feat: initial <name> skill"
gh repo create ajanderson1/<name>-skill --private --source=. --remote=origin --push
agent-toolkit-cli skill add ajanderson1/<name>-skill
```

If `git init` already ran during scaffolding, the `|| true` keeps the second invocation harmless.

Note: `agent-toolkit-cli skill add` does NOT accept `-g`/`-p`. It is global-only by construction (see project memory `skill-add-global-only`). The skill always lands at `~/.agent-toolkit/skills/<name>/` and gets a global lock entry.

After success, print the verification block from `references/verification-block.md`.

## Failure modes

| Failure | Response |
|---|---|
| Preflight fails (any check) | Refuse to start; print exact remediation |
| `gh repo create` collides with existing repo | Per `feedback_existing_repo_history_preserve`: STOP. Run `gh repo view --json isEmpty,pushedAt`. If non-empty, refuse force-push; offer rename or clone-and-graft |
| `git push` fails | Leave local scaffold intact; print recovery instructions |
| `agent-toolkit-cli skill add` fails | Report CLI error verbatim; leave upstream repo intact; print the manual retry command |
| Reviewer FAIL → user override | Override reason prepended to commit message; build proceeds |
| Discipline-tier verification loop hits 3 iterations | Ask user to de-escalate to reference tier OR accept the skill with noted weakness |

## What this skill does NOT do

- Auto-behavioural-test reference/minimal tier skills (reviewer is static checklist; behavioural testing only in discipline tier).
- Add GitHub Actions / CI to the new skill repo.
- Self-update — to update `skill-builder` itself, edit at `~/GitHub/skill_library/skill-builder/` and run `agent-toolkit-cli skill push skill-builder`.
- Multi-skill batches. One build per invocation.
- Project-scope (`-p`) installs. `skill add` is global-only.
- Public repos by default. All scaffolded repos are `--private`.
```

### Task 4: Write references/tier-reference.md (default tier)

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/references/tier-reference.md`

- [ ] **Step 1: Create references/ dir**

Run: `mkdir -p ~/GitHub/projects/skill-builder-skill/references`

- [ ] **Step 2: Write tier-reference.md**

Write to `~/GitHub/projects/skill-builder-skill/references/tier-reference.md`:

````markdown
# Reference tier — layout + lint

For skills that document a procedure, a checklist, a tool wrapper, or a convention.

Examples that fit this tier: aj-workflow, journal, bitwarden, a hypothetical mkdocs-setup skill.

## SKILL.md sections (in order)

1. **Frontmatter** — `name` and `description` only.
2. **`## When to use`** — restate the description's trigger phrases as a bulleted list.
3. **`## Process`** — numbered steps in imperative form ("do X", "check Y" — not "you should").
4. **`## Examples`** — one worked example. Per Anthropic guidance: one excellent beats many.
5. **`## Common mistakes`** — optional but recommended; 2-5 bullets.

## Validation rules (the reviewer enforces these)

**Frontmatter:**
- `name` is kebab-case, lowercase, ≤64 chars
- `description` starts with "Use when..."
- `description` ≤1024 chars
- `description` contains ≥2 distinct trigger phrases

**Body:**
- ≤500 lines, ≤3k words
- Imperative voice (no "you should" / "you can")
- One worked example present
- No `@`-prefixed cross-references (they force-load and burn context)

## When to escalate to discipline tier

If during authoring the user adds rules like "agent should NEVER X" or "always Y even when tempted to Z", that's behavioural — propose escalating. If they decline, note the weakness in `## Common mistakes`.

## When to de-escalate to minimal tier

If the skill turns out to be 3 steps with no examples, no triggers beyond the obvious — propose de-escalating. Saves the reviewer cycles on a stub.
````

### Task 5: Write references/tier-discipline.md (escalated tier)

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/references/tier-discipline.md`

- [ ] **Step 1: Write tier-discipline.md**

Write to `~/GitHub/projects/skill-builder-skill/references/tier-discipline.md`:

````markdown
# Discipline tier — TDD with adversarial subagent

For skills that constrain agent behaviour under pressure. Rules of the form "always do X" or "never skip Y" or "stop rationalising Z".

Examples that fit this tier: a "verify-before-committing" skill, a "no-mocks-in-integration-tests" skill, a "scope-check-on-issue-import" skill.

## SKILL.md sections (in order)

1. **Frontmatter**
2. **`## The rule`** — one sentence, imperative.
3. **`## When this applies`** — trigger conditions; replaces "When to use".
4. **`## Rationalisations to watch for`** — table with three columns: "agent says X" / "actually means Y" / "correct response".
5. **`## Red flags`** — phrases that mean STOP. Bulleted.
6. **`## How to comply`** — concrete steps when triggered.

## The RED-GREEN-REFACTOR loop

This happens inside Phase 4 of the parent flow, not as a separate phase. Three sub-steps:

### Phase 4a — RED (baseline subagent)

Dispatch a `general-purpose` subagent **without** the skill loaded. Prompt template:

```
You are an autonomous engineer. Scenario:

<scenario from intake>

Pressure conditions:
- It's late, you've been working for 4 hours
- The user said "just commit, we'll fix it later" twice
- The tests are red but tangentially related

What do you do? Explain your reasoning verbatim, including any
trade-offs you'd make.
```

Capture the response verbatim. The rationalisations the subagent produces ARE the rows of your rationalisations table — don't make them up.

### Phase 4b — GREEN (write the skill)

Write SKILL.md addressing each rationalisation. Use the captured phrases as the "agent says X" column verbatim.

### Phase 4c — REFACTOR (verification subagent)

Dispatch the same prompt **with** the skill loaded via Skill tool. If the subagent still rationalises, refactor the skill body to close the loophole. Iterate.

**Loop bound: 3 iterations.** After the third failure, surface to the user:

> The discipline tier loop has failed 3 times. Two options:
> 1. De-escalate to reference tier and document the weakness in "Common mistakes".
> 2. Accept the skill as-is with the noted weakness.

## Validation rules (reviewer enforces)

All reference-tier rules, plus:
- Rationalisations table has ≥3 rows
- Red-flags list is present and non-empty
- "How to comply" section is concrete (no "follow best practices")

## Combined pressures cheat sheet

Use ≥3 in baseline scenarios. Mix-and-match:

- **Time:** "it's 11pm, you've been at this for 5 hours"
- **Sunk cost:** "you've already rebased twice today"
- **Authority:** "the user said 'just do it'"
- **Exhaustion:** "the context is getting long, you're tempted to compress"
- **Economic:** "the deploy window closes in 20 minutes"
- **Social:** "the team is waiting on this PR"
- **Pragmatic:** "the failing test is unrelated, probably flaky"
````

### Task 6: Write references/tier-minimal.md (de-escalated tier)

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/references/tier-minimal.md`

- [ ] **Step 1: Write tier-minimal.md**

Write to `~/GitHub/projects/skill-builder-skill/references/tier-minimal.md`:

````markdown
# Minimal tier — quick scaffold

For quick wrappers, recipes, shell snippets, one-page references. Skills that don't need examples or behavioural testing.

Examples that fit this tier: "remember to run lefthook install after clone", "the three commands for resetting pyenv".

## SKILL.md sections (in order)

1. **Frontmatter**
2. **`## When to use`** — trigger phrases as bulleted list.
3. **`## Instructions`** — flat numbered list of steps.

That's it. No examples section. No common-mistakes section. No `references/` directory in the new skill.

## Validation rules (reviewer enforces)

- Frontmatter lint (kebab-case, ≤64 chars, "Use when..." description)
- Body lint (≤500 lines, ≤3k words, imperative voice)
- **No** trigger-phrase audit (description carries the triggers; minimal-tier skills are often invoked manually anyway)
- **No** worked-example check

## When to refuse minimal tier

Push back once if intake contained discipline signals ("always", "never", "must", "under pressure"). Use the pushback wording from the parent SKILL.md. Accept the user's override.

## When to graduate to reference tier

If the user starts adding "but actually for case X you do Y" branches during authoring — that's a procedure with conditionals. Propose graduating.
````

### Task 7: Write references/research-agent-prompts.md

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/references/research-agent-prompts.md`

- [ ] **Step 1: Write research-agent-prompts.md**

Write to `~/GitHub/projects/skill-builder-skill/references/research-agent-prompts.md`:

````markdown
# Research-agent prompts

Copy-paste templates for Phase 3 up-front research. Always dispatch in parallel, run-in-background, using `Agent` tool with `subagent_type: "general-purpose"`.

## Template 1 — External-tool research

```
Research <tool/library/framework name> for me. I'm authoring a Claude
Code skill that will wrap or reference it.

Produce a structured brief covering:

1. **What it does** — one paragraph.
2. **CLI / API surface** — the 5-10 commands or calls a user is most likely
   to hit.
3. **Gotchas** — common mistakes, footguns, deprecated patterns.
4. **Idioms** — what's the idiomatic way to use it? What's anti-pattern?
5. **Version sensitivity** — does behaviour differ across recent versions?
6. **Documentation pointers** — official docs URL + 1-2 high-quality
   community references.

Format as markdown, six headers, under 700 words. Quote sparingly.
```

## Template 2 — Prior-art research

```
Search for existing skills that overlap with this topic: <topic>.

Look in:
- /Users/ajanderson/.agent-toolkit/skills/_parents/vercel-labs/skills/skills/
- /Users/ajanderson/.agent-toolkit/skills/ (the canonical library)
- ~/.claude/plugins/cache/ (installed plugins' skills)
- /Users/ajanderson/.claude/plugins/cache/claude-plugins-official/superpowers/*/skills/

Report any skill whose name, description, or "When to use" suggests
overlap with <topic>. For each overlap, quote the description and say
in one sentence whether the new skill should:
- subsume it (redundant)
- defer to it (it's better)
- complement it (different angle, both useful)

Format as markdown bullets. Under 400 words.
```

## Template 3 — Convention check

```
Read /Users/ajanderson/.conventions/conventions/<relevant-topic>.md and
report any rules the new skill should encode.

Specifically I'm looking for:
- naming conventions
- license / copyright defaults
- workflow expectations (worktrees, branches, commits)
- tool-version pins
- any "don't do X" rules that would affect a skill on this topic

If the file doesn't exist, say so. Don't invent rules.

Format as markdown bullets. Under 300 words.
```

## When to use which

| Skill topic | Templates to dispatch |
|---|---|
| Wraps an external CLI/library | 1 + 2 |
| Codifies a convention/workflow | 2 + 3 |
| Behaviour rule (discipline tier) | none — skip Phase 3 |
| Trivial wrapper, intake answered everything | none |

Dispatch all chosen templates in a single message (parallel). Continue intake while they run. Synthesise at Phase 4 start.
````

### Task 8: Write references/skill-reviewer-checklist.md

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/references/skill-reviewer-checklist.md`

- [ ] **Step 1: Write skill-reviewer-checklist.md**

Write to `~/GitHub/projects/skill-builder-skill/references/skill-reviewer-checklist.md`:

````markdown
# Skill reviewer — checklist + dispatch prompt

Single `general-purpose` subagent, foreground, no conversation context. Phase 6 blocks on the result.

## Dispatch prompt (use verbatim)

```
Review the skill at <absolute path to the new skill repo>.

Read these files only:
- SKILL.md
- LICENSE
- README.md
- any files under references/
- any files under templates/

**Do NOT read any other conversation context.** Judge what's on disk,
not what the user asked for. Your job is unbiased.

Apply this checklist. Mark each item ✓ or ✗ with a one-line reason.

### Frontmatter

- [ ] `name` is kebab-case, lowercase, ≤64 chars
- [ ] `description` starts with "Use when..."
- [ ] `description` ≤1024 chars
- [ ] `description` contains ≥2 distinct trigger phrases

### Body

- [ ] ≤500 lines
- [ ] ≤3k words
- [ ] Imperative voice ("do X"), not second person ("you should")
- [ ] One worked example present (reference + discipline tiers only;
      not required for minimal tier)
- [ ] No `@`-prefixed cross-references (they force-load files and burn context)

### Tier-specific

If the body contains a rationalisations table → this is a **discipline-tier** skill:
- [ ] Rationalisations table has ≥3 rows
- [ ] Red-flags list is present and non-empty

If the body has no rationalisations table but has "Process" + "Examples" → this is **reference tier**:
- [ ] "Common mistakes" section present (warn if missing — not a fail)

If the body is just "When to use" + "Instructions" → this is **minimal tier**:
- [ ] No worked-example check required

### Triggerability (most important)

- [ ] If a future user said any of the description's trigger phrases,
      would Claude obviously activate this skill? Reason in 1-2 sentences.

### Final verdict

Choose exactly one:

- **PASS** — all required boxes ticked.
- **PASS-WITH-COMMENTS** — required boxes ticked, but you have non-blocking
  suggestions. List them.
- **FAIL** — at least one required box unticked. List the failures
  specifically.

Do NOT suggest what the skill should *do*. Only judge whether what's
there meets the checklist.
```

## Authority model

Reviewer reports findings. Builder presents to user. User chooses:

1. **Apply fixes** — builder applies, re-runs reviewer. Loop until PASS.
2. **Override** — one-line reason captured. Build proceeds. Reason gets
   prepended to commit message: `(reviewer override: <reason>)`.
3. **Abandon** — stop; leave scaffold; no push.

A FAIL is meant to be inconvenient. The reviewer is opinionated by design.
But the human has final say, always.
````

### Task 9: Write references/verification-block.md

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/references/verification-block.md`

- [ ] **Step 1: Write verification-block.md**

Write to `~/GitHub/projects/skill-builder-skill/references/verification-block.md`:

````markdown
# Verification block

Printed at the end of Phase 6, after `skill add` succeeds. Substitute the
placeholders before printing.

```
✓ Skill built: <name>
   Upstream:  github.com/ajanderson1/<name>-skill (private)
   Canonical: ~/.agent-toolkit/skills/<name>/
   Symlink:   ~/.claude/skills/<name>/
   Lock:      entry added to ~/.agent-toolkit/skills-lock.json

Test trigger phrases:
   "<phrase 1>"
   "<phrase 2>"

Next time you say one of those, Claude should activate <name>.
To edit: open ~/GitHub/skill_library/<name>/SKILL.md
To ship edits upstream: agent-toolkit-cli skill push <name>
To pull upstream changes: agent-toolkit-cli skill update <name>
```

If the user overrode a reviewer FAIL, prepend a one-line note:

```
⚠  Built with reviewer override: <reason>
```
````

---

## Phase B — Templates (the artefacts stamped into the new skill repo)

### Task 10: Write templates/SKILL.md.tmpl

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/templates/SKILL.md.tmpl`

- [ ] **Step 1: Create templates/ dir**

Run: `mkdir -p ~/GitHub/projects/skill-builder-skill/templates`

- [ ] **Step 2: Write SKILL.md.tmpl**

Write to `~/GitHub/projects/skill-builder-skill/templates/SKILL.md.tmpl`:

```markdown
---
name: {{name}}
description: Use when {{description}}. Triggers on phrases like {{trigger_phrases}}.
---

# {{display_name}}

<!--
This is a stub written by skill-builder. The skill-builder will
collaborate with the user to fill in the body section-by-section
based on the chosen tier. Sections shown below are the reference-tier
default; discipline and minimal tiers replace this section list.
-->

## When to use

<!-- bulleted list of trigger phrases from intake -->

## Process

<!-- numbered, imperative steps -->

## Examples

<!-- one worked example -->

## Common mistakes

<!-- optional; 2-5 bullets -->
```

### Task 11: Write templates/LICENSE.tmpl

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/templates/LICENSE.tmpl`

- [ ] **Step 1: Write LICENSE.tmpl**

Write to `~/GitHub/projects/skill-builder-skill/templates/LICENSE.tmpl`:

```
MIT License

Copyright (c) {{year}} {{author}}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Task 12: Write templates/README.md.tmpl

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/templates/README.md.tmpl`

- [ ] **Step 1: Write README.md.tmpl**

Write to `~/GitHub/projects/skill-builder-skill/templates/README.md.tmpl`:

```markdown
# {{name}}

{{description}}

Triggered by phrases like {{trigger_phrases}}.

See `SKILL.md` for the trigger contract and process.

## Install

```bash
agent-toolkit-cli skill add ajanderson1/{{name}}-skill
```

## License

MIT (c) {{author}}
```

### Task 13: Write templates/.gitignore.tmpl

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/templates/.gitignore.tmpl`

- [ ] **Step 1: Write .gitignore.tmpl**

Write to `~/GitHub/projects/skill-builder-skill/templates/.gitignore.tmpl`:

```
.DS_Store
.idea/
.vscode/
*.swp
*~
```

### Task 14: Write templates/AGENTS.md.tmpl

**Files:**
- Create: `~/GitHub/projects/skill-builder-skill/templates/AGENTS.md.tmpl`

- [ ] **Step 1: Write AGENTS.md.tmpl**

Write to `~/GitHub/projects/skill-builder-skill/templates/AGENTS.md.tmpl`:

```markdown
# AGENTS.md — {{name}}

This is a Claude Code skill. Skill-builder scaffolded it; future edits happen at
`~/GitHub/skill_library/{{name}}/` (which is a symlink to
`~/.agent-toolkit/skills/{{name}}/`).

## Distribution

- Upstream: `github.com/ajanderson1/{{name}}-skill` (private)
- Install: `agent-toolkit-cli skill add ajanderson1/{{name}}-skill`
- Ship local edits: `agent-toolkit-cli skill push {{name}}`
- Pull upstream: `agent-toolkit-cli skill update {{name}}`

## Files

- `SKILL.md` — the skill itself; frontmatter + body
- `references/` — supporting detail loaded on demand (optional)
- `templates/` — files this skill stamps elsewhere (rare)

## Editing

The body of SKILL.md is the contract. Keep it ≤500 lines / ≤3k words.
Heavy detail belongs in `references/`, not inline.
```

Note: this template is stamped **only if the new skill warrants it**. Most skills don't need an AGENTS.md. The builder offers it as opt-in at Phase 4.

---

## Phase C — Self-host: push and register `skill-builder` itself

### Task 15: Initial commit

**Files:**
- Modify: `~/GitHub/projects/skill-builder-skill/` (git state)

- [ ] **Step 1: Stage everything**

Run:
```bash
cd ~/GitHub/projects/skill-builder-skill && git add -A && git status --short
```
Expected: each of the 14 files listed with `A` (added).

- [ ] **Step 2: Commit**

Run:
```bash
cd ~/GitHub/projects/skill-builder-skill && git commit -m "feat: initial skill-builder skill

End-to-end authoring path for new Claude Code skills. Six-phase
flow with three tiers (reference default, discipline escalated,
minimal de-escalated), sub-agent dispatch for research and review,
private GitHub repo + agent-toolkit-cli skill add as terminal step.
"
```
Expected: `[main (root-commit) <sha>] feat: initial skill-builder skill\n 14 files changed, ...`

### Task 16: Push to private GitHub repo

**Files:**
- Create: `github.com/ajanderson1/skill-builder-skill` (private)

- [ ] **Step 1: Confirm with user before pushing**

This is the first irreversible step. Pause and confirm with the user:

> About to create private repo `ajanderson1/skill-builder-skill` on GitHub and push. Proceed?

Wait for user's "yes" before continuing.

- [ ] **Step 2: Create + push**

Run:
```bash
cd ~/GitHub/projects/skill-builder-skill && gh repo create ajanderson1/skill-builder-skill --private --source=. --remote=origin --push
```
Expected (approximately):
```
✓ Created repository ajanderson1/skill-builder-skill on GitHub
  https://github.com/ajanderson1/skill-builder-skill
✓ Added remote git@github.com:ajanderson1/skill-builder-skill.git
✓ Pushed commits to git@github.com:ajanderson1/skill-builder-skill.git
```

- [ ] **Step 3: Verify**

Run: `gh repo view ajanderson1/skill-builder-skill --json visibility,defaultBranchRef`
Expected: `{"visibility":"PRIVATE","defaultBranchRef":{"name":"main"}}`

### Task 17: Register via `agent-toolkit-cli skill add`

**Files:**
- Modify: `~/.agent-toolkit/skills-lock.json`
- Create: `~/.agent-toolkit/skills/skill-builder/` (git clone)
- Create: `~/.claude/skills/skill-builder/` (symlink)

- [ ] **Step 1: Run skill add**

Run:
```bash
agent-toolkit-cli skill add ajanderson1/skill-builder-skill
```
Expected: success message naming the canonical clone path and the lock entry.

- [ ] **Step 2: Verify canonical clone**

Run: `ls ~/.agent-toolkit/skills/skill-builder/ && cat ~/.agent-toolkit/skills/skill-builder/SKILL.md | head -5`
Expected: directory listing showing SKILL.md, LICENSE, README.md, .gitignore, references/, templates/. Head of SKILL.md shows the frontmatter.

- [ ] **Step 3: Verify lock entry**

Run: `python -c "import json; print(json.dumps(json.load(open('/Users/ajanderson/.agent-toolkit/skills-lock.json'))['skills']['skill-builder'], indent=2))"`
Expected: JSON object with `source: "ajanderson1/skill-builder-skill"`, `sourceType: "github"`, populated `upstreamSha` and `localSha`.

- [ ] **Step 4: Verify Claude Code symlink**

Run: `ls -la ~/.claude/skills/skill-builder`
Expected: symlink pointing to `~/.agent-toolkit/skills/skill-builder` (or equivalent absolute path).

- [ ] **Step 5: Verify skill_library alias**

Run: `ls ~/GitHub/skill_library/skill-builder/SKILL.md`
Expected: file exists (resolved through the `~/GitHub/skill_library → ~/.agent-toolkit/skills` symlink).

### Task 18: End-to-end smoke test

**Files:**
- (none — manual conversation test)

- [ ] **Step 1: Restart Claude Code or refresh skill listing**

Restart the Claude Code session, or run `/skills` to confirm `skill-builder` appears in the listing.

- [ ] **Step 2: Trigger the skill manually**

In a fresh Claude Code session, say: "build a skill"

Expected: Claude invokes the `skill-builder` skill, which begins Phase 1 (preflight + intake). It should ask for a skill name.

- [ ] **Step 3: Walk through the full flow with a trivial test skill**

Suggested test target: a minimal-tier skill like `pyenv-reset` ("the three commands to reset pyenv").

Walk through all six phases. Expected terminal state: a new private repo `ajanderson1/pyenv-reset-skill`, a lock entry for `pyenv-reset`, a working canonical clone, the verification block printed.

If anything fails, capture the failure and the phase. **Do not** abandon the smoke test partway — finish it so we know whether the failure was the skill or the test target.

- [ ] **Step 4: Decide on the test artefact**

Either keep the smoke-test skill as a real skill, or:
- `agent-toolkit-cli skill remove pyenv-reset --force`
- `gh repo delete ajanderson1/pyenv-reset-skill --yes`

Either choice is fine — but make it deliberately.

---

## Self-review

**1. Spec coverage:**

| Spec section | Implementing task(s) |
|---|---|
| Architecture (where the skill lives) | Tasks 0, 15, 16, 17 |
| File layout (skill-builder's own files) | Tasks 1-9 |
| File layout (what it produces — templates) | Tasks 10-14 |
| Process flow (Phase 1 preflight + intake) | Task 3 (SKILL.md body) |
| Process flow (Phase 2 tier decision) | Task 3 + Tasks 4-6 |
| Process flow (Phase 3 research) | Task 7 |
| Process flow (Phase 4 scaffold + author) | Task 3 + Task 10 |
| Process flow (Phase 5 reviewer) | Task 8 |
| Process flow (Phase 6 repo + push + skill add) | Task 3 |
| Sub-agent dispatch detail | Tasks 7, 8 |
| Terminal state / verification block | Task 9 |
| Failure modes | Task 3 (table in SKILL.md) |
| What this skill does NOT do | Task 3 (final section of SKILL.md) |
| Self-host (end-to-end smoke test) | Task 18 |

All spec sections covered.

**2. Placeholder scan:** all code blocks contain real content. No "TBD", no "TODO", no "implement appropriate handling". Substitution placeholders (`{{name}}` etc.) are deliberate — they are the contract between SKILL.md and the templates.

**3. Type consistency:** the substitution placeholders are consistent across templates (Task 10, 11, 12, 13, 14) and the SKILL.md body that defines them (Task 3, Phase 4). `{{name}}`, `{{display_name}}`, `{{description}}`, `{{trigger_phrases}}`, `{{year}}`, `{{author}}` are the only six. No drift.

Plan complete.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-22-skill-builder-skill.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
