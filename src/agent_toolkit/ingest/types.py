"""Shared types for ingest pipeline stages."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class InputForm(str, Enum):
    URL = "url"
    NAME = "name"
    FILE = "file"


@dataclass
class IngestTarget:
    """Result of the IDENTIFY stage."""
    input_value: str
    input_form: InputForm
    upstream_url: str | None
    kind_guess: str  # one of skill/agent/command/hook/mcp/plugin
    slug_guess: str
    vendor_strategy_guess: str  # submodule/clone/copy/symlink
    owner: str | None = None
    repo: str | None = None
    is_fork: bool = False
    is_archived: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class Proposal:
    """The on-disk shape proposed at the GO/NO-GO gate."""
    slug: str
    kind: str
    origin: str  # first-party/third-party
    harnesses: list[str]
    lifecycle: str
    target_path: str
    vendor_via: str
    upstream: str | None
    fork: str | None = None
    description: str = "TODO: one-sentence description ending in a period."

    def to_dict(self) -> dict:
        out: dict = {
            "apiVersion": "agent-toolkit/v1alpha2",
            "metadata": {
                "name": self.slug,
                "description": self.description,
                "lifecycle": self.lifecycle,
            },
            "spec": {
                "origin": self.origin,
                "vendored_via": self.vendor_via,
                "harnesses": list(self.harnesses),
            },
        }
        if self.upstream:
            out["spec"]["upstream"] = self.upstream
        if self.fork:
            out["spec"]["fork"] = self.fork
        return out
