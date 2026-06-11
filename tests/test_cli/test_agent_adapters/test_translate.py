"""translate mechanism: 10 cells reshape frontmatter or emit non-md formats.

Per-cell expected paths sourced from spec addendum Risk Resolution table:
docs/superpowers/specs/2026-05-28-v3-pr2-agent-facade-and-adapters-design.md
(path templates verified 2026-05-28).
"""
from __future__ import annotations

import json
import tomllib

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_xdg_env(monkeypatch):
    """Every test starts with XDG_CONFIG_HOME unset so the dev-shell
    environment cannot bleed into the translate path-expansion logic.
    Tests that need an XDG override set it explicitly via monkeypatch."""
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)


@pytest.fixture
def fake_content(tmp_path):
    """A canonical .md file with rich frontmatter for testing all emitters.

    Includes extra fields (extras) that gemini-strict must filter out.
    Includes a systemPrompt field that qwen-code must strip.
    Includes a flat runnable field that mux must convert to nested.
    """
    text = (
        "---\n"
        "name: test-agent\n"
        "description: A test agent.\n"
        "display_name: Test Agent\n"
        "model: gpt-4o\n"
        "temperature: 0.5\n"
        "max_turns: 10\n"
        "tools:\n"
        "  - read_file\n"
        "  - write_file\n"
        "runnable: true\n"
        "systemPrompt: should-be-stripped\n"
        "extra_unknown_field: should-be-dropped-by-gemini\n"
        "---\n"
        "\n"
        "This is the body content.\n"
    )
    content = tmp_path / "canonical" / "test-agent.md"
    content.parent.mkdir(parents=True, exist_ok=True)
    content.write_text(text)
    return content


# ---------------------------------------------------------------------------
# Per-cell behaviour tests
# ---------------------------------------------------------------------------

def test_gemini_cli_install_filters_to_allowed_fields(tmp_path, fake_content):
    """gemini-cli yaml-strict emitter must drop any frontmatter key outside
    the documented allow-list, emitting only the permitted subset."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    text = dest.read_text()
    # Allowed fields should be present
    assert "name:" in text
    assert "description:" in text
    assert "model:" in text
    assert "temperature:" in text
    assert "max_turns:" in text
    # Extra field NOT in allow-list must be absent
    assert "extra_unknown_field" not in text
    # systemPrompt not in gemini allow-list — must be absent
    assert "systemPrompt" not in text
    # File is .md
    assert dest.suffix == ".md"


def test_codex_install_writes_toml(tmp_path, fake_content):
    """codex toml emitter: body becomes developer_instructions, toml is valid."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("codex")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert dest.suffix == ".toml"
    data = tomllib.loads(dest.read_text())
    assert data.get("name") == "test-agent"
    assert data.get("description") == "A test agent."
    assert "This is the body content." in data.get("developer_instructions", "")
    assert dest.parent.name == "agents"


def test_kiro_cli_install_writes_json(tmp_path, fake_content):
    """kiro-cli json emitter: valid JSON with name, description, prompt fields."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("kiro-cli")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert dest.suffix == ".json"
    data = json.loads(dest.read_text())
    assert data.get("name") == "test-agent"
    assert data.get("description") == "A test agent."
    assert "This is the body content." in data.get("prompt", "")


def test_mux_install_emits_nested_subagent_block(tmp_path, fake_content):
    """mux emitter MUST emit 'subagent:\\n  runnable: true' (nested).
    Flat 'runnable: true' at root level silently leaves agents un-spawnable."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("mux")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    text = dest.read_text()
    # subagent: block must appear before runnable: true
    assert "subagent:" in text
    assert "runnable: true" in text
    lines = text.splitlines()
    sub_indices = [i for i, ln in enumerate(lines) if ln.strip() == "subagent:"]
    runnable_indices = [i for i, ln in enumerate(lines) if "runnable: true" in ln]
    assert sub_indices, "subagent: block not found"
    assert runnable_indices, "runnable: true not found"
    # runnable must be AFTER subagent (nested)
    assert runnable_indices[0] > sub_indices[0], (
        "runnable: true must appear AFTER subagent: (nested), not before/at root level"
    )
    # The runnable line must be indented (nested inside subagent block)
    runnable_line = lines[runnable_indices[0]]
    assert runnable_line.startswith("  "), (
        f"runnable: true must be indented under subagent:, got: {runnable_line!r}"
    )
    # flat runnable key must NOT appear at root level in frontmatter
    fm_lines = []
    in_fm = False
    dash_count = 0
    for ln in lines:
        if ln.strip() == "---":
            dash_count += 1
            in_fm = dash_count < 2
            continue
        if in_fm:
            fm_lines.append(ln)
    flat_root_runnable = [ln for ln in fm_lines if ln.startswith("runnable:")]
    assert not flat_root_runnable, (
        f"flat 'runnable:' at root frontmatter level must be stripped; found: {flat_root_runnable}"
    )


