"""Internal YAML writer — the only mutator for `.agent-toolkit.yaml`.

Underscore-prefixed: not advertised in `--help`. Used by `bin/lib/link.sh` and
`bin/lib/unlink.sh` to mutate the allow-list before re-projecting symlinks.
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

from agent_toolkit._allowlist import SECTIONS

_yaml = YAML()
_yaml.preserve_quotes = True
_yaml.indent(mapping=2, sequence=2, offset=0)


def _empty_doc() -> CommentedMap:
    doc = CommentedMap()
    for section in SECTIONS:
        doc[section] = CommentedSeq()
    return doc


def _load(path: Path) -> CommentedMap:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return _empty_doc()
    loaded = _yaml.load(path)
    if not isinstance(loaded, CommentedMap):
        return _empty_doc()
    for section in SECTIONS:
        if section not in loaded:
            loaded[section] = CommentedSeq()
        elif loaded[section] is None:
            loaded[section] = CommentedSeq()
    return loaded


def _dump(doc: CommentedMap, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        _yaml.dump(doc, fh)


@click.group("_yaml-edit", hidden=True)
def yaml_edit() -> None:
    """Internal: mutate `.agent-toolkit.yaml`. Not for direct use."""


@yaml_edit.command("add")
@click.argument("path", type=click.Path(path_type=Path))
@click.argument("section")
@click.argument("slug")
def add_cmd(path: Path, section: str, slug: str) -> None:
    """Add SLUG to SECTION in PATH (idempotent; creates file if missing)."""
    if section not in SECTIONS:
        raise click.ClickException(f"unknown section: {section!r}")
    doc = _load(path)
    seq = doc[section]
    if slug in list(seq):
        return
    seq.append(slug)
    _dump(doc, path)


@yaml_edit.command("remove")
@click.argument("path", type=click.Path(path_type=Path))
@click.argument("section")
@click.argument("slug")
def remove_cmd(path: Path, section: str, slug: str) -> None:
    """Remove SLUG from SECTION in PATH (idempotent; errors if file missing)."""
    if section not in SECTIONS:
        raise click.ClickException(f"unknown section: {section!r}")
    if not path.exists():
        raise click.ClickException(f"no such file: {path} — nothing to unlink.")
    doc = _load(path)
    seq = doc[section]
    items = list(seq)
    if slug not in items:
        return
    seq.remove(slug)
    _dump(doc, path)


@yaml_edit.command("snapshot")
@click.argument("path", type=click.Path(path_type=Path))
def snapshot_cmd(path: Path) -> None:
    """Replace PATH with sections built from stdin lines `<section> <slug>`."""
    doc = _empty_doc()
    for raw in sys.stdin.read().splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise click.ClickException(f"malformed snapshot line: {raw!r}")
        section, slug = parts
        if section not in SECTIONS:
            raise click.ClickException(f"unknown section in snapshot: {section!r}")
        if slug not in list(doc[section]):
            doc[section].append(slug)
    _dump(doc, path)
