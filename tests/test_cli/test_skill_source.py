from pathlib import Path

import pytest

from agent_toolkit_cli.skill_source import ParsedSource, SourceParseError, parse_source


def test_github_shorthand():
    s = parse_source("ajanderson1/journal")
    assert s == ParsedSource(
        type="github",
        url="https://github.com/ajanderson1/journal",
        owner_repo="ajanderson1/journal",
        ref=None,
        subpath=None,
    )


def test_github_https_with_tree_ref_and_subpath():
    s = parse_source("https://github.com/o/r/tree/main/skills/foo")
    assert s.owner_repo == "o/r"
    assert s.ref == "main"
    assert s.subpath == "skills/foo"


def test_github_ssh_url():
    s = parse_source("git@github.com:o/r.git")
    assert s.type == "github"
    assert s.owner_repo == "o/r"
    assert s.url == "git@github.com:o/r.git"


def test_local_absolute_path(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    s = parse_source(str(skill_dir))
    assert s.type == "local"
    assert s.url == str(skill_dir.resolve())
    assert s.owner_repo is None


def test_local_relative_path(tmp_path: Path, monkeypatch):
    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    s = parse_source("./demo")
    assert s.type == "local"
    assert s.url == str(skill_dir.resolve())


def test_path_traversal_rejected():
    with pytest.raises(SourceParseError, match="path traversal"):
        parse_source("https://github.com/o/r/tree/main/../etc")


def test_unparseable_rejected():
    with pytest.raises(SourceParseError):
        parse_source("not a url and not a path")


def test_file_url_happy_path():
    s = parse_source("file:///tmp/parent-src")
    assert s.type == "git"
    assert s.url == "file:///tmp/parent-src"
    assert s.owner_repo == "local/parent-src"
    assert s.ref is None
    assert s.subpath is None


def test_file_url_with_tree_ref_and_subpath():
    s = parse_source("file:///tmp/parent-src/tree/main/sub/folder")
    assert s.owner_repo == "local/parent-src"
    assert s.ref == "main"
    assert s.subpath == "sub/folder"


def test_file_url_strips_dotgit_suffix():
    s = parse_source("file:///tmp/parent-src.git")
    assert s.url == "file:///tmp/parent-src"
    assert s.owner_repo == "local/parent-src"


def test_file_url_empty_body_rejected():
    with pytest.raises(SourceParseError):
        parse_source("file://")
    with pytest.raises(SourceParseError):
        parse_source("file:///")
