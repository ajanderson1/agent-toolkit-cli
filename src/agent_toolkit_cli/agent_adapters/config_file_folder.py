"""config_file_folder mechanism: 4 cells, each requires registry mutation.

Per spec addendum:
  - aider-desk: per-slug subdir with `config.json`; subagent.enabled marks spawnable.
  - codex: per-slug `.toml` + [agents.<role>] entry in config.toml; role req description.
  - dexto: per-slug subdir with `<slug>.yml`; global-only (no project convention).
  - firebender: per-slug `.md` + atomic mutation of `firebender.json` agents array.

Per Task 8 fail-loud lessons: scope ∈ {"global","project"} validated up-front;
home/project required where scope demands it.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import textwrap
from pathlib import Path

from agent_toolkit_cli.agent_adapters import _guard_foreign, _sentinel_path
from agent_toolkit_cli.skill_agents import UnknownAgentError


_VALID_SCOPES = frozenset({"global", "project"})


def _atomic_write(path: Path, content: str) -> None:
    """Write file atomically via tmp + rename. Survives concurrent watchers."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)


def _check_scope(scope: str, harness: str) -> None:
    if scope not in _VALID_SCOPES:
        raise ValueError(
            f"{harness}: scope must be 'global' or 'project', got {scope!r}"
        )


def _resolve_base(
    harness: str,
    scope: str,
    home: Path | None,
    project: Path | None,
    dirname: str,
) -> Path:
    if scope == "global":
        if home is None:
            raise ValueError(f"{harness}: scope='global' requires home= argument")
        return home / dirname
    if project is None:
        raise ValueError(f"{harness}: scope='project' requires project= argument")
    return project / dirname


# ── aider-desk ───────────────────────────────────────────────────────────

class _AiderDeskAdapter:
    def destination(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
    ) -> Path:
        _check_scope(scope, "aider-desk")
        base = _resolve_base("aider-desk", scope, home, project, ".aider-desk")
        return base / "agents" / slug / "config.json"

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        _check_scope(scope, "aider-desk")
        base = _resolve_base("aider-desk", scope, home, project, ".aider-desk")
        subdir = base / "agents" / slug
        cfg = subdir / "config.json"
        _guard_foreign(cfg, harness="aider-desk", overwrite=overwrite)
        subdir.mkdir(parents=True, exist_ok=True)
        text = content_path.read_text()
        body = {
            "name": slug,
            "subagent": {"enabled": True},
            "source": text,
        }
        cfg.write_text(json.dumps(body, indent=2) + "\n")
        # Write the .attk sentinel so _guard_foreign recognises this as our
        # own file on future re-installs (without requiring the lock system).
        _sentinel_path(cfg).write_text("")
        return cfg

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        # canonical_content accepted for Protocol uniformity (#368); cff
        # removal semantics unchanged.
        _check_scope(scope, "aider-desk")
        base = _resolve_base("aider-desk", scope, home, project, ".aider-desk")
        subdir = base / "agents" / slug
        if subdir.exists():
            shutil.rmtree(subdir)
        return None


# ── dexto ────────────────────────────────────────────────────────────────

class _DextoAdapter:
    def destination(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
    ) -> Path:
        _check_scope(scope, "dexto")
        if scope != "global":
            raise ValueError("dexto: no project-scope convention exists; global-only writes")
        if home is None:
            raise ValueError("dexto: scope='global' requires home= argument")
        return home / ".dexto" / "agents" / slug / f"{slug}.yml"

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        _check_scope(scope, "dexto")
        if scope != "global":
            raise ValueError("dexto: no project-scope convention exists; global-only writes")
        if home is None:
            raise ValueError("dexto: scope='global' requires home= argument")
        base = home / ".dexto"
        subdir = base / "agents" / slug
        yml = subdir / f"{slug}.yml"
        _guard_foreign(yml, harness="dexto", overwrite=overwrite)
        subdir.mkdir(parents=True, exist_ok=True)
        # YAML block-scalar (`|`) requires EVERY line of the block to be
        # indented by at least the declared amount — textwrap.indent applies
        # the prefix to every line, not just the first. Single-line content
        # would also work with naive interpolation, but real agent files are
        # multi-line.
        source_block = textwrap.indent(content_path.read_text().strip(), "  ")
        yml.write_text(
            f"name: {slug}\n"
            f"description: imported by agent-toolkit-cli\n"
            f"source: |\n{source_block}\n"
        )
        # Write the .attk sentinel so _guard_foreign recognises this as our
        # own file on future re-installs (without requiring the lock system).
        _sentinel_path(yml).write_text("")
        return yml

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        # canonical_content accepted for Protocol uniformity (#368); cff
        # removal semantics unchanged.
        _check_scope(scope, "dexto")
        if scope != "global":
            return None  # project-scope is a no-op (was a raise on install)
        if home is None:
            return None  # nothing to clean up if we don't know where to look
        subdir = home / ".dexto" / "agents" / slug
        if subdir.exists():
            shutil.rmtree(subdir)
        return None


