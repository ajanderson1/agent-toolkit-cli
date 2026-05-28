"""Agents catalog — port of vercel-labs/skills/src/agents.ts.

53 real agents + 1 synthetic 'universal' pseudo-agent. An agent is
'universal' iff its skills_dir is exactly '.agents/skills' (all such
agents read skills from a single shared canonical location, so no
per-harness symlink is needed at global scope).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


# Resolve env-overridable home dirs once at import time (matching TS source).
HOME = Path.home()
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME") or (HOME / ".config"))
CODEX_HOME = Path(os.environ.get("CODEX_HOME") or (HOME / ".codex"))
CLAUDE_HOME = Path(os.environ.get("CLAUDE_CONFIG_DIR") or (HOME / ".claude"))
VIBE_HOME = Path(os.environ.get("VIBE_HOME") or (HOME / ".vibe"))


def _openclaw_skills_dir() -> Path:
    """Match TS getOpenClawGlobalSkillsDir(): probe several legacy dirs."""
    for d in (".openclaw", ".clawdbot", ".moltbot"):
        if (HOME / d).exists():
            return HOME / d / "skills"
    return HOME / ".openclaw" / "skills"


@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    skills_dir: str
    global_skills_dir: Path
    detect_installed: Callable[[], bool]
    show_in_universal_list: bool = True

    @property
    def is_universal(self) -> bool:
        return self.skills_dir == ".agents/skills"


# 54 entries — port verbatim from tests/fixtures/vercel-labs-skills-agents.ts.
# Keys match skills.sh exactly (e.g. "claude-code", "gemini-cli", "kimi-cli").
AGENTS: dict[str, AgentConfig] = {
    "aider-desk": AgentConfig(
        name="aider-desk",
        display_name="AiderDesk",
        skills_dir=".aider-desk/skills",
        global_skills_dir=HOME / ".aider-desk/skills",
        detect_installed=lambda: (HOME / ".aider-desk").exists(),
    ),
    "amp": AgentConfig(
        name="amp",
        display_name="Amp",
        skills_dir=".agents/skills",
        global_skills_dir=XDG_CONFIG / "agents/skills",
        detect_installed=lambda: (XDG_CONFIG / "amp").exists(),
    ),
    "antigravity": AgentConfig(
        name="antigravity",
        display_name="Antigravity",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".gemini/antigravity/skills",
        detect_installed=lambda: (HOME / ".gemini/antigravity").exists(),
    ),
    "augment": AgentConfig(
        name="augment",
        display_name="Augment",
        skills_dir=".augment/skills",
        global_skills_dir=HOME / ".augment/skills",
        detect_installed=lambda: (HOME / ".augment").exists(),
    ),
    "bob": AgentConfig(
        name="bob",
        display_name="IBM Bob",
        skills_dir=".bob/skills",
        global_skills_dir=HOME / ".bob/skills",
        detect_installed=lambda: (HOME / ".bob").exists(),
    ),
    "claude-code": AgentConfig(
        name="claude-code",
        display_name="Claude Code",
        skills_dir=".claude/skills",
        global_skills_dir=CLAUDE_HOME / "skills",
        detect_installed=lambda: CLAUDE_HOME.exists(),
    ),
    "openclaw": AgentConfig(
        name="openclaw",
        display_name="OpenClaw",
        skills_dir="skills",
        global_skills_dir=_openclaw_skills_dir(),
        detect_installed=lambda: any(
            (HOME / d).exists() for d in (".openclaw", ".clawdbot", ".moltbot")
        ),
    ),
    "cline": AgentConfig(
        name="cline",
        display_name="Cline",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".agents/skills",
        detect_installed=lambda: (HOME / ".cline").exists(),
    ),
    "codearts-agent": AgentConfig(
        name="codearts-agent",
        display_name="CodeArts Agent",
        skills_dir=".codeartsdoer/skills",
        global_skills_dir=HOME / ".codeartsdoer/skills",
        detect_installed=lambda: (HOME / ".codeartsdoer").exists(),
    ),
    "codebuddy": AgentConfig(
        name="codebuddy",
        display_name="CodeBuddy",
        skills_dir=".codebuddy/skills",
        global_skills_dir=HOME / ".codebuddy/skills",
        detect_installed=lambda: (Path.cwd() / ".codebuddy").exists()
        or (HOME / ".codebuddy").exists(),
    ),
    "codemaker": AgentConfig(
        name="codemaker",
        display_name="Codemaker",
        skills_dir=".codemaker/skills",
        global_skills_dir=HOME / ".codemaker/skills",
        detect_installed=lambda: (HOME / ".codemaker").exists(),
    ),
    "codestudio": AgentConfig(
        name="codestudio",
        display_name="Code Studio",
        skills_dir=".codestudio/skills",
        global_skills_dir=HOME / ".codestudio/skills",
        detect_installed=lambda: (HOME / ".codestudio").exists(),
    ),
    "codex": AgentConfig(
        name="codex",
        display_name="Codex",
        skills_dir=".agents/skills",
        global_skills_dir=CODEX_HOME / "skills",
        detect_installed=lambda: CODEX_HOME.exists() or Path("/etc/codex").exists(),
    ),
    "command-code": AgentConfig(
        name="command-code",
        display_name="Command Code",
        skills_dir=".commandcode/skills",
        global_skills_dir=HOME / ".commandcode/skills",
        detect_installed=lambda: (HOME / ".commandcode").exists(),
    ),
    "continue": AgentConfig(
        name="continue",
        display_name="Continue",
        skills_dir=".continue/skills",
        global_skills_dir=HOME / ".continue/skills",
        detect_installed=lambda: (Path.cwd() / ".continue").exists()
        or (HOME / ".continue").exists(),
    ),
    "cortex": AgentConfig(
        name="cortex",
        display_name="Cortex Code",
        skills_dir=".cortex/skills",
        global_skills_dir=HOME / ".snowflake/cortex/skills",
        detect_installed=lambda: (HOME / ".snowflake/cortex").exists(),
    ),
    "crush": AgentConfig(
        name="crush",
        display_name="Crush",
        skills_dir=".crush/skills",
        global_skills_dir=HOME / ".config/crush/skills",
        detect_installed=lambda: (HOME / ".config/crush").exists(),
    ),
    "cursor": AgentConfig(
        name="cursor",
        display_name="Cursor",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".cursor/skills",
        detect_installed=lambda: (HOME / ".cursor").exists(),
    ),
    "deepagents": AgentConfig(
        name="deepagents",
        display_name="Deep Agents",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".deepagents/agent/skills",
        detect_installed=lambda: (HOME / ".deepagents").exists(),
    ),
    "devin": AgentConfig(
        name="devin",
        display_name="Devin for Terminal",
        skills_dir=".devin/skills",
        global_skills_dir=XDG_CONFIG / "devin/skills",
        detect_installed=lambda: (XDG_CONFIG / "devin").exists(),
    ),
    "dexto": AgentConfig(
        name="dexto",
        display_name="Dexto",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".agents/skills",
        detect_installed=lambda: (HOME / ".dexto").exists(),
    ),
    "droid": AgentConfig(
        name="droid",
        display_name="Droid",
        skills_dir=".factory/skills",
        global_skills_dir=HOME / ".factory/skills",
        detect_installed=lambda: (HOME / ".factory").exists(),
    ),
    "firebender": AgentConfig(
        name="firebender",
        display_name="Firebender",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".firebender/skills",
        detect_installed=lambda: (HOME / ".firebender").exists(),
    ),
    "forgecode": AgentConfig(
        name="forgecode",
        display_name="ForgeCode",
        skills_dir=".forge/skills",
        global_skills_dir=HOME / ".forge/skills",
        detect_installed=lambda: (HOME / ".forge").exists(),
    ),
    "gemini-cli": AgentConfig(
        name="gemini-cli",
        display_name="Gemini CLI",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".gemini/skills",
        detect_installed=lambda: (HOME / ".gemini").exists(),
    ),
    "github-copilot": AgentConfig(
        name="github-copilot",
        display_name="GitHub Copilot",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".copilot/skills",
        detect_installed=lambda: (HOME / ".copilot").exists(),
    ),
    "goose": AgentConfig(
        name="goose",
        display_name="Goose",
        skills_dir=".goose/skills",
        global_skills_dir=XDG_CONFIG / "goose/skills",
        detect_installed=lambda: (XDG_CONFIG / "goose").exists(),
    ),
    "hermes-agent": AgentConfig(
        name="hermes-agent",
        display_name="Hermes Agent",
        skills_dir=".hermes/skills",
        global_skills_dir=HOME / ".hermes/skills",
        detect_installed=lambda: (HOME / ".hermes").exists(),
    ),
    "junie": AgentConfig(
        name="junie",
        display_name="Junie",
        skills_dir=".junie/skills",
        global_skills_dir=HOME / ".junie/skills",
        detect_installed=lambda: (HOME / ".junie").exists(),
    ),
    "iflow-cli": AgentConfig(
        name="iflow-cli",
        display_name="iFlow CLI",
        skills_dir=".iflow/skills",
        global_skills_dir=HOME / ".iflow/skills",
        detect_installed=lambda: (HOME / ".iflow").exists(),
    ),
    "kilo": AgentConfig(
        name="kilo",
        display_name="Kilo Code",
        skills_dir=".kilocode/skills",
        global_skills_dir=HOME / ".kilocode/skills",
        detect_installed=lambda: (HOME / ".kilocode").exists(),
    ),
    "kimi-cli": AgentConfig(
        name="kimi-cli",
        display_name="Kimi Code CLI",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".config/agents/skills",
        detect_installed=lambda: (HOME / ".kimi").exists(),
    ),
    "kiro-cli": AgentConfig(
        name="kiro-cli",
        display_name="Kiro CLI",
        skills_dir=".kiro/skills",
        global_skills_dir=HOME / ".kiro/skills",
        detect_installed=lambda: (HOME / ".kiro").exists(),
    ),
    "kode": AgentConfig(
        name="kode",
        display_name="Kode",
        skills_dir=".kode/skills",
        global_skills_dir=HOME / ".kode/skills",
        detect_installed=lambda: (HOME / ".kode").exists(),
    ),
    "mcpjam": AgentConfig(
        name="mcpjam",
        display_name="MCPJam",
        skills_dir=".mcpjam/skills",
        global_skills_dir=HOME / ".mcpjam/skills",
        detect_installed=lambda: (HOME / ".mcpjam").exists(),
    ),
    "mistral-vibe": AgentConfig(
        name="mistral-vibe",
        display_name="Mistral Vibe",
        skills_dir=".vibe/skills",
        global_skills_dir=VIBE_HOME / "skills",
        detect_installed=lambda: VIBE_HOME.exists(),
    ),
    "mux": AgentConfig(
        name="mux",
        display_name="Mux",
        skills_dir=".mux/skills",
        global_skills_dir=HOME / ".mux/skills",
        detect_installed=lambda: (HOME / ".mux").exists(),
    ),
    "opencode": AgentConfig(
        name="opencode",
        display_name="OpenCode",
        skills_dir=".agents/skills",
        global_skills_dir=XDG_CONFIG / "opencode/skills",
        detect_installed=lambda: (XDG_CONFIG / "opencode").exists(),
    ),
    "openhands": AgentConfig(
        name="openhands",
        display_name="OpenHands",
        skills_dir=".openhands/skills",
        global_skills_dir=HOME / ".openhands/skills",
        detect_installed=lambda: (HOME / ".openhands").exists(),
    ),
    "pi": AgentConfig(
        name="pi",
        display_name="Pi",
        skills_dir=".pi/skills",
        global_skills_dir=HOME / ".pi/agent/skills",
        detect_installed=lambda: (HOME / ".pi/agent").exists(),
    ),
    "qoder": AgentConfig(
        name="qoder",
        display_name="Qoder",
        skills_dir=".qoder/skills",
        global_skills_dir=HOME / ".qoder/skills",
        detect_installed=lambda: (HOME / ".qoder").exists(),
    ),
    "qwen-code": AgentConfig(
        name="qwen-code",
        display_name="Qwen Code",
        skills_dir=".qwen/skills",
        global_skills_dir=HOME / ".qwen/skills",
        detect_installed=lambda: (HOME / ".qwen").exists(),
    ),
    "replit": AgentConfig(
        name="replit",
        display_name="Replit",
        skills_dir=".agents/skills",
        global_skills_dir=XDG_CONFIG / "agents/skills",
        show_in_universal_list=False,
        detect_installed=lambda: (Path.cwd() / ".replit").exists(),
    ),
    "rovodev": AgentConfig(
        name="rovodev",
        display_name="Rovo Dev",
        skills_dir=".rovodev/skills",
        global_skills_dir=HOME / ".rovodev/skills",
        detect_installed=lambda: (HOME / ".rovodev").exists(),
    ),
    "roo": AgentConfig(
        name="roo",
        display_name="Roo Code",
        skills_dir=".roo/skills",
        global_skills_dir=HOME / ".roo/skills",
        detect_installed=lambda: (HOME / ".roo").exists(),
    ),
    "tabnine-cli": AgentConfig(
        name="tabnine-cli",
        display_name="Tabnine CLI",
        skills_dir=".tabnine/agent/skills",
        global_skills_dir=HOME / ".tabnine/agent/skills",
        detect_installed=lambda: (HOME / ".tabnine").exists(),
    ),
    "trae": AgentConfig(
        name="trae",
        display_name="Trae",
        skills_dir=".trae/skills",
        global_skills_dir=HOME / ".trae/skills",
        detect_installed=lambda: (HOME / ".trae").exists(),
    ),
    "trae-cn": AgentConfig(
        name="trae-cn",
        display_name="Trae CN",
        skills_dir=".trae/skills",
        global_skills_dir=HOME / ".trae-cn/skills",
        detect_installed=lambda: (HOME / ".trae-cn").exists(),
    ),
    "warp": AgentConfig(
        name="warp",
        display_name="Warp",
        skills_dir=".agents/skills",
        global_skills_dir=HOME / ".agents/skills",
        detect_installed=lambda: (HOME / ".warp").exists(),
    ),
    "windsurf": AgentConfig(
        name="windsurf",
        display_name="Windsurf",
        skills_dir=".windsurf/skills",
        global_skills_dir=HOME / ".codeium/windsurf/skills",
        detect_installed=lambda: (HOME / ".codeium/windsurf").exists(),
    ),
    "zencoder": AgentConfig(
        name="zencoder",
        display_name="Zencoder",
        skills_dir=".zencoder/skills",
        global_skills_dir=HOME / ".zencoder/skills",
        detect_installed=lambda: (HOME / ".zencoder").exists(),
    ),
    "neovate": AgentConfig(
        name="neovate",
        display_name="Neovate",
        skills_dir=".neovate/skills",
        global_skills_dir=HOME / ".neovate/skills",
        detect_installed=lambda: (HOME / ".neovate").exists(),
    ),
    "pochi": AgentConfig(
        name="pochi",
        display_name="Pochi",
        skills_dir=".pochi/skills",
        global_skills_dir=HOME / ".pochi/skills",
        detect_installed=lambda: (HOME / ".pochi").exists(),
    ),
    "adal": AgentConfig(
        name="adal",
        display_name="AdaL",
        skills_dir=".adal/skills",
        global_skills_dir=HOME / ".adal/skills",
        detect_installed=lambda: (HOME / ".adal").exists(),
    ),
    "universal": AgentConfig(
        name="universal",
        display_name="Universal",
        skills_dir=".agents/skills",
        global_skills_dir=XDG_CONFIG / "agents/skills",
        show_in_universal_list=False,
        detect_installed=lambda: False,
    ),
    "general-skill": AgentConfig(
        name="general-skill",
        display_name="General (skills)",
        skills_dir=".agents/skills",
        global_skills_dir=XDG_CONFIG / "agents/skills",
        show_in_universal_list=False,
        detect_installed=lambda: False,
    ),
}


class UnknownAgentError(KeyError):
    """Raised when an agent name is not in AGENTS."""


def get_agent(name: str) -> AgentConfig:
    if name not in AGENTS:
        raise UnknownAgentError(name)
    return AGENTS[name]


def get_universal_agents() -> list[str]:
    """Agents whose skillsDir == '.agents/skills', excluding the synthetic
    'universal' pseudo-entry. Matches getUniversalAgents() in agents.ts."""
    return [
        n
        for n, c in AGENTS.items()
        if c.is_universal and c.show_in_universal_list
    ]


def get_non_universal_agents() -> list[str]:
    return [n for n, c in AGENTS.items() if not c.is_universal]


def is_universal(name: str) -> bool:
    return AGENTS[name].is_universal


def detect_installed_agents() -> list[str]:
    return [n for n, c in AGENTS.items() if c.detect_installed()]
