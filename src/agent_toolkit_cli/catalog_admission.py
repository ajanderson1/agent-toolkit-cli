"""Catalogue publication checks: source fit plus explicit curator review evidence.

No upstream code is imported or executed. This validates evidence, not the truth
of a reviewer's quality judgement; ordinary catalogue browsing never calls it.
"""
from __future__ import annotations

import base64
from datetime import date
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile

from wcmatch import glob

from agent_toolkit_cli.skill_catalog import CatalogEntry, npm_identity, parse_catalog_entries, run_git


def selector_record(item):
    value = item.as_dict()
    value.pop("description")
    return value


def _regular_entry(tree, relative):
    parts = PurePosixPath(relative).parts
    for index in range(len(parts)):
        mode = tree.get("/".join(parts[:index + 1]))
        allowed = ("100644", "100755") if index == len(parts) - 1 else ("040000",)
        if mode not in allowed:
            raise ValueError(f"missing, symlinked or unsupported entry file: {relative}")


def _pi_entries(files, package, *, tree=None, read_package=None):
    """Resolve Pi's directory/index discovery using metadata, never importing code.

    ``tree`` retains unsafe Git/local nodes so a good entry cannot hide a link.
    npm already rejects links; its directories may be implicit in file names.
    Nested manifests are read through a caller-supplied, bounded JSON reader.
    """
    files = set(files)
    directories = {parent.as_posix() for name in files for parent in PurePosixPath(name).parents}
    if tree is not None:
        directories.update(name for name, mode in tree.items() if mode == "040000")
    nodes = files | directories | (set(tree) if tree is not None else set())
    children = {}
    for name in nodes - {"."}:
        children.setdefault(PurePosixPath(name).parent.as_posix(), set()).add(name)
    active = set()
    flags = glob.GLOBSTAR | glob.BRACE

    def checked(name):
        if tree is not None and name != ".":
            if name in directories and tree.get(name) == "040000":
                parts = PurePosixPath(name).parts
                if any(tree.get("/".join(parts[:index + 1])) != "040000" for index in range(len(parts))):
                    raise ValueError(f"missing, symlinked or unsupported directory: {name}")
            else:
                _regular_entry(tree, name)
        return name

    def declarations(data):
        if not isinstance(data, dict) or not isinstance(data.get("pi", {}), dict):
            raise ValueError("invalid Pi package manifest")
        entries = data.get("pi", {}).get("extensions")
        if entries is not None and (not isinstance(entries, list) or not all(isinstance(v, str) for v in entries)):
            raise ValueError("Pi extensions must be an array of relative paths/patterns")
        return entries

    def safe(value):
        if (not value or PurePosixPath(value).is_absolute() or ".." in PurePosixPath(value).parts or "\\" in value):
            raise ValueError("unsafe Pi extension entrypoint")
        return PurePosixPath(value).as_posix()

    def resolve_path(name, *, discover=True):
        checked(name)
        if name in files:
            return {name}
        if name not in directories:
            return set()
        if name in active or len(active) >= 64:
            raise ValueError("Cyclic or excessively nested Pi extension directory manifest")
        active.add(name)
        try:
            manifest = (PurePosixPath(name) / "package.json").as_posix()
            if manifest in nodes:
                checked(manifest)
                if manifest == "package.json":
                    data = package
                elif read_package is None:
                    raise ValueError("nested Pi package manifest requires a metadata reader")
                else:
                    data = read_package(manifest)
                entries = declarations(data)
                if entries:
                    selected = set()
                    for value in entries:
                        value = safe(value)
                        # Pi's nested resolveExtensionEntries checks literal paths,
                        # unlike the root package manifest's glob expansion.
                        if value.startswith(("!", "+", "-")) or glob.is_magic(value, flags=flags):
                            raise ValueError("nested Pi extension manifest requires literal paths")
                        target = (PurePosixPath(name) / value).as_posix()
                        if target in nodes:
                            selected.update(resolve_path(target))
                    if selected:
                        return selected
            for filename in ("index.ts", "index.js"):
                target = (PurePosixPath(name) / filename).as_posix()
                if target in nodes:
                    return resolve_path(target)
            selected = set()
            if discover:
                # No implicit deep recursion: children need an index/manifest.
                for child in sorted(children.get(name, ())):
                    basename = PurePosixPath(child).name
                    if basename.startswith(".") or basename == "node_modules":
                        continue
                    checked(child)
                    if child in files:
                        if child.endswith((".ts", ".js")):
                            selected.add(child)
                    elif child in directories:
                        selected.update(resolve_path(child, discover=False))
            return selected
        finally:
            active.remove(name)

    patterns = declarations(package)
    if patterns is not None:
        selected, exclusions = set(), []
        for pattern in patterns:
            negative = pattern.startswith("!")
            value = safe(pattern[1:] if negative else pattern)
            if value.startswith(("+", "-")):
                raise ValueError("unsupported Pi extension override")
            if negative:
                exclusions.append(value)
            else:
                for name in sorted(nodes):
                    if glob.globmatch(name, value, flags=flags):
                        selected.update(resolve_path(name))
        # Native manifest exclusions filter resolved files (also by basename),
        # not directory subtrees, and apply regardless of declaration order.
        selected = {name for name in selected if not any(
            glob.globmatch(name, pattern, flags=flags)
            or glob.globmatch(PurePosixPath(name).name, pattern, flags=flags) for pattern in exclusions)}
        if not selected:
            raise ValueError("Pi package declares no existing extension entrypoints")
        return selected
    for name in ("index.ts", "index.js"):
        if name in nodes:
            return resolve_path(name)
    raise ValueError("Pi extension needs index.ts/index.js or declared pi.extensions entrypoints")


