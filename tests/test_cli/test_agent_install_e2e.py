"""End-to-end: install one agent into each of the 28 supported harnesses
in a tmp HOME and assert the on-disk projection exists at the matrix path.

Acceptance criterion #3 (the 28 supported cells are installable through
agent_install.install()).
"""
from __future__ import annotations

import pytest


# 28 supported harnesses (mechanism doesn't matter for this smoke test —
# whatever subagent_mechanism is set in skill_agents.py, the e2e flow
# should produce ≥1 on-disk file inside HOME or XDG_CONFIG_HOME).
SUPPORTED_HARNESSES = [
    # symlink (15)
    "augment", "claude-code", "codebuddy", "command-code", "cortex",
    "cursor", "droid", "forgecode", "junie", "kode", "neovate", "pi",
    "pochi", "qoder", "rovodev",
    # translate (9 — codex moved to config_file_folder in Task 12)
    "devin", "gemini-cli", "github-copilot", "kilo",
    "kiro-cli", "mistral-vibe", "mux", "opencode", "qwen-code",
    # config_file_folder (4 — codex joined per Task 12)
    "aider-desk", "codex", "dexto", "firebender",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts with PI_CODING_AGENT_DIR + XDG_CONFIG_HOME unset
    so dev-shell env doesn't leak into expected paths."""
    monkeypatch.delenv("PI_CODING_AGENT_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


@pytest.fixture
def fake_canonical(tmp_path, monkeypatch):
    """Seed a canonical agent directory with a content file."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Use XDG_CONFIG_HOME under tmp_path so {XDG_CONFIG} translate cells
    # (devin, kilo, opencode) write inside the sandbox.
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / ".config"))
    from agent_toolkit_cli.agent_paths import canonical_agent_dir
    canonical = canonical_agent_dir("smoke-agent", scope="global")
    canonical.mkdir(parents=True, exist_ok=True)
    (canonical / "smoke-agent.md").write_text(
        "---\nname: smoke-agent\ndescription: smoke\n---\n\nSmoke body.\n"
    )
    return canonical


@pytest.mark.parametrize("harness", SUPPORTED_HARNESSES)
def test_install_one_harness_creates_projection(harness, fake_canonical, tmp_path):
    """Per-harness smoke: install creates at least one file under HOME/XDG."""
    from agent_toolkit_cli.agent_install import apply
    from agent_toolkit_cli._install_core import InstallPlan

    plan = InstallPlan(
        slug="smoke-agent", scope="global", source=None, ref=None,
        add_agents=(harness,), remove_agents=(),
    )
    result = apply(plan, home=tmp_path)
    # Either the harness is supported and produces ≥1 file, OR it raises
    # UnsupportedMechanismError (recorded as 'skipped'). Smoke asserts the
    # supported case — none of the 28 cells should be skipped.
    assert harness not in result.skipped, f"{harness} unexpectedly skipped"
    assert len(result.created) >= 1, f"{harness} produced no projection"
    for path in result.created:
        assert path.exists(), f"{harness}: created path {path} does not exist"
        # Must be inside the tmp HOME or XDG_CONFIG (no leakage to real FS).
        path_str = str(path)
        assert str(tmp_path) in path_str, (
            f"{harness}: projection at {path} escaped tmp_path"
        )
