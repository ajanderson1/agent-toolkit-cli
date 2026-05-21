# agent-toolkit-cli

Python CLI and Textual TUI for managing AI-agent **skills** across Claude Code, Codex, OpenCode, Gemini CLI, and Pi. Lock-file-driven, byte-compatible with [`vercel-labs/skills`](https://github.com/vercel-labs/skills).

> **v2.3.0 — single-command CLI.** The pre-v2 surface (`check`, `link`, `doctor`, `fix`, `ingest`, `inventory`, `migrate-skills`, `new`, `diff`, `list`, `unlink`, `pi`) was removed in #160. The frozen v1 surface lives on at the `v1.0.0` tag — install it with `uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli@v1.0.0 agent-toolkit` if you need it. v2 commands will be rebuilt one by one in follow-up issues; see the tracker issue linked from PR #160.

## Install

```bash
uv tool install --from git+https://github.com/ajanderson1/agent-toolkit-cli agent-toolkit
# SSH form: git+ssh://git@github.com/ajanderson1/agent-toolkit-cli
```

> **Don't `pip install -e .` into a Python that comes earlier on `$PATH` than `~/.local/bin/`** (e.g., pyenv-managed Pythons). The pip shim will shadow `uv tool install`'s shim. If you must install editable for development, either:
>
> - Use a venv that you activate per-session (`python -m venv .venv && source .venv/bin/activate && pip install -e .`), or
> - First `uv tool uninstall agent-toolkit` to make the precedence explicit, and re-install from uv when you're done.

## Commands

### Skills — lock-file driven, agent-aware

```text
agent-toolkit-cli skill add <source> [--ref <ref>] [--slug <slug>] [--skill <name>]
agent-toolkit-cli skill list [-g|-p]
agent-toolkit-cli skill status [<slug>...] [-g|-p]
agent-toolkit-cli skill update [<slug>...] [-g|-p]      # merge-aware
agent-toolkit-cli skill push   [<slug>...] [-g|-p]      # self-improvements upstream
agent-toolkit-cli skill remove <slug>... [-g|-p] [--force]
```

`<source>` accepts `owner/repo`, full URL, SSH URL, or local path — same scheme as `npx skills add`. See [`docs/agent-toolkit/skill-lock.md`](docs/agent-toolkit/skill-lock.md) for the lock-file format and skills.sh interop details.

The CLI uses the 55-agent catalog ported from [vercel-labs/skills](https://github.com/vercel-labs/skills/blob/main/src/agents.ts). Universal agents (codex, opencode, gemini-cli, +11 more whose `skillsDir == .agents/skills`) skip per-harness symlinks at global scope. Non-universal agents (claude-code, pi, windsurf, +37 more) still get their per-harness symlink. Interactive wizard groups by universality; TUI skill grid covers the two we explicitly support (claude-code, pi). v2.0.0's `AGENT_TOOLKIT_TUI_LEGACY=1` escape hatch is preserved.

**Monorepo skills:** A `<source>` may name a parent repo that contains several skills. Pick one with `--skill <name>` (matches `SKILL.md` frontmatter `name:`), or pass the subpath inline (`owner/repo/<subpath>` or `<repo>/tree/<ref>/<subpath>`). `https://www.skills.sh/<owner>/<repo>/<skill>` URLs also work end-to-end.

The parent clone lives at `<library>/_parents/<owner>/<repo>/` and is yours to edit — local commits are first-class. `skill update` runs `git fetch` + `git merge` on that clone, so your work merges with upstream like any normal git repo. On conflict the clone is left mid-merge; resolve in place and re-run `skill update`. The TUI reports each monorepo skill's `state` as `clean` or `dirty`, same semantics as per-skill repos. `skill push` still refuses monorepo entries — sharing changes back upstream means forking the parent yourself.

### TUI

```text
agent-toolkit-tui                              # interactive skill grid (claude-code + pi)
AGENT_TOOLKIT_TUI_LEGACY=1 agent-toolkit-tui   # restore the legacy multi-tab layout
```

Full reference: [`docs/agent-toolkit/cli.md`](docs/agent-toolkit/cli.md).

## Development

```bash
git clone https://github.com/ajanderson1/agent-toolkit-cli ~/GitHub/projects/agent-toolkit-cli
cd ~/GitHub/projects/agent-toolkit-cli
uv sync --all-extras
uv run pytest -q
```

The `lefthook.yml` runs pytest on pre-commit.

## License

MIT (c) AJ Anderson
