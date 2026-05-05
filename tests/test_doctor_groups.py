"""Tests for doctor check-group modules."""
from agent_toolkit.doctor.result import GroupResult, Status


def test_group_result_overall_status_picks_worst():
    r = GroupResult(name="x", status=Status.WARN, summary="2 issues",
                    findings=["a", "b"])
    assert r.status == Status.WARN
    assert r.is_failure() is False
    assert r.is_warning() is True


def test_status_ordering():
    assert Status.OK < Status.WARN < Status.FAIL
    assert max([Status.OK, Status.WARN]) == Status.WARN


def test_environment_group_ok_in_real_repo(tmp_path):
    from agent_toolkit.doctor.environment import run

    # Synthesize a "valid enough" repo
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text("{}")
    (tmp_path / "AGENTS.md").write_text("# AGENTS")
    (tmp_path / ".gitmodules").write_text("")
    result = run(tmp_path)
    # We can't assert OK because gh/uv might not be on PATH in CI; just assert structure
    assert result.name == "environment"
    assert result.status in (Status.OK, Status.WARN)
    assert isinstance(result.findings, list)


def test_environment_group_fails_when_schema_missing(tmp_path):
    from agent_toolkit.doctor.environment import run
    (tmp_path / "AGENTS.md").write_text("# AGENTS")
    (tmp_path / ".gitmodules").write_text("")
    result = run(tmp_path)
    assert result.status == Status.FAIL
    assert any("schema" in f.lower() for f in result.findings)


def test_environment_group_warn_when_tool_missing(monkeypatch):
    """If a tool is missing from PATH, status is WARN with the right finding."""
    import shutil
    from pathlib import Path
    import tempfile

    from agent_toolkit.doctor import environment as env_mod
    from agent_toolkit.doctor.environment import run

    real_which = shutil.which

    def fake_which(name, *args, **kwargs):
        if name == "gh":
            return None
        return real_which(name, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", fake_which)
    # Suppress PATH-shadow checks so the summary stays predictable
    monkeypatch.setattr(env_mod, "_cli_entries_on_path", lambda _name: [])
    monkeypatch.setattr(env_mod, "_stale_editable_installs", lambda: [])

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "schemas").mkdir()
        (root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text("{}")
        (root / "AGENTS.md").write_text("# AGENTS")
        (root / ".gitmodules").write_text("")
        result = run(root)

    assert result.status == Status.WARN
    assert result.summary == "some tools not on PATH"
    assert any("gh NOT on PATH" in f for f in result.findings)


def test_frontmatter_group_ok_when_no_assets(tmp_path):
    from agent_toolkit.doctor.frontmatter import run as run_fm
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha2.json").write_text(
        '{"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object"}'
    )
    result = run_fm(tmp_path)
    assert result.status == Status.OK


def test_frontmatter_group_fail_when_invalid_asset(tmp_path):
    from agent_toolkit.doctor.frontmatter import run as run_fm
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    # Use the real schema so validation actually rejects bad frontmatter
    real_schema = (
        '{"$schema":"https://json-schema.org/draft/2020-12/schema",'
        '"type":"object","required":["apiVersion","metadata","spec"],'
        '"properties":{"apiVersion":{"const":"agent-toolkit/v1alpha2"},'
        '"metadata":{"type":"object","required":["name","description","lifecycle"],'
        '"properties":{"name":{"type":"string"},"description":{"type":"string","pattern":"\\\\.$"},'
        '"lifecycle":{"enum":["experimental","stable","deprecated"]}}},'
        '"spec":{"type":"object","required":["origin","vendored_via","harnesses"],'
        '"properties":{"origin":{"enum":["first-party","third-party"]},'
        '"vendored_via":{"enum":["none","submodule","clone","symlink"]},'
        '"harnesses":{"type":"array","minItems":1,"items":{"enum":["claude","codex","opencode","pi"]}}}}}}'
    )
    (schema_dir / "asset-frontmatter.v1alpha2.json").write_text(real_schema)
    bad_skill = tmp_path / "skills" / "bad" / "SKILL.md"
    bad_skill.parent.mkdir(parents=True)
    bad_skill.write_text("---\nname: bad\n---\n# bad\n")  # missing required keys
    result = run_fm(tmp_path)
    assert result.status == Status.FAIL
    assert any("bad" in f for f in result.findings)


def test_submodules_group_ok_when_no_gitmodules(tmp_path):
    from agent_toolkit.doctor.submodules import run as run_sm
    result = run_sm(tmp_path)
    assert result.status == Status.OK
    assert "no .gitmodules" in result.summary.lower() or "0 submodule" in result.summary.lower()


