# AGENTS.md — agent-toolkit-cli

The Python CLI (`src/agent_toolkit_cli`) and the Textual TUI (`src/agent_toolkit_tui`) for managing AI-agent skills. v2.3.0 removed the pre-v2 surface (`check`, `link`, `doctor`, ...); only `skill` remains. The frozen v1 surface is pinned at the `v1.0.0` tag — see `README.md` for the install command.

## Code map

```
src/agent_toolkit_cli/             Python package: skill command + lockfile machinery.
  cli.py                           Click group; only `skill` is registered.
  commands/skill/                  `skill add | list | status | update | push | remove`.
  skill_agents.py                  55-agent catalog (ported from vercel-labs/skills).
  skill_git.py                     Git operations against per-skill upstream repos.
  skill_install.py                 Install/uninstall a skill into a harness home.
  skill_lock.py                    Read/write the `skill-lock.toml` lockfile.
  skill_paths.py                   Canonical paths for skills, lockfiles, projections.
  skill_source.py                  Parse `<owner/repo>` / URL / SSH / local-path sources.
  _repo_resolution.py              Resolve toolkit-repo root (used by TUI).
  _support.py                      Status constants used by TUI.
src/agent_toolkit_tui/             Textual TUI: skill grid (claude-code + pi).
docs/agent-toolkit/                Human-readable reference (cli.md, skill-lock.md).
docs/solutions/                    Documented decisions & fixes (bugs, trade-offs, patterns) by category, with YAML frontmatter (module, tags, problem_type).
tests/                             pytest. TUI tests live in tests/test_tui/.
```

## Development workflow

```bash
uv sync --all-extras
uv run pytest -q
uv run agent-toolkit-cli skill list
```

`lefthook.yml` runs `uv run pytest -q` on pre-commit.

## Testing

`tests/conftest.py` includes an autouse fixture that strips `GIT_*` env vars from `os.environ` before every test runs. This closes the lefthook-leak trap (#209): a test that shells out to `git` without an explicit `env=` argument no longer inherits `GIT_DIR` / `GIT_INDEX_FILE` from a parent hook and cannot accidentally write commits into the outer repo.

For most tests this means `subprocess.run(["git", ...], cwd=tmp_path)` is safe by default. Pass an explicit `env=` only when the test needs to **set** identity vars (e.g. `GIT_AUTHOR_NAME` for a deterministic commit) — not when it merely needs to **prevent leakage**.

## Adding a new `skill` subcommand

1. Add a new module under `src/agent_toolkit_cli/commands/skill/<name>_cmd.py`.
2. Define a Click command; import shared helpers from `_common.py`.
3. Register the command in `src/agent_toolkit_cli/commands/skill/__init__.py`.
4. Add a test under `tests/test_cli/test_cli_skill_<name>.py`.

## What lives elsewhere

- **Skill content** (the actual skill markdown / source) lives in each skill's upstream git repo; this CLI clones into a canonical lockfile-driven directory.
- **Schema** for skill-lock entries: see `docs/agent-toolkit/skill-lock.md`.
- **Agent catalog** (which harnesses are universal vs. per-harness): ported from `vercel-labs/skills` at the v2.1.0 cut; lives in `skill_agents.py`.
