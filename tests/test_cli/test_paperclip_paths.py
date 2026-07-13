"""Pure Paperclip company-context detection and normalization contract."""
from __future__ import annotations

from pathlib import Path

import pytest

from agent_toolkit_cli.paperclip_paths import (
    PaperclipContextError,
    detect_paperclip_company,
    normalize_skill_project_root,
    require_paperclip_company,
)


def _company(tmp_path: Path, instance: str = "default", company: str = "company-123"):
    root = tmp_path / ".paperclip"
    company_root = root / "instances" / instance / "companies" / company
    company_root.mkdir(parents=True)
    return root, company_root


def test_detects_exact_company_and_derives_skill_root(tmp_path):
    root, company = _company(tmp_path)
    ctx = detect_paperclip_company(company, paperclip_root=root)
    assert ctx is not None
    assert ctx.company_root == company.resolve()
    assert ctx.instance_root == (root / "instances/default").resolve()
    assert ctx.instance_name == "default"
    assert ctx.company_id == "company-123"
    assert ctx.skills_root == (root / "instances/default/skills/company-123").resolve()


def test_walks_up_from_company_descendant(tmp_path):
    root, company = _company(tmp_path, "staging", "abc")
    descendant = company / "workspace" / "nested"
    descendant.mkdir(parents=True)
    assert normalize_skill_project_root(descendant, paperclip_root=root) == company.resolve()


@pytest.mark.parametrize("parts", [
    ("instances", "default", "company", "abc"),
    ("instance", "default", "companies", "abc"),
    ("instances", "default", "companies"),
])
def test_rejects_lookalike_layouts(tmp_path, parts):
    root = tmp_path / ".paperclip"
    candidate = root.joinpath(*parts)
    candidate.mkdir(parents=True)
    assert detect_paperclip_company(candidate, paperclip_root=root) is None


def test_require_fails_with_expected_shape(tmp_path):
    project = tmp_path / "ordinary"
    project.mkdir()
    with pytest.raises(PaperclipContextError, match=r"instances/<instance>/companies/<company-id>"):
        require_paperclip_company(project, paperclip_root=tmp_path / ".paperclip")


def test_normalize_returns_input_for_non_paperclip(tmp_path):
    project = tmp_path / "ordinary"
    project.mkdir()
    assert normalize_skill_project_root(
        project, paperclip_root=tmp_path / ".paperclip",
    ) == project