def inspect_git(item):
    assert item.source is not None
    with tempfile.TemporaryDirectory(prefix="toolkit-catalog-inspection-") as tmp:
        root = Path(tmp)
        run_git(["init", "--bare", "--quiet"], cwd=root)
        run_git(["fetch", "--quiet", "--depth=1", "--", item.source.url, item.source.ref or "HEAD"], cwd=root)
        revision = run_git(["rev-parse", "FETCH_HEAD"], cwd=root)
        tree = {}
        for record in run_git(["ls-tree", "-r", "-t", "-z", "FETCH_HEAD"], cwd=root).split("\0"):
            if record:
                metadata, name = record.split("\t", 1)
                tree[name] = metadata.split()[0]
        directory = "" if item.source.subpath == "." else item.source.subpath + "/"
        if item.kind == "pi-extension":
            def read_package(relative):
                _regular_entry(tree, relative)
                body = run_git(["show", "FETCH_HEAD:" + relative], cwd=root)
                if len(body.encode()) > 1024 * 1024:
                    raise ValueError("Pi package manifest is too large")
                return json.loads(body)
            package = read_package("package.json") if "package.json" in tree else {}
            files = {name for name, mode in tree.items() if mode in ("100644", "100755")}
            for relative in _pi_entries(files, package, tree=tree, read_package=read_package):
                _regular_entry(tree, relative)
        else:
            filename = {"skill": "SKILL.md", "command": "COMMAND.md", "agent": item.entry_file}[item.kind]
            relative = directory + filename
            _regular_entry(tree, relative)
            if item.kind == "agent":
                if filename == "AGENTS.md" and directory + item.key + ".md" in tree:
                    raise ValueError("agent shape conflicts with the existing flat-file preference")
                from agent_toolkit_cli.agent_paths import validate_agent_revision
                validate_agent_revision(root, "FETCH_HEAD", {item.key: relative})
        return dict(revision=revision)


