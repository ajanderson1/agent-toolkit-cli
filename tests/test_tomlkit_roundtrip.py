"""Phase-0 gate: tomlkit must round-trip a realistic Codex config byte-equal."""
from __future__ import annotations

from pathlib import Path

import tomlkit


_FIXTURE = Path(__file__).parent / "_fixtures" / "codex_config_realistic.toml"


def test_tomlkit_byte_equal_roundtrip():
    """Parse and re-dump must equal the source bytes verbatim."""
    src = _FIXTURE.read_bytes()
    doc = tomlkit.parse(src.decode("utf-8"))
    rendered = tomlkit.dumps(doc).encode("utf-8")
    assert rendered == src, (
        "tomlkit round-trip is NOT byte-equal — adapter design assumes it is.\n"
        f"Length src={len(src)} rendered={len(rendered)}.\n"
        "Investigate before continuing with Codex adapter."
    )
