"""Doctor: plugins group — Claude plugin health via the adapter.

Plugins aren't symlinks: Claude Code (v2.0.13+) discovers them via
`installed_plugins.json` + `known_marketplaces.json` and clones into
`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` on first start.
This sibling group mirrors `doctor/mcps.py`'s adapter-driven shape.

Rules:
- allow-listed but key absent from installed_plugins.json → FAIL
- allow-listed and key present, cache dir present → finding (pass)
- allow-listed and key present, cache dir absent → WARN (Claude clones
  lazily on next start, so missing cache is not fatal)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from agent_toolkit_cli._allowlist import read_allowlist
from agent_toolkit_cli.commands._plugin_dispatch import _build_plugin_entries
from agent_toolkit_cli.doctor.result import GroupResult, Status
from agent_toolkit_cli.harness_adapters import get_adapter
from agent_toolkit_cli.harness_adapters.base import UnimplementedAdapter


def run(toolkit_root: Path, *, harness: str = "claude") -> GroupResult:
    """Per-plugin adapter-driven health check.

    Only Claude has a plugin adapter today; other harnesses return OK/skipped.
    """
    findings: list[str] = []
    warns: list[str] = []
    fails: list[str] = []

    if harness != "claude":
        return GroupResult(
            name="plugins",
            status=Status.OK,
            summary=f"no plugin adapter for {harness}",
            findings=[f"no plugin adapter for harness {harness} — skipped"],
        )

    home = Path(os.environ.get("HOME", str(Path.home())))
    allowlist_path = home / ".agent-toolkit.yaml"
    allowed_slugs = read_allowlist(allowlist_path).get("plugins", [])
    if not allowed_slugs:
        return GroupResult(
            name="plugins",
            status=Status.OK,
            summary="no plugins allow-listed",
            findings=["no allow-listed plugins for claude/user"],
        )

    adapter = get_adapter("claude", kind="plugin")
    if isinstance(adapter, UnimplementedAdapter):
        return GroupResult(
            name="plugins",
            status=Status.OK,
            summary="no plugin adapter for claude yet",
            findings=["no plugin adapter for harness claude yet — skipped"],
        )

    # The adapter signature is `(scope, project_root)`. Plugin doctor is
    # user-scope-only (matches the existing skill/agent/command checks) —
    # project plugins aren't supported in v1.
    scope = "user"
    project_root = Path(".")  # unused for user scope

    config_target = adapter.config_target(scope, project_root)
    if config_target is None:
        return GroupResult(
            name="plugins",
            status=Status.OK,
            summary="no plugin config target",
            findings=findings,
        )

    installed_keys = set(adapter.list_installed(scope, project_root))

    entries = _build_plugin_entries(toolkit_root, allowed_slugs)
    entry_by_slug = {e.name: e for e in entries}

    # Recorded versions for the cache-dir probe come from the JSON itself.
    recorded_versions: dict[str, str] = {}
    if config_target.is_file():
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

    if fails:
        return GroupResult(
            name="plugins",
            status=Status.FAIL,
            summary=(
                f"{len(fails)} plugin(s) not recorded, "
                f"{len(warns)} other issue(s) for harness={harness}"
            ),
            findings=findings + warns + fails,
            fix_hint=f"`agent-toolkit link user {harness}` to reconcile",
        )
    if warns:
        return GroupResult(
            name="plugins",
            status=Status.WARN,
            summary=f"{len(warns)} plugin issue(s) for harness={harness}",
            findings=findings + warns,
            fix_hint=f"`agent-toolkit link user {harness}` to reconcile",
        )
    return GroupResult(
        name="plugins",
        status=Status.OK,
        summary=f"{len(findings)} plugin(s) all healthy for harness={harness}",
        findings=findings,
    )
