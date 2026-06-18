from agent_toolkit_tui.app import TUIApp


async def test_app_sidebar_includes_commands():
    app = TUIApp()
    async with app.run_test() as pilot:
        option_list = app.query_one("#asset-types-list")
        labels = [str(option.prompt) for option in option_list.options]
        assert "Commands" in labels
