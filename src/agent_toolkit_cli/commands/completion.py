"""Read-only completion generation and explicit, reversible shell setup."""
from __future__ import annotations

import os
from pathlib import Path
import shlex
import stat
import tempfile

import click
from click.shell_completion import get_completion_class

SHELLS = ("zsh", "bash", "fish")
START = "# >>> agent-toolkit completion >>>"
END = "# <<< agent-toolkit completion <<<"


def completion_source(shell: str) -> str:
    """Generate Click's dynamic completion protocol for all shipped names."""
    from agent_toolkit_cli.cli import main as cli
    from agent_toolkit_tui.launcher import launcher

    completion_class = get_completion_class(shell)
    if completion_class is None:
        raise click.ClickException(f"Unsupported shell: {shell}")
    scripts = []
    for name, command in (("atc", cli), ("agent-toolkit-cli", cli), ("att", launcher), ("agent-toolkit-tui", launcher)):
        complete_var = f"_{name.replace('-', '_').upper()}_COMPLETE"
        scripts.append(completion_class(command, {}, name, complete_var).source())
    return "\n".join(scripts)


def _shell(selected: str | None) -> str:
    shell = selected or Path(os.environ.get("SHELL", "")).name
    if shell not in SHELLS:
        raise click.ClickException("Cannot detect a supported shell. Pass --shell zsh, bash, or fish.")
    return shell


def _rc_path(shell: str) -> Path:
    if shell == "zsh":
        return Path(os.environ.get("ZDOTDIR", str(Path.home()))) / ".zshrc"
    if shell == "bash":
        return Path.home() / ".bashrc"
    return Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "fish/conf.d/agent-toolkit-completion.fish"


def _block(shell: str) -> str:
    if shell == "fish":
        body = "if type -q atc\n    command atc completion init fish | source\nend"
    else:
        prerequisite = ""
        if shell == "zsh":
            prerequisite = "    if ! (( $+functions[compdef] )); then\n        autoload -Uz compinit && compinit\n    fi\n"
        body = f'if command -v atc >/dev/null 2>&1; then\n{prerequisite}    eval "$(command atc completion init {shell})"\nfi'
    return f"{START}\n{body}\n{END}\n"


def _managed_region(text: str) -> tuple[int, int] | None:
    if START not in text and END not in text:
        return None
    if text.count(START) != 1 or text.count(END) != 1:
        raise click.ClickException("Completion markers are incomplete or duplicated; repair them manually before retrying.")
    start = text.index(START)
    end = text.index(END)
    after_start = text[start + len(START):]
    if (end < start or (start and text[start - 1] != "\n")
            or not after_start.startswith(("\n", "\r\n"))
            or (end and text[end - 1] != "\n")):
        raise click.ClickException("Malformed completion markers; refusing to change shell configuration.")
    end += len(END)
    if text[end:end + 2] == "\r\n":
        end += 2
    elif text[end:end + 1] == "\n":
        end += 1
    elif end != len(text):
        raise click.ClickException("Malformed completion end marker; refusing to change shell configuration.")
    return start, end


def _configure(path: Path, shell: str, *, remove: bool) -> bool:
    """Preserve unrelated text, permissions and symlinked dotfile layouts."""
    target = path.expanduser().resolve()
    old = target.read_bytes().decode("utf-8") if target.exists() else ""
    region = _managed_region(old)
    if remove:
        if region is None:
            return False
        new = old[:region[0]] + old[region[1]:]
    else:
        block = _block(shell)
        if region:
            new = old[:region[0]] + block + old[region[1]:]
        else:
            new = old + ("\n" if old and not old.endswith("\n") else "") + block
    if new == old:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(new.encode("utf-8"))
        if target.exists():
            os.chmod(temporary, stat.S_IMODE(target.stat().st_mode))
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return True


@click.group()
def completion() -> None:
    """Set up TAB completion for atc/att and their long command names."""


@completion.command("init")
@click.argument("shell", type=click.Choice(SHELLS))
def init(shell: str) -> None:
    """Print shell integration (read-only); source/eval it in your shell."""
    click.echo(completion_source(shell))


def _configuration_options(function):
    function = click.option("--rc-file", type=click.Path(dir_okay=False, path_type=Path), help="Override the shell configuration path.")(function)
    return click.option("--shell", type=click.Choice(SHELLS), help="Shell to configure (default: $SHELL).")(function)


@completion.command("install")
@_configuration_options
def install(shell: str | None, rc_file: Path | None) -> None:
    """Add/update a marked completion block in your shell configuration."""
    shell = _shell(shell)
    path = rc_file or _rc_path(shell)
    try:
        changed = _configure(path, shell, remove=False)
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Could not configure completion: {exc}") from exc
    click.echo(f"{'Configured' if changed else 'Already configured'} {shell} completion: {path}")
    click.echo(f"Open a new shell, or run: source {shlex.quote(str(path))}")
    if shell == "bash":
        click.echo("For login shells, ensure ~/.bash_profile sources ~/.bashrc.")


@completion.command("uninstall")
@_configuration_options
def uninstall(shell: str | None, rc_file: Path | None) -> None:
    """Remove only Toolkit's marked completion block; preserve other settings."""
    shell = _shell(shell)
    path = rc_file or _rc_path(shell)
    try:
        changed = _configure(path, shell, remove=True)
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Could not remove completion: {exc}") from exc
    click.echo(f"{'Removed completion from' if changed else 'No Toolkit completion block in'} {path}")
    click.echo("Open a new shell to clear completion functions already loaded in this session.")
