# Issue #482 verification — Commands standard projection

## Verdict (R1 visual judgment)

**Standard is first, the scope count is legible, the info copy distinguishes Devin, and one slot is visibly actionable.**

| Check | Evidence |
|---|---|
| Global header `Standard (2)` first, then Pi + Gemini | `visual-capture.txt`, `command-standard-global.svg` |
| Project header `Standard (3)` first | `visual-capture.txt`, `command-standard-project.svg` |
| Header info lists Claude + Neovate globally; + Devin-as-skill in project | `visual-capture.txt` info lines |
| Space on Standard queues a single shared-slot pending op | `command-standard-*-pending.svg`, pending keys |
| No duplicate Claude column | headers lack `Claude` / `claude-code` |

## Automated gates

| Suite | Result | Artifact |
|---|---|---|
| Focused CLI | 66 passed | `focused-cli.txt` |
| Focused TUI | 87 passed | `focused-tui.txt` |
| Full project suite | 2272 passed, 2 skipped | `full-suite.txt` |

## Commands

```bash
uv run pytest -q \
  tests/test_cli/test_command_adapters \
  tests/test_cli/test_command_lock.py \
  tests/test_cli/test_command_install.py \
  tests/test_cli/test_command_standard_projection.py \
  tests/test_cli/test_command_cli_standard.py

uv run pytest -q \
  tests/test_tui/test_command_state.py \
  tests/test_tui/test_command_grid.py \
  tests/test_tui/test_command_app.py \
  tests/test_tui/test_command_apply.py \
  tests/test_tui/test_composition.py \
  tests/test_tui/test_standard_column_rule.py \
  tests/test_tui/test_column_info.py

uv run pytest -q
uv run python assets/verification/issue-482/capture_visual_evidence.py
git diff --check
```

## Spec coverage

- `STANDARD_COMMAND_READERS` SSOT + ownership adapter
- Optional v1 lock `harnesses` field (legacy-compatible)
- Default install `standard,pi,gemini-cli`; `claude-code` → `standard`
- CLI list/status/doctor truthful about Standard
- TUI Standard-first composition + Apply via facade