# ── firebender ───────────────────────────────────────────────────────────

class _FirebenderAdapter:
    def destination(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
    ) -> Path:
        _check_scope(scope, "firebender")
        base = _resolve_base("firebender", scope, home, project, ".firebender")
        return base / "agents" / f"{slug}.md"

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        _check_scope(scope, "firebender")
        base = _resolve_base("firebender", scope, home, project, ".firebender")
        md = base / "agents" / f"{slug}.md"
        # Guard only our per-slug .md — firebender.json is a shared registry
        # we intentionally append-merge (see below), never clobber.
        _guard_foreign(md, harness="firebender", overwrite=overwrite)
        md.parent.mkdir(parents=True, exist_ok=True)
        # Inject callable: true into frontmatter. Spec requires this be true
        # for the agent to be spawnable, so an existing `callable: false` is
        # replaced (NOT preserved) — install always means "make it callable".
        text = content_path.read_text()
        if text.startswith("---\n"):
            head, _, rest = text[4:].partition("\n---\n")
            # Strip any existing callable: <anything> line, then append true.
            head_lines = [ln for ln in head.split("\n") if not ln.strip().startswith("callable:")]
            head = "\n".join(head_lines) + "\ncallable: true"
            text = "---\n" + head + "\n---\n" + rest
        else:
            text = "---\ncallable: true\n---\n" + text
        md.write_text(text)
        _sentinel_path(md).write_text("")
        # Mutate firebender.json atomically.
        fb_json = base / "firebender.json"
        if fb_json.exists():
            body = json.loads(fb_json.read_text())
        else:
            body = {"agents": []}
        # Always store the path relative to `base` — absolute paths in
        # firebender.json would break checkin and project relocation. base
        # is the .firebender root for both scopes, so the registry entry
        # always reads like "agents/<slug>.md".
        rel = str(md.relative_to(base))
        if rel not in body.get("agents", []):
            body.setdefault("agents", []).append(rel)
        _atomic_write(fb_json, json.dumps(body, indent=2) + "\n")
        return md

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        # canonical_content accepted for Protocol uniformity (#368); cff
        # removal semantics unchanged.
        _check_scope(scope, "firebender")
        try:
            base = _resolve_base("firebender", scope, home, project, ".firebender")
        except ValueError:
            return None  # nothing to clean up if args are missing
        md = base / "agents" / f"{slug}.md"
        if md.exists():
            md.unlink()
        # Unconditional: clean the sidecar even when the .md was already
        # deleted out-of-band (orphan-sidecar hygiene, as in codex below).
        _sentinel_path(md).unlink(missing_ok=True)
        fb_json = base / "firebender.json"
        if fb_json.exists():
            body = json.loads(fb_json.read_text())
            if "agents" in body:
                body["agents"] = [p for p in body["agents"] if f"{slug}.md" not in p]
            _atomic_write(fb_json, json.dumps(body, indent=2) + "\n")
        return None


# ── codex ────────────────────────────────────────────────────────────────

