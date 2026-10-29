"""Explicit consent for persistent native Pi npm project blocks."""
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class PiProjectBlocksScreen(ModalScreen[bool]):
    """Review the whole batch before any kind writes; Cancel is the default."""

    DEFAULT_CSS = """
    PiProjectBlocksScreen { align: center middle; }
    PiProjectBlocksScreen > Vertical {
        width: 88; max-width: 95%; height: 90%;
        background: $panel; border: thick $warning; padding: 1 2;
    }
    PiProjectBlocksScreen #block-title { text-style: bold; color: $warning; height: auto; }
    PiProjectBlocksScreen VerticalScroll { height: 1fr; margin: 1 0; }
    PiProjectBlocksScreen #block-review { height: auto; }
    PiProjectBlocksScreen Horizontal { height: auto; align: center middle; }
    PiProjectBlocksScreen Button { margin: 0 1; min-width: 8; }
    PiProjectBlocksScreen #cancel { width: 1fr; }
    PiProjectBlocksScreen #apply-blocks { width: 2fr; }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("ctrl+s", "ignore_apply", show=False, priority=True),
    ]

    def __init__(self, *, packages: tuple[str, ...], project: Path, settings: Path,
                 pending_count: int, asset_types: tuple[str, ...]) -> None:
        super().__init__()
        self._body = Text(
            f"Project: {project}\nSettings: {settings}\n\n"
            "Persistently block ALL extension entrypoints in this project for:\n"
            + "\n".join(f"  • npm:{package}" for package in packages)
            + "\n\nThis writes an explicit project off policy, not removal of a local "
            "selection. Global enablement will not make these extensions available "
            "here while this block remains. Global settings, package files and "
            "bundled skills, prompts and themes are unchanged by these blocks.\n\n"
            "To restore inheritance for a global package, select it in Pi Extensions "
            "→ Project and press R, then Ctrl+S. Reset is not force-on: it follows "
            "global policy. Space on a blocked package instead queues explicit on. "
            "For a separate project installation, R resets its own extension filter.\n\n"
            f"Apply saves ALL {pending_count} pending change(s), across both scopes "
            f"and these asset types: {', '.join(asset_types)}. "
            "Other queued changes retain their own effects.\n"
            "Cancel / Escape keeps all drafts without applying anything. "
            "Ctrl+Z after cancelling discards all drafts."
        )

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Review persistent Pi project blocks", id="block-title")
            with VerticalScroll():
                yield Static(self._body, id="block-review")
            with Horizontal():
                yield Button("Cancel", variant="primary", id="cancel")
                yield Button("Apply all changes", variant="warning", id="apply-blocks")

    def on_mount(self) -> None:
        self.query_one("#cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == "apply-blocks")

    def action_cancel(self) -> None:
        self.dismiss(False)

    def action_ignore_apply(self) -> None:
        """Repeated Save never implies consent."""
