# Roadmap

Where `agent-toolkit-cli` and `agent-toolkit-tui` are headed after v2.0.0. Items are listed in rough priority order, not strict chronology.

The v2.0.0 release stripped the TUI down to the skill kind and adopted the [`vercel-labs/skills`](https://github.com/vercel-labs/skills) lock-file model end-to-end for skills. Everything below is work that the v2.0.0 release **explicitly defers** — the README is the source of truth for what's actually shipped today.

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

## v3.x (the other six kinds)

### Phase 2: revisit agent, command, hook, mcp, plugin, pi-extension

For each kind, decide whether the lock-file model applies. The likely outcomes:

| Kind | Likely model |
|---|---|
| agent | Per-agent repo + lock — same shape as skills. |
| command | Per-command repo + lock — same shape as skills. |
| plugin | Per-plugin repo containing manifest + README; CLI does the `installed_plugins.json` injection. |
| mcp | Per-MCP repo containing manifest + README; CLI does the `~/.codex/config.toml` injection. |
| hook | Per-hook repo containing manifest + README; CLI does the `settings.json` injection. |
| pi-extension | Per-extension repo + lock — likely same shape as skills. |

The structural-shape constraint (folder-with-markdown vs. config-injection) is the determinant. Skills, agents, commands, and pi-extensions are folder-shaped → easy. MCPs, hooks, and plugins are config-injection → need an adapter layer that translates `<slug>/manifest.toml` to the target config file.

Each kind will land in its own spec + plan, not a single bulk PR.

### TUI: collapse legacy mode

Once all seven kinds are lock-file-driven, the `AGENT_TOOLKIT_TUI_LEGACY=1` flag becomes redundant. The default TUI gets a real kinds sidebar populated from lock entries, not from the walker. The seven tabs converge on the SkillGrid's shape (slug · source · ref · state).

`AGENT_TOOLKIT_TUI_LEGACY` is removed at that point. The current default-mode behaviour (skills only) is itself a transitional state.

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
