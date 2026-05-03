"""Validator must load the schema from its own bundled copy, not from repo_root."""
from __future__ import annotations

from pathlib import Path

from agent_toolkit.schema import Validator


def test_validator_loads_bundled_schema(tmp_path: Path) -> None:
    # tmp_path has NO schemas/ directory — this would fail under the old code
    # which read repo_root/schemas/asset-frontmatter.v1alpha1.json.
    v = Validator(tmp_path)
    assert v.schema["$schema"].startswith("https://json-schema.org/")
    assert "properties" in v.schema
