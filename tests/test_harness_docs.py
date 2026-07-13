"""Guard the generated Paperclip harness page against dishonest capability copy.

Paperclip is a company-scoped, Skills-only main harness (issue #474). The
generator must render its real company-library projection path and must never
reintroduce the catalog sentinel dir, the non-actionable global path, or
vercel-labs attribution for this custom entry. It must also not imply support
for asset types Paperclip does not integrate.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PAGE = REPO_ROOT / "docs/harnesses/paperclip.md"
MATRIX = REPO_ROOT / "docs/matrix.md"


def _gen_module():
    name = "gen_harness_docs"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(
        name, REPO_ROOT / "scripts/gen_harness_docs.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec so dataclass field resolution can find the module.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_paperclip_is_a_headline_harness():
    gen = _gen_module()
    assert "paperclip" in gen.MAIN
    assert gen.LOGOS.get("paperclip")


def test_paperclip_skills_section_is_honest():
    gen = _gen_module()
    section = gen.skills_section("paperclip")
    assert "<instance-root>/skills/<company-id>" in section
    assert "company-scoped" in section
    # Never the catalog sentinel, the non-actionable global path, or vercel-labs.
    assert ".paperclip-company/skills" not in section
    assert "~/.paperclip/skills" not in section
    assert "vercel-labs/skills" not in section


def test_generated_paperclip_page_has_no_dishonest_paths():
    assert PAGE.exists(), "run scripts/gen_harness_docs.py"
    text = PAGE.read_text()
    assert "<instance-root>/skills/<company-id>" in text
    assert "unavailable — Paperclip skills are company-scoped" in text
    for forbidden in (
        ".paperclip-company/skills",
        "~/.paperclip/skills",
        "vercel-labs/skills",
    ):
        assert forbidden not in text, f"forbidden string in page: {forbidden!r}"


def test_generated_page_marks_unsupported_asset_types():
    text = PAGE.read_text()
    # Instructions, Agents, and Commands are not integrated → no actionable tick.
    assert "| [Instructions](../asset-types/instructions.md) | N/A |" in text
    assert "| [Agents (subagents)](../asset-types/agents.md) | N/A |" in text
    assert "| [Commands](../asset-types/commands.md) | N/A |" in text


def test_matrix_lists_paperclip_with_only_skills_supported():
    text = MATRIX.read_text()
    assert "[Paperclip](harnesses/paperclip.md)" in text
    row = next(
        line for line in text.splitlines()
        if "harnesses/paperclip.md)" in line and line.startswith("<tr")
    )
    # Skills is the only supported (✅) asset type for Paperclip.
    assert "harnesses/paperclip.md#skills" in row
    assert "#instructions" not in row
    assert "#agents" not in row
