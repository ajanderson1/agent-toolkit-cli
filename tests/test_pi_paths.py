from pathlib import Path

from agent_toolkit_cli._pi_paths import PiPaths


def test_pi_paths_user_scope(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    pp = PiPaths(home=home, project_root=project)

    assert pp.user_extensions_dir == home / ".pi" / "agent" / "extensions"
    assert pp.user_settings_json == home / ".pi" / "agent" / "settings.json"
    assert pp.user_node_modules_dir == home / ".pi" / "agent" / "npm" / "node_modules"


def test_pi_paths_project_scope(tmp_path):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    pp = PiPaths(home=home, project_root=project)

    # Project scope omits the /agent/ infix (see _support.py docstring).
    assert pp.project_extensions_dir == project / ".pi" / "extensions"
    assert pp.project_settings_json == project / ".pi" / "settings.json"
    assert pp.project_node_modules_dir == project / ".pi" / "npm" / "node_modules"
