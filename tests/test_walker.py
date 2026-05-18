"""Tests for src/agent_toolkit_cli/walker.py — discovery and metadata loading."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit_cli.walker import discover_assets, extract_frontmatter, load_asset_record


def _write_mcp(toolkit_root: Path, slug: str, *, harnesses: list[str]) -> None:
    mcp_dir = toolkit_root / "mcps" / slug
    mcp_dir.mkdir(parents=True, exist_ok=True)
    (mcp_dir / "config.json").write_text(
        '{"type": "stdio", "command": "npx", "args": ["-y", "fake"]}\n'
    )
    harness_lines = "\n".join(f"    - {h}" for h in harnesses)
    (mcp_dir / "README.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        f"  name: {slug}\n"
        f"  description: {slug} mcp.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: third-party\n"
        "  vendored_via: none\n"
        "  upstream: https://example.com\n"
        "  harnesses:\n"
        f"{harness_lines}\n"
        "---\n\n"
        f"# {slug}\n\n"
        f"Body for {slug}.\n"
    )


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


def test_discover_mcps_via_config_json(tmp_path):
    (tmp_path / "mcps" / "first_party" / "demo").mkdir(parents=True)
    (tmp_path / "mcps" / "first_party" / "demo" / "config.json").write_text("{}")

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


def test_discover_hooks_via_subdir_meta_yaml(tmp_path):
    """Hook assets in subdirectory layout (hooks/<slug>/.meta.yaml)
    must be discovered with slug = parent dir name.

    The flat layout (hooks/<slug>.meta.yaml) is also supported (see
    sibling test). Both layouts coexist because the dispatcher uses
    the subdirectory layout (script files live alongside the meta).
    """
    hook_dir = tmp_path / "hooks" / "subdir-demo"
    hook_dir.mkdir(parents=True)
    (hook_dir / ".meta.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: subdir-demo\n"
        "  description: Demo subdirectory hook.\n"
        "  kind: hook\n"
        "  lifecycle: experimental\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses: [codex]\n"
        "  hook:\n"
        "    events: [PreToolUse]\n"
        "    command: check.sh\n",
        encoding="utf-8",
    )
    (hook_dir / "check.sh").write_text("#!/usr/bin/env bash\nexit 0\n")

    assets = list(discover_assets(tmp_path))
    hook_assets = [a for a in assets if a.kind == "hook"]
    assert len(hook_assets) == 1
    assert hook_assets[0].slug == "subdir-demo"


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


def test_load_asset_record_returns_metadata_and_body_excerpt(tmp_path):
    from agent_toolkit_cli.walker import discover_assets, load_asset_record

    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: Alpha skill.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses:\n"
        "    - claude\n"
        "---\n"
        "\n"
        "# alpha\n"
        "\n"
        "First paragraph of body content.\n"
        "\n"
        "Second paragraph that should not be in the excerpt.\n"
    )
    asset = discover_assets(tmp_path)[0]
    record = load_asset_record(asset)
    assert record.metadata["metadata"]["name"] == "alpha"
    assert record.metadata["spec"]["harnesses"] == ["claude"]
    assert record.body_excerpt == "First paragraph of body content."


def test_load_asset_record_does_not_eat_paragraphs_starting_with_hash(tmp_path):
    """A line starting with '#1' (no space after) is body, not a heading."""
    from agent_toolkit_cli.walker import discover_assets, load_asset_record

    (tmp_path / "skills" / "alpha").mkdir(parents=True)
    (tmp_path / "skills" / "alpha" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: alpha\n"
        "  description: X.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses:\n"
        "    - claude\n"
        "---\n"
        "\n"
        "#1 priority is to ship.\n"
        "\n"
        "Second paragraph.\n"
    )
    asset = discover_assets(tmp_path)[0]
    record = load_asset_record(asset)
    assert record.body_excerpt == "#1 priority is to ship."


def test_load_asset_record_skips_atx_headings_correctly(tmp_path):
    """Multiple ATX heading lines (with required space) are correctly skipped."""
    from agent_toolkit_cli.walker import discover_assets, load_asset_record

    (tmp_path / "skills" / "beta").mkdir(parents=True)
    (tmp_path / "skills" / "beta" / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n"
        "  name: beta\n"
        "  description: X.\n"
        "  lifecycle: stable\n"
        "spec:\n"
        "  origin: first-party\n"
        "  vendored_via: none\n"
        "  harnesses:\n"
        "    - claude\n"
        "---\n"
        "\n"
        "# Top heading\n"
        "## Sub heading\n"
        "\n"
        "Real paragraph.\n"
    )
    asset = discover_assets(tmp_path)[0]
    record = load_asset_record(asset)
    assert record.body_excerpt == "Real paragraph."


def test_discover_mcp_uses_config_json(tmp_path):
    _write_mcp(tmp_path, "context7", harnesses=["claude", "codex"])
    assets = discover_assets(tmp_path)
    mcps = [a for a in assets if a.kind == "mcp"]
    assert len(mcps) == 1
    assert mcps[0].slug == "context7"
    assert mcps[0].path.name == "config.json"


def test_load_asset_record_mcp_reads_readme_frontmatter(tmp_path):
    _write_mcp(tmp_path, "context7", harnesses=["claude"])
    [asset] = [a for a in discover_assets(tmp_path) if a.kind == "mcp"]
    record = load_asset_record(asset)
    assert record.metadata["metadata"]["name"] == "context7"
    assert record.metadata["spec"]["harnesses"] == ["claude"]


def test_discover_mcp_skips_directory_without_readme(tmp_path):
    """A config.json without sibling README.md is still discovered (no metadata loss)
    but record metadata is empty. This pins the contract: discovery is structural,
    metadata read is best-effort."""
    mcp_dir = tmp_path / "mcps" / "orphan"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text("{}\n")
    [asset] = [a for a in discover_assets(tmp_path) if a.kind == "mcp"]
    record = load_asset_record(asset)
    assert record.metadata == {}
