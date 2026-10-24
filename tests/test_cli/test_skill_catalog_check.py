"""Read-only revision checks are explicit CLI operations, not updates."""
import json

from click.testing import CliRunner

from agent_toolkit_cli.cli import main
from tests.test_cli.test_reground import sandbox, git, invoke
from tests.test_cli.test_skill_catalog_acquire import subscribed


def test_check_detects_upstream_without_mutating_backing(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    invoke("skills", "catalog", "add", "demo")
    backing = (sandbox / ".agent-toolkit/skills/demo").resolve().parents[1]
    before = git(backing, "rev-parse", "HEAD")
    first = json.loads(invoke("skills", "check", "demo", "-g", "--json").stdout)[0]
    assert first["status"] == "current" and first["checked_at"]
    (upstream / "skills/demo/SKILL.md").write_text("Changed upstream")
    git(upstream, "add", ".")
    git(upstream, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "advance")
    second = json.loads(invoke("skills", "check", "demo", "-g", "--json").stdout)[0]
    assert second["status"] == "different"
    assert second["remote_sha"] != second["local_sha"]
    assert git(backing, "rev-parse", "HEAD") == before
    assert (sandbox / ".agent-toolkit/skills/demo/SKILL.md").read_text().startswith("---")
    invoke("skills", "update", "demo", "-g")
    from agent_toolkit_cli.skill_update_check import read_check
    assert read_check("demo", scope="global", home=sandbox, project=None)["status"] == "stale"
    assert (sandbox / ".agent-toolkit/skills/demo/SKILL.md").read_text() == "Changed upstream"


def test_unreachable_skill_remote_becomes_unknown_not_current(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    invoke("skills", "catalog", "add", "demo")
    invoke("skills", "check", "-g")
    upstream.rename(upstream.with_name("offline"))
    result = CliRunner().invoke(main, ["skills", "check", "demo", "-g", "--json"])
    assert result.exit_code != 0
    row = json.loads(result.stdout)[0]
    assert row["status"] == "unknown" and row["error"]


def test_pin_check_and_doctor_do_not_update_or_write(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    sha = git(upstream, "rev-parse", "HEAD")
    data = json.loads((cat / "catalog.json").read_text())
    data["skills"][0]["ref"] = sha
    (cat / "catalog.json").write_text(json.dumps(data))
    git(cat, "add", ".")
    git(cat, "-c", "user.name=Test", "-c", "user.email=test@example.test", "commit", "-m", "pin")
    invoke("skills", "catalog", "add", "demo")
    row = json.loads(invoke("skills", "check", "-g", "--json").stdout)[0]
    assert row["status"] == "pinned"
    state = sandbox / ".agent-toolkit/skills-update-checks.json"
    before = state.read_bytes()
    lock = sandbox / ".agent-toolkit/skills-lock.json"
    lock_before = lock.read_bytes()
    invoke("skills", "doctor", "demo", "-g", "--no-fix")
    assert state.read_bytes() == before and lock.read_bytes() == lock_before


def test_check_works_after_catalog_unsubscribe_and_marks_local_edits(tmp_path, sandbox):
    upstream, cat = subscribed(tmp_path)
    invoke("skills", "catalog", "add", "demo")
    invoke("skills", "catalog", "unsubscribe")
    (sandbox / ".agent-toolkit/skills/demo/SKILL.md").write_text("local work")
    row = json.loads(invoke("skills", "check", "-g", "--json").stdout)[0]
    assert row["status"] == "current" and row["local_changes"]
    assert (sandbox / ".agent-toolkit/skills/demo/SKILL.md").read_text() == "local work"


def test_no_subscription_check_has_no_side_effects(sandbox):
    assert json.loads(invoke("skills", "check", "-g", "--json").stdout) == []
    assert not (sandbox / ".agent-toolkit").exists()
