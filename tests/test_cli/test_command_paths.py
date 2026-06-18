from agent_toolkit_cli.command_paths import canonical_command_dir, library_command_path, library_lock_path, library_root, lock_file_path


def test_command_library_paths_use_agent_toolkit_root(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert library_root() == tmp_path / ".agent-toolkit" / "commands"
    assert library_command_path("demo") == tmp_path / ".agent-toolkit" / "commands" / "demo"
    assert library_lock_path() == tmp_path / ".agent-toolkit" / "commands-lock.json"


def test_command_project_paths_use_external_store(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "repo"
    project.mkdir()
    assert lock_file_path(scope="project", project=project) == project / "commands-lock.json"
    assert canonical_command_dir("demo", scope="project", project=project).name == "demo"
    assert ".agent-toolkit" in str(canonical_command_dir("demo", scope="project", project=project))
