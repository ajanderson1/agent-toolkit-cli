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
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha1.json").write_text("{}")
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

    from agent_toolkit.doctor.environment import run

    real_which = shutil.which

    def fake_which(name, *args, **kwargs):
        if name == "gh":
            return None
        return real_which(name, *args, **kwargs)

    monkeypatch.setattr(shutil, "which", fake_which)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "schemas").mkdir()
        (root / "schemas" / "asset-frontmatter.v1alpha1.json").write_text("{}")
        (root / "AGENTS.md").write_text("# AGENTS")
        (root / ".gitmodules").write_text("")
        result = run(root)

    assert result.status == Status.WARN
    assert result.summary == "some tools not on PATH"
    assert any("gh NOT on PATH" in f for f in result.findings)


def test_frontmatter_group_ok_when_no_assets(tmp_path):
    from agent_toolkit.doctor.frontmatter import run as run_fm
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "asset-frontmatter.v1alpha1.json").write_text(
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
        '"properties":{"apiVersion":{"const":"agent-toolkit/v1alpha1"},'
        '"metadata":{"type":"object","required":["name","description","lifecycle"],'
        '"properties":{"name":{"type":"string"},"description":{"type":"string","pattern":"\\\\.$"},'
        '"lifecycle":{"enum":["experimental","stable","deprecated"]}}},'
        '"spec":{"type":"object","required":["origin","vendored_via","harnesses"],'
        '"properties":{"origin":{"enum":["first-party","third-party"]},'
        '"vendored_via":{"enum":["none","submodule","clone","symlink"]},'
        '"harnesses":{"type":"array","minItems":1,"items":{"enum":["claude","codex","opencode","pi"]}}}}}}'
    )
    (schema_dir / "asset-frontmatter.v1alpha1.json").write_text(real_schema)
    bad_skill = tmp_path / "skills" / "bad" / "SKILL.md"
    bad_skill.parent.mkdir(parents=True)
    bad_skill.write_text("---\nname: bad\n---\n# bad\n")  # missing required keys
    result = run_fm(tmp_path)
    assert result.status == Status.FAIL
    assert any("bad" in f for f in result.findings)


def test_frontmatter_group_fail_when_schema_missing(tmp_path):
    from agent_toolkit.doctor.frontmatter import run as run_fm
    # No schemas/ dir at all
    result = run_fm(tmp_path)
    assert result.status == Status.FAIL
    assert "schema not loadable" in result.summary
    assert any("FileNotFoundError" in f or "schema" in f.lower() for f in result.findings)


def test_frontmatter_group_fail_when_schema_invalid_json(tmp_path):
    from agent_toolkit.doctor.frontmatter import run as run_fm
    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    (schema_dir / "asset-frontmatter.v1alpha1.json").write_text("{not valid json")
    result = run_fm(tmp_path)
    assert result.status == Status.FAIL
    assert "schema not loadable" in result.summary
    assert any("JSONDecodeError" in f for f in result.findings)


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


def _make_skill_with_harnesses(repo_root, slug, harnesses):
    skill_dir = repo_root / "skills" / slug
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "apiVersion: agent-toolkit/v1alpha1\n"
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
