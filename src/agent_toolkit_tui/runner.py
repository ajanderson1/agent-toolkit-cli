"""Subprocess wrapper around the agent-toolkit-cli CLI.

The TUI's only writer-of-truth on the filesystem. The widgets and state code
never call subprocess directly — they go through this class. Mockable: pass
a fake to TUIApp(runner=...) in tests.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


def _locate_cli() -> Path:
    """Find the installed `agent-toolkit-cli` script.

    Resolution order:
      1. $AGENT_TOOLKIT_CLI override (escape hatch for tests/installs)
      2. `shutil.which("agent-toolkit-cli")` — picks up the script installed by
         `uv tool install` or the dev `.venv/bin/agent-toolkit-cli` entry point
      3. Raise FileNotFoundError with an actionable message
    """
    override = os.environ.get("AGENT_TOOLKIT_CLI")
    if override:
        p = Path(override)
        if p.is_file():
            return p
        raise FileNotFoundError(f"$AGENT_TOOLKIT_CLI={override} is not a file")

    found = shutil.which("agent-toolkit-cli")
    if found:
        return Path(found)

    raise FileNotFoundError(
        "Cannot locate `agent-toolkit-cli` on PATH. Run `uv tool install agent-toolkit` "
        "or `uv sync` from a source checkout, or set $AGENT_TOOLKIT_CLI to "
        "the script's path."
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
    """Single chokepoint for shelling out to the agent-toolkit-cli CLI.

    Resolves the CLI script via `_locate_cli()` (PATH lookup + env override).
    Override `cli_path` in tests.
    """

    def __init__(self, toolkit_root: Path, cli_path: Path | None = None) -> None:
        self.toolkit_root = toolkit_root.resolve()
        self.cli_path = cli_path or _locate_cli()

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

    def pi_inventory(self) -> list[dict]:
        """Invoke `pi inventory --format json` and return the parsed list of records."""
        proc = subprocess.run(
            [str(self.cli_path), "pi", "inventory", "--format", "json",
             "--toolkit-repo", str(self.toolkit_root)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            raise RunnerError(
                f"pi inventory --format json exited {proc.returncode}: {proc.stderr.strip()}"
            )
        try:
            doc = json.loads(proc.stdout)
        except json.JSONDecodeError as e:
            raise RunnerError(f"pi inventory --format json returned invalid JSON: {e}") from e
        # CLI returns a list of records.
        if not isinstance(doc, list):
            raise RunnerError(
                f"pi inventory --format json: expected list, got {type(doc).__name__}"
            )
        return doc

    def pi_load(self, slug: str, scope: str) -> None:
        """Invoke `pi load <slug> --scope <scope>`. Raise RunnerError on non-zero exit."""
        proc = subprocess.run(
            [str(self.cli_path), "pi", "load", slug,
             "--scope", scope,
             "--toolkit-repo", str(self.toolkit_root)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            raise RunnerError(
                f"pi load {slug} --scope {scope} exited {proc.returncode}: "
                f"{proc.stderr.strip()}"
            )

    def pi_unload(self, slug: str, scope: str) -> None:
        """Invoke `pi unload <slug> --scope <scope>`. Raise RunnerError on non-zero exit."""
        proc = subprocess.run(
            [str(self.cli_path), "pi", "unload", slug,
             "--scope", scope,
             "--toolkit-repo", str(self.toolkit_root)],
            capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            raise RunnerError(
                f"pi unload {slug} --scope {scope} exited {proc.returncode}: "
                f"{proc.stderr.strip()}"
            )

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
