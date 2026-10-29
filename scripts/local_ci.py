#!/usr/bin/env python3
"""Run the hosted Linux checks against immutable outgoing Git commits."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def run(args, **kwargs):
    # Hooks export Git routing variables; never let these redirect snapshot Git.
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("GIT_")}
    return subprocess.run(args, check=True, env=env, **kwargs)


def push_targets(value: str) -> list[str]:
    targets = []
    for line in value.splitlines():
        fields = line.split()
        if len(fields) != 4 or not re.fullmatch(r"[0-9a-f]{40}", fields[1]):
            raise ValueError("Invalid pre-push input; refusing unchecked push")
        sha = fields[1]
        if sha != "0" * 40 and sha not in targets:
            targets.append(sha)
    return targets


def snapshot(repo: Path, target: str, destination: Path) -> None:
    run(["git", "init", "-q", str(destination)])
    run(["git", "-C", str(destination), "-c", "core.hooksPath=/dev/null",
         "fetch", "-q", "--depth=1", str(repo), target])
    run(["git", "-C", str(destination), "-c", "core.hooksPath=/dev/null",
         "checkout", "-q", "--detach", "FETCH_HEAD"])


def verify(repo: Path, target: str) -> None:
    with tempfile.TemporaryDirectory(prefix="agent-toolkit-ci-") as directory:
        source = Path(directory) / "source"
        snapshot(repo, target, source)
        # One image per invocation; remove it after success OR failure.
        image = "agent-toolkit-ci:" + Path(directory).name.lower()
        try:
            run(["docker", "build", "-t", image,
                 "-f", str(source / "scripts/ci/Dockerfile"), str(source)])
            run(["docker", "run", "--rm", image])
        finally:
            # Do not mask the failing gate if Docker is unavailable.
            try:
                run(["docker", "image", "rm", image],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.CalledProcessError):
                pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-push", action="store_true",
                        help="read and verify every outgoing ref from Git stdin")
    parser.add_argument("revision", nargs="?", default="HEAD")
    args = parser.parse_args(argv)
    repo = Path(__file__).resolve().parents[1]
    targets = push_targets(sys.stdin.read()) if args.pre_push else [args.revision]
    for target in targets:
        print(f"Linux CI preflight: {target}", flush=True)
        verify(repo, target)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Local CI failed; push blocked: {error}", file=sys.stderr)
        sys.exit(1)
