from agent_toolkit_cli import pi_extension_paths as pep


def test_library_and_lock(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert pep.library_root(env={}) == tmp_path / ".agent-toolkit" / "pi-extensions"
    assert pep.library_pi_extension_path("e", env={}) == (
        tmp_path / ".agent-toolkit" / "pi-extensions" / "e"
    )
    assert pep.library_lock_path(env={}) == (
        tmp_path / ".agent-toolkit" / "pi-extensions-lock.json"
    )


def test_lock_file_path_scopes(tmp_path):
    proj = tmp_path / "proj"
    assert pep.lock_file_path(scope="project", project=proj) == (
        proj / "pi-extensions-lock.json"
    )


def test_pi_extension_dir_global(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert pep.pi_extension_dir("e", scope="global", home=tmp_path) == (
        tmp_path / ".pi" / "agent" / "extensions" / "e"
    )


def test_pi_extension_dir_project(tmp_path):
    proj = tmp_path / "proj"
    assert pep.pi_extension_dir("e", scope="project", project=proj) == (
        proj / ".pi" / "extensions" / "e"
    )
