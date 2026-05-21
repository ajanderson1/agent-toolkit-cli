"""Parser coverage for monorepo input shapes (issue #162)."""
import pytest
from agent_toolkit_cli.skill_source import (
    SourceParseError, parse_source,
)


def test_third_segment_shorthand_is_subpath():
    s = parse_source("vamseeachanta/workspace-hub/mkdocs")
    assert s.type == "github"
    assert s.owner_repo == "vamseeachanta/workspace-hub"
    assert s.subpath == "mkdocs"
    assert s.skill_name is None
    assert s.url == "https://github.com/vamseeachanta/workspace-hub"


def test_third_segment_shorthand_with_nested_subpath():
    s = parse_source("o/r/sub/dir")
    assert s.owner_repo == "o/r"
    assert s.subpath == "sub/dir"


def test_skills_sh_url_translates_to_github_with_skill_name():
    s = parse_source("https://www.skills.sh/vamseeachanta/workspace-hub/mkdocs")
    assert s.type == "github"
    assert s.url == "https://github.com/vamseeachanta/workspace-hub"
    assert s.owner_repo == "vamseeachanta/workspace-hub"
    assert s.skill_name == "mkdocs"
    assert s.subpath is None
    assert s.ref is None


def test_skills_sh_url_bare_host_also_works():
    s = parse_source("https://skills.sh/o/r/skill-name")
    assert s.skill_name == "skill-name"
    assert s.owner_repo == "o/r"


def test_skills_sh_url_missing_skill_segment_rejected():
    with pytest.raises(SourceParseError):
        parse_source("https://www.skills.sh/o/r")


def test_github_tree_ref_subpath_still_works():
    s = parse_source("https://github.com/o/r/tree/main/skills/foo")
    assert s.owner_repo == "o/r"
    assert s.ref == "main"
    assert s.subpath == "skills/foo"
    assert s.skill_name is None


def test_shorthand_third_segment_traversal_rejected():
    with pytest.raises(SourceParseError):
        parse_source("o/r/../bad")


def test_existing_owner_repo_unchanged_shape():
    s = parse_source("o/r")
    assert s.owner_repo == "o/r"
    assert s.subpath is None
    assert s.skill_name is None


def test_skills_sh_url_extra_segment_rejected():
    with pytest.raises(SourceParseError):
        parse_source("https://www.skills.sh/o/r/skill/extra")


def test_skills_sh_url_trailing_slash_still_parses():
    s = parse_source("https://www.skills.sh/o/r/skill/")
    assert s.skill_name == "skill"
    assert s.owner_repo == "o/r"
