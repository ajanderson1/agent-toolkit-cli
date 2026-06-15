"""End-to-end: apply() lays the correct pointer per Phase A cell."""
from __future__ import annotations

import pytest

from agent_toolkit_cli import instructions_install
from agent_toolkit_cli.instructions_adapters.symlink import CELLS
from agent_toolkit_cli.instructions_lock import (
    InstructionsLockEntry,
    InstructionsLockFile,
    write_lock,
)


@pytest.mark.parametrize(
    "harness",
    [h for h, cell in CELLS.items() if cell["project"]],
)
def test_project_scope_pointer_created(tmp_path, harness):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "AGENTS.md").write_text("# canon\n")
    write_lock(
        project / "instructions-lock.json",
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="project", source="AGENTS.md", harnesses=[harness],
                ),
            },
        ),
    )

    instructions_install.apply(scope="project", project_root=project, home=None)

    pointer_name = CELLS[harness]["pointer_name"]
    pointer = project / pointer_name
    assert pointer.is_symlink(), f"{harness}: expected symlink at {pointer}"
    assert pointer.resolve() == (project / "AGENTS.md").resolve()


@pytest.mark.parametrize(
    "harness",
    [h for h, cell in CELLS.items() if cell["global"]],
)
def test_global_scope_pointer_created(tmp_path, monkeypatch, harness):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    canonical = home / ".agent-toolkit" / "AGENTS.md"
    canonical.parent.mkdir(parents=True)
    canonical.write_text("# canon\n")
    write_lock(
        home / ".agent-toolkit" / "instructions-lock.json",
        InstructionsLockFile(
            version=1,
            instructions={
                "AGENTS.md": InstructionsLockEntry(
                    scope="global", source="AGENTS.md", harnesses=[harness],
                ),
            },
        ),
    )

    instructions_install.apply(scope="global", project_root=None, home=home)

    # The actual global pointer location varies per cell; reconstruct it.
    from agent_toolkit_cli.instructions_adapters.symlink import _pointer_path
    pointer = _pointer_path(harness, "global", None, home)
    assert pointer.is_symlink(), f"{harness}: expected symlink at {pointer}"
    assert pointer.resolve() == canonical.resolve()
