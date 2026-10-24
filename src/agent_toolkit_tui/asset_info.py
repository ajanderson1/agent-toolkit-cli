"""Display-only explanations of source ownership and manual local removal."""
from pathlib import Path
from shlex import quote

from rich.markup import escape


def local_path_info(path: Path, *, configurable: bool = False) -> list[str]:
    lines = [
        "Origin: local",
        f"Source path: {escape(str(path))}",
        "Existing files are used where they are, not moved or registered.",
        ("Enable/Disable changes Pi settings only; source files are kept. No TUI deletion."
         if configurable else "Local assets cannot be enabled, disabled or deleted in the TUI."),
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


def catalog_skill_info(slug: str, *, scope: str, home: Path, project: Path | None, item=None, catalog_url: str = "") -> list[str]:
    """Read-only catalog/update guidance. Never probe remote skill repositories."""
    from agent_toolkit_cli.skill_lock import read_lock, is_sha_pinned
    from agent_toolkit_cli.skill_paths import lock_file_path, library_lock_path, canonical_skill_dir, library_skill_path
    from agent_toolkit_cli.skill_update_check import read_check
    entry = read_lock(lock_file_path(scope=scope, home=home, project=project)).skills.get(slug)
    if entry is None:
        entry = read_lock(library_lock_path(home=home)).skills.get(slug)
    provenance = entry.extras.get("catalog", {}) if entry else {}
    if not isinstance(provenance, dict):
        provenance = {}
    if not provenance and item is None:
        return []
    lines = [f"Catalog: {escape(catalog_url or str(provenance.get('url', '(not currently connected)')))}"]
    if item is not None:
        lines += [f"Upstream: {escape(item.source.url)}", f"Directory: {escape(item.source.subpath or '.')}"]
    elif provenance:
        lines += [f"Upstream: {escape(str(provenance.get('source', '')))}", f"Directory: {escape(str(provenance.get('path', '.')))}"]
    if entry is None:
        return lines + ["Not downloaded. Enable to acquire the selected upstream skill."]
    check_scope, check_project = scope, project
    central = canonical_skill_dir(slug, scope=scope, home=home, project=project).resolve() == library_skill_path(slug, home=home).resolve()
    if central:
        check_scope, check_project = "global", None
    observed = read_check(slug, scope=scope, home=home, project=project)
    if observed is None and central:
        observed = read_check(slug, scope=check_scope, home=home, project=check_project)
    flag = "-g" if check_scope == "global" else "-p"
    lines += [f"Recorded ref: {escape(entry.ref or '(default)')}"]
    from agent_toolkit_cli.skill_catalog import run_git
    import subprocess
    try:
        backing = canonical_skill_dir(slug, scope=scope, home=home, project=project)
        if not backing.exists():
            backing = library_skill_path(slug, home=home)
        current_head = run_git(["rev-parse", "HEAD"], cwd=backing)
        lines.append(f"Installed revision: {escape(current_head)}")
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError):
        lines.append("Installed revision: unavailable; inspect backing with skills doctor.")
    if observed:
        lines += [f"Installed revision at check: {escape(str(observed.get('local_sha') or '(unknown)'))}", f"Upstream status: {escape(str(observed['status']))} (historical observation)", f"Last checked: {escape(str(observed['checked_at']))}"]
        if observed.get("status") == "different":
            lines.append("Upstream revision differs; ancestry and per-skill content changes are not inferred.")
        if observed.get("error"):
            lines.append(f"Check failed: {escape(str(observed['error']))}")
        if observed.get("local_changes"):
            lines.append("Local changes were present at check; review before updating.")
    else:
        lines.append("Upstream status: not checked. No automatic upstream checks in the TUI.")
    lines.append(escape(f"Check: agent-toolkit-cli skills check {quote(slug)} {flag}"))
    if is_sha_pinned(entry):
        lines.append("Pinned commit: updates do not advance this selection; change the source/ref explicitly using the CLI.")
    elif entry.parent_url and not central and scope == "project":
        lines.append("Private project monorepo updates are unsupported; inspect its recorded backing with the CLI.")
    else:
        lines.append(escape(f"Update: agent-toolkit-cli skills update {quote(slug)} {flag}"))
    return lines


def library_info(path: Path) -> list[str]:
    return [
        "Origin: library",
        f"Source path: {escape(str(path.resolve()))}",
        "Toolkit-managed central source, connected through the existing installation mechanism.",
        "Disable removes the connection, not the source.",
        "Updates use Toolkit source update handling; Git changes and health are shown separately.",
    ]
