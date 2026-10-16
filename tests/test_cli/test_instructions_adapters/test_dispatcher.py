"""The adapter's CELLS table must equal the Phase A symlink-verdict set."""
from __future__ import annotations

import re
from pathlib import Path

from agent_toolkit_cli.instructions_adapters import (
    SUPPORTED_HARNESSES,
    get_adapter,
)
from agent_toolkit_cli.instructions_adapters.symlink import (
    Adapter,
    UnknownHarnessError,
)

_DOC = Path(__file__).resolve().parents[3] / "docs/agent-toolkit/harness-matrix.md"
_SECTION_HEADING = "## Instruction-file (`instructions` asset type) support — all harnesses"
_ROW_RE = re.compile(
    r"^\|\s*`(?P<harness>[a-z][a-z0-9-]*)`\s*\|"
    r"(?P<verdict>[^|]+)\|"
    r"(?P<default>[^|]*)\|"
    r"(?P<paths>[^|]*)\|"
    r"(?P<global_verdict>[^|]*)\|"
)


def _matrix_symlink_set() -> set[str]:
    text = _DOC.read_text(encoding="utf-8")
    section = text.split(_SECTION_HEADING, 1)[1]
    section = re.split(r"^## ", section, maxsplit=1, flags=re.MULTILINE)[0]
    out: set[str] = set()
    for line in section.splitlines():
        m = _ROW_RE.match(line.strip())
        if not m:
            continue
        if any(
            verdict.strip().lower().startswith("symlink")
            for verdict in (m.group("verdict"), m.group("global_verdict"))
        ):
            out.add(m.group("harness"))
    return out


def test_supported_harnesses_matches_matrix_symlink_set():
    """The adapter table is the implementation; the matrix is the contract."""
    assert SUPPORTED_HARNESSES == _matrix_symlink_set()


def test_global_only_native_readers_have_no_project_pointer(tmp_path):
    """#499: global AGENTS.md slots do not turn project readers into pointers."""
    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
    import pytest

    for harness, expected in {
        "codex": tmp_path / ".codex" / "AGENTS.md",
        "opencode": tmp_path / ".config" / "opencode" / "AGENTS.md",
        "pi": tmp_path / ".pi" / "agent" / "AGENTS.md",
    }.items():
        assert _pointer_path(harness, "global", None, tmp_path) == expected
        with pytest.raises(ValueError, match="no project pointer slot"):
            _pointer_path(harness, "project", tmp_path / "project", tmp_path)


def test_get_adapter_returns_adapter_instance():
    for harness in SUPPORTED_HARNESSES:
        adapter = get_adapter(harness)
        assert isinstance(adapter, Adapter)
        assert adapter.harness == harness


def test_get_adapter_unknown_harness_raises():
    import pytest
    with pytest.raises(UnknownHarnessError):
        get_adapter("notreal")
