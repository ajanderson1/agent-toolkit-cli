"""Standard command projection (#482): the .claude/commands/<slug>.md slot.

`.claude/commands/` is read natively by Claude Code and Neovate at both scopes,
and by Devin CLI (as skills) at project scope. Installing `standard` writes
ONE owned Markdown file that all covered harnesses consume.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.command_adapters.base import (
    ensure_regular_command_file,
    is_managed_file,
    read_sidecar,
    remove_managed_file,
    sidecar_path,
    write_sidecar,
)

STANDARD_COMMAND_READERS: dict[str, frozenset[str]] = {
    "global": frozenset({"claude-code", "neovate"}),
    "project": frozenset({"claude-code", "neovate", "devin"}),
}

_TEMPLATES = {
    "global": (".claude", "commands"),
    "project": (".claude", "commands"),
}


def commands_standard_covered(scope: str) -> frozenset[str]:
    """Covered set for a scope. KeyError on unknown scope (fail loud)."""
    return STANDARD_COMMAND_READERS[scope]


def _valid_slug(slug: str) -> None:
    if "/" in slug or "\\" in slug or slug in (".", "..") or not slug:
        raise ValueError(f"standard: invalid slug {slug!r}")


def _resolves_to(dest: Path, source_file: Path) -> bool:
    try:
        return dest.is_symlink() and dest.resolve() == source_file.resolve()
    except OSError:
        return False


def _bytes_match(dest: Path, source_file: Path) -> bool:
    if not dest.exists() or dest.is_symlink():
        return False
    try:
        return dest.read_bytes() == source_file.read_bytes()
    except OSError:
        return False


class StandardCommandAdapter:
    """Install/uninstall the single standard commands slot."""

    name = "standard"

    def destination(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None,
        project: Path | None,
    ) -> Path:
        _valid_slug(slug)
        if scope not in _TEMPLATES:
            raise ValueError(f"standard: scope must be 'global' or 'project', got {scope!r}")
        parts = _TEMPLATES[scope]
        if scope == "global":
            if home is None:
                raise ValueError("global scope requires home")
            return home.joinpath(*parts, f"{slug}.md")
        if project is None:
            raise ValueError("project scope requires project")
        return project.joinpath(*parts, f"{slug}.md")

    def is_installed(
        self,
        slug: str,
        source_file: Path,
        *,
        scope: str,
        home: Path | None,
        project: Path | None,
    ) -> bool:
        """True only for a live Standard-owned slot (sidecar + matching dest)."""
        dest = self.destination(slug, scope=scope, home=home, project=project)
        if not is_managed_file(dest, slug=slug, harness="standard"):
            return False
        if _resolves_to(dest, source_file):
            return True
        if _bytes_match(dest, source_file):
            return True
        return False

    def install(
        self,
        slug: str,
        source_file: Path,
        *,
        scope: str,
        home: Path | None,
        project: Path | None,
    ) -> Path:
        ensure_regular_command_file(source_file)
        dest = self.destination(slug, scope=scope, home=home, project=project)
        content = source_file.read_text()
        created_new = False

        if not dest.exists() and not dest.is_symlink():
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest.symlink_to(source_file)
            except OSError:
                shutil.copyfile(source_file, dest)
            created_new = True
            try:
                write_sidecar(
                    dest,
                    slug=slug,
                    harness="standard",
                    scope=scope,
                    canonical=source_file,
                    content=content,
                )
            except Exception:
                if created_new and (dest.exists() or dest.is_symlink()):
                    dest.unlink(missing_ok=True)
                raise
            return dest

        if _resolves_to(dest, source_file):
            write_sidecar(
                dest,
                slug=slug,
                harness="standard",
                scope=scope,
                canonical=source_file,
                content=content,
            )
            return dest

        if dest.exists() and not dest.is_symlink() and _bytes_match(dest, source_file):
            write_sidecar(
                dest,
                slug=slug,
                harness="standard",
                scope=scope,
                canonical=source_file,
                content=content,
            )
            return dest

        if is_managed_file(dest, slug=slug, harness="standard"):
            # Refresh owned slot. Never write through a user-replaced symlink.
            if dest.is_symlink() or dest.exists():
                dest.unlink()
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest.symlink_to(source_file)
            except OSError:
                shutil.copyfile(source_file, dest)
            write_sidecar(
                dest,
                slug=slug,
                harness="standard",
                scope=scope,
                canonical=source_file,
                content=content,
            )
            return dest

        raise InstallError(f"{dest}: unmanaged command exists")

    def uninstall(
        self,
        slug: str,
        source_file: Path | None = None,
        *,
        scope: str,
        home: Path | None,
        project: Path | None,
        canonical: Path | None = None,
    ) -> Path | None:
        """Remove owned/adoptable Standard slot. Leave divergent foreign files.

        Accepts either positional source_file or keyword ``canonical`` for
        facade symmetry with MarkdownCommandAdapter.
        """
        source = source_file if source_file is not None else canonical
        dest = self.destination(slug, scope=scope, home=home, project=project)

        if not dest.exists() and not dest.is_symlink():
            sidecar_path(dest).unlink(missing_ok=True)
            return None

        owned = is_managed_file(dest, slug=slug, harness="standard")
        if not owned and source is not None:
            owned = _resolves_to(dest, source) or _bytes_match(dest, source)

        if owned:
            if dest.is_symlink() or dest.exists():
                dest.unlink(missing_ok=True)
            sidecar_path(dest).unlink(missing_ok=True)
            return dest
        return None
