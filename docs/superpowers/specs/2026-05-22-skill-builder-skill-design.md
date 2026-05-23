# skill-builder — design

A Claude Code skill that scaffolds, validates, and ships new skills end-to-end. Private-by-default, git-versioned, integrated with `agent-toolkit-cli`'s lock-file model.

## Why this skill

AJ's existing skills (`aj-workflow`, `journal`, `bitwarden`) were each authored ad-hoc. The agent-toolkit-cli treats every skill as a standalone git repo registered in `skills-lock.json`, but there's no first-class authoring path — `skill add` *clones* from an existing upstream; it does not *adopt* a local tree. Hand-rolling the upstream repo + push + `skill add` sequence works, but it's repetitive and skipping steps (no LICENSE, weak trigger phrases, untested description) is easy.

`skill-builder` is the missing authoring path. It is itself a skill — same shape and same lifecycle as everything else under `~/.agent-toolkit/skills/`.

## Scope

- Authoring + validation + registration of a single new skill per invocation.
- Three quality tiers (reference, discipline, minimal) with progressive disclosure.
- Sub-agent dispatch for up-front research and end-of-build review.
- Private GitHub repos by default; MIT license.
- Integration with `agent-toolkit-cli skill add` as the terminal step.

Out of scope (explicit non-goals listed at the end).

## Architecture

`skill-builder` is a Claude Code skill, model-invoked via description triggers, distributed exactly like AJ's other skills:

| Location | Purpose |
|---|---|
| `github.com/ajanderson1/skill-builder-skill` (private) | Upstream source-of-truth |
| `~/GitHub/projects/skill-builder-skill/` | Working tree (where AJ edits it day-to-day) |
| `~/.agent-toolkit/skills/skill-builder/` | Canonical clone after `skill add` |
| `~/GitHub/skill_library/skill-builder/` | Symlink alias for the canonical clone |
| `~/.claude/skills/skill-builder/` | Per-harness symlink, auto-created by `skill add` |

When invoked, the skill produces a new git repo at `~/GitHub/projects/<name>-skill/`, pushed to a new private GitHub repo `ajanderson1/<name>-skill`, registered via `agent-toolkit-cli skill add ajanderson1/<name>-skill`. The skill's job ends there. Future edits to the new skill happen at `~/GitHub/skill_library/<name>/`, shipped via `skill push`.

The naming convention `<name>-skill` for upstream repos and `<name>` for the canonical/symlink directory matches AJ's existing pattern (`aj-workflow-skill` → `aj-workflow`).

## File layout

### The `skill-builder` skill itself

```
~/GitHub/projects/skill-builder-skill/
├── SKILL.md                              # ≤500 lines: triggers, flow, tier decision, links
├── LICENSE                                # MIT, AJ Anderson
├── README.md                              # short, points at SKILL.md
├── .gitignore
├── references/
│   ├── tier-discipline.md                # TDD/RED-GREEN-REFACTOR detail (loaded only when escalated)
│   ├── tier-reference.md                 # layout+lint detail (default tier)
│   ├── tier-minimal.md                   # quick-scaffold detail (de-escalated)
│   ├── research-agent-prompts.md         # copy-paste prompts for up-front research dispatch
│   └── skill-reviewer-checklist.md       # what the reviewer subagent reads at the end
└── templates/
    ├── SKILL.md.tmpl                     # the scaffold stamped into the new skill repo
    ├── LICENSE.tmpl                      # MIT with {{year}} + {{author}} placeholders
    ├── README.md.tmpl
    ├── .gitignore.tmpl
    └── AGENTS.md.tmpl                    # optional, stamped only if the new skill warrants it
```

### What it produces (the new skill repo)

```
~/GitHub/projects/<name>-skill/
├── SKILL.md                              # filled from SKILL.md.tmpl per chosen tier
├── LICENSE                                # MIT, AJ Anderson, current year
├── README.md
├── .gitignore
├── references/                            # empty in reference-tier; omitted in minimal-tier
└── templates/                             # only if the skill warrants it (rare)
```

