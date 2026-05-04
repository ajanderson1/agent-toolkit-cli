"""Textual messages exchanged between widgets and the App."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from textual.message import Message


@dataclass
class AssetToggled(Message):
    """A cell in the asset grid was toggled by the user."""
    kind: str
    slug: str
    harness: str
    scope: Literal["user", "project"]
    op: Literal["link", "unlink", "clear"]   # link/unlink = queue, clear = un-queue


@dataclass
class ApplyRequested(Message):
    """User pressed Ctrl-S — drain the pending queue."""


@dataclass
class DiffRequested(Message):
    """User pressed Ctrl-D — preview the pending queue without applying."""


@dataclass
class ScopeChanged(Message):
    """Scope radio toggled."""
    scope: Literal["user", "project"]


@dataclass
class KindChanged(Message):
    """Sidebar selection changed."""
    kind: str   # "skill" | "agent" | "command" | "hook" | "plugin" | "pi-extension"
