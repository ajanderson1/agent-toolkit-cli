"""Parse a skill source string into a ParsedSource.

Mirrors vercel-labs/skills/src/source-parser.ts addressing scheme so that
sources accepted by `npx skills add` are accepted here, byte-for-byte.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

SourceType = Literal["github", "gitlab", "git", "local"]


class SourceParseError(ValueError):
    """Raised when a source string cannot be parsed or contains traversal."""


@dataclass(frozen=True)
class ParsedSource:
    type: SourceType
    url: str
    owner_repo: str | None
    ref: str | None
    subpath: str | None


_LOCAL_PREFIXES = ("./", "../")
_SSH_RE = re.compile(r"^git@([^:]+):(.+)$")


def _is_local(input_: str) -> bool:
    if input_.startswith(_LOCAL_PREFIXES) or input_ in (".", ".."):
        return True
    p = Path(input_)
    return p.is_absolute()


def _sanitize_subpath(subpath: str) -> str:
    norm = subpath.replace("\\", "/")
    if any(seg == ".." for seg in norm.split("/")):
        raise SourceParseError(
            f"Unsafe subpath: '{subpath}' contains path traversal segments."
        )
    return subpath


def _parse_https(url: str) -> ParsedSource:
    parsed = urlparse(url)
    if parsed.hostname is None:
        raise SourceParseError(f"Unparseable URL: {url}")
    host = parsed.hostname
    path = parsed.path.lstrip("/").removesuffix(".git")

    ref: str | None = None
    subpath: str | None = None
    if "/tree/" in path:
        head, _, rest = path.partition("/tree/")
        parts = rest.split("/", 1)
        ref = parts[0] or None
        if len(parts) == 2 and parts[1]:
            subpath = _sanitize_subpath(parts[1])
        path = head

    if "/" not in path:
        raise SourceParseError(f"URL missing owner/repo: {url}")

    owner, repo = path.split("/", 1)
    owner_repo = f"{owner}/{repo}"

    if "github.com" in host:
        source_type: SourceType = "github"
    elif "gitlab" in host:
        source_type = "gitlab"
    else:
        source_type = "git"

    canonical_url = f"https://{host}/{owner_repo}"
    return ParsedSource(
        type=source_type,
        url=canonical_url,
        owner_repo=owner_repo,
        ref=ref,
        subpath=subpath,
    )


def parse_source(input_: str) -> ParsedSource:
    if not input_:
        raise SourceParseError("empty source")

    if _is_local(input_):
        path = Path(input_).resolve()
        return ParsedSource(
            type="local", url=str(path), owner_repo=None, ref=None, subpath=None
        )

    ssh = _SSH_RE.match(input_)
    if ssh:
        host, path = ssh.group(1), ssh.group(2).removesuffix(".git")
        if "/" not in path:
            raise SourceParseError(f"SSH URL missing owner/repo: {input_}")
        owner_repo = path
        if "github.com" in host:
            source_type: SourceType = "github"
        elif "gitlab" in host:
            source_type = "gitlab"
        else:
            source_type = "git"
        return ParsedSource(
            type=source_type,
            url=input_,
            owner_repo=owner_repo,
            ref=None,
            subpath=None,
        )

    if input_.startswith(("http://", "https://")):
        return _parse_https(input_)

    # GitHub shorthand: owner/repo (no scheme, no leading dot/slash, exactly one slash).
    if re.fullmatch(r"[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+", input_):
        owner_repo = input_
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner_repo}",
            owner_repo=owner_repo,
            ref=None,
            subpath=None,
        )

    raise SourceParseError(f"Unrecognised source: {input_}")