`references/` is created empty in reference-tier so the skill can graduate to richer content later without restructuring. Minimal-tier omits it entirely. `scripts/` and `examples/` directories are not created by default — added per-skill only when content needs them. This diverges from Anthropic plugin-dev's recommendation but matches AJ's existing skills, which use none.

## Process flow

Six phases, surfaced via TodoWrite at start so progress is visible.

```
1. Preflight + intake
2. Tier decision (default = reference)
3. Up-front research (conditional)
4. Scaffold + author
5. Reviewer subagent pass (mandatory, opinionated)
6. Repo creation + push + skill add
```

### Phase 1 — Preflight + intake

**Preflight (parallel, fail-fast):**
- `gh auth status` — GitHub CLI authenticated
- `which agent-toolkit-cli` — CLI on PATH
- `gh repo view ajanderson1/<derived-slug>-skill 2>/dev/null` — surface repo name collisions early
- `test -e ~/GitHub/projects/<derived-slug>-skill/` — surface local path collisions early

Any preflight failure is fatal. Builder prints what's missing and stops.

**Intake (one question at a time):**
- Skill name (kebab-case, lowercase, ≤64 chars; default derived from intake)
- One-sentence purpose
- Trigger phrases that should load it (minimum 2, max 5)

### Phase 2 — Tier decision

Builder pre-proposes a tier from intake signals; user confirms or overrides.

| Tier | Signal words | Reference doc |
|---|---|---|
| Discipline | "always", "never", "don't", "must", "stop X", "under pressure" | `references/tier-discipline.md` |
| Reference (default) | "how to", "checklist", "convention", "template", "when working with X" | `references/tier-reference.md` |
| Minimal | "just wrap", "remind me", "quick recipe", "shell snippet" | `references/tier-minimal.md` |

Only the chosen tier's reference doc loads. Tier choice gates downstream rigor; the user can override even after a pushback.

**Mandatory pushback case:** if the user picks **minimal** but intake contained discipline signals, builder pushes back once:

> "Your intake said 'always X under pressure' — that's a behaviour rule, which usually needs discipline-tier rigor. Sure you want minimal? Minimal skills get ignored under pressure."

User can still override. Builder does not block.

### Phase 3 — Up-front research (conditional)

**Fires when:** intake mentions an external dependency (CLI, library, framework, service, third-party tool) that the builder doesn't already know cold.

**Skipped when:** tier = discipline (behaviour-focused, not facts) or intake is purely about AJ's own tooling.

**Pattern:** parallel `general-purpose` subagents, run-in-background, one per topic, dispatched in a single message. Prompts come from `references/research-agent-prompts.md`, which has three reusable templates:

1. External-tool research — what does `<tool>` do, CLI surface, gotchas, idioms?
2. Prior-art research — search `vercel-labs/skills`, `anthropics/skills`, `~/.agent-toolkit/skills/` for overlapping skills.
3. Convention check — read `~/.conventions/conventions/<relevant>.md` and report applicable rules.

Synthesis happens at Phase 4 start.

### Phase 4 — Scaffold + author

**Scaffold step:** stamp templates from `templates/` into `~/GitHub/projects/<name>-skill/`, with substitutions:
- `{{name}}` → kebab-case slug
- `{{display_name}}` → human title-case form
- `{{description}}` → from intake
- `{{trigger_phrases}}` → from intake
- `{{year}}` → current year
- `{{author}}` → "AJ Anderson"

**Author step:** builder writes SKILL.md body collaboratively, section by section, asking after each. Tier-specific guidance from the loaded `tier-<picked>.md` shapes which sections exist:

