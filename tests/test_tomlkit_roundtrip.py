"""Phase-0 gate: tomlkit must round-trip a realistic Codex config byte-equal."""
from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit


_FIXTURES_DIR = Path(__file__).parent / "_fixtures"
_FIXTURES = [
    _FIXTURES_DIR / "codex_config_realistic.toml",
    _FIXTURES_DIR / "codex_config_realistic_with_hooks.toml",
]


@pytest.mark.parametrize("fixture_path", _FIXTURES, ids=lambda p: p.name)
def test_tomlkit_byte_equal_roundtrip(fixture_path):
    """Parse and re-dump must equal the source bytes verbatim."""
    src = fixture_path.read_bytes()
    doc = tomlkit.parse(src.decode("utf-8"))
    rendered = tomlkit.dumps(doc).encode("utf-8")
    assert rendered == src, (
        "tomlkit round-trip is NOT byte-equal — adapter design assumes it is.\n"
        f"Fixture: {fixture_path.name}\n"
        f"Length src={len(src)} rendered={len(rendered)}.\n"
        "Investigate before continuing with Codex adapter."
    )
