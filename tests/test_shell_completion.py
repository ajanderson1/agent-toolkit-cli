"""Read-only dynamic completion and explicit/reversible shell integration."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

from click.testing import CliRunner
import pytest

from agent_toolkit_cli.cli import main
from agent_toolkit_cli.commands.completion import END, START, _configure
from agent_toolkit_cli import self_update
from agent_toolkit_tui.launcher import launcher


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(self_update, "_api_json", lambda *a: pytest.fail("Completion must not check for updates"))


@pytest.mark.parametrize("shell", ["zsh", "bash", "fish"])
def test_source_registers_all_names_and_is_read_only(shell, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(main, ["completion", "init", shell])
    assert result.exit_code == 0, result.output
    for variable in ("_ATC_COMPLETE", "_ATT_COMPLETE", "_AGENT_TOOLKIT_CLI_COMPLETE", "_AGENT_TOOLKIT_TUI_COMPLETE"):
        assert variable in result.output
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("command,name,prefix,words,cword,expected", [
    (main, "atc", "_ATC", "atc sk", "1", "skills"),
    (main, "agent-toolkit-cli", "_AGENT_TOOLKIT_CLI", "agent-toolkit-cli skills in", "2", "install"),
    (main, "atc", "_ATC", "atc skill in", "2", "install"),
    (main, "atc", "_ATC", "atc update --", "2", "--main"),
    (main, "atc", "_ATC", "atc instructions list --format j", "4", "json"),
    (main, "atc", "_ATC", "atc skills install --scope g", "4", "global"),
    (launcher, "att", "_ATT", "att up", "1", "update"),
    (launcher, "agent-toolkit-tui", "_AGENT_TOOLKIT_TUI", "agent-toolkit-tui update --", "2", "--check"),
])
def test_dynamic_commands_flags_and_choices(command, name, prefix, words, cword, expected, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    result = CliRunner().invoke(command, [], prog_name=name, env={
        f"{prefix}_COMPLETE": "bash_complete", "COMP_WORDS": words, "COMP_CWORD": cword,
    })
    assert result.exit_code == 0, result.output
    assert f"plain,{expected}" in result.output
    assert not list(tmp_path.iterdir())


def test_directory_arguments_use_native_shell_completion():
    result = CliRunner().invoke(main, [], prog_name="atc", env={
        "_ATC_COMPLETE": "bash_complete", "COMP_WORDS": "atc --project /tm", "COMP_CWORD": "2",
    })
    assert result.exit_code == 0
    assert "dir,/tm" in result.output


@pytest.mark.parametrize("name,variable", [("att", "_ATT_COMPLETE"), ("agent-toolkit-tui", "_AGENT_TOOLKIT_TUI_COMPLETE")])
def test_actual_tui_main_completes_without_opening_app(name, variable, monkeypatch):
    from agent_toolkit_tui import app
    monkeypatch.setattr(sys, "argv", [name])
    monkeypatch.setattr(app.TUIApp, "run", lambda self: pytest.fail("Completion opened the TUI"))
    monkeypatch.setenv(variable, "bash_complete")
    monkeypatch.setenv("COMP_WORDS", f"{name} up")
    monkeypatch.setenv("COMP_CWORD", "1")
    with pytest.raises(SystemExit) as exc:
        app.main()
    assert exc.value.code == 0


def test_completion_setup_suppresses_interactive_update_check(monkeypatch):
    monkeypatch.setattr(self_update.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(self_update.sys, "stderr", SimpleNamespace(isatty=lambda: True))
    self_update.cli_startup_notice(("completion", "init", "zsh"))


@pytest.mark.parametrize("shell,relative", [
    ("zsh", ".zshrc"), ("bash", ".bashrc"),
    ("fish", ".config/fish/conf.d/agent-toolkit-completion.fish"),
])
def test_install_is_idempotent_and_uninstall_preserves_other_text(shell, relative, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ZDOTDIR", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    original = "# My existing shell settings\n"
    path.write_text(original)
    path.chmod(0o640)
    runner = CliRunner()
    result = runner.invoke(main, ["completion", "install", "--shell", shell])
    assert result.exit_code == 0, result.output
    assert str(path) in result.output
    first = path.read_text()
    assert first.startswith(original)
    assert first.count(START) == 1
    assert f"atc completion init {shell}" in first
    assert path.stat().st_mode & 0o777 == 0o640
    result = runner.invoke(main, ["completion", "install", "--shell", shell])
    assert "Already configured" in result.output
    assert path.read_text() == first
    # Preserve user additions on either side of the managed region.
    path.write_text(first + "# Another setting\n")
    result = runner.invoke(main, ["completion", "uninstall", "--shell", shell])
    assert result.exit_code == 0, result.output
    assert path.read_text() == original + "# Another setting\n"
    assert "No Toolkit" in runner.invoke(main, ["completion", "uninstall", "--shell", shell]).output


def test_install_detects_shell_and_honors_zdotdir(tmp_path, monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.setenv("ZDOTDIR", str(tmp_path / "zsh"))
    result = CliRunner().invoke(main, ["completion", "install"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "zsh/.zshrc").exists()


def test_custom_rc_and_symlink_are_preserved(tmp_path):
    target = tmp_path / "dotfiles/zshrc"
    target.parent.mkdir()
    target.write_text("# Existing\n")
    link = tmp_path / ".zshrc"
    link.symlink_to(target)
    result = CliRunner().invoke(main, ["completion", "install", "--shell", "zsh", "--rc-file", str(link)])
    assert result.exit_code == 0, result.output
    assert link.is_symlink()
    assert START in target.read_text()


@pytest.mark.parametrize("text", [
    START, END, f"{START}\n{START}\n{END}\n", f"{END}\n{START}\n",
    f"echo {START}\n{END}\n", f"{START} extra\n{END}\n",
    f"{START}\necho {END}\n",
])
def test_malformed_markers_refuse_changes(text, tmp_path):
    path = tmp_path / "rc"
    path.write_text(text)
    result = CliRunner().invoke(main, ["completion", "install", "--shell", "zsh", "--rc-file", str(path)])
    assert result.exit_code != 0
    assert path.read_text() == text


def test_unknown_shell_requires_explicit_choice(monkeypatch):
    monkeypatch.setenv("SHELL", "/bin/unknown")
    result = CliRunner().invoke(main, ["completion", "install"])
    assert result.exit_code == 1
    assert "--shell" in result.output


def test_uninstall_does_not_create_missing_configuration(tmp_path):
    path = tmp_path / "missing/rc"
    result = CliRunner().invoke(main, ["completion", "uninstall", "--shell", "zsh", "--rc-file", str(path)])
    assert result.exit_code == 0
    assert not path.parent.exists()


@pytest.mark.parametrize("shell", ["zsh", "bash", "fish"])
def test_generated_source_and_managed_block_have_valid_shell_syntax(shell, tmp_path):
    binary = shutil.which(shell)
    if not binary:
        pytest.skip(f"{shell} not available")
    result = CliRunner().invoke(main, ["completion", "init", shell])
    assert result.exit_code == 0
    source = tmp_path / f"completion.{shell}"
    source.write_text(result.output)
    _configure(tmp_path / "rc", shell, remove=False)
    for path in (source, tmp_path / "rc"):
        result = subprocess.run([binary, "-n", str(path)], text=True, capture_output=True, timeout=10)
        assert result.returncode == 0, result.stderr


def test_zsh_registration_in_real_shell(tmp_path):
    zsh = shutil.which("zsh")
    if not zsh:
        pytest.skip("zsh not available")
    script = CliRunner().invoke(main, ["completion", "init", "zsh"]).output
    source = tmp_path / "completion.zsh"
    source.write_text(script)
    env = dict(os.environ, HOME=str(tmp_path), ZDOTDIR=str(tmp_path))
    result = subprocess.run([zsh, "-f", "-c", 'autoload -Uz compinit; compinit -D; source "$1"; print -r -- ${_comps[atc]} ${_comps[att]} ${_comps[agent-toolkit-cli]} ${_comps[agent-toolkit-tui]}', "zsh", str(source)], env=env, text=True, capture_output=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().split() == ["_atc_completion", "_att_completion", "_agent_toolkit_cli_completion", "_agent_toolkit_tui_completion"]