| Section | Reference | Discipline | Minimal |
|---|---|---|---|
| Frontmatter | ✓ | ✓ | ✓ |
| When to use | ✓ | (folded into "When this applies") | ✓ |
| Process / Instructions | ✓ | ✓ ("How to comply") | ✓ |
| Examples (one worked) | ✓ | ✓ | ✗ |
| Common mistakes | ✓ (optional) | ✗ | ✗ |
| The rule | ✗ | ✓ | ✗ |
| When this applies | ✗ | ✓ | ✗ |
| Rationalisations table | ✗ | ✓ (≥3 rows) | ✗ |
| Red flags | ✗ | ✓ | ✗ |

**Discipline tier inserts behavioural testing within Phase 4:**

- **Phase 4a (baseline):** dispatch a subagent with 3+ combined pressures (time, sunk cost, authority, exhaustion, etc.) running the skill's target scenarios WITHOUT the skill loaded. Capture rationalisations verbatim.
- **Phase 4c (verification):** same subagent prompt, WITH the skill present. Must comply.
- **Refactor loop:** failures feed back into the rationalisations table and skill body until the agent complies. Loop is bounded at 3 iterations (see Failure modes).

Reference and minimal tiers skip behavioural testing entirely. This matches Anthropic plugin-dev guidance and matches AJ's existing skills.

### Phase 5 — Reviewer subagent (mandatory, opinionated)

