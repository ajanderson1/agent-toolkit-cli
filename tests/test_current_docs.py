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
