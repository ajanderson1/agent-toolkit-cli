# Roadmap

Where `agent-toolkit-cli` and `agent-toolkit-tui` are headed after v2.0.0. Items are listed in rough priority order, not strict chronology.

The v2.0.0 release stripped the TUI down to the skill asset type and adopted the [`vercel-labs/skills`](https://github.com/vercel-labs/skills) lock-file model end-to-end for skills. Everything below is work that the v2.0.0 release **explicitly defers** — the README is the source of truth for what's actually shipped today.

## v2.x (additive)

### Auto-push of self-improvements

End-of-session hook that runs `agent-toolkit-cli skill push` for any dirty canonical clones, so the agent's in-place edits flow back to upstream without manual `push`. Opt-in via per-skill `autoPush: true` in the lock entry.

Open questions: where the hook installs (Claude Code session-end? generic shell exit?), how to surface push failures without interrupting the next session.

### Real-skill extraction sweep

The monorepo `~/GitHub/agent-toolkit/skills/` still contains ~30 first-party skills. Each needs extracting to its own GitHub repo via `git filter-repo --path skills/<slug>` to preserve history, then `agent-toolkit-cli skill add ajanderson1/<slug> -g`.

Worth doing one skill at a time, validating self-improvement flow on each, before bulk migrating. The mechanism is proven; only the manual extraction labour remains.

### skills.sh v3 global write-through

Today, `agent-toolkit-cli skill add -g` against a fresh `$HOME` writes a v1 lock. If `npx skills` is the dominant tool on the same machine, it expects v3. The reader handles both, the writer preserves an existing v3 file's version — but a brand-new global lock our CLI creates won't be readable by `npx skills` until they bump their reader to accept v1 (or we default to v3 for global scope).

Decision pending: default `-g` to v3 entry shape, or stay on v1 and document the asymmetry.

## v3.x (the other six asset types)

### Phase 2: revisit agent, command, hook, plugin, pi-extension

For each asset type, decide whether the lock-file model applies. Status as of 2026-06-10:

| Asset type | Model | Status |
|---|---|---|
| agent | Per-agent repo + lock — same shape as skills. | **Delivered** (v3.4.0, #252 SAFE slice) |
| pi-extension | Per-extension repo + lock — same shape as skills. | **Delivered** (v3.3.0) |
| instructions | Managed AGENTS.md/CLAUDE.md slots + lock. | **Delivered** (v3.5.x, #283/#305/#337) |
| mcp | Local library at `~/.agent-toolkit/mcps/` (`add` authors from `--npx`/`--uvx`/`--docker`/`--url`/`--local`) + config-injection adapters across four harnesses + `mcps-lock.json`. | **Delivered** (foundations slice, #329 — `add`/`install`/`uninstall`/`remove`/`update`/`list`/`status`/read-only `doctor`; `fix`/`diff`/TUI/library-sync deferred) |
| command | Per-command repo + lock — same shape as skills. | Pending |
| plugin | Per-plugin repo; CLI drives `installed_plugins.json` / local-path marketplace. | Pending — see the bundle ADR (`docs/solutions/architecture-patterns/`, 2026-06-10) |
| hook | Per-hook repo; CLI does the `settings.json` injection. | Pending |

The structural-shape constraint (folder-with-markdown vs. config-injection) is the determinant. Skills, agents, commands, and pi-extensions are folder-shaped → easy. MCPs, hooks, and plugins are config-injection → need an adapter layer that translates `<slug>/manifest.toml` to the target config file.

Each asset type will land in its own spec + plan, not a single bulk PR.

### TUI: collapse legacy mode

Once all seven asset types are lock-file-driven, the `AGENT_TOOLKIT_TUI_LEGACY=1` flag becomes redundant. The default TUI gets a real asset-types sidebar populated from lock entries, not from the walker. The seven tabs converge on the SkillGrid's shape (slug · source · ref · state).

`AGENT_TOOLKIT_TUI_LEGACY` is removed at that point. The current default-mode behaviour (skills only) is itself a transitional state.

### Verb remap: `enable`/`disable` for projection { #verb-remap-enable-disable-for-projection }

**Status: idea, not committed.** The lifecycle verbs split across [two axes](../glossary.md): `add`/`remove` change [library](../glossary.md#library) membership (destructive), while `install`/`uninstall` change [projection](../glossary.md#projection) into a harness/scope (non-destructive). The friction is that all four read as generic "put / take away" words, so nothing in the verb tells you which axis you're on — the glossary has to spell it out.

Proposal: rename the Axis-2 pair from `install`/`uninstall` to **`enable`/`disable`**, keeping `add`/`remove` for Axis 1. This makes the two axes use *different verb families* — the legible pattern every clean two-axis tool follows (`systemctl enable`/`start`; VS Code `install`/`enable`; Claude Code `plugin install`/`enable`). It also matches the harness we live closest to: the Claude Code plugin flow is `marketplace add` → `plugin install` → `plugin enable`/`disable`, where `enable`/`disable` is exactly the per-context activation axis we call `install`/`uninstall`.

Resulting surface, per asset type and scope (project / global):

| Today | Proposed | Axis |
|---|---|---|
| `add` / `remove` | `add` / `remove` (unchanged) | 1 — library membership |
| `install` / `uninstall` | `enable` / `disable` | 2 — projection into a harness/scope |

Open questions before this is worth committing:

- **Breaking-change cost.** `install`/`uninstall` are load-bearing across every asset-type CLI namespace, the TUI, tests, skills, docs, and lock-adjacent tooling. A remap is a major-version surface change; likely shipped with `install`/`uninstall` kept as hidden aliases for one or more releases.
- **`enable` vs `disable` connotations.** `enable` could read as "toggle on in place" rather than "render into this scope"; verify it doesn't blur into a config-flag mental model. Alternatives considered: `apply`/`unapply` (chezmoi-style), `link`/`unlink` (Homebrew-style, but inaccurate for non-symlink mechanisms).
- **Interop.** The skills lock format is byte-compatible with `vercel-labs/skills`; confirm the verb rename touches only our CLI surface, not the persisted lock shape, so interop is unaffected.

If adopted, the glossary's two-axis callout and every asset-type page's verb table update in the same change.

### Walker + sidecar retirement — delivered in v2.3.0 (#160)

The `walker.py` module, `*.toolkit.yaml` sidecar discovery, the `agent-frontmatter.v1alpha2.json` schema's sidecar branch, the `--toolkit-repo` flag, and the `link` / `unlink` / `check` / `fix` / `doctor` / `inventory` / `new` / `migrate-skills` / `diff` / `list` / `pi` legacy commands were deleted in #160. The frozen v1 surface lives at the `v1.0.0` tag for anyone still needing it.

This was a one-shot cleanup commit, not a gradual deprecation. It is the structural finish line for the v1 → v3 transition that started with v2.0.0.

## Not on the roadmap (explicit non-goals)

- **Submitting to the public skills.sh catalogue.** Private repos remain private; we use the addressing scheme and lock format without depending on or appearing in the public index.
- **Wrapping `npx skills` as a subprocess.** We re-implement in Python so we are not exposed to upstream breakage. The interop test (`tests/test_cli/test_skill_interop.py`) verifies bit-compatibility, but the CLI does not depend on `npx skills` being installed.
- **Multi-user / team sync of self-improvements.** Self-improvements flow per-user via the user's own forks; team-wide propagation is out of scope.
- **Shallow clones / disk-cost optimisation.** Full `.git/` per skill is acceptable (~few hundred KB each); revisit if disk becomes a real problem.

## Open questions

- How to surface "you have N dirty skills" prominently when the agent is about to end a session — a quiet TUI hint vs. a hard prompt vs. nothing at all.
- Whether to add a `skill diff` verb that runs `git diff` against upstream for a given slug (cheap convenience but adds surface area).
- What happens when a user runs `skill add` against a slug that's already installed by `npx skills` in copy-mode — overwrite? error? prompt to convert?

Suggestions / pushback welcome in PRs against this file or in GitHub issues.