class _CodexAdapter:
    """Codex agent adapter.

    Writes ~/.codex/agents/<slug>.toml (global) or .codex/agents/<slug>.toml
    (project) and mutates config.toml to add an [agents.<role>] section that
    points at the TOML file via config_file=. The role declaration requires
    a description field; the agent file requires developer_instructions.

    Per matrix: developers.openai.com/codex/subagents + codex-rs/config/src/config_toml.rs:649-691
    """

    def destination(
        self, slug: str, *, scope: str,
        home: Path | None = None, project: Path | None = None,
    ) -> Path:
        _check_scope(scope, "codex")
        base = _resolve_base("codex", scope, home, project, ".codex")
        return base / "agents" / f"{slug}.toml"

    def install(
        self,
        slug: str,
        content_path: Path,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        overwrite: bool = False,
    ) -> Path:
        _check_scope(scope, "codex")
        base = _resolve_base("codex", scope, home, project, ".codex")
        agents_dir = base / "agents"
        toml_path = agents_dir / f"{slug}.toml"
        # Guard only our per-slug .toml — config.toml is a shared registry
        # we mutate by section, never clobber.
        _guard_foreign(toml_path, harness="codex", overwrite=overwrite)
        agents_dir.mkdir(parents=True, exist_ok=True)
        # Produce a minimal TOML with developer_instructions from content.
        source_text = content_path.read_text()
        # Escape any triple-quoted strings by using single-quoted TOML multiline.
        escaped = source_text.replace("'''", "''\\''")
        toml_path.write_text(
            f"developer_instructions = '''\n{escaped}\n'''\n"
        )
        _sentinel_path(toml_path).write_text("")
        # Mutate config.toml: add/update [agents.<slug>] section.
        config_toml = base / "config.toml"
        if config_toml.exists():
            existing = config_toml.read_text()
        else:
            existing = ""
        section_header = f"[agents.{slug}]"
        role_block = (
            f"\n{section_header}\n"
            f'description = "imported by agent-toolkit-cli"\n'
            f'config_file = "agents/{slug}.toml"\n'
        )
        if section_header in existing:
            # Replace the existing [agents.<slug>] block.
            existing = re.sub(
                rf"\[agents\.{re.escape(slug)}\][^\[]*",
                role_block.lstrip("\n"),
                existing,
                flags=re.DOTALL,
            )
            _atomic_write(config_toml, existing)
        else:
            _atomic_write(config_toml, existing.rstrip("\n") + role_block)
        return toml_path

    def uninstall(
        self,
        slug: str,
        *,
        scope: str,
        home: Path | None = None,
        project: Path | None = None,
        canonical_content: Path | None = None,
    ) -> Path | None:
        # canonical_content accepted for Protocol uniformity (#368); cff
        # removal semantics unchanged.
        _check_scope(scope, "codex")
        try:
            base = _resolve_base("codex", scope, home, project, ".codex")
        except ValueError:
            return None
        toml_path = base / "agents" / f"{slug}.toml"
        if toml_path.exists():
            toml_path.unlink()
        # Unconditional: clean the sidecar even when the .toml was already
        # deleted out-of-band — an orphan sidecar would later authorize a
        # silent clobber via _guard_foreign (#361 hazard, #368 review F3).
        _sentinel_path(toml_path).unlink(missing_ok=True)
        config_toml = base / "config.toml"
        if config_toml.exists():
            existing = config_toml.read_text()
            cleaned = re.sub(
                rf"\[agents\.{re.escape(slug)}\][^\[]*",
                "",
                existing,
                flags=re.DOTALL,
            )
            _atomic_write(config_toml, cleaned)
        return None


_ADAPTERS: dict[str, type] = {
    "aider-desk": _AiderDeskAdapter,
    "codex": _CodexAdapter,
    "dexto": _DextoAdapter,
    "firebender": _FirebenderAdapter,
}


def adapter_for(harness: str):
    """Return the config_file_folder-mechanism adapter for `harness`.

    Returns an `AgentAdapter`-shaped object (Protocol; see
    `agent_adapters/__init__.py`). The concrete classes are intentionally
    private — callers should rely only on the Protocol surface so a 5th
    cell can land without touching every call site.
    """
    cls = _ADAPTERS.get(harness)
    if cls is None:
        raise UnknownAgentError(harness)
    return cls()
