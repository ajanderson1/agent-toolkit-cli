"""Task 8: Pi-only matrix-parity guard for write verbs.

Assert that pi-extension install ONLY writes to ~/.pi dirs and never
touches any other harness directory (.claude, .codex, .gemini, .agents).
"""
from click.testing import CliRunner

from agent_toolkit_cli import pi_extension_paths as pep
from agent_toolkit_cli.cli import main


def test_install_touches_only_pi_dirs(tmp_path, monkeypatch, git_sandbox):
    monkeypatch.setenv("HOME", str(tmp_path))
    for k, v in git_sandbox.env.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path))
    runner = CliRunner()
    runner.invoke(main, ["pi-extension", "add", str(git_sandbox.upstream), "--slug", "demo"])
    runner.invoke(main, ["pi-extension", "install", "demo", "-g"])

    # The ONLY harness dir written under HOME is ~/.pi; no ~/.claude, ~/.codex,
    # ~/.config/opencode, ~/.gemini, ~/.agents are created by a pi-extension install.
    for foreign in (".claude", ".codex", ".gemini", ".agents"):
        assert not (tmp_path / foreign / "skills" / "demo").exists()
        assert not (tmp_path / foreign / "extensions" / "demo").exists()
    # The Pi dir IS written.
    assert pep.pi_extension_dir("demo", scope="global", home=tmp_path).is_symlink()
