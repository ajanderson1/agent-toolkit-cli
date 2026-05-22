# Spec — `agent-toolkit-tui --version` should print and exit

Closes #211.

## Problem

`agent-toolkit-tui --version` (and `-V`) currently launches the TUI instead of printing the version string. The CLI sister command (`agent-toolkit-cli --version`) uses Click's `@click.version_option` and exits 0 with `agent-toolkit-cli, version X.Y.Z`. The two entrypoints should be symmetric for the version flag.

## Approach

Intercept `--version` / `-V` in `agent_toolkit_tui.app.main()` before the `TUIApp` constructor runs. The TUI does not use Click (Textual app, no command group), so we handle argv manually — minimal surface, no new dependency.

Behaviour:
- `agent-toolkit-tui --version` → prints `agent-toolkit-tui, version X.Y.Z\n` and exits 0.
- `agent-toolkit-tui -V` → identical.
- Any other argv (including none) → unchanged; TUI launches as before.

Output format matches Click's default (`<prog>, version <ver>`) so users get the same UX regardless of which binary they invoke.

Version source: existing `agent_toolkit_tui.__version__`, which already resolves via `importlib.metadata.version("agent-toolkit")` with `"unknown"` fallback.

## Implementation sketch

In `src/agent_toolkit_tui/app.py`:

```python
def main() -> int:
    import sys
    argv = sys.argv[1:]
    if argv and argv[0] in ("--version", "-V"):
        print(f"agent-toolkit-tui, version {__version__}")
        return 0
    TUIApp().run()
    return 0
```

Keep the check narrow — only the first positional flag, exact match. No argparse, no Click — `main()` stays a thin entrypoint.

## Tests

New `tests/test_tui/test_version_flag.py`:

1. `agent-toolkit-tui --version` via `subprocess.run(["uv", "run", "agent-toolkit-tui", "--version"])`:
   - exit code 0
   - stdout matches `r"^agent-toolkit-tui, version \S+\n$"`
   - stdout does NOT contain Textual TUI markup
2. Same for `-V`.
3. Sanity: with no argv, `main()` does not invoke the version path (mock `TUIApp.run` to a no-op and assert it was called).

The subprocess tests are the canonical regression check — they prove the user-visible behaviour without booting Textual.

## Out of scope

- Renaming the TUI binary or changing the CLI's version output format.
- Adding `--help` to the TUI (separate concern; Textual provides bindings help in-app).
- Migrating the TUI to Click.

## Definition of done

- `uv run agent-toolkit-tui --version` prints the version and exits 0.
- `uv run agent-toolkit-tui -V` behaves identically.
- `tests/test_tui/test_version_flag.py` passes.
- `uv run pytest -q` green.
