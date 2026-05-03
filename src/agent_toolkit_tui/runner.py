"""Subprocess wrapper around bin/agent-toolkit.

The TUI's only writer-of-truth on the filesystem. The widgets and state code
never call subprocess directly — they go through this class. Mockable: pass
a fake to TUIApp(runner=...) in tests.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


def _locate_bash_cli() -> Path:
    """Find this CLI's bash entry point (`bin/agent-toolkit`).

    The TUI shells out to the bash CLI for `list`/`link`/`unlink` (which the
    Python entry point doesn't expose). The bash script lives in this CLI's
    source tree and is not installed onto $PATH by `uv tool install`, so we
    walk up from this module's location to find it.

    Resolution order:
      1. $AGENT_TOOLKIT_BASH_CLI override (escape hatch for tests/installs)
      2. Walk up from runner.py looking for `bin/agent-toolkit`
      3. Raise FileNotFoundError with an actionable message
    """
    override = os.environ.get("AGENT_TOOLKIT_BASH_CLI")
    if override:
        p = Path(override)
        if p.is_file():
            return p
        raise FileNotFoundError(f"$AGENT_TOOLKIT_BASH_CLI={override} is not a file")

    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "bin" / "agent-toolkit"
        # The bash CLI sits next to a `lib/` subdir of helper sourceables; the
        # python entry point installed by `uv tool install` does not. This
        # disambiguates the two when both happen to share the parent name.
        if candidate.is_file() and (candidate.parent / "lib").is_dir():
            return candidate

    raise FileNotFoundError(
        "Cannot locate `bin/agent-toolkit` — the TUI requires a source checkout "
        "of agent-toolkit-cli (the wheel does not bundle the bash script). "
        "Set $AGENT_TOOLKIT_BASH_CLI to override, or run from "
        "`uv run --project <cli-repo> agent-toolkit-tui`."
    )


class RunnerError(RuntimeError):
    """Raised when a CLI invocation returns a non-zero exit code we don't expect."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        super().__init__(message)
        self.errors: list[str] = errors or []


@dataclass(frozen=True)
class PlanResult:
    ok: int
    failed: int
    errors: list[str] = field(default_factory=list)


_SUMMARY_RE = re.compile(r"Plan applied: (\d+) ok, (\d+) failed")


class CLIRunner:
    """Single chokepoint for shelling out to bin/agent-toolkit.

    Defaults to `<toolkit_root>/bin/agent-toolkit` so the TUI invokes the CLI
    from the same checkout it's reading metadata from. Override `cli_path`
    in tests.
    """

    def __init__(self, toolkit_root: Path, cli_path: Path | None = None) -> None:
        self.toolkit_root = toolkit_root.resolve()
        self.cli_path = cli_path or _locate_bash_cli()

    # ----- reads ----------------------------------------------------------
    def list_state(self) -> dict:
        """Invoke `list --format=json` and return the parsed document."""
        proc = subprocess.run(
            [str(self.cli_path), "list", "--format=json", "--toolkit-repo", str(self.toolkit_root)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            raise RunnerError(f"list --format=json exited {proc.returncode}: {proc.stderr.strip()}")
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RunnerError(f"list --format=json returned invalid JSON: {e}") from e

    # ----- writes ---------------------------------------------------------
    def link_plan(self, *, scope: str, harness: str,
                  entries: list[tuple[str, str]], dry_run: bool = False) -> PlanResult:
        """Batch-link N (kind, slug) pairs via stdin."""
        return self._plan("link", scope, harness, entries, dry_run)

    def unlink_plan(self, *, scope: str, harness: str,
                    entries: list[tuple[str, str]], dry_run: bool = False) -> PlanResult:
        """Batch-unlink N (kind, slug) pairs via stdin."""
        return self._plan("unlink", scope, harness, entries, dry_run)

    def _plan(self, op: str, scope: str, harness: str,
              entries: list[tuple[str, str]], dry_run: bool) -> PlanResult:
        if not entries:
            return PlanResult(ok=0, failed=0)
        cmd = [str(self.cli_path), op, scope, harness, "--plan", "-",
               "--toolkit-repo", str(self.toolkit_root)]
        if dry_run:
            cmd.append("--dry-run")
        stdin = "".join(f"{k}:{s}\n" for k, s in entries)
        proc = subprocess.run(cmd, capture_output=True, text=True, input=stdin, check=False)
        ok, failed, errors = self._parse_summary(proc.stderr)
        if proc.returncode == 2:
            # CLI grammar error — programmer bug, surface loudly
            raise RunnerError(
                f"{op} --plan grammar error (rc=2): {proc.stderr.strip()}",
                errors=errors,
            )
        return PlanResult(ok=ok, failed=failed, errors=errors)

    @staticmethod
    def _parse_summary(stderr: str) -> tuple[int, int, list[str]]:
        match = _SUMMARY_RE.search(stderr)
        ok = int(match.group(1)) if match else 0
        failed = int(match.group(2)) if match else 0
        errors = [line for line in stderr.splitlines()
                  if line.startswith("failed:") or line.startswith("malformed")]
        return ok, failed, errors
