"""Doctor: symlink-integrity group — per-harness link health."""
from __future__ import annotations

import os
from pathlib import Path

from agent_toolkit_cli._support import _USER_TARGET_ALIASES, _USER_TARGETS
from agent_toolkit_cli._translators import TRANSLATORS
from agent_toolkit_cli.commands._link_lib import _translate_slot_layout, _slot_filename
from agent_toolkit_cli.doctor.result import GroupResult, Status
from agent_toolkit_cli.walker import discover_assets, extract_metadata, frontmatter_path

# Strip the "{home}/" template prefix to get a relative path under $HOME,
# matching this module's existing convention of joining with `home / rel`.
# Primary slot only; alias slots (e.g. (pi, agent)'s `~/.agents/`) are handled
# separately via `_USER_PATHS_ALL` for sweep operations.
_USER_PATHS: dict[tuple[str, str], str] = {
    pair: tmpl.removeprefix("{home}/")
    for pair, tmpl in _USER_TARGETS.items()
}
# All slots (primary + aliases) per pair, in stable order. Used by stale-link
# detection so it sees orphans in mirror directories too.
_USER_PATHS_ALL: dict[tuple[str, str], list[str]] = {
    pair: [tmpl.removeprefix("{home}/")]
    + [t.removeprefix("{home}/") for t in _USER_TARGET_ALIASES.get(pair, [])]
    for pair, tmpl in _USER_TARGETS.items()
}


def run(toolkit_root: Path, *, harness: str = "claude") -> GroupResult:
    home = Path(os.environ.get("HOME", str(Path.home())))

    findings: list[str] = []
    warns: list[str] = []
    fails: list[str] = []

    expected: dict[tuple[str, str], Path] = {}
    for asset in discover_assets(toolkit_root):
        # Plugin is managed by ClaudePluginAdapter (JSON config files), not by
        # filesystem symlinks. Its check is delegated to `_check_plugins_via_adapter`
        # below; skip here so the symlink-shaped loop never inspects the
        # `~/.claude/plugins/<slug>` slot (which is no longer authoritative).
        if asset.kind == "plugin" and harness == "claude":
            continue
        meta = _meta_for(asset)
        spec = meta.get("spec") or {}
        if harness not in (spec.get("harnesses") or []):
            continue
        rel = _USER_PATHS.get((harness, asset.kind))
        if rel is None:
            continue
        link_path = home / rel / _slot_filename(asset.slug, asset.kind, harness)
        expected[(asset.kind, asset.slug)] = link_path

    for (kind, slug), link_path in expected.items():
        # For the "dir-with-file-symlink" translate layout (e.g. opencode skill),
        # link_path is a real slot directory; the actual symlink lives at
        # link_path/<inner-file>. Look one level deeper before deciding.
        check_path = link_path
        if (
            (harness, kind) in TRANSLATORS
            and _translate_slot_layout(harness, kind) == "dir-with-file-symlink"
            and link_path.is_dir()
            and not link_path.is_symlink()
        ):
            inner_symlinks = [c for c in link_path.iterdir() if c.is_symlink()]
            if inner_symlinks:
                check_path = inner_symlinks[0]

        # For pairs with alias slots (e.g. (pi, agent) at `~/.agents/`),
        # also check each alias for completeness — a missing alias-side
        # symlink is a warn, not an error, because pi-subagents reads both.
        alias_rels = [
            t.removeprefix("{home}/")
            for t in _USER_TARGET_ALIASES.get((harness, kind), [])
        ]
        alias_paths = [home / rel / _slot_filename(slug, kind, harness)
                       for rel in alias_rels]

        if not check_path.exists() and not check_path.is_symlink():
            warns.append(f"{kind}/{slug}: expected symlink {check_path} missing")
            continue
        if check_path.is_symlink():
            target = Path(os.readlink(check_path))
            if not target.is_absolute():
                target = (check_path.parent / target).resolve()
            if not target.exists():
                warns.append(f"{kind}/{slug}: dangling symlink → {target}")
            else:
                findings.append(f"{kind}/{slug}: linked")
        elif check_path.exists():
            # Slot is occupied by a real file or directory rather than a symlink.
            # This is "replaced symlink" tampering — doctor must FAIL loudly so
            # the user runs `agent-toolkit link user <harness>` to reconcile.
            fails.append(
                f"{kind}/{slug}: slot exists but is not a symlink: {check_path}"
            )
            continue
        # Alias slots: warn if missing (dual-write expects both).
        for ap in alias_paths:
            if not ap.exists() and not ap.is_symlink():
                warns.append(f"{kind}/{slug}: alias-slot symlink {ap} missing")

    # Stale: a symlink under user dir that points into the repo for an asset that
    # does NOT declare this harness.
    declared_slugs = {(a.kind, a.slug): a for a in discover_assets(toolkit_root)}
    for (kind_dir_name, kind) in [
        ("skills", "skill"), ("agents", "agent"), ("commands", "command"),
        ("hooks", "hook"), ("extensions", "pi-extension"),
    ]:
        rels = _USER_PATHS_ALL.get((harness, kind))
        if not rels:
            continue
        for rel in rels:
            user_kind_dir = home / rel
            if not user_kind_dir.is_dir():
                continue
            _sweep_stale_in_dir(
                user_kind_dir, harness, kind, declared_slugs,
                toolkit_root, warns,
            )

    # Plugin checks are adapter-driven (JSON config files in ~/.claude/plugins/),
    # not symlink-shaped. Delegate to a dedicated routine that consults the
    # ClaudePluginAdapter's `list_installed()` plus a warn-only cache-dir probe.
    if harness == "claude":
        _check_plugins_via_adapter(
            toolkit_root=toolkit_root,
            home=home,
            findings=findings,
            warns=warns,
            fails=fails,
        )


    if fails:
        summary = (
            f"{len(fails)} replaced symlink(s), {len(warns)} other issue(s) "
            f"for harness={harness}"
        )
        return GroupResult(
            name="symlink-integrity",
            status=Status.FAIL,
            summary=summary,
            findings=findings + warns + fails,
            fix_hint=f"`agent-toolkit link user {harness}` to reconcile",
        )
    if warns:
        return GroupResult(
            name="symlink-integrity",
            status=Status.WARN,
            summary=f"{len(warns)} symlink issue(s) for harness={harness}",
            findings=findings + warns,
            fix_hint=f"`agent-toolkit link user {harness}` to reconcile",
        )
    return GroupResult(
        name="symlink-integrity",
        status=Status.OK,
        summary=f"{len(findings)} link(s) all healthy for harness={harness}",
        findings=findings,
    )


