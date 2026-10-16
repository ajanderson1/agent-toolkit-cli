"""Subcommand group that collapses aliased commands in help output."""
from __future__ import annotations

import click
from click.core import _


class AliasedGroup(click.Group):
    """Click Group that collapses subcommand aliases into single rows in help."""

    def format_commands(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        """Format subcommands, collapsing aliases pointing to the same Command object."""
        # 1. Collect visible subcommands and group by Command object identity
        grouped: dict[int, tuple[click.Command, list[str]]] = {}
        for subcommand in self.list_commands(ctx):
            cmd = self.get_command(ctx, subcommand)
            if cmd is None or cmd.hidden:
                continue
            cmd_id = id(cmd)
            if cmd_id not in grouped:
                grouped[cmd_id] = (cmd, [subcommand])
            else:
                grouped[cmd_id][1].append(subcommand)

        if not grouped:
            return

        # 2. Determine canonical name and format labels
        rows_data: list[tuple[str, str, click.Command]] = []
        for cmd, names in grouped.values():
            if cmd.name and cmd.name in names:
                canonical = cmd.name
            else:
                canonical = names[0]
            aliases = sorted(name for name in names if name != canonical)
            if aliases:
                label = f"{canonical}, {', '.join(aliases)}"
            else:
                label = canonical
            rows_data.append((canonical, label, cmd))

        # Sort rows alphabetically by canonical name
        rows_data.sort(key=lambda item: item[0])

        # 3. Calculate column width limit for short help
        max_label_len = max(len(label) for _canon, label, _cmd in rows_data)
        limit = formatter.width - 6 - max_label_len

        # 4. Generate rows
        rows: list[tuple[str, str]] = []
        for _canon, label, cmd in rows_data:
            help_str = cmd.get_short_help_str(limit)
            rows.append((label, help_str))

        if rows:
            with formatter.section(_("Commands")):
                formatter.write_dl(rows)
