from pathlib import Path

import agent_toolkit_tui.mcp_state as mcp_state
from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_tui.mcp_state import _cell_for, mcp_interactive_harnesses


def test_interactive_harnesses_project_has_standard_first():
    # ("standard",) + mcp_nonstandard_main("project")
    assert mcp_interactive_harnesses("project") == (
        "standard", "codex", "opencode",
    )


def test_interactive_harnesses_global_no_standard():
    # No standard column at global (KeyError-guarded covered set).
    assert mcp_interactive_harnesses("global") == (
        "claude-code", "codex", "opencode", "pi",
    )


class _FakeAdapter:
    def __init__(self, installed: bool):
        self._installed = installed

    def is_installed(self, slug, *, scope, home, project):
        return self._installed


def test_cell_for_linked_true(monkeypatch):
    monkeypatch.setattr(mcp_state, "get_adapter", lambda h: _FakeAdapter(True))
    cell = _cell_for("ctx7", "codex", scope="project",
                     home=Path("/home"), project=Path("/proj"))
    assert cell is not None and cell.linked is True


def test_cell_for_linked_false(monkeypatch):
    monkeypatch.setattr(mcp_state, "get_adapter", lambda h: _FakeAdapter(False))
    cell = _cell_for("ctx7", "codex", scope="project",
                     home=Path("/home"), project=Path("/proj"))
    assert cell is not None and cell.linked is False


def test_cell_for_unknown_harness_none(monkeypatch):
    def _boom(h):
        raise InstallError(f"unknown harness {h}")  # real type: UnsupportedMcpHarnessError(InstallError)
    monkeypatch.setattr(mcp_state, "get_adapter", _boom)
    assert _cell_for("ctx7", "bogus", scope="project",
                     home=Path("/home"), project=Path("/proj")) is None


def test_cell_for_standard_at_global_none(monkeypatch):
    # The standard adapter raises InstallError for a global target (no global
    # .mcp.json). _cell_for must swallow it → None, never crash.
    class _GlobalRefuser:
        def is_installed(self, slug, *, scope, home, project):
            raise InstallError("no global standard target")
    monkeypatch.setattr(mcp_state, "get_adapter", lambda h: _GlobalRefuser())
    assert _cell_for("ctx7", "standard", scope="global",
                     home=Path("/home"), project=None) is None
