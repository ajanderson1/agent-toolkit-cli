"""Pi directory declarations must be inspected without executing their code."""
import base64
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

import pytest

from agent_toolkit_cli.asset_catalog_ops import validate_pi_content
from agent_toolkit_cli.catalog_admission import _pi_entries, inspect_git, inspect_npm
from agent_toolkit_cli.skill_catalog import parse_catalog_entries
from tests.test_cli.test_asset_catalog import entry, manifest
from tests.test_cli.test_reground import git, repo, sandbox


def selected(files, entries, **kwargs):
    return _pi_entries(set(files), {"pi": {"extensions": entries}}, **kwargs)


@pytest.mark.parametrize(("files", "entries", "expected"), [
    (["extensions/sticky/index.ts", "extensions/sticky/index.js", "extensions/sticky/helper.ts"],
     ["./extensions/sticky"], {"extensions/sticky/index.ts"}),
    (["extensions/one.ts", "extensions/two.js", "extensions/README.md", "extensions/deep/helper.ts"],
     ["./extensions"], {"extensions/one.ts", "extensions/two.js"}),
    (["extensions/a/index.js", "extensions/a/helper.ts", "extensions/b/helper.ts"],
     ["extensions"], {"extensions/a/index.js"}),
    (["plugins/a/index.ts", "plugins/b/index.js"], ["plugins/*"],
     {"plugins/a/index.ts", "plugins/b/index.js"}),
    ([".pi/extensions/main.ts", ".pi/extensions/.hidden.ts", ".pi/extensions/node_modules/bad.ts"],
     ["./.pi/extensions"], {".pi/extensions/main.ts"}),
    (["extensions/new.ts", "extensions/old.js"], ["!**/old.js", "./extensions"], {"extensions/new.ts"}),
    (["extensions/new.ts", "extensions/old.js"], ["./extensions", "!old.js"], {"extensions/new.ts"}),
    (["extensions/new.ts", "extensions/module/index.ts"], ["extensions", "!extensions/module"],
     {"extensions/new.ts", "extensions/module/index.ts"}),
])
def test_directory_discovery_follows_pi_index_shallow_and_exclusion_rules(files, entries, expected):
    assert selected(files, entries) == expected


def test_nested_package_manifest_precedes_index_and_is_read_only_as_data():
    files = {"extensions/pkg/package.json", "extensions/pkg/index.ts", "extensions/pkg/src/main.ts"}
    read = []
    def package(path):
        read.append(path)
        return {"pi": {"extensions": ["./src/main.ts"]}}
    assert selected(files, ["extensions"], read_package=package) == {"extensions/pkg/src/main.ts"}
    assert read == ["extensions/pkg/package.json"]


def test_nested_manifest_cannot_be_assumed_safe_when_reader_is_missing():
    with pytest.raises(ValueError, match="manifest"):
        selected({"extensions/pkg/package.json", "extensions/pkg/index.ts"}, ["extensions"])


@pytest.mark.parametrize("path", ["../escape.ts", "/escape.ts", "..\\escape.ts", ""])
def test_nested_manifest_rejects_unsafe_declarations(path):
    with pytest.raises(ValueError, match="unsafe"):
        selected({"extensions/pkg/package.json", "extensions/pkg/index.ts"}, ["extensions"],
                 read_package=lambda _: {"pi": {"extensions": [path]}})


def test_cyclic_directory_manifest_is_rejected_instead_of_recursing_forever():
    with pytest.raises(ValueError, match="[Cc]yclic"):
        selected({"extensions/package.json"}, ["extensions"],
                 read_package=lambda _: {"pi": {"extensions": ["."]}})


@pytest.mark.parametrize("files", [[], ["extensions/README.md"], ["extensions/deep/helper.ts"]])
def test_empty_or_nonentry_directories_are_not_admitted(files):
    with pytest.raises(ValueError, match="no existing extension entrypoints"):
        selected(files, ["extensions"])


def test_directory_entrypoint_git_inspection_does_not_execute_code(tmp_path, sandbox):
    source = repo(tmp_path, {
        "package.json": json.dumps({"pi": {"extensions": ["./extensions/sticky"]}}),
        "extensions/sticky/index.ts": "throw new Error('must never execute')",
    })
    pin = git(source, "rev-parse", "HEAD")
    item = parse_catalog_entries(manifest(entry("pi-extension", source=source.as_uri(), ref=pin)))[0]
    assert inspect_git(item) == {"revision": pin}


@pytest.mark.parametrize("declared", [["extensions"], ["extensions/good.ts", "extensions/link.ts"]])
def test_local_directory_and_mixed_file_selectors_cannot_hide_a_symlink(tmp_path, declared):
    (tmp_path / "extensions").mkdir()
    (tmp_path / "extensions/good.ts").write_text("export default () => {}")
    target = tmp_path / "outside.ts"
    target.write_text("throw new Error('never execute')")
    (tmp_path / "extensions/link.ts").symlink_to(target)
    (tmp_path / "package.json").write_text(json.dumps({"pi": {"extensions": declared}}))
    with pytest.raises(ValueError, match="symlinked|unsupported"):
        validate_pi_content(tmp_path)


def test_nested_package_manifest_symlink_is_not_followed(tmp_path):
    nested = tmp_path / "extensions/plugin"
    nested.mkdir(parents=True)
    (nested / "index.ts").write_text("export default () => {}")
    target = tmp_path / "outside.json"
    target.write_text('{"pi":{"extensions":["index.ts"]}}')
    (nested / "package.json").symlink_to(target)
    (tmp_path / "package.json").write_text('{"pi":{"extensions":["extensions"]}}')
    with pytest.raises(ValueError, match="symlinked|unsupported"):
        validate_pi_content(tmp_path)


def test_npm_directory_discovery_infers_tar_directories_and_reads_nested_manifest(tmp_path, monkeypatch):
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w:gz") as tar:
        # Deliberately no explicit directory entries, as in npm's published archives.
        for name, body in {
            "package/package.json": json.dumps({"name": "directory-test", "version": "1.0.0", "pi": {"extensions": ["extensions"]}}),
            "package/extensions/plugin/package.json": '{"pi":{"extensions":["main.ts"]}}',
            "package/extensions/plugin/main.ts": "throw new Error('never execute')",
        }.items():
            encoded = body.encode()
            info = tarfile.TarInfo(name)
            info.size = len(encoded)
            tar.addfile(info, io.BytesIO(encoded))
    payload = archive.getvalue()
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(payload).digest()).decode()
    def pack(command, **kwargs):
        assert command[:4] == ["npm", "pack", "--ignore-scripts", "--json"]
        root = Path(command[command.index("--pack-destination") + 1])
        (root / "test.tgz").write_bytes(payload)
        return subprocess.CompletedProcess(command, 0, json.dumps([{"filename": "test.tgz", "integrity": integrity}]), "")
    monkeypatch.setattr("agent_toolkit_cli.catalog_admission.subprocess.run", pack)
    item = parse_catalog_entries(manifest({"kind": "pi-extension", "sourceType": "npm", "key": "directory-test",
        "description": "Test", "source": "npm:directory-test@1.0.0"}))[0]
    assert inspect_npm(item) == {"revision": "1.0.0", "integrity": integrity}
