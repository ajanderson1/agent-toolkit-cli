"""Capture SVG screenshots and visual judgment evidence for issue #491."""

import asyncio
from pathlib import Path
from agent_toolkit_tui.app import TUIApp

OUT_DIR = Path(__file__).parent


async def capture() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Main harnesses command palette
    app1 = TUIApp()
    async with app1.run_test() as pilot:
        app1.action_main_harnesses()
        await pilot.pause()
        app1.save_screenshot(str(OUT_DIR / "01_main_harnesses_palette.svg"))

    # 2. Theme command palette
    app2 = TUIApp()
    async with app2.run_test() as pilot:
        app2.search_themes()
        await pilot.pause()
        app2.save_screenshot(str(OUT_DIR / "02_theme_palette.svg"))

    # 3. Long-tail harness toggle (aider-desk) on Skills grid
    app3 = TUIApp()
    async with app3.run_test() as pilot:
        app3.toggle_main_harness("aider-desk")
        await pilot.pause()
        app3.save_screenshot(str(OUT_DIR / "03_long_tail_toggled_skills.svg"))

    # 4. Long-tail harness toggle on Commands grid
    app4 = TUIApp()
    async with app4.run_test() as pilot:
        app4.action_asset_type("command")
        await pilot.pause()
        app4.toggle_main_harness("aider-desk")
        await pilot.pause()
        app4.save_screenshot(str(OUT_DIR / "04_long_tail_toggled_commands.svg"))

    # 5. Pending edit protection confirmation modal
    app5 = TUIApp()
    async with app5.run_test() as pilot:
        grid = app5.query_one("#skill-grid")
        grid.restore_pending({("project", "test-skill"): "link"})
        app5.toggle_main_harness("aider-desk")
        await pilot.pause()
        app5.save_screenshot(str(OUT_DIR / "05_pending_discard_confirmation.svg"))

    print("SVG evidence captured successfully.")


if __name__ == "__main__":
    asyncio.run(capture())
