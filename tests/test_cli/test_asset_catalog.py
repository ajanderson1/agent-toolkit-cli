"""Shared, typed catalog discovery; no live user assets or network services."""
import copy
import json

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_reground import sandbox, repo, invoke


def entry(kind="agent", key="reviewer", **overrides):
    value = dict(kind=kind, key=key, description="Review work", sourceType="git",
                 source="example/assets", path=".", ref="main")
    if kind == "agent":
        value["entryFile"] = f"{key}.md"
    value.update(overrides)
    return value


def manifest(*entries):
    return dict(version=2, entries=list(entries))


def test_mixed_catalog_snapshot_and_kind_filtered_cli(tmp_path, sandbox):
    values = [entry("skill"), entry(), entry("command"), entry("pi-extension"),
              dict(kind="pi-extension", key="native", description="Native package",
                   sourceType="npm", source="npm:@example/tools@1.2.3")]
    source = repo(tmp_path, {"catalog.json": json.dumps(manifest(*values))})
    invoke("catalog", "subscribe", source.as_uri())
    from agent_toolkit_cli.skill_catalog import read_catalog
    snapshot = read_catalog()
    assert snapshot.error is None
    assert len(snapshot.entries) == 5 and len(snapshot.skills) == 1
    rows = json.loads(invoke("catalog", "list", "--json").output)
    assert {row["kind"] for row in rows} == {"skill", "agent", "command", "pi-extension"}
    assert len(json.loads(invoke("agents", "catalog", "list", "--json").output)) == 1
    assert len(json.loads(invoke("pi-extensions", "catalog", "list", "--json").output)) == 2
    for group, expected in (("agents", 1), ("commands", 1), ("pi-extensions", 2)):
        inventory = json.loads(invoke(group, "list", "-g", "--json").stdout)
        assert len(inventory) == expected and all(row["origin"] == "catalog" for row in inventory)
    assert json.loads(invoke("skills", "catalog", "list", "--json").output)[0]["key"] == "reviewer"
    assert not (sandbox / ".agent-toolkit/agents-lock.json").exists()
    invoke("catalog", "unsubscribe")
    assert json.loads(invoke("catalog", "list", "--json").output) == []


@pytest.mark.parametrize("change", [
    {"kind": "mcp"}, {"sourceType": "archive"}, {"entryFile": "../reviewer.md"},
    {"entryFile": "other.md"}, {"entryFile": None}, {"path": "../escape"},
    {"source": "example/assets@other"}, {"source": "https://user:secret@example.com/assets.git"},
    {"source": "example/assets/reviewer"}, {"ref": True}, {"key": "../bad"},
])
def test_v2_invalid_selectors_rejected(change):
    from agent_toolkit_cli.skill_catalog import parse_catalog_entries
    with pytest.raises(ValueError):
        parse_catalog_entries(manifest(entry(**change)))


def test_duplicate_selectors_and_keys_but_cross_kind_keys_allowed():
    from agent_toolkit_cli.skill_catalog import parse_catalog_entries
    item = entry()
    assert len(parse_catalog_entries(manifest(item, entry("command")))) == 2
    with pytest.raises(ValueError):
        parse_catalog_entries(manifest(item, copy.deepcopy(item)))
    with pytest.raises(ValueError):
        parse_catalog_entries(manifest(entry("command"), entry("command", key="alias")))


@pytest.mark.parametrize("item", [
    entry("pi-extension", path="nested"),
    entry("command", entryFile="COMMAND.md"),
    dict(kind="agent", key="native", description="Bad", sourceType="npm", source="npm:tools@1.2.3"),
    dict(kind="pi-extension", key="native", description="Bad", sourceType="npm", source="npm:tools@latest"),
    dict(kind="pi-extension", key="native", description="Bad", sourceType="npm", source="npm:tools"),
    dict(kind="pi-extension", key="native", description="Bad", sourceType="npm", source="npm:tools@1.2.3", path="."),
])
def test_unsupported_kind_source_shapes_fail(item):
    from agent_toolkit_cli.skill_catalog import parse_catalog_entries
    with pytest.raises(ValueError):
        parse_catalog_entries(manifest(item))


def test_catalog_has_only_one_selected_version_per_native_package():
    from agent_toolkit_cli.skill_catalog import parse_catalog_entries
    first = dict(kind="pi-extension", key="native", description="Native package",
                 sourceType="npm", source="npm:@example/tools@1.2.3")
    second = {**first, "key": "native-new", "source": "npm:@example/tools@2.0.0"}
    with pytest.raises(ValueError, match="npm identity"):
        parse_catalog_entries(manifest(first, second))


def test_bad_catalog_list_fails_without_leaking_credentials(tmp_path, sandbox):
    config = sandbox / ".agent-toolkit/config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"skillCatalog": {"url": "https://user:secret@example.com/catalog.git"}}))
    result = CliRunner().invoke(main, ["catalog", "list", "--json"])
    assert result.exit_code != 0 and "secret" not in result.output
