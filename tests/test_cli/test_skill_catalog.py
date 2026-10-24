"""Live optional catalog discovery uses real disposable Git remotes."""
import json
import subprocess

import pytest
from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_reground import sandbox, repo, git, invoke


def manifest(**overrides):
    item = dict(key="demo", description="Demo skill", source="https://github.com/example/skills.git", path="skills/demo", ref="main")
    item.update(overrides)
    return {"version": 1, "skills": [item]}


def catalog_repo(tmp_path, data=None):
    return repo(tmp_path, {"catalog.json": json.dumps(data if data is not None else manifest())})


def test_no_subscription_is_noop(sandbox):
    from agent_toolkit_cli.skill_catalog import read_catalog
    assert read_catalog() is None
    assert not (sandbox / ".agent-toolkit").exists()


def test_subscribe_live_read_changed_remote_and_unsubscribe(tmp_path, sandbox):
    source = catalog_repo(tmp_path)
    config = sandbox / ".agent-toolkit/config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"projectBacking": "central", "keep": 42}))
    invoke("skills", "catalog", "subscribe", source.as_uri())
    from agent_toolkit_cli.skill_catalog import read_catalog
    first = read_catalog()
    assert not first.error and first.skills[0].key == "demo"
    assert first.skills[0].source.subpath == "skills/demo"
    (source / "catalog.json").write_text(json.dumps(manifest(key="second")))
    git(source, "add", ".")
    git(source, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "change")
    second = read_catalog()
    assert second.revision != first.revision
    assert [s.key for s in second.skills] == ["second"]
    assert not (sandbox / ".agent-toolkit/skills-lock.json").exists()
    source.rename(tmp_path / "unavailable")
    failed = read_catalog()
    assert failed.error and not failed.skills
    invoke("skills", "catalog", "unsubscribe")
    assert json.loads(config.read_text()) == {"projectBacking": "central", "keep": 42}
    assert read_catalog() is None


@pytest.mark.parametrize("data", [
    {"version": 2, "skills": []}, manifest(path="../escape"),
    manifest(path="/absolute"), manifest(ref="--upload-pack=bad"),
    manifest(source="https://user:secret@example.com/skills.git"),
    {"version": 1, "skills": [manifest()["skills"][0]] * 2},
])
def test_invalid_catalog_refuses_subscription_without_writes(tmp_path, sandbox, data):
    source = catalog_repo(tmp_path, data)
    result = CliRunner().invoke(main, ["skills", "catalog", "subscribe", source.as_uri()])
    assert result.exit_code != 0
    assert "secret" not in result.output
    assert not (sandbox / ".agent-toolkit/config.json").exists()


def test_timeout_is_bounded_and_no_stale_rows(tmp_path, sandbox, monkeypatch):
    source = catalog_repo(tmp_path)
    invoke("skills", "catalog", "subscribe", source.as_uri())
    from agent_toolkit_cli import skill_catalog
    real_run = subprocess.run
    def timeout(cmd, **kwargs):
        if "fetch" in cmd:
            assert kwargs.get("timeout", 9999) <= 20
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        return real_run(cmd, **kwargs)
    monkeypatch.setattr(skill_catalog.subprocess, "run", timeout)
    result = skill_catalog.read_catalog()
    assert result.error and result.skills == ()


@pytest.mark.parametrize("bad_ref", [42, [], {}, True])
def test_malformed_subscription_ref_does_not_break_local_commands(tmp_path, sandbox, bad_ref):
    from tests.test_cli.test_skill_catalog_acquire import subscribed
    upstream, cat = subscribed(tmp_path)
    invoke("skills", "catalog", "add", "demo")
    config = sandbox / ".agent-toolkit/config.json"
    data = json.loads(config.read_text())
    data["skillCatalog"]["ref"] = bad_ref
    config.write_text(json.dumps(data))
    listed = invoke("skills", "list", "-g", "--json")
    assert [row["slug"] for row in json.loads(listed.stdout)] == ["demo"]
    assert "catalog" in listed.stderr.lower()
    diagnosed = invoke("skills", "doctor", "demo", "-g", "--no-fix")
    assert "catalog warning" in diagnosed.output.lower()
    from agent_toolkit_cli.skill_catalog import read_catalog
    assert read_catalog().error


def test_catalog_list_json_and_regular_no_subscription_json(tmp_path, sandbox):
    assert json.loads(invoke("skills", "list", "-g", "--json").stdout) == []
    source = catalog_repo(tmp_path)
    invoke("skills", "catalog", "subscribe", source.as_uri())
    rows = json.loads(invoke("skills", "catalog", "list", "--json").stdout)
    assert rows[0]["key"] == "demo"
    assert not (sandbox / ".agents/skills/demo").exists()
