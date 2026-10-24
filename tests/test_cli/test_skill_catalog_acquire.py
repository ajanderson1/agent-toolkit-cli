"""Catalog actions reuse real library acquisition and projections."""
import json

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_reground import sandbox, repo, git, invoke
from tests.test_cli.test_skill_catalog import manifest, catalog_repo


SKILL = "---\nname: demo\ndescription: Demo\n---\nRead only fixture.\n"


def subscribed(tmp_path):
    folder = tmp_path / "upstream"
    folder.mkdir()
    upstream = repo(folder, {"skills/demo/SKILL.md": SKILL, "skills/other/SKILL.md": SKILL, "skills/demo/references/test.md": "reference"})
    cat = catalog_repo(tmp_path, manifest(source=upstream.as_uri()))
    invoke("skills", "catalog", "subscribe", cat.as_uri())
    return upstream, cat


def test_add_and_enable_only_selected_nested_child(tmp_path, sandbox, monkeypatch):
    upstream, cat = subscribed(tmp_path)
    invoke("skills", "catalog", "add", "demo")
    library = sandbox / ".agent-toolkit/skills/demo"
    assert (library / "references/test.md").read_text() == "reference"
    assert not (sandbox / ".agents/skills/demo").exists()
    lock = json.loads((sandbox / ".agent-toolkit/skills-lock.json").read_text())
    assert set(lock["skills"]) == {"demo"}
    assert lock["skills"]["demo"]["catalog"]["key"] == "demo"
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("skills", "catalog", "enable", "demo", "--scope", "project", "--agents", "standard")
    assert (project / ".agents/skills/demo").resolve() == library.resolve()
    assert not (project / ".agents/skills/other").exists()
    assert not (sandbox / ".agents/skills/demo").exists()


def test_reuse_custom_slug_and_inventory_no_duplicates(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    invoke("skills", "add", upstream.as_uri(), "--path", "skills/demo", "--slug", "custom", "--ref", "main")
    lockpath = sandbox / ".agent-toolkit/skills-lock.json"
    before = lockpath.read_bytes()
    rows = json.loads(invoke("skills", "list", "-g", "--json").stdout)
    assert [row["slug"] for row in rows] == ["custom"]
    assert lockpath.read_bytes() == before, "browsing cannot associate provenance"
    invoke("skills", "catalog", "enable", "demo", "--scope", "global", "--agents", "standard")
    assert (sandbox / ".agents/skills/custom").is_symlink()
    assert not (sandbox / ".agents/skills/demo").exists()
    entry = json.loads(lockpath.read_text())["skills"]["custom"]
    assert entry["catalog"]["key"] == "demo" and entry["ref"] == "main"


def test_name_ref_conflict_refuses_without_changing_local_content(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    sha = git(upstream, "rev-parse", "HEAD")
    invoke("skills", "add", upstream.as_uri(), "--path", "skills/demo", "--slug", "demo", "--ref", sha)
    lockpath = sandbox / ".agent-toolkit/skills-lock.json"
    before = lockpath.read_bytes()
    result = CliRunner().invoke(main, ["skills", "catalog", "add", "demo"])
    assert result.exit_code != 0
    assert lockpath.read_bytes() == before


def test_catalog_only_list_hides_when_offline_but_keeps_acquired(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    rows = json.loads(invoke("skills", "list", "-g", "--json").stdout)
    assert rows[0]["origin"] == "catalog"
    assert json.loads(invoke("skills", "list", "-g", "--agent", "standard", "--json").stdout) == []
    invoke("skills", "catalog", "add", "demo")
    cat.rename(tmp_path / "offline")
    result = invoke("skills", "list", "-g", "--json")
    assert [r["slug"] for r in json.loads(result.stdout)] == ["demo"]
    assert "catalog" in result.stderr.lower()
    invoke("skills", "install", "demo", "--scope", "global", "--agents", "standard")
    assert (sandbox / ".agents/skills/demo").is_symlink()


def test_changed_selection_and_invalid_target_refuse_before_acquire(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    from agent_toolkit_cli.skill_catalog_ops import resolve_catalog_skill
    _, expected = resolve_catalog_skill("demo")
    (cat / "catalog.json").write_text(json.dumps(manifest(source=upstream.as_uri(), path="skills/other")))
    git(cat, "add", ".")
    git(cat, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "change")
    import pytest
    with pytest.raises(ValueError, match="changed"):
        resolve_catalog_skill("demo", expected=expected)
    result = CliRunner().invoke(main, ["skills", "catalog", "enable", "demo", "--agents", "invalid-harness"])
    assert result.exit_code != 0
    assert not (sandbox / ".agent-toolkit/skills-lock.json").exists()
