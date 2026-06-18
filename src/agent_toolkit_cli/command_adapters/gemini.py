from __future__ import annotations

import warnings
from pathlib import Path

import tomlkit
import yaml

from agent_toolkit_cli._install_core import InstallError
from agent_toolkit_cli.command_adapters.base import ensure_regular_command_file, is_managed_file, remove_managed_file, sidecar_path, write_sidecar


def _split_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            raw = text[4:end]
            body = text[end + len("\n---"):]
            if body.startswith("\n"):
                body = body[1:]
            data = yaml.safe_load(raw) or {}
            return (data if isinstance(data, dict) else {}), body
    return {}, text


def render_gemini_toml(command_text: str) -> str:
    meta, body = _split_frontmatter(command_text)
    body = body.replace("$ARGUMENTS", "{{args}}")
    doc = tomlkit.document()
    description = meta.get("description")
    if description:
        doc["description"] = str(description)
    doc["prompt"] = body
    return tomlkit.dumps(doc)


class GeminiCommandAdapter:
    name = "gemini-cli"

    def destination(self, slug: str, *, scope: str, home: Path | None, project: Path | None) -> Path:
        if scope == "global":
            if home is None:
                raise ValueError("global scope requires home")
            return home / ".gemini" / "commands" / f"{slug}.toml"
        if project is None:
            raise ValueError("project scope requires project")
        return project / ".gemini" / "commands" / f"{slug}.toml"

    def install(self, slug: str, source_file: Path, *, scope: str, home: Path | None, project: Path | None) -> Path:
        ensure_regular_command_file(source_file)
        text = source_file.read_text()
        if "!{" in text or "@{" in text:
            warnings.warn("Gemini command injection token detected (!{ or @{); install preserves content", UserWarning, stacklevel=2)
        rendered = render_gemini_toml(text)
        dest = self.destination(slug, scope=scope, home=home, project=project)
        if dest.is_symlink():
            raise InstallError(f"{dest}: foreign symlink exists")
        if dest.exists() and not is_managed_file(dest, slug=slug, harness=self.name):
            raise InstallError(f"{dest}: unmanaged command exists")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(rendered)
        write_sidecar(dest, slug=slug, harness=self.name, scope=scope, canonical=source_file, content=rendered)
        return dest

    def uninstall(self, slug: str, *, scope: str, home: Path | None, project: Path | None) -> Path | None:
        dest = self.destination(slug, scope=scope, home=home, project=project)
        return remove_managed_file(dest, slug=slug, harness=self.name)