def inspect_npm(item):
    """Download a versioned package with lifecycle scripts disabled; never extract it."""
    identity = npm_identity(item.npm_source)
    with tempfile.TemporaryDirectory(prefix="toolkit-catalog-npm-inspection-") as tmp:
        result = subprocess.run(["npm", "pack", "--ignore-scripts", "--json", "--pack-destination", tmp,
            "--cache", str(Path(tmp) / "cache"), "--", item.npm_source.removeprefix("npm:")], cwd=tmp,
            capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise ValueError("npm inspection failed; check registry access and exact package version")
        metadata = json.loads(result.stdout)[0]
        filename = metadata.get("filename")
        if not isinstance(filename, str) or Path(filename).name != filename:
            raise ValueError("invalid npm package inspection result")
        archive = Path(tmp) / filename
        if archive.stat().st_size > 50 * 1024 * 1024:
            raise ValueError("npm package exceeds the 50 MiB inspection limit")
        integrity = "sha512-" + base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode()
        if metadata.get("integrity") != integrity:
            raise ValueError("npm package integrity mismatch")
        with tarfile.open(archive) as package:
            members, total_size = [], 0
            for member in package:
                members.append(member)
                total_size += member.size
                if len(members) > 10000 or total_size > 200 * 1024 * 1024:
                    raise ValueError("npm archive exceeds inspection limits")
            if any(not member.name.startswith("package/") or ".." in PurePosixPath(member.name).parts
                   or member.issym() or member.islnk() or not (member.isfile() or member.isdir()) for member in members):
                raise ValueError("npm package contains unsafe paths or links")
            def read_package(relative):
                manifest = package.getmember("package/" + relative)
                if not manifest.isfile() or manifest.size > 1024 * 1024:
                    raise ValueError("npm package manifest is not a bounded regular file")
                return json.load(package.extractfile(manifest))
            data = read_package("package.json")
            if not isinstance(data, dict):
                raise ValueError("invalid npm package manifest")
            if data.get("name") != identity or data.get("version") != item.npm_source.rsplit("@", 1)[1]:
                raise ValueError("npm package identity/version mismatch")
            files = {member.name.removeprefix("package/") for member in members if member.isfile()}
            _pi_entries(files, data, read_package=read_package)
        return dict(revision=data["version"], integrity=integrity)


def _review(item, reviews):
    path = reviews / item.kind / (item.key + ".json")
    try:
        record = json.loads(path.read_text())
        if not isinstance(record, dict) or record.get("version") != 1 or record.get("selector") != selector_record(item):
            raise ValueError("review does not match the selected catalogue source")
        if not isinstance(record.get("reviewer"), str) or not record["reviewer"].strip():
            raise ValueError("reviewer is required")
        date.fromisoformat(record.get("reviewedAt", ""))
        for name in ("fit", "quality", "functional", "security", "license"):
            check = record.get("checks", {}).get(name, {})
            if (not isinstance(check, dict) or check.get("passed") is not True
                    or not isinstance(check.get("evidence"), str) or not check["evidence"].strip()):
                raise ValueError(f"completed {name} inspection with evidence is required")
        if not isinstance(record.get("limitations"), list) or not all(isinstance(v, str) for v in record["limitations"]):
            raise ValueError("review limitations must be recorded (an empty array is allowed)")
        targets = record.get("targets")
        if not isinstance(targets, list) or not targets:
            raise ValueError("tested harness/scope targets are required")
        from agent_toolkit_cli.asset_catalog_ops import validate_targets
        from agent_toolkit_cli.skill_agents import AGENTS
        for target in targets:
            if not isinstance(target, dict) or target.get("scope") not in ("global", "project") or target.get("harness") not in AGENTS:
                raise ValueError("invalid review target")
            if item.kind != "skill" and item.source_type == "git":
                validate_targets(item, (target["harness"],), scope=target["scope"],
                    home=Path.home(), project=path.parent if target["scope"] == "project" else None)
        return record
    except (ValueError, OSError, TypeError, AttributeError) as exc:
        raise ValueError(f"{item.kind}:{item.key}: missing or incomplete inspection review ({path})") from exc


def validate_catalog(path, *, admission=False, base=None, reviews=None):
    entries = parse_catalog_entries(json.loads(path.read_text()))
    if not admission:
        return len(entries), 0
    previous = parse_catalog_entries(json.loads(base.read_text())) if base else ()
    old = {(item.kind, item.key): item.selector for item in previous}
    changed = [item for item in entries if old.get((item.kind, item.key)) != item.selector]
    reviews = reviews or path.parent / "reviews"
    # Check all review evidence before making even a read-only upstream request.
    records = [(item, _review(item, reviews)) for item in changed]
    for item, record in records:
        observed = inspect_npm(item) if item.source_type == "npm" else inspect_git(item)
        if any(record.get(field) != value for field, value in observed.items()):
            raise ValueError(f"{item.kind}:{item.key}: inspection revision/integrity differs from the review")
        if item.source_type == "git" and item.source.ref != observed["revision"]:
            raise ValueError(f"{item.kind}:{item.key}: admission requires the full reviewed Git commit pin")
    return len(entries), len(changed)
