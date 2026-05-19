"""Wraps each audit/ shell test as a pytest case so CI runs them all."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SHELL_TESTS = sorted(HERE.glob("test_*.sh"))


@pytest.mark.parametrize("script", SHELL_TESTS, ids=lambda p: p.name)
def test_audit_shell_test(script: Path) -> None:
    result = subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.fail(
            f"{script.name} failed (rc={result.returncode})\n"
            f"--- stdout ---\n{result.stdout}\n"
            f"--- stderr ---\n{result.stderr}\n"
        )
