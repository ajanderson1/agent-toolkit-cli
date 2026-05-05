"""Pure-Python projection of CLI output into widget-renderable state.

`build_state(runner)` is the single function the App calls to (re)build state.
No I/O of its own — accepts the runner as a parameter and consumes its
`list_state()` output. Mockable in tests via the FakeRunner pattern.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

CellStatus = Literal[
    "linked", "unlinked", "unsupported", "broken",
    "linked-matches", "linked-drifted", "unlinked-allowlisted", "installed-not-allowlisted",
]


@dataclass(frozen=True)
class CellState:
    status: CellStatus
    target_path: Path | None
    allowlisted: bool


@dataclass(frozen=True)
class AssetRow:
    slug: str
    kind: str                       # "skill" | "agent" | "command" | "hook" | "plugin" | "mcp" | "pi-extension"
    origin: str                     # "first-party" | "third-party" | "unknown"
    description: str
    path: Path
    declared_harnesses: tuple[str, ...]
    cells: dict[tuple[str, str], CellState]   # (harness, scope) → state — both scopes stored


@dataclass(frozen=True)
class InventoryState:
    toolkit_root: Path
    rows: tuple[AssetRow, ...]
    all_harnesses: tuple[str, ...]


class _RunnerProto(Protocol):
    def list_state(self) -> dict: ...


def build_state(runner: _RunnerProto) -> InventoryState:
    doc = runner.list_state()
    rows: list[AssetRow] = []
    for a in doc.get("assets", []):
        cells: dict[tuple[str, str], CellState] = {}
        for c in a.get("cells", []):
            cells[(c["harness"], c["scope"])] = CellState(
                status=c["status"],
                target_path=Path(c["target"]) if c["target"] else None,
                allowlisted=bool(c["allowlisted"]),
            )
        rows.append(AssetRow(
            slug=a["slug"],
            kind=a["kind"],
            origin=a.get("origin", "unknown"),
            description=a.get("description", ""),
            path=Path(a["path"]),
            declared_harnesses=tuple(a.get("declared_harnesses", [])),
            cells=cells,
        ))
    return InventoryState(
        toolkit_root=Path(doc.get("toolkit_root", "")),
        rows=tuple(rows),
        all_harnesses=tuple(doc.get("harnesses", ())),
    )