def _check_plugins_via_adapter(
    *,
    toolkit_root: Path,
    home: Path,
    findings: list[str],
    warns: list[str],
    fails: list[str],
) -> None:
    """Plugin health via `ClaudePluginAdapter` — not filesystem symlinks.

    Rules:
    - allow-listed but key absent from installed_plugins.json → FAIL
    - allow-listed and key present, cache dir present → finding (pass)
    - allow-listed and key present, cache dir absent → WARN (Claude clones
      lazily on next start, so missing cache is not fatal)
    """
    from agent_toolkit_cli._allowlist import read_allowlist  # noqa: PLC0415
    from agent_toolkit_cli.commands._plugin_dispatch import (  # noqa: PLC0415
        _build_plugin_entries,
    )
    from agent_toolkit_cli.harness_adapters import get_adapter  # noqa: PLC0415
    from agent_toolkit_cli.harness_adapters.base import (  # noqa: PLC0415
        UnimplementedAdapter,
    )

    allowlist_path = home / ".agent-toolkit.yaml"
    allowed_slugs = read_allowlist(allowlist_path).get("plugins", [])
    if not allowed_slugs:
        return

    adapter = get_adapter("claude", kind="plugin")
    if isinstance(adapter, UnimplementedAdapter):
        return

    # The adapter signature is `(scope, project_root)`. Doctor's symlink
    # group is user-scope-only (matches the existing skill/agent/command
    # checks above) — project plugins aren't supported in v1.
    scope = "user"
    project_root = Path(".")  # unused for user scope

    config_target = adapter.config_target(scope, project_root)
    if config_target is None:
        return

    installed_keys = set(adapter.list_installed(scope, project_root))

    entries = _build_plugin_entries(toolkit_root, allowed_slugs)
    # Map slug → entry so we can report by sidecar-slug.
    entry_by_slug = {e.name: e for e in entries}

    # Recorded versions for the cache-dir probe come from the JSON itself.
    recorded_versions: dict[str, str] = {}
    if config_target.is_file():
        import json  # noqa: PLC0415
        try:
            doc = json.loads(config_target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            doc = {}
        for key, items in (doc.get("plugins") or {}).items():
            if not isinstance(items, list):
                continue
            user_rec = next(
                (e for e in items if isinstance(e, dict) and e.get("scope") == "user"),
                None,
            )
            if user_rec and user_rec.get("version"):
                recorded_versions[key] = str(user_rec["version"])

    for slug in allowed_slugs:
        entry = entry_by_slug.get(slug)
        if entry is None:
            # Sidecar missing / incomplete — link would also have skipped.
            # Don't crash doctor; surface a warn so the user notices.
            warns.append(
                f"plugin/{slug}: sidecar missing or incomplete; skipped"
            )
            continue
        key = f"{entry.plugin}@{entry.marketplace}"
        if key not in installed_keys:
            fails.append(
                f"plugin/{slug}: not recorded in installed_plugins.json "
                f"(key {key!r} missing) — run `agent-toolkit link user claude`"
            )
            continue
        # Cache-dir probe (warn-only). Path layout per the marketplace cache:
        #   ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/
        version = recorded_versions.get(key) or entry.version
        cache_dir = (
            home / ".claude" / "plugins" / "cache"
            / entry.marketplace / entry.plugin / version
        )
        if cache_dir.is_dir():
            findings.append(f"plugin/{slug}: installed (cache present)")
        else:
            warns.append(
                f"plugin/{slug}: cache dir {cache_dir} absent — "
                f"Claude will clone on next start"
            )


def _sweep_stale_in_dir(
    user_kind_dir: Path,
    harness: str,
    kind: str,
    declared_slugs: dict,
    toolkit_root: Path,
    warns: list[str],
) -> None:
    """Scan one slot directory for symlinks pointing into the toolkit repo
    whose asset (a) no longer exists, or (b) no longer declares this harness.
    Mutates `warns` in place. Used for the primary slot AND each alias slot.
    """
    for entry in user_kind_dir.iterdir():
        if not entry.is_symlink():
            continue
        target = Path(os.readlink(entry))
        if not target.is_absolute():
            target = (entry.parent / target).resolve()
        try:
            target.relative_to(toolkit_root)
        except ValueError:
            continue
        lookup_name = entry.name[:-3] if entry.name.endswith(".md") else entry.name
        asset = declared_slugs.get((kind, lookup_name))
        if asset is None:
            if not target.exists():
                warns.append(
                    f"{kind}/{entry.name}: dangling symlink → {target} (no asset in repo)"
                )
            else:
                warns.append(f"{kind}/{entry.name}: stale link (no asset in repo)")
            continue
        meta = _meta_for(asset)
        spec = meta.get("spec") or {}
        if harness not in (spec.get("harnesses") or []):
            warns.append(
                f"{kind}/{entry.name}: linked but {harness} not in spec.harnesses"
            )


def _meta_for(asset) -> dict:
    if asset.kind in {"skill", "agent", "command"}:
        fm = frontmatter_path(asset.path, asset.kind)
        return extract_metadata(fm) or {}
    if asset.kind == "hook":
        import yaml
        return yaml.safe_load(asset.path.read_text()) or {}
    if asset.kind == "plugin":
        import json
        doc = json.loads(asset.path.read_text())
        return doc.get("agent_toolkit_cli") or {}
    if asset.kind == "mcp":
        fm = frontmatter_path(asset.path, asset.kind)
        if not fm.is_file():
            return {}
        return extract_metadata(fm) or {}
    return {}
