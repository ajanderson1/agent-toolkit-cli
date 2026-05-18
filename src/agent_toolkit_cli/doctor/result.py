"""Shared result types for doctor check groups."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Status(IntEnum):
    OK = 0
    WARN = 1
    FAIL = 2

    def label(self) -> str:
        return {Status.OK: "OK", Status.WARN: "WARN", Status.FAIL: "FAIL"}[self]


@dataclass
class GroupResult:
    name: str
    status: Status
    summary: str
    findings: list[str] = field(default_factory=list)
    fix_hint: str | None = None  # e.g. "run `agent-toolkit link user claude`"

    def is_failure(self) -> bool:
        return self.status == Status.FAIL

    def is_warning(self) -> bool:
        return self.status == Status.WARN
