"""The discovery benchmark uses disposable assets and guards resource counts."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/benchmark_tui_inventory.py"


def test_inventory_benchmark_reports_real_scans_without_using_inherited_assets(tmp_path, monkeypatch):
    home = tmp_path / "untouched-home"
    home.mkdir()
    sentinel = home / "sentinel"
    sentinel.write_text("preserve\n")
    library = tmp_path / "untouched-library"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(library))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--skills", "2", "--samples", "2"],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["skills"] == 2 and report["samples"] == 2
    assert set(report["scopes"]) == {"global", "project"}
    for scope, values in report["scopes"].items():
        assert values["rows"] == 2
        assert 0 <= values["milliseconds"]["min"] <= values["milliseconds"]["median"] <= values["milliseconds"]["max"]
        assert values["git_processes"]["max"] <= 2
        assert values["project_lock_reads"]["max"] <= 4
    assert list(home.iterdir()) == [sentinel]
    assert sentinel.read_text() == "preserve\n"
    assert not library.exists()


@pytest.mark.parametrize("option", ["--skills", "--samples"])
def test_inventory_benchmark_requires_positive_counts(option):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), option, "0"],
        capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 2
    assert "positive" in result.stderr
