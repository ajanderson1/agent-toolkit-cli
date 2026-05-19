"""Doctor mcps group: drift, env, prereq, verify."""
from __future__ import annotations

from pathlib import Path

import pytest


def _seed_toolkit_with_mcp(toolkit_root: Path, *,
                           env: list[str] | None = None,
                           prerequisites: list[str] | None = None,
                           verify: str | None = None) -> None:
    """Seed a tmp toolkit with one MCP at mcps/context7/."""
    (toolkit_root / "schemas").mkdir(parents=True, exist_ok=True)
    src_schema = (
        Path(__file__).resolve().parents[1] / "schemas"
        / "asset-frontmatter.v1alpha2.json"
    )
    (toolkit_root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(
        src_schema.read_text()
    )
    (toolkit_root / ".agent-toolkit-source").write_text("")
    mcp_dir = toolkit_root / "mcps" / "context7"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "config.json").write_text(
        '{"type":"stdio","command":"npx","args":["-y","@upstash/context7-mcp"]}\n'
    )
    extra = ""
    if env:
        items = "\n".join(f"      - {e}" for e in env)
        extra += f"    env:\n{items}\n"
    if prerequisites:
        items = "\n".join(f"      - {p}" for p in prerequisites)
        extra += f"    prerequisites:\n{items}\n"
    if verify:
        # YAML strings need quoting; use double quotes since we control content.
        extra += f'    verify: "{verify}"\n'
    (toolkit_root / "mcps" / "context7.toolkit.yaml").write_text(
        "apiVersion: agent-toolkit/v1alpha2\n"
        "metadata:\n  name: context7\n  description: c.\n  lifecycle: stable\n"
        "spec:\n  origin: third-party\n  vendored_via: none\n"
        "  upstream: https://example.com\n  harnesses:\n    - codex\n"
        "  mcp:\n    transport: stdio\n    install_method: npx\n"
        f"{extra}"
    )


def test_doctor_mcps_no_allowlist_returns_ok(monkeypatch, tmp_path):
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    _seed_toolkit_with_mcp(tmp_path)
    # No allow-list → group is OK with note "no MCPs allow-listed".

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.OK
    assert any("no" in f.lower() and "mcp" in f.lower() for f in result.findings)


def test_doctor_mcps_ok_when_no_drift(monkeypatch, tmp_path):
    """Allow-listed and installed and aligned → OK."""
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path)

    # Pre-populate codex config with the canonical render.
    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_bytes(act.contents)

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.OK


def test_doctor_mcps_warn_when_not_installed(monkeypatch, tmp_path):
    """Allow-listed but not installed → finding noted (not a hard failure)."""
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path)

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    # Status is OK or WARN depending on contract; the finding mentions context7
    # is not installed.
    assert any("context7" in f and ("not installed" in f.lower() or "link" in f.lower())
               for f in result.findings)


def test_doctor_mcps_warn_on_drift(monkeypatch, tmp_path):
    """Drift between installed entry and template → WARN with drift note."""
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path)

    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    target = home / ".codex" / "config.toml"
    target.write_bytes(act.contents)
    # Hand-edit to introduce drift.
    text = target.read_text().replace(
        '"@upstash/context7-mcp"', '"@upstash/context7-mcp", "--debug"'
    )
    target.write_text(text)

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status in {Status.WARN, Status.FAIL}
    assert any("drift" in f.lower() for f in result.findings)


def test_doctor_mcps_warn_on_missing_env(monkeypatch, tmp_path):
    """Required env var not set → WARN with var name in findings."""
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CONTEXT7_API_KEY", raising=False)
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path, env=["CONTEXT7_API_KEY"])

    # Install (so we test env-warn against an installed MCP, not the not-installed message).
    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_bytes(act.contents)

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.WARN
    assert any("CONTEXT7_API_KEY" in f for f in result.findings)


def test_doctor_mcps_ok_when_env_present(monkeypatch, tmp_path):
    """Required env var present → OK."""
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CONTEXT7_API_KEY", "x")
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path, env=["CONTEXT7_API_KEY"])

    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_bytes(act.contents)

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.OK


def test_doctor_mcps_warn_on_missing_prereq(monkeypatch, tmp_path):
    """Prerequisite not on PATH → WARN with prereq name."""
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path, prerequisites=["definitelynotacommand_xyz"])

    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_bytes(act.contents)

    result = run(toolkit_root=tmp_path, harness="codex", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.WARN
    assert any("definitelynotacommand_xyz" in f for f in result.findings)


def test_doctor_mcps_skips_unimplemented_harness(monkeypatch, tmp_path):
    """harness=pi → group reports OK with 'no adapter' note (Pi MCP unsupported by design)."""
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path)

    result = run(toolkit_root=tmp_path, harness="pi", scope="user",
                 project_root=tmp_path)
    assert result.status == Status.OK
    assert any("no MCP adapter" in f for f in result.findings)


def test_doctor_mcps_verify_off_by_default(monkeypatch, tmp_path):
    """`verify:` command is NOT run unless run_verify=True."""
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    # The verify command would touch this file; if it runs, the test fails.
    sentinel = tmp_path / "verify_ran"
    _seed_toolkit_with_mcp(tmp_path, verify=f"touch {sentinel}")

    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_bytes(act.contents)

    run(toolkit_root=tmp_path, harness="codex", scope="user",
        project_root=tmp_path)  # run_verify defaults to False
    assert not sentinel.exists(), "verify command ran without --verify flag"


def test_doctor_mcps_verify_on_runs_command(monkeypatch, tmp_path):
    """run_verify=True executes the verify command."""
    from agent_toolkit_cli.commands._mcp_dispatch import _build_mcp_entries
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.harness_adapters import get_adapter

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    sentinel = tmp_path / "verify_ran"
    _seed_toolkit_with_mcp(tmp_path, verify=f"touch {sentinel}")

    [entry] = _build_mcp_entries(tmp_path, ["context7"])
    a = get_adapter("codex")
    [act] = a.diff("user", tmp_path, [entry])
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_bytes(act.contents)

    run(toolkit_root=tmp_path, harness="codex", scope="user",
        project_root=tmp_path, run_verify=True)
    assert sentinel.exists(), "verify command should have run with run_verify=True"


def test_doctor_mcps_fail_on_unparseable_codex_toml(monkeypatch, tmp_path):
    """Broken TOML in ~/.codex/config.toml → FAIL finding, no traceback (#122)."""
    from agent_toolkit_cli.doctor.mcps import run
    from agent_toolkit_cli.doctor.result import Status

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    (home / ".agent-toolkit.yaml").write_text("mcps:\n  - context7\n")
    _seed_toolkit_with_mcp(tmp_path)
    (home / ".codex").mkdir()
    (home / ".codex" / "config.toml").write_text("{{{not toml\n")

    result = run(
        toolkit_root=tmp_path, harness="codex", scope="user",
        project_root=tmp_path,
    )
    assert result.status == Status.FAIL
    assert any(
        "config.toml" in f and ("parse" in f.lower() or "toml" in f.lower())
        for f in result.findings
    ), result.findings