def test_opencode_writes_plural_agents_with_mode(tmp_path, fake_content):
    """opencode emitter: writes to 'agents/' (plural) and injects mode: subagent."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("opencode")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    # Plural agents/ dir
    assert dest.parent.name == "agents"
    text = dest.read_text()
    assert "mode: subagent" in text


def test_kilo_install_injects_mode_subagent(tmp_path, fake_content):
    """kilo global path uses singular 'agent/' and injects mode: subagent."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("kilo")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    # Global uses singular agent/
    assert dest.parent.name == "agent"
    text = dest.read_text()
    assert "mode: subagent" in text


def test_kilo_project_path_plural(tmp_path, fake_content):
    """kilo project path is plural 'agents/' — asymmetric from global."""
    project = tmp_path / "myproj"
    project.mkdir()
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("kilo")
    dest = adapter.install("test-agent", fake_content, scope="project", project=project)
    assert dest.parent.name == "agents"


def test_mistral_vibe_install_writes_toml_with_safety(tmp_path, fake_content):
    """mistral-vibe toml emitter: valid TOML with required fields + safety default."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("mistral-vibe")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert dest.suffix == ".toml"
    data = tomllib.loads(dest.read_text())
    assert data.get("agent_type") == "subagent"
    # safety defaults to "neutral" when not specified in frontmatter
    assert data.get("safety") == "neutral"
    assert "enabled_tools" in data
    assert data.get("display_name") == "Test Agent"
    assert data.get("description") == "A test agent."


def test_github_copilot_global_writes_agent_md_suffix(tmp_path, fake_content):
    """github-copilot global: written to ~/.copilot/agents/{SLUG}.agent.md"""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("github-copilot")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert dest.name.endswith(".agent.md"), (
        f"github-copilot global path must use .agent.md suffix, got {dest.name!r}"
    )
    assert dest.parent.name == "agents"
    assert ".copilot" in str(dest)


def test_github_copilot_project_path_under_github(tmp_path, fake_content):
    """github-copilot project: path must be under .github/agents/ (not .copilot/)."""
    project = tmp_path / "myproj"
    project.mkdir()
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("github-copilot")
    dest = adapter.install("test-agent", fake_content, scope="project", project=project)
    assert ".github" in str(dest), (
        f"github-copilot project must write under .github/agents/, got {dest!r}"
    )
    assert dest.name.endswith(".agent.md")


def test_devin_install_uses_profile_and_agent_md_filename(tmp_path, fake_content):
    """devin: uses 'default' profile and AGENT.md filename (not slug.md)."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("devin")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert dest.name == "AGENT.md", (
        f"devin must write AGENT.md (not the slug), got {dest.name!r}"
    )
    assert "default" in str(dest), (
        f"devin path must include 'default' profile, got {dest!r}"
    )
    # Uses XDG_CONFIG_HOME (unset in test → home/.config)
    assert ".config" in str(dest)


def test_qwen_code_install_body_is_prompt(tmp_path, fake_content):
    """qwen-code: body is the system prompt; systemPrompt key must NOT appear."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("qwen-code")
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    text = dest.read_text()
    assert "systemPrompt" not in text, (
        "qwen-code must never emit a 'systemPrompt' frontmatter key"
    )
    # Body content should be present
    assert "This is the body content." in text


# ---------------------------------------------------------------------------
# Parametrized uninstall idempotency
# ---------------------------------------------------------------------------

TRANSLATE_CELLS = [
    "codex",
    "devin",
    "gemini-cli",
    "github-copilot",
    "kilo",
    "kiro-cli",
    "mistral-vibe",
    "mux",
    "opencode",
    "qwen-code",
]


@pytest.mark.parametrize("harness", TRANSLATE_CELLS)
def test_translate_uninstall_idempotent(harness, tmp_path, fake_content):
    """Uninstall is a no-op if the file does not exist; no exception raised."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for(harness)
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    adapter.uninstall("test-agent", scope="global", home=tmp_path)
    # Second call must not raise
    adapter.uninstall("test-agent", scope="global", home=tmp_path)


# ---------------------------------------------------------------------------
# Fail-loud regression tests (per Task-8 lessons)
# ---------------------------------------------------------------------------

def test_adapter_for_unknown_harness_raises():
    """translate.adapter_for must raise UnknownAgentError for any harness
    not in CELL_PATHS — independent of the dispatcher layer's check."""
    from agent_toolkit_cli.agent_adapters import translate
    from agent_toolkit_cli.skill_agents import UnknownAgentError
    with pytest.raises(UnknownAgentError):
        translate.adapter_for("nonexistent-harness-xyz")


def test_install_with_invalid_scope_raises(tmp_path, fake_content):
    """Bad scope must raise ValueError (not bare KeyError)."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("gemini-cli")
    with pytest.raises(ValueError, match="global.*project"):
        adapter.install("test", fake_content, scope="globall", home=tmp_path)


def test_install_global_without_home_raises(tmp_path, fake_content):
    """Fail-loud: scope='global' on a {HOME} template without home= would
    silently write to './{HOME}/...' under cwd. Must raise ValueError."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("gemini-cli")
    with pytest.raises(ValueError, match="requires home="):
        adapter.install("test", fake_content, scope="global", home=None)


