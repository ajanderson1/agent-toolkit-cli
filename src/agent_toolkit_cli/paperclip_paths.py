"""Pure Paperclip company-context detection for the Skills harness.

Filesystem-only: recognises a Paperclip company root by its on-disk layout and
derives the sibling company skills library. No Paperclip API, authentication,
credential, or agent-assignment concern lives here.

A company root is::

    <paperclip_root>/instances/<instance>/companies/<company-id>

and its skills library is the sibling::

    <paperclip_root>/instances/<instance>/skills/<company-id>

Detection walks upward from a descendant to the nearest valid company root so
commands launched inside a company workspace normalise to that company.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PaperclipContextError(ValueError):
    """The requested path is not inside a Paperclip company root."""


@dataclass(frozen=True)
class PaperclipCompanyContext:
    """Resolved Paperclip company placement for skill projection."""

    company_root: Path
    instance_root: Path
    instance_name: str
    company_id: str
    skills_root: Path


def detect_paperclip_company(
    path: Path, *, paperclip_root: Path | None = None,
) -> PaperclipCompanyContext | None:
    """Return the nearest enclosing Paperclip company context, or None.

    ``paperclip_root`` defaults to ``~/.paperclip`` in production; tests pass an
    explicit temporary root so detection never touches the real tree.
    """
    root = (paperclip_root or (Path.home() / ".paperclip")).resolve()
    current = path.resolve()
    for candidate in (current, *current.parents):
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            continue
        parts = relative.parts
        if (
            len(parts) == 4
            and parts[0] == "instances"
            and parts[1]
            and parts[2] == "companies"
            and parts[3]
            and candidate.is_dir()
        ):
            instance_root = root / "instances" / parts[1]
            return PaperclipCompanyContext(
                company_root=candidate,
                instance_root=instance_root,
                instance_name=parts[1],
                company_id=parts[3],
                skills_root=instance_root / "skills" / parts[3],
            )
    return None


def require_paperclip_company(
    path: Path, *, paperclip_root: Path | None = None,
) -> PaperclipCompanyContext:
    """Return the enclosing company context or fail loudly with guidance."""
    context = detect_paperclip_company(path, paperclip_root=paperclip_root)
    if context is None:
        raise PaperclipContextError(
            "Paperclip skills require project scope inside "
            "~/.paperclip/instances/<instance>/companies/<company-id>"
        )
    return context


def normalize_skill_project_root(
    path: Path, *, paperclip_root: Path | None = None,
) -> Path:
    """Normalise a skill project root, folding Paperclip descendants upward.

    Inside a Paperclip company the resolved company root becomes the project
    root; every other path is returned unchanged.
    """
    context = detect_paperclip_company(path, paperclip_root=paperclip_root)
    return context.company_root if context is not None else path
