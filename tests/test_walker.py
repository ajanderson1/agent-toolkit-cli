from pathlib import Path

from agent_toolkit.walker import discover_assets, extract_frontmatter


def test_extracts_yaml_frontmatter_from_markdown(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text(
        "---\n"
        "name: example\n"
        "description: Example.\n"
        "---\n"
        "\n"
        "# Body\n"
    )
    fm = extract_frontmatter(f)
    assert fm == {"name": "example", "description": "Example."}


def test_returns_none_when_no_frontmatter(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text("# Just a body, no frontmatter\n")
    assert extract_frontmatter(f) is None


def test_handles_crlf_line_endings(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_bytes(b"---\r\nname: example\r\ndescription: Example.\r\n---\r\n\r\n# Body\r\n")
    fm = extract_frontmatter(f)
    assert fm == {"name": "example", "description": "Example."}


def test_discover_skills(tmp_path):
    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\n")
    (tmp_path / "skills" / "beta").mkdir()
    (tmp_path / "skills" / "beta" / "SKILL.md").write_text("---\nname: beta\n---\n")

    assets = list(discover_assets(tmp_path))
    paths = sorted(a.path.name for a in assets)
    kinds = sorted({a.kind for a in assets})
    assert paths == ["SKILL.md", "SKILL.md"]
    assert kinds == ["skill"]


def test_discover_handles_nested_first_party_dir(tmp_path):
    (tmp_path / "skills" / "first_party" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "first_party" / "alpha" / "SKILL.md").write_text("---\nname: alpha\n---\n")

    assets = list(discover_assets(tmp_path))
    assert len(assets) == 1
    assert assets[0].kind == "skill"
    assert assets[0].slug == "alpha"


def test_discover_handles_archived_dir(tmp_path):
    (tmp_path / "skills" / "first_party" / ".archived" / "old").mkdir(parents=True)
    (tmp_path / "skills" / "first_party" / ".archived" / "old" / "SKILL.md").write_text("---\nname: old\n---\n")

    assets = list(discover_assets(tmp_path))
    # .archived assets ARE discovered (they're real assets with lifecycle: deprecated)
    assert len(assets) == 1
    assert assets[0].slug == "old"


def test_discover_mcps_via_mcp_json(tmp_path):
    (tmp_path / "mcps" / "first_party" / "demo").mkdir(parents=True)
    (tmp_path / "mcps" / "first_party" / "demo" / "mcp.json").write_text("{}")

    assets = list(discover_assets(tmp_path))
    assert len(assets) == 1
    assert assets[0].kind == "mcp"
    assert assets[0].slug == "demo"


def test_discover_hooks_via_meta_yaml(tmp_path):
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "confirm-rm.sh").write_text("#!/usr/bin/env bash\n")
    (tmp_path / "hooks" / "confirm-rm.meta.yaml").write_text("name: confirm-rm\n")

    assets = list(discover_assets(tmp_path))
    hook_assets = [a for a in assets if a.kind == "hook"]
    assert len(hook_assets) == 1
    assert hook_assets[0].slug == "confirm-rm"
    assert hook_assets[0].path.name == "confirm-rm.meta.yaml"


def test_discover_walks_deterministically_sorted(tmp_path):
    for name in ["zeta", "alpha", "mu"]:
        (tmp_path / "skills" / name).mkdir(parents=True)
        (tmp_path / "skills" / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")

    assets = list(discover_assets(tmp_path))
    slugs = [a.slug for a in assets]
    assert slugs == ["alpha", "mu", "zeta"]


def test_returns_none_when_frontmatter_is_unparseable_yaml(tmp_path):
    f = tmp_path / "SKILL.md"
    f.write_text(
        "---\n"
        'description: "quoted" — unquoted scalar after\n'
        "---\n\n# Body\n"
    )
    assert extract_frontmatter(f) is None


def test_discover_skips_doc_files_under_commands(tmp_path):
    (tmp_path / "commands" / "first_party").mkdir(parents=True)
    (tmp_path / "commands" / "first_party" / "actual.md").write_text(
        "---\nname: actual\n---\n"
    )
    (tmp_path / "commands" / "README.md").write_text("# Commands docs\n")
    (tmp_path / "commands" / "first_party" / "CLAUDE.md").write_text("# instructions\n")
    (tmp_path / "commands" / "AGENTS.md").write_text("# instructions\n")

    assets = list(discover_assets(tmp_path))
    slugs = sorted(a.slug for a in assets)
    assert slugs == ["actual"]


def test_discover_skips_assets_inside_submodules(tmp_path):
    (tmp_path / ".gitmodules").write_text(
        '[submodule "skills/vendored"]\n'
        '\tpath = skills/vendored\n'
        '\turl = https://example.com/upstream.git\n'
    )
    (tmp_path / "skills" / "vendored").mkdir(parents=True)
    (tmp_path / "skills" / "vendored" / "SKILL.md").write_text(
        "---\nname: vendored\n---\nupstream content\n"
    )
    (tmp_path / "skills" / "ours").mkdir()
    (tmp_path / "skills" / "ours" / "SKILL.md").write_text(
        "---\nname: ours\n---\nour content\n"
    )

    assets = list(discover_assets(tmp_path))
    slugs = sorted(a.slug for a in assets)
    assert slugs == ["ours"], f"submodule contents should be excluded; got {slugs!r}"
