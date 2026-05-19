"""Doctor group: orphan body directories (no metadata anywhere)."""
from __future__ import annotations

import re
from pathlib import Path

from agent_toolkit_cli.doctor.result import GroupResult, Status

_VALID_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
from agent_toolkit_cli.walker import (
    _KIND_ROOT,
    _SIDECAR_KINDS,
    _inline_body_path,
    _sidecar_path,
    extract_frontmatter,
    read_sidecar,
)


def run(toolkit_root: Path) -> GroupResult:
    """Return an ADVISORY GroupResult listing any body dirs with no metadata."""
    findings: list[str] = []
    for kind in sorted(_SIDECAR_KINDS):
        root = toolkit_root / _KIND_ROOT[kind]
        if not root.exists():
            continue
        for body_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            slug = body_dir.name
            if not _VALID_SLUG.match(slug):
                # Not a toolkit slug — skip __pycache__, .git, scratch dirs, etc.
                continue
            inline = _inline_body_path(kind, slug, toolkit_root)
            sidecar = _sidecar_path(kind, slug, toolkit_root)
            has_inline = inline.is_file() and extract_frontmatter(inline) is not None
            has_sidecar = read_sidecar(sidecar) is not None
            if not has_inline and not has_sidecar:
                findings.append(
                    f"Orphan body: {body_dir.relative_to(toolkit_root)} "
                    f"has no metadata. Add inline frontmatter or {sidecar.name}."
                )
    count = len(findings)
    return GroupResult(
        name="orphans",
        status=Status.ADVISORY if findings else Status.OK,
        summary=f"{count} orphan body director{'y' if count == 1 else 'ies'} found",
        findings=findings,
    )


# Alias for callers that import the diagnose_orphans name directly.
diagnose_orphans = run