def test_submodules_group_warns_when_uninitialised(tmp_path):
    from agent_toolkit.doctor.submodules import run as run_sm
    (tmp_path / ".gitmodules").write_text(
        '[submodule "skills/foo"]\n\tpath = skills/foo\n\turl = https://example.com/x.git\n'
    )
    # No actual checkout — this represents a freshly-cloned repo
    result = run_sm(tmp_path)
    assert result.status in (Status.WARN, Status.FAIL)
    assert any("foo" in f for f in result.findings)


def test_submodules_group_ok_when_initialised(tmp_path):
    from agent_toolkit.doctor.submodules import run as run_sm
    (tmp_path / ".gitmodules").write_text(
        '[submodule "skills/foo"]\n\tpath = skills/foo\n\turl = https://example.com/x.git\n'
    )
    (tmp_path / "skills" / "foo").mkdir(parents=True)
    (tmp_path / "skills" / "foo" / "README.md").write_text("hi")
    result = run_sm(tmp_path)
    assert result.status == Status.OK
    assert "skills/foo" in result.findings[0]


def test_submodules_group_fail_when_gitmodules_malformed(tmp_path):
    from agent_toolkit.doctor.submodules import run as run_sm
    (tmp_path / ".gitmodules").write_text("not a valid ini file at all\n=====\n")
    result = run_sm(tmp_path)
    assert result.status == Status.FAIL
    assert ".gitmodules not loadable" in result.summary


def test_submodules_group_handles_path_pointing_to_file(tmp_path):
    """Regression: if .gitmodules path resolves to a regular file, we WARN (not crash)."""
    from agent_toolkit.doctor.submodules import run as run_sm
    (tmp_path / ".gitmodules").write_text(
        '[submodule "broken"]\n\tpath = broken\n\turl = https://example.com/x.git\n'
    )
    # broken is a *file*, not a directory
    (tmp_path / "broken").write_text("oops")
    result = run_sm(tmp_path)
    assert result.status == Status.WARN
    assert any("broken" in f for f in result.findings)


def test_conventions_group_ok_when_correctly_linked(tmp_path, monkeypatch):
    from agent_toolkit.doctor.conventions import run as run_conv

    # Build a fake repo that has CONVENTIONS.md and conventions/topic.md
    (tmp_path / "CONVENTIONS.md").write_text("# C")
    (tmp_path / "conventions").mkdir()
    (tmp_path / "conventions" / "git.md").write_text("# git")

    # Build a fake $HOME with the symlinks pointing back into the repo
    fake_home = tmp_path / "home"
    (fake_home / ".claude" / "conventions").mkdir(parents=True)
    (fake_home / ".claude" / "CONVENTIONS.md").symlink_to(tmp_path / "CONVENTIONS.md")
    (fake_home / ".claude" / "conventions" / "git.md").symlink_to(tmp_path / "conventions" / "git.md")

    monkeypatch.setenv("HOME", str(fake_home))
    result = run_conv(tmp_path)
    assert result.status == Status.OK


def _make_skill_with_harnesses(toolkit_root, slug, harnesses):
    skill_dir = toolkit_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha2\n"
        f"metadata:\n  name: {slug}\n  description: X.\n  lifecycle: stable\n"
        "spec:\n  origin: first-party\n  vendored_via: none\n  harnesses:\n"
        + "".join(f"    - {h}\n" for h in harnesses)
        + "---\n# x\n"
    )


def test_symlinks_group_ok_when_all_correct(tmp_path, monkeypatch):
    from agent_toolkit.doctor.symlinks import run as run_sl
    _make_skill_with_harnesses(tmp_path, "alpha", ["claude"])
    fake_home = tmp_path / "home"
    (fake_home / ".claude" / "skills").mkdir(parents=True)
    (fake_home / ".claude" / "skills" / "alpha").symlink_to(tmp_path / "skills" / "alpha")
    monkeypatch.setenv("HOME", str(fake_home))
    result = run_sl(tmp_path, harness="claude")
    assert result.status == Status.OK


def test_symlinks_group_warns_on_expected_unlinked(tmp_path, monkeypatch):
    from agent_toolkit.doctor.symlinks import run as run_sl
    _make_skill_with_harnesses(tmp_path, "alpha", ["claude"])
    fake_home = tmp_path / "home"
    (fake_home / ".claude" / "skills").mkdir(parents=True)
    # No symlink at all
    monkeypatch.setenv("HOME", str(fake_home))
    result = run_sl(tmp_path, harness="claude")
    assert result.status == Status.WARN
    assert any("alpha" in f for f in result.findings)


