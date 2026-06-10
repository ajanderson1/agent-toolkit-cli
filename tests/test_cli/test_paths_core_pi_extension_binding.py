from agent_toolkit_cli._paths_core import (
    PI_EXTENSION_BINDING,
    library_lock_path_for_kind,
    library_root_for_kind,
)


def test_binding_fields():
    b = PI_EXTENSION_BINDING
    assert b.kind == "pi-extension"
    assert b.canonical_dirname == "pi-extensions"
    assert b.library_subdir == "pi-extensions"
    assert b.lock_filename == "pi-extensions-lock.json"
    assert b.standard_harness_name == "standard-pi-extension"


def test_library_root(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    root = library_root_for_kind(PI_EXTENSION_BINDING, env={})
    assert root == tmp_path / ".agent-toolkit" / "pi-extensions"


def test_library_lock_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    p = library_lock_path_for_kind(PI_EXTENSION_BINDING, env={})
    assert p == tmp_path / ".agent-toolkit" / "pi-extensions-lock.json"


def test_skills_root_override_does_not_leak(monkeypatch, tmp_path):
    # The AGENT_TOOLKIT_SKILLS_ROOT override is skill-only; pi-extension ignores it.
    monkeypatch.setenv("HOME", str(tmp_path))
    root = library_root_for_kind(
        PI_EXTENSION_BINDING, env={"AGENT_TOOLKIT_SKILLS_ROOT": "/should/be/ignored"}
    )
    assert root == tmp_path / ".agent-toolkit" / "pi-extensions"
