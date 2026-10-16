"""Documentation media must come from this checkout and disposable state."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest


@pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="PNG rasterizer not installed")
def test_documentation_capture_is_isolated_and_real(tmp_path):
    root = Path(__file__).resolve().parents[1]
    # Parent HOME is deliberately unusable: the script must construct its own.
    env = dict(os.environ, HOME=str(tmp_path / "not-the-fixture-home"))
    result = subprocess.run(
        [sys.executable, str(root / "scripts/capture_docs_tui.py"), "--output", str(tmp_path / "media")],
        env=env, cwd=root, capture_output=True, text=True, timeout=70,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "source-asserted" in result.stdout
    png = tmp_path / "media/agent-toolkit-cli-tui.png"
    assert png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    svg = (tmp_path / "media/agent-toolkit-cli-tui.svg").read_text()
    assert "demo-project" in svg and "code-review" in svg
    assert str(root) not in svg and "/Users/" not in svg
    assert not (tmp_path / "not-the-fixture-home").exists()