def test_symlinks_group_flags_dangling(tmp_path, monkeypatch):
    from agent_toolkit.doctor.symlinks import run as run_sl
    _make_skill_with_harnesses(tmp_path, "alpha", ["claude"])
    fake_home = tmp_path / "home"
    (fake_home / ".claude" / "skills").mkdir(parents=True)
    bogus = fake_home / ".claude" / "skills" / "ghost"
    bogus.symlink_to(tmp_path / "skills" / "ghost")  # target does not exist
    monkeypatch.setenv("HOME", str(fake_home))
    result = run_sl(tmp_path, harness="claude")
    assert result.status == Status.WARN
    assert any("ghost" in f and "dangl" in f.lower() for f in result.findings)


def test_conventions_group_warn_when_topic_missing(tmp_path, monkeypatch):
    from agent_toolkit.doctor.conventions import run as run_conv
    (tmp_path / "CONVENTIONS.md").write_text("# C")
    (tmp_path / "conventions").mkdir()
    (tmp_path / "conventions" / "git.md").write_text("# git")
    (tmp_path / "conventions" / "ci.md").write_text("# ci")

    fake_home = tmp_path / "home"
    (fake_home / ".claude" / "conventions").mkdir(parents=True)
    (fake_home / ".claude" / "CONVENTIONS.md").symlink_to(tmp_path / "CONVENTIONS.md")
    (fake_home / ".claude" / "conventions" / "git.md").symlink_to(tmp_path / "conventions" / "git.md")
    # ci.md is missing from the harness's projected conventions dir

    monkeypatch.setenv("HOME", str(fake_home))
    result = run_conv(tmp_path)
    assert result.status == Status.WARN
    assert any("ci" in f for f in result.findings)


def test_duplicates_group_ok_when_unique(tmp_path):
    from agent_toolkit.doctor.duplicates import run as run_dupes
    cmd = tmp_path / "commands" / "alpha.md"
    cmd.parent.mkdir(parents=True)
    cmd.write_text("---\nname: alpha\n---\n# alpha\n")
    result = run_dupes(tmp_path)
    assert result.status == Status.OK
    assert "no duplicate" in result.summary


def test_duplicates_group_fails_when_kind_slug_collide(tmp_path):
    """Two files producing the same (kind, slug) — the SSOT-side drift the TUI exposes."""
    from agent_toolkit.doctor.duplicates import run as run_dupes
    a = tmp_path / "commands" / "aj" / "session" / "shared.md"
    b = tmp_path / "commands" / "custom_commands" / "session" / "shared.md"
    for p in (a, b):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("---\nname: shared\n---\n# shared\n")
    result = run_dupes(tmp_path)
    assert result.status == Status.FAIL
    assert "1 duplicate" in result.summary
    assert any("command:shared" in f and "appears 2x" in f for f in result.findings)
    assert result.fix_hint is not None


def test_duplicates_group_ok_with_no_assets(tmp_path):
    from agent_toolkit.doctor.duplicates import run as run_dupes
    result = run_dupes(tmp_path)
    assert result.status == Status.OK
    assert "0 asset" in result.summary


# ---------------------------------------------------------------------------
# PATH-shadowing checks (environment group)
# ---------------------------------------------------------------------------

def _make_valid_repo(root):
    (root / "schemas").mkdir(exist_ok=True)
    (root / "schemas" / "asset-frontmatter.v1alpha2.json").write_text("{}")
    (root / "AGENTS.md").write_text("# AGENTS")
    (root / ".gitmodules").write_text("")


def test_environment_warn_multiple_cli_entries_on_path(tmp_path, monkeypatch):
    """Two different agent-toolkit executables on PATH → WARN with PATH-shadow finding."""
    import os
    from agent_toolkit.doctor import environment as env_mod
    from agent_toolkit.doctor.environment import run

    # Create two fake agent-toolkit shims in separate directories
    bin_a = tmp_path / "bin_a"
    bin_b = tmp_path / "bin_b"
    bin_a.mkdir()
    bin_b.mkdir()
    (bin_a / "agent-toolkit").write_text("#!/bin/sh\necho a\n")
    (bin_a / "agent-toolkit").chmod(0o755)
    (bin_b / "agent-toolkit").write_text("#!/bin/sh\necho b\n")
    (bin_b / "agent-toolkit").chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_a}:{bin_b}")

    _make_valid_repo(tmp_path)
    result = run(tmp_path)

    assert result.status == Status.WARN
    assert "PATH-shadow" in result.summary or any("PATH-shadow" in f for f in result.findings)
    assert any("PATH-shadow" in f and "2 entries" in f for f in result.findings)
    assert result.fix_hint is not None


