"""Complete-directory projection. This does not claim native role/skill loading."""
from pathlib import Path

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.project_backing import record_created_path


def supported(harness: str) -> bool:
    # Other adapters require a single file or translate it into native metadata.
    return harness == "pi"


def install(dest: Path, canonical: Path) -> Path:
    dest = dest.with_suffix("")
    if dest.is_symlink():
        if dest.resolve() != canonical.resolve():
            raise InstallError(f"foreign directory projection at {dest}")
    elif dest.exists():
        raise InstallError(f"foreign directory projection at {dest}")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(canonical, target_is_directory=True)
        record_created_path(dest)
    return dest


def uninstall(dest: Path, canonical: Path | None) -> Path | None:
    dest = dest.with_suffix("")
    if not dest.exists() and not dest.is_symlink():
        return None
    if dest.is_symlink() and canonical is not None and dest.resolve() == canonical.resolve():
        dest.unlink()
        return None
    return dest
