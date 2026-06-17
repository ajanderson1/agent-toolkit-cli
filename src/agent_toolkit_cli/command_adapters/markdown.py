from __future__ import annotations

import shutil
from pathlib import Path

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.command_adapters.base import ensure_regular_command_file, remove_managed_file, write_sidecar

DESTINATIONS = {
    "claude-code": ((".claude", "commands"), (".claude", "commands")),
    "pi": ((".pi", "agent", "prompts"), (".pi", "prompts")),
    "codex": ((".codex", "prompts"), None),
}


class MarkdownCommandAdapter:
    def __init__(self, name: str) -> None:
        if name not in DESTINATIONS:
            raise ValueError(f"unsupported command harness: {name}")
        self.name = name

    def destination(self, slug: str, *, scope: str, home: Path | None, project: Path | None) -> Path:
        global_parts, project_parts = DESTINATIONS[self.name]
        if scope == "global":
            if home is None:
                raise ValueError("global scope requires home")
            return home.joinpath(*global_parts, f"{slug}.md")
        if project_parts is None:
            raise ValueError("Codex commands are global-only")
        if project is None:
            raise ValueError("project scope requires project")
        return project.joinpath(*project_parts, f"{slug}.md")

    def install(self, slug: str, source_file: Path, *, scope: str, home: Path | None, project: Path | None) -> Path:
        ensure_regular_command_file(source_file)
        dest = self.destination(slug, scope=scope, home=home, project=project)
        if dest.is_symlink():
            if dest.resolve() == source_file.resolve():
                return dest
            raise InstallError(f"{dest}: foreign symlink exists")
        if dest.exists():
            raise InstallError(f"{dest}: unmanaged command exists")
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.symlink_to(source_file)
        except OSError:
            content = source_file.read_text()
            shutil.copyfile(source_file, dest)
            write_sidecar(dest, slug=slug, harness=self.name, scope=scope, canonical=source_file, content=content)
        return dest

    def uninstall(self, slug: str, *, scope: str, home: Path | None, project: Path | None, canonical: Path | None = None) -> Path | None:
        dest = self.destination(slug, scope=scope, home=home, project=project)
        if dest.is_symlink():
            if canonical is not None and dest.resolve() == canonical.resolve():
                dest.unlink()
                return dest
            return None
        return remove_managed_file(dest, slug=slug, harness=self.name)