def test_install_project_without_project_raises(tmp_path, fake_content):
    """Fail-loud: scope='project' without project= on a {PROJECT} template
    would silently write to './{PROJECT}/...' under cwd. Must raise ValueError."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("gemini-cli")
    with pytest.raises(ValueError, match="requires project="):
        adapter.install("test", fake_content, scope="project", project=None)


def test_install_xdg_template_without_home_raises(tmp_path, fake_content, monkeypatch):
    """Fail-loud: {XDG_CONFIG} template with no XDG_CONFIG_HOME env AND no
    home= must raise ValueError rather than falling back to real Path.home()."""
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("devin")
    with pytest.raises(ValueError, match="requires home="):
        adapter.install("test", fake_content, scope="global", home=None)


def test_github_copilot_install_raises_when_description_missing(tmp_path):
    """github-copilot REQUIRES `description` in frontmatter; data-dependent
    emitter failures surface as InstallError at the adapter boundary (#370)
    so the CLI layer converts them to a clean ClickException."""
    content = tmp_path / "no-desc.md"
    content.write_text("---\nname: test-agent\n---\n\nBody.\n")
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("github-copilot")
    with pytest.raises(InstallError, match="description"):
        adapter.install("test-agent", content, scope="global", home=tmp_path)


def test_mistral_vibe_install_raises_on_invalid_safety(tmp_path):
    """mistral-vibe `safety` must be one of safe|neutral|destructive|yolo.
    Anything else surfaces as InstallError at the adapter boundary (#370)
    rather than a raw ValueError traceback mid-fan-out."""
    content = tmp_path / "bad-safety.md"
    content.write_text(
        "---\nname: test\ndescription: test\nsafety: tornado\n---\n\nBody.\n"
    )
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("mistral-vibe")
    with pytest.raises(InstallError, match="safety"):
        adapter.install("test", content, scope="global", home=tmp_path)


# ── #368: install-side ownership contract ────────────────────────────────

# All 10 translate cells; gemini-cli exercises the strict filter, codex the
# TOML emitter, kiro-cli the JSON emitter — the sentinel must appear for all.
TRANSLATE_HARNESSES = [
    "codex", "devin", "gemini-cli", "github-copilot", "kilo",
    "kiro-cli", "mistral-vibe", "mux", "opencode", "qwen-code",
]


@pytest.mark.parametrize("harness", TRANSLATE_HARNESSES)
def test_install_writes_sentinel(harness, tmp_path, fake_content):
    """#368: every translate-cell install writes the .attk ownership sidecar."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for(harness)
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert _sentinel_path(dest).exists(), f"{harness}: no sentinel beside {dest}"


def test_install_adopts_emission_identical_file(tmp_path, fake_content):
    """#368 (F3): a pre-existing file matching the EMITTER OUTPUT (not the
    canonical bytes) is adopted — sentinel written, no error."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for("gemini-cli")
    # First install produces the emitted shape; strip the sentinel to fake
    # a pre-#368 projection.
    dest = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    _sentinel_path(dest).unlink()
    out = adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert out == dest
    assert _sentinel_path(dest).exists()


def test_install_ignores_facade_overwrite_flag(tmp_path, fake_content):
    """#368 (G5): divergent sentinel-less file refuses even with overwrite=True."""
    from agent_toolkit_cli.agent_adapters import AgentProjectionConflictError, translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("# user-authored, divergent\n")
    with pytest.raises(AgentProjectionConflictError):
        adapter.install("test-agent", fake_content, scope="global",
                        home=tmp_path, overwrite=True)
    assert dest.read_text() == "# user-authored, divergent\n"


def test_install_with_sentinel_overwrites_divergent_file(tmp_path, fake_content):
    """#368: the sentinel authorizes refreshing our own drifted projection."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    dest.write_text("stale projection\n")
    _sentinel_path(dest).write_text("")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert "name: test-agent" in dest.read_text()


def test_install_replaces_symlink_at_destination(tmp_path, fake_content):
    """#368 (F6 parity): write_text through a symlink would land in its target."""
    from agent_toolkit_cli.agent_adapters import _sentinel_path, translate
    adapter = translate.adapter_for("gemini-cli")
    dest = adapter.destination("test-agent", scope="global", home=tmp_path)
    dest.parent.mkdir(parents=True)
    target = tmp_path / "users-dotfile.md"
    target.write_text("user dotfile source\n")
    dest.symlink_to(target)
    _sentinel_path(dest).write_text("")
    adapter.install("test-agent", fake_content, scope="global", home=tmp_path)
    assert not dest.is_symlink()
    assert target.read_text() == "user dotfile source\n"


def test_install_missing_canonical_raises_install_error(tmp_path):
    """#368 (F8 parity): missing canonical → InstallError, not raw OSError."""
    from agent_toolkit_cli._install_core import InstallError
    from agent_toolkit_cli.agent_adapters import translate
    adapter = translate.adapter_for("gemini-cli")
    missing = tmp_path / "canonical" / "test-agent.md"
    with pytest.raises(InstallError, match="canonical content file missing"):
        adapter.install("test-agent", missing, scope="global", home=tmp_path)
