"""`agent-toolkit-cli mcp <verb>` — manage MCP servers across four harnesses
via config-injection adapters + mcps-lock.json. Mirrors commands/agent/.

Read verbs (list/status/doctor) pass read_only=True → default to global outside
a project. Write verbs (install/uninstall/remove) default to project when a
project lock is present. `add` authors a library entry from flags (global-only);
`update` advances the float. Supported harnesses: claude-code, codex, opencode, pi.
"""
from __future__ import annotations

import click

from agent_toolkit_cli.commands.mcp.add_cmd import add_cmd
from agent_toolkit_cli.commands.mcp.doctor_cmd import doctor_cmd
from agent_toolkit_cli.commands.mcp.install_cmd import install_cmd
from agent_toolkit_cli.commands.mcp.list_cmd import list_cmd
from agent_toolkit_cli.commands.mcp.remove_cmd import remove_cmd
from agent_toolkit_cli.commands.mcp.status_cmd import status_cmd
from agent_toolkit_cli.commands.mcp.uninstall_cmd import uninstall_cmd
from agent_toolkit_cli.commands.mcp.update_cmd import update_cmd


@click.group(name="mcp")
def mcp() -> None:
    """Manage MCP servers via config-injection adapters + mcps-lock.json."""


mcp.add_command(list_cmd)
mcp.add_command(list_cmd, name="ls")
mcp.add_command(status_cmd)
mcp.add_command(add_cmd)
mcp.add_command(install_cmd)
mcp.add_command(uninstall_cmd)
mcp.add_command(remove_cmd)
mcp.add_command(update_cmd)
mcp.add_command(doctor_cmd)
