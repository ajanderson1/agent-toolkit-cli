"""Guard current reference links and the README's published media."""
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import markdown

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = {"audit", "plans", "specs", "superpowers", "reviews", "solutions", "research"}


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []
        self.ids = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.add(values["id"])
        for name in ("href", "src"):
            if name in values:
                self.targets.append(values[name])


def parsed(path):
    parser = Links()
    parser.feed(markdown.markdown(path.read_text(), extensions=["toc", "attr_list", "tables", "fenced_code", "def_list", "md_in_html"]))
    return parser


def test_current_markdown_relative_links_and_anchors():
    docs = [p for p in (ROOT / "docs").rglob("*.md") if not HISTORICAL.intersection(p.relative_to(ROOT / "docs").parts)]
    pages = [ROOT / "README.md", *docs]
    failures = []
    for page in pages:
        for link in parsed(page).targets:
            parts = urlsplit(link)
            if parts.scheme or parts.netloc or not link:
                continue
            target = (page.parent / unquote(parts.path)).resolve() if parts.path else page
            if not target.exists():
                failures.append(f"{page.relative_to(ROOT)} -> {link}: missing")
            elif parts.fragment and target.suffix == ".md":
                if unquote(parts.fragment) not in parsed(target).ids:
                    failures.append(f"{page.relative_to(ROOT)} -> {link}: missing anchor")
    assert not failures, "\n".join(failures)


def test_documentation_images_are_current_png_and_identical():
    readme_png = ROOT / "assets/agent-toolkit-cli-tui.png"
    site_png = ROOT / "docs/assets/screenshots/tui-overview.png"
    assert readme_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert readme_png.read_bytes() == site_png.read_bytes()
    svg = (ROOT / "assets/agent-toolkit-cli-tui.svg").read_text()
    for forbidden in ("/Users/", str(ROOT), "Bearer "):
        assert forbidden not in svg
    assert "disposable documentation fixture" in unescape(svg).replace("\u00a0", " ")


def test_all_registered_help_is_read_only(tmp_path, monkeypatch):
    from click import Group
    from click.testing import CliRunner
    from agent_toolkit_cli.cli import main

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("AGENT_TOOLKIT_SKILLS_ROOT", str(tmp_path / "skills"))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for name, command in main.commands.items():
        verbs = [None, *command.commands] if isinstance(command, Group) else [None]
        for verb in verbs:
            args = [name, *([verb] if verb else []), "--help"]
            result = runner.invoke(main, args)
            assert result.exit_code == 0, (args, result.output)
    assert not list(tmp_path.iterdir()), "help must not author library/config state"


def test_package_guides_are_discoverable_from_nav_home_and_readme():
    config = (ROOT / "mkdocs.yml").read_text()
    home = (ROOT / "docs/index.md").read_text()
    readme = (ROOT / "README.md").read_text()
    for filename in ("installation.md", "updates.md", "shell-completion.md"):
        assert (ROOT / "docs/agent-toolkit" / filename).is_file()
        assert f"agent-toolkit/{filename}" in config
        assert f"agent-toolkit/{filename}" in home
        assert f"docs/agent-toolkit/{filename}" in readme


def test_package_option_reference_matches_shipped_commands():
    from agent_toolkit_cli.commands.update import update
    from agent_toolkit_cli.commands.completion import completion, SHELLS, _block
    from agent_toolkit_tui.launcher import launcher

    updates = (ROOT / "docs/agent-toolkit/updates.md").read_text()
    complete = (ROOT / "docs/agent-toolkit/shell-completion.md").read_text()
    tui = (ROOT / "docs/agent-toolkit/tui.md").read_text()
    for parameter in update.params:
        for option in parameter.opts:
            assert option in updates
    for name in ("init", "install", "uninstall"):
        assert f"atc completion {name}" in complete
        for parameter in completion.commands[name].params:
            for option in parameter.opts:
                if option.startswith("-"):
                    assert option in complete
    for shell in SHELLS:
        assert f"--shell {shell}" in complete
    assert _block("zsh").strip() in complete
    for parameter in launcher.params:
        for option in parameter.opts:
            assert option in tui


def test_documented_update_defaults_and_storage_match_runtime(tmp_path, monkeypatch):
    from agent_toolkit_cli import self_update

    text = (ROOT / "docs/agent-toolkit/updates.md").read_text()
    assert self_update.CACHE_SECONDS == 6 * 60 * 60 and "**six hours**" in text
    assert self_update.RETRY_SECONDS == 15 * 60 and "**15 minutes**" in text
    assert self_update.STARTUP_TIMEOUT == 1.0 and "**one-second network socket timeout**" in text
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    assert self_update.cache_path() == tmp_path / ".cache/agent-toolkit/update.json"
    assert self_update.state_dir() == tmp_path / ".local/state/agent-toolkit/updates"
    assert "${XDG_CACHE_HOME:-~/.cache}/agent-toolkit/update.json" in text
    assert "${XDG_STATE_HOME:-~/.local/state}/agent-toolkit/updates/" in text


def test_all_generated_compatibility_pages_link_package_guides():
    pages = [ROOT / "docs/matrix.md", *sorted((ROOT / "docs/harnesses").glob("*.md"))]
    for page in pages:
        text = page.read_text()
        assert "**`atc` CLI** / **`att` TUI**" in text, page
        for guide in ("installation.md", "updates.md", "shell-completion.md"):
            assert f"agent-toolkit/{guide}" in text, page


def test_asset_and_current_cli_examples_use_the_packaged_short_name():
    pages = [ROOT / "docs/agent-toolkit/cli.md", *sorted((ROOT / "docs/asset-types").glob("*.md"))]
    for page in pages:
        assert not any(line.startswith("agent-toolkit-cli ") for line in page.read_text().splitlines()), page
