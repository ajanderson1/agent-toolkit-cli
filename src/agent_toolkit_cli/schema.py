"""Validate asset frontmatter against the v1alpha2 JSON schema + cross-asset rules."""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import jsonschema
import yaml

from agent_toolkit_cli.walker import Asset, extract_frontmatter, extract_metadata, frontmatter_path


class Validator:
    def __init__(self, toolkit_root: Path):
        self.toolkit_root = toolkit_root
        # Schema is the contract the CLI enforces; it ships with the CLI.
        # The toolkit repo holds the SSOT for humans, but the validator's runtime
        # source of truth is the bundled copy in the agent_toolkit_cli package.
        schema_text = (files("agent_toolkit_cli") / "_schemas" / "asset-frontmatter.v1alpha2.json").read_text()
        self.schema = json.loads(schema_text)

    def validate(self, asset: Asset) -> list[str]:
        data = self._load_metadata(asset)
        errors: list[str] = []
        if data is None:
            return [f"{asset.path}: no frontmatter / metadata block found"]

        # Cross-check declared metadata.kind against walker-derived kind.
        declared_kind = ((data.get("metadata") or {}).get("kind"))
        if declared_kind is not None and declared_kind != asset.kind:
            errors.append(
                f"{asset.path}: metadata.kind={declared_kind!r} but walker derived {asset.kind!r}"
            )
            # Skip JSON-Schema validation for the mismatched-kind case so
            # the conditional spec.mcp rule doesn't fire spuriously.
            return errors

        # Inject walker-derived kind so the JSON-Schema conditional
        # ("spec.mcp required iff metadata.kind == mcp") fires regardless
        # of whether frontmatter declared metadata.kind.
        data_for_schema = dict(data)
        meta_for_schema = dict(data_for_schema.get("metadata") or {})
        meta_for_schema.setdefault("kind", asset.kind)
        data_for_schema["metadata"] = meta_for_schema

        try:
            jsonschema.validate(data_for_schema, self.schema)
        except jsonschema.ValidationError as e:
            errors.append(f"{asset.path}: schema: {e.message}")

        # Cross-asset rule: metadata.name must equal asset.slug
        name = (data.get("metadata") or {}).get("name")
        if name and name != asset.slug:
            errors.append(
                f"{asset.path}: slug mismatch — metadata.name={name!r} but path slug is {asset.slug!r}"
            )

        # Skill-shape rules (new shape only — legacy inline skills are tolerated
        # during the one-release window and surfaced via doctor advisory).
        if asset.kind == "skill":
            errors.extend(self._validate_skill_shape(asset, data))

        return errors

    def _validate_skill_shape(self, asset: Asset, sidecar_data: dict) -> list[str]:
        """Cross-file skill-shape validation.

        - SKILL.md must have top-level name + description.
        - SKILL.md description must end with a period.
        - SKILL.md name must equal asset slug.
        - Sidecar metadata.description period rule is enforced by JSON Schema.

        Legacy inline skills (no sidecar; v1alpha2 wrapper inside SKILL.md) are
        detected by the absence of a sidecar file and return [] — they're tolerated
        during the one-release tolerance window. Doctor surfaces an advisory.
        """
        errors: list[str] = []
        sidecar = self.toolkit_root / "skills" / f"{asset.slug}.toolkit.yaml"
        if not sidecar.is_file():
            # Legacy inline shape — tolerated, doctor handles the advisory.
            return errors

        # New-shape skill: SKILL.md must have its own top-level frontmatter.
        skill_md_fm = extract_frontmatter(asset.path)
        if not skill_md_fm:
            errors.append(
                f"{asset.path}: SKILL.md is missing top-level frontmatter "
                f"(required for sidecar-shape skills)"
            )
            return errors

        name = skill_md_fm.get("name")
        description = skill_md_fm.get("description")

        if not name:
            errors.append(f"{asset.path}: SKILL.md missing top-level `name`")
        elif name != asset.slug:
            errors.append(
                f"{asset.path}: SKILL.md name={name!r} does not match slug {asset.slug!r}"
            )

        if not description:
            errors.append(f"{asset.path}: SKILL.md missing top-level `description`")
        elif not description.endswith("."):
            errors.append(
                f"{asset.path}: SKILL.md description must end with a period "
                f"(got {description!r})"
            )

        sidecar_name = (sidecar_data.get("metadata") or {}).get("name")
        if sidecar_name and name and sidecar_name != name:
            errors.append(
                f"{asset.path}: SKILL.md name={name!r} != sidecar metadata.name={sidecar_name!r}"
            )

        return errors

    def _load_metadata(self, asset: Asset) -> dict | None:
        if asset.kind in {"skill", "agent", "command"}:
            fm_path = frontmatter_path(asset.path, asset.kind)
            return extract_metadata(fm_path)
        if asset.kind in {"hook", "pi-extension"}:
            return yaml.safe_load(asset.path.read_text())
        if asset.kind == "mcp":
            fm_path = frontmatter_path(asset.path, asset.kind)
            if not fm_path.is_file():
                return None
            return extract_metadata(fm_path)
        if asset.kind == "plugin":
            doc = json.loads(asset.path.read_text())
            return doc.get("agent_toolkit_cli")
        return None
