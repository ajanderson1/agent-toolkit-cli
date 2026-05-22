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
    skill_name: str | None = None


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


def _sanitize_ref(ref: str) -> str:
    if not ref:
        raise SourceParseError("Empty ref")
    if any(ch.isspace() for ch in ref):
        raise SourceParseError(f"Unsafe ref: '{ref}' contains whitespace")
    if ref.startswith("-"):
        raise SourceParseError(f"Unsafe ref: '{ref}' must not start with '-'")
    if "\\" in ref:
        raise SourceParseError(f"Unsafe ref: '{ref}' contains backslash")
    if "@{" in ref:
        raise SourceParseError(f"Unsafe ref: '{ref}' contains '@{{'")
    if ".." in ref:
        raise SourceParseError(f"Unsafe ref: '{ref}' contains '..'")
    for seg in ref.split("/"):
        if seg.startswith("."):
            raise SourceParseError(
                f"Unsafe ref: '{ref}' has a segment starting with '.'"
            )
        if seg.endswith(".lock"):
            raise SourceParseError(
                f"Unsafe ref: '{ref}' has a segment ending in '.lock'"
            )
    return ref


def _parse_https(url: str) -> ParsedSource:
    parsed = urlparse(url)
    if parsed.hostname is None:
        raise SourceParseError(f"Unparseable URL: {url}")
    host = parsed.hostname
    path = parsed.path.lstrip("/").removesuffix(".git")

    if host in ("skills.sh", "www.skills.sh"):
        parts = path.split("/")
        # Tolerate a single trailing empty segment from a trailing slash.
        if parts and parts[-1] == "":
            parts = parts[:-1]
        if len(parts) != 3 or not all(parts):
            raise SourceParseError(
                f"skills.sh URL needs /<owner>/<repo>/<skill>: {url}"
            )
        owner, repo, skill_name = parts[0], parts[1], parts[2]
        owner_repo = f"{owner}/{repo}"
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner_repo}",
            owner_repo=owner_repo,
            ref=None,
            subpath=None,
            skill_name=skill_name,
        )

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


def _parse_file_url(url: str) -> ParsedSource:
    """Parse a file:// URL into a synthetic owner/repo so the monorepo path can
    treat a local clone as if it had a remote owner/repo.

    Uses the file path's last component as `repo` and `local` as the synthetic
    owner. Supports `/tree/<ref>/<subpath>` to address a subpath within the
    parent, matching the GitHub URL convention.
    """
    body = url[len("file://"):]
    # body might be "/abs/path[/tree/main/sub]" — split off tree/<ref>/<sub>.
    ref: str | None = None
    subpath: str | None = None
    if "/tree/" in body:
        head, _, rest = body.partition("/tree/")
        parts = rest.split("/", 1)
        ref = parts[0] or None
        if len(parts) == 2 and parts[1]:
            subpath = _sanitize_subpath(parts[1])
        body = head
    abs_path = body.removesuffix(".git").rstrip("/")
    if not abs_path:
        raise SourceParseError(f"Unparseable file:// URL: {url}")
    repo = Path(abs_path).name
    if not repo:
        raise SourceParseError(f"Unparseable file:// URL: {url}")
    owner_repo = f"local/{repo}"
    return ParsedSource(
        type="git",
        url=f"file://{abs_path}",
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

    if input_.startswith("file://"):
        return _parse_file_url(input_)

    # GitHub shorthand: owner/repo[@ref][/subpath] (no scheme, no leading dot/slash).
    m = re.fullmatch(
        r"(?P<owner>[A-Za-z0-9_.\-]+)"
        r"/(?P<repo>[A-Za-z0-9_.\-]+)"
        r"(?:@(?P<ref>[^\s/][^\s/]*))?"
        r"(?:/(?P<subpath>[^\s].*))?",
        input_,
    )
    if m:
        owner_repo = f"{m['owner']}/{m['repo']}"
        ref = _sanitize_ref(m["ref"]) if m["ref"] else None
        subpath = _sanitize_subpath(m["subpath"]) if m["subpath"] else None
        return ParsedSource(
            type="github",
            url=f"https://github.com/{owner_repo}",
            owner_repo=owner_repo,
            ref=ref,
            subpath=subpath,
            skill_name=None,
        )

    raise SourceParseError(f"Unrecognised source: {input_}")