def test_environment_warn_cli_not_from_uv_tools(tmp_path, monkeypatch):
    """Single agent-toolkit entry that is NOT under the uv tools prefix → WARN."""
    import os
    from pathlib import Path
    from agent_toolkit.doctor import environment as env_mod
    from agent_toolkit.doctor.environment import run

    # Place a single agent-toolkit shim somewhere outside uv tools
    fake_bin = tmp_path / "some_other_bin"
    fake_bin.mkdir()
    shim = fake_bin / "agent-toolkit"
    shim.write_text("#!/bin/sh\necho x\n")
    shim.chmod(0o755)

    monkeypatch.setenv("PATH", str(fake_bin))
    # Make _UV_TOOLS_PREFIX point somewhere that doesn't contain our shim
    monkeypatch.setattr(env_mod, "_UV_TOOLS_PREFIX", tmp_path / "uv_tools" / "agent-toolkit")

    _make_valid_repo(tmp_path)
    result = run(tmp_path)

    assert result.status == Status.WARN
    assert any("not from uv tools" in f.lower() or "PATH-shadow" in f for f in result.findings)
    assert result.fix_hint is not None


def test_environment_ok_when_cli_from_uv_tools(tmp_path, monkeypatch):
    """agent-toolkit entry under the uv tools prefix → no PATH-shadow warning."""
    import os
    from agent_toolkit.doctor import environment as env_mod
    from agent_toolkit.doctor.environment import run

    uv_prefix = tmp_path / "uv_tools" / "agent-toolkit"
    uv_bin = uv_prefix / "bin"
    uv_bin.mkdir(parents=True)
    shim = uv_bin / "agent-toolkit"
    shim.write_text("#!/bin/sh\necho ok\n")
    shim.chmod(0o755)

    monkeypatch.setenv("PATH", str(uv_bin))
    monkeypatch.setattr(env_mod, "_UV_TOOLS_PREFIX", uv_prefix)

    _make_valid_repo(tmp_path)
    result = run(tmp_path)

    # No PATH-shadow warnings expected
    assert not any("PATH-shadow" in f for f in result.findings)


def test_environment_fail_stale_editable_install(tmp_path, monkeypatch):
    """direct_url.json pointing at a non-existent directory → FAIL."""
    import json
    from pathlib import Path
    from agent_toolkit.doctor import environment as env_mod
    from agent_toolkit.doctor.environment import run

    # Build a fake site-packages with a stale editable dist-info
    site_pkgs = tmp_path / "site-packages"
    dist_info = site_pkgs / "agent_toolkit-0.1.0.dist-info"
    dist_info.mkdir(parents=True)
    missing_source = tmp_path / "deleted_worktree"
    (dist_info / "direct_url.json").write_text(
        json.dumps({"url": f"file://{missing_source}", "dir_info": {"editable": True}})
    )

    def fake_site_packages(python_exe):
        return site_pkgs

    monkeypatch.setattr(env_mod, "_site_packages_for", fake_site_packages)
    # Ensure at least one Python is "found" by which()
    import shutil
    real_which = shutil.which

    def fake_which(name, *args, **kwargs):
        if name in ("python3", "python"):
            return str(tmp_path / "python3")
        return real_which(name, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", fake_which)
    # Make the fake python path exist so resolve() works
    (tmp_path / "python3").write_text("#!/bin/sh\n")
    (tmp_path / "python3").chmod(0o755)

    _make_valid_repo(tmp_path)
    result = run(tmp_path)

    assert result.status == Status.FAIL
    assert any("stale editable" in f for f in result.findings)
    assert any(str(missing_source) in f for f in result.findings)
    assert result.fix_hint is not None
    assert "pip uninstall" in result.fix_hint


def test_environment_no_cli_on_path_skips_shadow_checks(tmp_path, monkeypatch):
    """When agent-toolkit is not on PATH at all, no PATH-shadow findings are emitted."""
    from agent_toolkit.doctor.environment import run

    monkeypatch.setenv("PATH", str(tmp_path / "empty_bin"))

    _make_valid_repo(tmp_path)
    result = run(tmp_path)

    assert not any("PATH-shadow" in f for f in result.findings)
