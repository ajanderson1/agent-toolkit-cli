"""Validate asset frontmatter against the v1alpha1 JSON schema + cross-asset rules."""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

from agent_toolkit.walker import Asset, extract_frontmatter


class Validator:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        schema_path = repo_root / "schemas" / "asset-frontmatter.v1alpha1.json"
        self.schema = json.loads(schema_path.read_text())

    def validate(self, asset: Asset) -> list[str]:
        data = self._load_metadata(asset)
        errors: list[str] = []
        if data is None:
            return [f"{asset.path}: no frontmatter / metadata block found"]
        try:
            jsonschema.validate(data, self.schema)
        except jsonschema.ValidationError as e:
            errors.append(f"{asset.path}: schema: {e.message}")
        # Cross-asset rule: metadata.name must equal asset.slug
        name = (data.get("metadata") or {}).get("name")
        if name and name != asset.slug:
            errors.append(
                f"{asset.path}: slug mismatch — metadata.name={name!r} but path slug is {asset.slug!r}"
            )
        return errors

    def _load_metadata(self, asset: Asset) -> dict | None:
        if asset.kind in {"skill", "agent", "command"}:
            return extract_frontmatter(asset.path)
        if asset.kind == "hook":
            return yaml.safe_load(asset.path.read_text())
        if asset.kind in {"mcp", "plugin"}:
            doc = json.loads(asset.path.read_text())
            return doc.get("agent_toolkit")
        return None
