"""Benchmark real skill discovery, never the user's HOME/library/project.

Run: uv run python scripts/benchmark_tui_inventory.py --skills 60 --samples 3
Fixture creation is excluded from timings. Run sequentially on the same machine
and compare medians; subprocess/read counts are deterministic regression guards.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
from time import perf_counter
from unittest.mock import patch


def positive(value: str) -> int:
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def benchmark(root: Path, count: int, samples: int) -> dict:
    home = root / "home"
    project = root / "project"
    source = root / "source"
    for path in (home, project, source):
        path.mkdir()
    # Set these before toolkit imports: some adapters bind HOME at import time.
    # The script runs in its own process; no environment escapes to the caller.
    for key in list(os.environ):
        if key.startswith("GIT_") or key in ("AGENT_TOOLKIT_SKILLS_ROOT", "AGENT_TOOLKIT_TUI_SETTINGS"):
            del os.environ[key]
    os.environ.update({
        "HOME": str(home), "USERPROFILE": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "CLAUDE_CONFIG_DIR": str(home / ".claude"),
        "CODEX_HOME": str(home / ".codex"), "VIBE_HOME": str(home / ".vibe"),
        "HERMES_HOME": str(home / ".hermes"),
        "PI_CODING_AGENT_DIR": str(home / ".pi/agent"),
        "AGENT_TOOLKIT_SKILLS_ROOT": str(root / "library/skills"),
        "AGENT_TOOLKIT_NPM_GLOBAL_ROOT": str(root / "empty-global-npm"),
    })
    os.chdir(project)
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main
    from agent_toolkit_cli.skill_lock import LockFile, read_lock, write_lock
    from agent_toolkit_cli.skill_paths import library_lock_path, library_skill_path
    from agent_toolkit_tui.skill_state import build_skill_rows

    for i in range(count):
        child = source / f"skill-{i:05d}"
        child.mkdir()
        (child / "SKILL.md").write_text(f"---\nname: {child.name}\ndescription: Fixture {i}\n---\n")
    for command in (("init", "-q", "-b", "main"), ("add", "."), ("commit", "-qm", "fixture")):
        subprocess.run([
            "git", "-C", str(source), "-c", "user.name=Benchmark",
            "-c", "user.email=benchmark@example.invalid", *command,
        ], check=True, capture_output=True)
    result = CliRunner().invoke(main, ["skills", "add", source.as_uri()])
    if result.exit_code:
        raise RuntimeError(result.output) from result.exception
    # Seed the recorded central project backing and Standard projections, outside
    # the timed region. Enable facade behavior has separate integration tests.
    library = read_lock(library_lock_path())
    project_lock = project / "skills-lock.json"
    write_lock(project_lock, LockFile(version=3, skills={
        slug: replace(entry, extras={**entry.extras, "projectBacking": "central"})
        for slug, entry in library.skills.items()
    }))
    for slug in library.skills:
        target = project / ".agents/skills" / slug
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(library_skill_path(slug))
    backing = library_skill_path(next(iter(library.skills))).resolve().parent
    index = (backing / ".git/index").read_bytes()
    report = {}
    run, read_text = subprocess.run, Path.read_text
    counts = Counter()

    def traced_run(command, *args, **kwargs):
        if Path(command[0]).name == "git":
            counts["git_processes"] += 1
        return run(command, *args, **kwargs)

    def traced_read(path, *args, **kwargs):
        if path == project_lock:
            counts["project_lock_reads"] += 1
        return read_text(path, *args, **kwargs)

    with patch("subprocess.run", traced_run), patch.object(Path, "read_text", traced_read):
        for scope in ("global", "project"):
            timings, resources = [], []
            for _ in range(samples):
                counts.clear()
                start = perf_counter()
                rows = build_skill_rows(scope=scope, home=home, project=project if scope == "project" else None)
                timings.append((perf_counter() - start) * 1000)
                resources.append(counts.copy())
                if len(rows) != count or any(row.state != "clean" for row in rows):
                    raise RuntimeError("benchmark fixture inventory is not clean/complete")
            report[scope] = {
                "rows": count,
                "milliseconds": {"median": round(statistics.median(timings), 2),
                                 "min": round(min(timings), 2), "max": round(max(timings), 2)},
                **{key: {"min": min(value[key] for value in resources),
                         "max": max(value[key] for value in resources)}
                   for key in ("git_processes", "project_lock_reads")},
            }
    if (backing / ".git/index").read_bytes() != index:
        raise RuntimeError("discovery modified the Git index")
    return {"skills": count, "samples": samples, "scopes": report}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills", type=positive, default=60)
    parser.add_argument("--samples", type=positive, default=3)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="att-inventory-benchmark-") as directory:
        result = benchmark(Path(directory).resolve(), args.skills, args.samples)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