**Pattern:** single `general-purpose` subagent, **foreground** (Phase 6 needs the result), **no conversation context** ("Do NOT read any other conversation context" in the prompt — reviewer judges what's on disk, not what the user wanted to write).

**Checklist** (lives in `references/skill-reviewer-checklist.md`):

- **Frontmatter:** `name` kebab-case ≤64 chars; `description` starts with "Use when..."; ≤1024 chars; contains ≥2 distinct trigger phrases
- **Body:** ≤500 lines; ≤3k words; imperative voice (no "you should"); one worked example present (reference + discipline tiers); no `@`-prefixed cross-references
- **Tier-specific:** rationalisations table ≥3 rows (discipline); red-flags list (discipline); "Common mistakes" section warned-if-missing (reference)
- **Triggerability:** if a future user said any trigger phrase, would the skill obviously activate? (Y/N + reasoning)

**Result:** PASS / PASS-WITH-COMMENTS / FAIL.

**Authority model:** the human has final say. Reviewer is opinionated by design — a FAIL is meant to be inconvenient, otherwise it gets rubber-stamped. On a FAIL the builder presents findings and asks the user to either:

1. **Apply fixes** — builder helps, re-runs reviewer, loops until PASS.
2. **Override** — "ship it anyway, here's why" — the one-line reason gets prepended to the commit message as `(reviewer override: <reason>)`. Build proceeds to Phase 6.
3. **Abandon** — stop the build, leave the local scaffold in place, don't push.

### Phase 6 — Repo creation + push + `skill add`

This is the first phase that touches a shared system. Builder asks for confirmation once before running:

```bash
cd ~/GitHub/projects/<name>-skill
git init && git add -A && git commit -m "feat: initial <name> skill"
gh repo create ajanderson1/<name>-skill --private --source=. --remote=origin --push
agent-toolkit-cli skill add ajanderson1/<name>-skill
```

Note: `agent-toolkit-cli skill add` does NOT accept `-g`/`-p` flags — it is global-only by construction. The skill always lands at `~/.agent-toolkit/skills/<name>/` and gets a global lock entry. See memory: `project_skill_add_global_only`.

After success, builder prints the verification block (see Terminal state).

## Sub-agent dispatch

Two dispatch points, three patterns.

| Point | Pattern | Foreground/background | Context |
|---|---|---|---|
| Phase 3 — research | Parallel `general-purpose`, 1-3 topics, prompts from `research-agent-prompts.md` | Background; builder continues intake | Topic-specific prompt only |
| Phase 4a/4c — pressure tests (discipline only) | Sequential `general-purpose`, adversarial scenarios | Foreground (need results before refactor) | Scenario prompt only; no skill body until 4c |
| Phase 5 — reviewer | Single `general-purpose`, checklist | Foreground (Phase 6 blocks on result) | **Reviewer reads files only; explicitly no conversation context** |

Reviewer-no-context is load-bearing. Otherwise the reviewer rubber-stamps what it heard the user ask for instead of judging what's on disk.

## Terminal state

When the build succeeds, this is true:

- `~/GitHub/projects/<name>-skill/` exists as a working git repo with an initial commit
- `github.com/ajanderson1/<name>-skill` exists as a private repo with `main` pushed and the local branch tracking origin
- `~/.agent-toolkit/skills/<name>/` is a clone of that upstream
- `~/.agent-toolkit/skills-lock.json` has a new entry for `<name>` with the upstream sha
- `~/.claude/skills/<name>/` symlink exists (created by `skill add`)

Builder prints a verification block:

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

## Failure modes

| Failure | Builder's response |
|---|---|
| `gh repo create` collides with existing repo | Per `feedback_existing_repo_history_preserve`: STOP. Run `gh repo view --json isEmpty,pushedAt`. If non-empty, refuse to force-push; offer rename or clone-and-graft flow. |
| `git push` fails (network, auth) | Leave the local scaffold in place. Print recovery instructions. Don't roll back. |
| `agent-toolkit-cli skill add` fails | Report the CLI error verbatim. Leave the upstream repo intact. Print the manual `skill add` command for retry. |
| Reviewer FAILs and user overrides | Override reason prepended to commit message as `(reviewer override: <reason>)`. Build proceeds. |
| `gh` not authenticated / CLI not on PATH | Detected in Phase 1 preflight. Builder refuses to start with clear remediation. |
| Discipline-tier verification subagent keeps failing | Loop bounded at 3 iterations. After that, builder asks user to either de-escalate to reference tier or accept the skill as-is with a noted weakness. |

## What this design intentionally does NOT do

- **No auto-behavioural-test of the built skill in non-discipline tiers.** The reviewer is a static checklist; behavioural testing only happens in discipline tier. Reference and minimal tiers are not test-driven — matches plugin-dev guidance and matches AJ's existing skills.
- **No GitHub Actions / CI scaffold** in the new skill repo. Skills are markdown. CI would be cargo-cult.
- **No `skill-builder` self-update mechanism.** When `skill-builder` improves, it updates via the normal `skill push` / `skill update` workflow — same as any other skill.
- **No multi-skill batch builds.** One build per invocation. Each skill ships before the next is started — matches Anthropic writing-skills' STOP gate.
- **No `skill register <local-path>` CLI verb.** The chicken-and-egg of "adopt an in-place tree into the lock" is sidestepped by always authoring at `~/GitHub/projects/<name>-skill/` (separate from canonical) and letting `skill add` do the clone. If a future use case demands in-place adoption, that's a separate CLI feature.
- **No project-scope (`-p`) variant.** `skill add` is global-only; new skills always land in the global library. Project pinning is a follow-on workflow, not part of authoring.
- **No public-by-default.** Every skill repo is created `--private`. Flipping to public is a manual `gh repo edit --visibility public` later.

## References

- `vercel-labs/skills` — lock-file schema and `npx skills init` template (minimal-tier baseline)
- Anthropic `superpowers:writing-skills` — TDD-with-pressure-tests methodology (discipline-tier baseline)
- Anthropic `plugin-dev/skill-development` — file layout + lint rules (reference-tier baseline)
- `~/.conventions/CONVENTIONS.md` — copyright, license, host defaults
- `docs/agent-toolkit/skill-lock.md` — lock-file format
- Memory: `project_skill_add_global_only`, `project_agent_toolkit_cli_scope_defaults`, `feedback_existing_repo_history_preserve`, `feedback_subagent_git_isolation`, `feedback_git_env_leak`
