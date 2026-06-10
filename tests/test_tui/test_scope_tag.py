"""Unit tests for app._scope_tag — scope attribution for pending summaries."""
from __future__ import annotations

from agent_toolkit_tui.app import _scope_tag


def test_scope_tag_empty():
    assert _scope_tag([]) == ""


def test_scope_tag_single_scope_global():
    keys = [("global", "a"), ("global", "claude", "b")]
    assert _scope_tag(keys) == ""


def test_scope_tag_single_scope_project():
    keys = [("project", "a")]
    assert _scope_tag(keys) == ""


def test_scope_tag_spanning_scopes():
    keys = [("global", "a"), ("project", "b"), ("global", "claude", "c")]
    assert _scope_tag(keys) == " (2 global, 1 project)"


def test_scope_tag_accepts_dict():
    pending = {("global", "a"): "link", ("project", "b"): "unlink"}
    assert _scope_tag(pending) == " (1 global, 1 project)"
