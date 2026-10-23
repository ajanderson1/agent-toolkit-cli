"""Display-only explanations of source ownership and manual local removal."""
from pathlib import Path
from shlex import quote

from rich.markup import escape


def local_path_info(path: Path) -> list[str]:
    lines = [
        "Origin: local",
        f"Source path: {escape(str(path))}",
        "Existing files are used where they are, not moved or registered.",
        "Local assets cannot be enabled, disabled or deleted in the TUI.",
        "Edit/update these files directly; Toolkit does not update local assets.",
    ]
    if path.is_symlink():
        lines += [
            f"Symlink target: {escape(str(path.resolve()))}",
            "Manual removal removes only this symlink; target files are kept:",
            escape(f"  rm -- {quote(str(path))}"),
        ]
    else:
        flags = "-rf --" if path.is_dir() else "--"
        lines += [
            "WARNING: manual removal permanently deletes these files.",
            "Remove only this asset, not its shared parent checkout:",
            escape(f"  rm {flags} {quote(str(path))}"),
        ]
    return lines


def library_info(path: Path) -> list[str]:
    return [
        "Origin: library",
        f"Source path: {escape(str(path.resolve()))}",
        "Toolkit-managed central source, connected through the existing installation mechanism.",
        "Disable removes the connection, not the source.",
        "Updates use Toolkit source update handling; Git changes and health are shown separately.",
    ]
