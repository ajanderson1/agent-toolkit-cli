"""Integration review: harmless metadata edits do not retarget queued selectors."""
from dataclasses import replace

from tests.test_cli.test_asset_catalog import entry
from tests.test_cli.test_asset_catalog_acquire import subscribe
from tests.test_cli.test_reground import sandbox, repo


def test_description_change_between_target_selections_keeps_same_acquisition(tmp_path, sandbox):
    source = repo(tmp_path, {"COMMAND.md": "Summarize the supplied input"})
    subscribe(tmp_path, entry("command", source=source.as_uri()))
    from agent_toolkit_cli.skill_catalog import read_catalog
    from agent_toolkit_tui.catalog_apply import prepare_entry

    snapshot = read_catalog()
    original = snapshot.assets[0]
    corrected = replace(original, description="Corrected description only")
    refreshed = replace(snapshot, assets=(corrected,))
    intents = {
        ("project", "standard", "reviewer"): (snapshot.url, snapshot.ref, original),
        ("project", "pi", "reviewer"): (snapshot.url, snapshot.ref, corrected),
    }
    project = tmp_path / "project"
    project.mkdir()
    slug = prepare_entry("command", "reviewer", intents=intents, snapshot=refreshed,
        targets=("standard", "pi"), scope="project", home=sandbox, project=project)
    assert slug == "reviewer"
    assert (sandbox / ".agent-toolkit/commands/reviewer/COMMAND.md").read_text() == "Summarize the supplied input"
    assert not (project / "commands-lock.json").exists()
