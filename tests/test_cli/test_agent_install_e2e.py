"""End-to-end: install one agent into each of the supported harnesses
in a tmp HOME and assert the on-disk projection exists at the matrix path.

Acceptance criterion #3 (the supported cells are installable through
agent_install.install()).
"""
from __future__ import annotations

import pytest


# Enabled harnesses (mechanism doesn't matter for this smoke test —
# whatever subagent_mechanism is set in skill_agents.py, the e2e flow
# should produce ≥1 on-disk file inside HOME or XDG_CONFIG_HOME).
#
# PR2 shipped: 15 symlink + 9 translate = 24 harnesses.
# PR4 adds: aider-desk + dexto (config_file_folder, self-owned per-slug files).
# Total: 26 supported harnesses.
#
# Note: codex + firebender remain intentionally DISABLED (subagent_mechanism=none)
# pending an AJ decision on shared-config mutation — see PR2_DISABLED_PENDING_AJ_DECISION.
SUPPORTED_HARNESSES = [
    # symlink (15)
    "augment", "claude-code", "codebuddy", "command-code", "cortex",
    "cursor", "droid", "forgecode", "junie", "kode", "neovate", "pi",
    "pochi", "qoder", "rovodev",
    # translate (9)
    "devin", "gemini-cli", "github-copilot", "kilo",
    "kiro-cli", "mistral-vibe", "mux", "opencode", "qwen-code",
    # config_file_folder — self-owned per-slug writes (PR4, #252)
    "aider-desk", "dexto",
]


# PR4 reduced this set from 4 → 2. aider-desk + dexto were enabled because
# they write only self-owned per-slug files (no shared-config mutation).
# codex + firebender remain disabled pending AJ decision (PR5a) — both mutate
# a shared registry file owned by a third-party tool.
PR2_DISABLED_PENDING_AJ_DECISION = frozenset({
    "codex", "firebender",
})


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
    # PR2-enabled cells must NOT be skipped + must produce ≥1 file inside tmp.
    assert harness not in result.skipped, f"{harness} unexpectedly skipped"
    assert len(result.created) >= 1, f"{harness} produced no projection"
    for path in result.created:
        assert path.exists(), f"{harness}: created path {path} does not exist"
        # Must be inside the tmp HOME or XDG_CONFIG (no leakage to real FS).
        path_str = str(path)
        assert str(tmp_path) in path_str, (
            f"{harness}: projection at {path} escaped tmp_path"
        )


@pytest.mark.parametrize("harness", sorted(PR2_DISABLED_PENDING_AJ_DECISION))
def test_pr2_disabled_cells_skip_cleanly(harness, fake_canonical, tmp_path):
    """The 2 remaining disabled config_file_folder cells (codex + firebender) skip cleanly.

    Confirms the disable is in effect: apply() records each as 'skipped',
    creates no files, and surfaces UnsupportedMechanismError cleanly. If
    someone re-enables a cell by flipping the literal back from 'none' to
    'config_file_folder' WITHOUT also adding deeper smoke coverage AND an AJ
    decision on shared-config mutation, this test starts failing — fail-loud,
    not silent re-enable.

    aider-desk + dexto were moved to SUPPORTED_HARNESSES in PR4 (#252) because
    they write only self-owned per-slug files. codex + firebender remain here
    pending PR5a (shared-registry mutation decision).
    """
    from agent_toolkit_cli._install_core import InstallPlan
    from agent_toolkit_cli.agent_install import apply

    plan = InstallPlan(
        slug="smoke-agent", scope="global", source=None, ref=None,
        add_agents=(harness,), remove_agents=(),
    )
    result = apply(plan, home=tmp_path)
    assert harness in result.skipped, (
        f"{harness} is meant to remain disabled (subagent_mechanism='none', "
        f"shared-registry mutation needs AJ decision) but apply() did not "
        f"record it as skipped. If you re-enabled it, also remove it from "
        f"PR2_DISABLED_PENDING_AJ_DECISION and add it to SUPPORTED_HARNESSES, "
        f"AND ensure the PR5a AJ decision has been made."
    )
    assert len(result.created) == 0, (
        f"{harness} disabled but produced files: {result.created}"
    )
