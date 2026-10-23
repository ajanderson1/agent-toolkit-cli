"""9f8 review: resolve linked directories before consuming parent components."""
import pytest
from click.testing import CliRunner

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.agent_paths import library_agent_path, validate_agent_revision
from agent_toolkit_cli.cli import main
from tests.test_cli.test_reground import sandbox, repo, git, invoke
from tests.test_cli.test_reground_review import commit
from tests.test_cli.test_reground_recheck import index_bytes


@pytest.mark.parametrize("target", ["back/../foreign-secret", "back/./../foreign-secret"])
def test_parent_components_after_linked_directory_cannot_escape(tmp_path, target):
    source = repo(tmp_path, {"AGENTS.md": "Role", "nested/foreign-secret": "internal decoy"})
    outside = tmp_path / "foreign-secret"
    outside.write_text("outside repository")
    (source / "nested/back").symlink_to("..", target_is_directory=True)
    leak = source / "nested/leak"
    leak.symlink_to(target)
    commit(source)
    # Native filesystem semantics: back resolves to the repo before ../ is read.
    assert leak.resolve(strict=True) == outside
    assert leak.read_text() == "outside repository"
    with pytest.raises(InstallError, match="escaping agent resource symlink"):
        validate_agent_revision(source, git(source, "rev-parse", "HEAD"), {"shared": "AGENTS.md"})


@pytest.mark.parametrize("target", ["back/nested/foreign-secret", "back/nested/../nested/foreign-secret"])
def test_internal_linked_directory_and_parent_components_remain_valid(tmp_path, target):
    source = repo(tmp_path, {"AGENTS.md": "Role", "nested/foreign-secret": "internal resource"})
    (source / "nested/back").symlink_to("..", target_is_directory=True)
    link = source / "nested/resource"
    link.symlink_to(target)
    commit(source)
    assert link.resolve(strict=True) == source / "nested/foreign-secret"
    validate_agent_revision(source, git(source, "rev-parse", "HEAD"), {"shared": "AGENTS.md"})
    assert link.read_text() == "internal resource"


def test_parent_component_cannot_traverse_a_regular_file(tmp_path):
    source = repo(tmp_path, {"AGENTS.md": "Role", "nested/data": "not a directory"})
    link = source / "nested/resource"
    link.symlink_to("data/../data")
    commit(source)
    with pytest.raises(NotADirectoryError):
        link.resolve(strict=True)
    with pytest.raises(InstallError, match="unproven prospective agent resource"):
        validate_agent_revision(source, git(source, "rev-parse", "HEAD"), {"shared": "AGENTS.md"})


def test_internal_directory_alias_checks_reachable_descendants(tmp_path):
    source = repo(tmp_path, {"manager/AGENTS.md": "Role", "common/data": "internal resource"})
    (source / "manager/resources").symlink_to("../common", target_is_directory=True)
    commit(source)
    validate_agent_revision(source, git(source, "rev-parse", "HEAD"), {"manager": "manager/AGENTS.md"})
    outside = tmp_path / "foreign"
    outside.mkdir()
    (outside / "secret").write_text("outside repository")
    (source / "common/outside").symlink_to(outside, target_is_directory=True)
    commit(source)
    assert (source / "manager/resources/outside/secret").read_text() == "outside repository"
    with pytest.raises(InstallError, match="escaping agent resource symlink"):
        validate_agent_revision(source, git(source, "rev-parse", "HEAD"), {"manager": "manager/AGENTS.md"})


@pytest.mark.parametrize("verb", ["add", "update", "reset"])
def test_dotdot_refresh_refusal_preserves_active_projection(tmp_path, sandbox, monkeypatch, verb):
    source = repo(tmp_path, {"AGENTS.md": "Role", "nested/foreign-secret": "internal decoy"})
    invoke("agent", "add", str(source), "--slug", "shared")
    project = tmp_path / "project"
    project.mkdir()
    monkeypatch.chdir(project)
    invoke("agent", "install", "shared", "-p", "--harnesses", "pi")
    canonical = library_agent_path("shared")
    library_lock = sandbox / ".agent-toolkit/agents-lock.json"
    project_lock = project / "agents-lock.json"
    def state():
        return (git(canonical, "rev-parse", "HEAD"), index_bytes(canonical),
                git(canonical, "for-each-ref", "--format=%(refname) %(objectname)"),
                library_lock.read_bytes(), project_lock.read_bytes())
    before = state()
    (source / "nested/back").symlink_to("..", target_is_directory=True)
    (source / "nested/leak").symlink_to("back/../foreign-secret")
    commit(source)
    # Standalone re-add is intentionally idempotent, so exercise its existing
    # legacy source-driven refresh helper as well as CLI update/reset.
    if verb == "add":
        from agent_toolkit_cli.agent_install import install
        from agent_toolkit_cli.skill_source import parse_source
        with pytest.raises(InstallError, match="escaping agent resource symlink"):
            install(parsed=parse_source(str(source)), slug="shared", scope="global",
                    home=sandbox, project=None, harnesses=("pi",), env=None)
    else:
        result = CliRunner().invoke(main, ["agent", verb, "shared", "-g"])
        assert result.exit_code != 0 and "escaping agent resource symlink" in result.output
    assert state() == before
    slot = project / ".pi/agents/shared"
    assert slot.resolve() == canonical and (slot / "AGENTS.md").read_text() == "Role"
    assert not (slot / "nested/leak").is_symlink()


def test_fresh_registration_does_not_publish_dotdot_escape(tmp_path, sandbox):
    source = repo(tmp_path, {"AGENTS.md": "Role", "nested/foreign-secret": "internal decoy"})
    (source / "nested/back").symlink_to("..", target_is_directory=True)
    (source / "nested/leak").symlink_to("back/../foreign-secret")
    commit(source)
    result = CliRunner().invoke(main, ["agent", "add", str(source), "--slug", "shared"])
    assert result.exit_code != 0 and "escaping agent resource symlink" in result.output
    assert not library_agent_path("shared").exists()
    assert not (sandbox / ".agent-toolkit/agents-lock.json").exists()
