import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from agent_toolkit_cli.cli import main


def _setup_pi_home(
    home: Path,
    ext_slugs: list[str],
    packages: list[str],
    node_modules: list[str],
) -> None:
    (home / ".pi/agent/extensions").mkdir(parents=True, exist_ok=True)
    for s in ext_slugs:
        (home / ".pi/agent/extensions" / s).mkdir()
    (home / ".pi/agent").mkdir(parents=True, exist_ok=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": packages})
    )
    (home / ".pi/agent/npm/node_modules").mkdir(parents=True, exist_ok=True)
    for pkg in node_modules:
        (home / ".pi/agent/npm/node_modules" / pkg).mkdir()


def test_pi_inventory_json_format(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    _setup_pi_home(
        home,
        ext_slugs=["status-bar"],
        packages=["npm:pi-subagents"],
        node_modules=["pi-subagents"],
    )
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory", "--format", "json"],
    )
    assert result.exit_code == 0, result.output

    records = json.loads(result.output)
    slugs = {r["slug"] for r in records}
    assert slugs == {"status-bar", "pi-subagents"}

    sb = next(r for r in records if r["slug"] == "status-bar")
    assert sb["origin"] == "first-party"
    assert sb["user_loaded"] is True

    ps = next(r for r in records if r["slug"] == "pi-subagents")
    assert ps["origin"] == "third-party"
    assert ps["user_loaded"] is True


def test_pi_inventory_text_format(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    _setup_pi_home(home, ext_slugs=["status-bar"], packages=[], node_modules=[])
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory"],  # default --format text
    )
    assert result.exit_code == 0
    assert "status-bar" in result.output
    assert "first-party" in result.output


def test_pi_inventory_text_format_dims_disabled(tmp_path: Path, monkeypatch):
    """Loaded-but-disabled extensions render with `~` in the text view, not `✓`."""
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent/extensions/status-bar").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"extensions": ["!status-bar"]})
    )
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(main, ["--project", str(project), "pi", "inventory"])
    assert result.exit_code == 0, result.output
    # Find the data row (not the header).
    rows = [line for line in result.output.splitlines() if "status-bar" in line]
    assert rows, result.output
    assert "~" in rows[0]
    assert "✓" not in rows[0]


def test_pi_inventory_scope_filter(tmp_path: Path, monkeypatch):
    """`--scope user` hides project-only records; `--scope project` shows them."""
    home = tmp_path / "home"
    project = tmp_path / "proj"
    home.mkdir()
    project.mkdir()

    # Project-only third-party: settings.json + node_modules + allowlist.
    (project / ".pi").mkdir()
    (project / ".pi/settings.json").write_text(
        json.dumps({"packages": ["npm:project-only"]})
    )
    (project / ".pi/npm/node_modules/project-only").mkdir(parents=True)
    (project / ".agent-toolkit.yaml").write_text(
        "pi_packages:\n  - npm:project-only\n"
    )

    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()

    # user scope — nothing should match
    result = runner.invoke(
        main,
        [
            "--project",
            str(project),
            "pi",
            "inventory",
            "--scope",
            "user",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == []

    # project scope — record appears
    result = runner.invoke(
        main,
        [
            "--project",
            str(project),
            "pi",
            "inventory",
            "--scope",
            "project",
            "--format",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output
    records = json.loads(result.output)
    assert len(records) == 1
    assert records[0]["slug"] == "project-only"
    assert records[0]["toolkit_intent"] == "project"
    assert records[0]["project_loaded"] is True


def test_pi_inventory_malformed_settings_json(tmp_path: Path, monkeypatch):
    """Corrupt settings.json should surface a loud error mentioning the file."""
    home = tmp_path / "home"
    project = tmp_path / "proj"
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text("{ not json")
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory", "--format", "json"],
    )
    assert result.exit_code != 0
    combined = (result.output or "") + (
        str(result.exception) if result.exception else ""
    )
    assert "settings.json" in combined


def test_pi_inventory_empty(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    home.mkdir()
    project.mkdir()
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "inventory", "--format", "json"],
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_pi_sync_adds_missing_package(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(json.dumps({"packages": []}))

    allow = home / ".agent-toolkit.yaml"
    allow.write_text(yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]}))

    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "sync", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output

    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert settings["packages"] == ["npm:pi-subagents"]


def test_pi_sync_removes_orphan_package(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-orphan"]})
    )
    allow = home / ".agent-toolkit.yaml"
    allow.write_text(yaml.safe_dump({"pi_packages": []}))

    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "sync", "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert settings["packages"] == []


def test_pi_sync_idempotent(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-subagents"]})
    )
    allow = home / ".agent-toolkit.yaml"
    allow.write_text(yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]}))

    monkeypatch.setenv("HOME", str(home))
    runner = CliRunner()
    before = (home / ".pi/agent/settings.json").read_text()
    r1 = runner.invoke(
        main, ["--project", str(project), "pi", "sync", "--scope", "user"]
    )
    assert r1.exit_code == 0
    after_first = (home / ".pi/agent/settings.json").read_text()
    r2 = runner.invoke(
        main, ["--project", str(project), "pi", "sync", "--scope", "user"]
    )
    assert r2.exit_code == 0
    after_second = (home / ".pi/agent/settings.json").read_text()
    assert before == after_first == after_second


# ---------------------------------------------------------------------------
# `pi load` / `pi unload` (commit 3)
# ---------------------------------------------------------------------------

import subprocess  # noqa: E402


def _fake_run_factory(calls: list[list[str]], simulate_fetch: Path | None = None):
    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        if simulate_fetch is not None:
            simulate_fetch.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(cmd, 0, "", "")
    return fake_run


def test_pi_load_third_party_writes_allowlist_and_settings_then_fetches(
    tmp_path: Path, monkeypatch
):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    calls: list[list[str]] = []
    nm = home / ".pi/agent/npm/node_modules/pi-subagents"
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(calls, nm))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "npm:pi-subagents",
         "--scope", "user"],
    )
    assert result.exit_code == 0, result.output

    # 1. Allowlist gained the entry under pi_packages.
    allow = yaml.safe_load((home / ".agent-toolkit.yaml").read_text())
    assert "npm:pi-subagents" in (allow.get("pi_packages") or [])
    # 2. settings.json has the entry.
    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert "npm:pi-subagents" in settings["packages"]
    # 3. pi install was invoked.
    assert any(
        "install" in c and "npm:pi-subagents" in c for c in calls
    ), calls
    # 4. node_modules dir exists (simulated by fake).
    assert nm.is_dir()


def test_pi_load_idempotent_no_second_install(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent/npm/node_modules/pi-subagents").mkdir(parents=True)
    (home / ".pi/agent").mkdir(parents=True, exist_ok=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-subagents"]})
    )
    (home / ".agent-toolkit.yaml").write_text(
        yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]})
    )
    monkeypatch.setenv("HOME", str(home))

    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(calls))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "npm:pi-subagents",
         "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    # No `pi install` call — already loaded.
    assert not any("install" in c for c in calls), calls


def test_pi_load_first_party_creates_symlink(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    # Stage a fake toolkit repo with an extension/<slug>/extension.meta.yaml.
    toolkit = tmp_path / "toolkit"
    (toolkit / "extensions" / "status-bar").mkdir(parents=True)
    (toolkit / "extensions" / "status-bar" / "extension.meta.yaml").write_text(
        "kind: pi-extension\n"
        "slug: status-bar\n"
        "name: status-bar\n"
        "spec:\n"
        "  harnesses:\n"
        "    - pi\n"
    )
    # Make resolve_toolkit_root accept this fake repo: drop the two required
    # marker files (see `_repo_resolution._is_toolkit_repo`).
    (toolkit / ".agent-toolkit-source").write_text("")
    (toolkit / "schemas").mkdir()
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text("{}")
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(toolkit))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "status-bar",
         "--scope", "user"],
    )
    assert result.exit_code == 0, result.output

    slot = home / ".pi/agent/extensions/status-bar"
    assert slot.is_symlink(), f"expected symlink at {slot}"
    # Allowlist gained entry under pi_extensions, not pi_packages.
    allow = yaml.safe_load((home / ".agent-toolkit.yaml").read_text())
    assert "status-bar" in (allow.get("pi_extensions") or [])
    assert "status-bar" not in (allow.get("pi_packages") or [])


def test_pi_load_pi_missing_surfaces_actionable_error(
    tmp_path: Path, monkeypatch
):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    def fake_run(cmd, *args, **kwargs):
        raise FileNotFoundError("pi")
    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "npm:pi-subagents",
         "--scope", "user"],
    )
    assert result.exit_code != 0
    out = result.output.lower()
    assert "pi" in out
    assert "path" in out or "not on" in out


def test_pi_unload_third_party_removes_config_and_calls_pi_remove(
    tmp_path: Path, monkeypatch
):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-subagents"]})
    )
    (home / ".agent-toolkit.yaml").write_text(
        yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]})
    )
    monkeypatch.setenv("HOME", str(home))

    calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "run", _fake_run_factory(calls))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "unload", "npm:pi-subagents",
         "--scope", "user"],
    )
    assert result.exit_code == 0, result.output

    # settings.json no longer lists the source.
    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert "npm:pi-subagents" not in settings.get("packages", [])
    # Allowlist no longer lists the source.
    allow = yaml.safe_load((home / ".agent-toolkit.yaml").read_text()) or {}
    assert "npm:pi-subagents" not in (allow.get("pi_packages") or [])
    # `pi remove` was invoked.
    assert any(
        "remove" in c and "npm:pi-subagents" in c for c in calls
    ), calls


def test_pi_unload_third_party_pi_missing_is_non_fatal(
    tmp_path: Path, monkeypatch
):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    (home / ".pi/agent/settings.json").write_text(
        json.dumps({"packages": ["npm:pi-subagents"]})
    )
    (home / ".agent-toolkit.yaml").write_text(
        yaml.safe_dump({"pi_packages": ["npm:pi-subagents"]})
    )
    monkeypatch.setenv("HOME", str(home))

    def fake_run(cmd, *args, **kwargs):
        raise FileNotFoundError("pi")
    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "unload", "npm:pi-subagents",
         "--scope", "user"],
    )
    # Toolkit removed its records; `pi remove` failure was swallowed.
    assert result.exit_code == 0, result.output
    settings = json.loads((home / ".pi/agent/settings.json").read_text())
    assert "npm:pi-subagents" not in settings.get("packages", [])


def test_pi_unload_first_party_removes_symlink_only(
    tmp_path: Path, monkeypatch
):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    # Stage an existing symlink (as if `pi load status-bar` had run).
    src_dir = tmp_path / "toolkit-source" / "status-bar"
    src_dir.mkdir(parents=True)
    ext_dir = home / ".pi/agent/extensions"
    ext_dir.mkdir(parents=True)
    slot = ext_dir / "status-bar"
    slot.symlink_to(src_dir)
    (home / ".agent-toolkit.yaml").write_text(
        yaml.safe_dump({"pi_extensions": ["status-bar"]})
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "unload", "status-bar",
         "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    assert not slot.exists() and not slot.is_symlink()
    allow = yaml.safe_load((home / ".agent-toolkit.yaml").read_text()) or {}
    assert "status-bar" not in (allow.get("pi_extensions") or [])


def test_pi_unload_first_party_refuses_to_delete_real_dir(
    tmp_path: Path, monkeypatch
):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    real = home / ".pi/agent/extensions/handmade"
    real.mkdir(parents=True)
    (real / "extension.yaml").write_text("kind: pi-extension\n")
    (home / ".agent-toolkit.yaml").write_text(
        yaml.safe_dump({"pi_extensions": ["handmade"]})
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "unload", "handmade",
         "--scope", "user"],
    )
    assert result.exit_code != 0
    out = result.output.lower()
    assert "not a symlink" in out
    # Real dir is preserved.
    assert real.is_dir()


def test_pi_unload_first_party_real_dir_preserves_allowlist(
    tmp_path: Path, monkeypatch
):
    """Important #1: refusal must NOT remove the allowlist entry.

    If a real (non-symlink) dir sits at the slot, we refuse to delete it —
    and we must do so BEFORE touching the allowlist, otherwise the yaml
    flips to "unloaded" while disk still has the dir (drift).
    """
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    real = home / ".pi/agent/extensions/handmade"
    real.mkdir(parents=True)
    (real / "extension.yaml").write_text("kind: pi-extension\n")
    (home / ".agent-toolkit.yaml").write_text(
        yaml.safe_dump({"pi_extensions": ["handmade"]})
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "unload", "handmade",
         "--scope", "user"],
    )
    assert result.exit_code != 0
    assert "not a symlink" in result.output.lower()
    # The slug must STILL be in the allowlist — refusal happened before any
    # config mutation.
    allow = yaml.safe_load((home / ".agent-toolkit.yaml").read_text()) or {}
    assert "handmade" in (allow.get("pi_extensions") or [])
    # Real dir is preserved (also covered in the older test).
    assert real.is_dir()


def test_pi_load_first_party_refuses_asset_without_pi_harness(
    tmp_path: Path, monkeypatch
):
    """Important #2: a pi-extension asset that doesn't declare `pi` in
    spec.harnesses must NOT be silently linked.
    """
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    toolkit = tmp_path / "toolkit"
    ext_dir = toolkit / "extensions" / "claude-only-ext"
    ext_dir.mkdir(parents=True)
    # spec.harnesses: ["claude"] — explicitly excludes pi.
    (ext_dir / "extension.meta.yaml").write_text(
        "kind: pi-extension\n"
        "slug: claude-only-ext\n"
        "name: claude-only-ext\n"
        "spec:\n"
        "  harnesses:\n"
        "    - claude\n"
    )
    (toolkit / ".agent-toolkit-source").write_text("")
    (toolkit / "schemas").mkdir()
    (toolkit / "schemas" / "asset-frontmatter.v1alpha2.json").write_text("{}")
    monkeypatch.setenv("AGENT_TOOLKIT_REPO", str(toolkit))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "claude-only-ext",
         "--scope", "user"],
    )
    assert result.exit_code != 0, result.output
    assert "not found" in result.output.lower() or "harness" in result.output.lower()
    # No symlink was created.
    slot = home / ".pi/agent/extensions/claude-only-ext"
    assert not slot.exists() and not slot.is_symlink()


def test_pi_load_writes_config_before_invoking_pi_install(
    tmp_path: Path, monkeypatch
):
    """Important #3: allowlist + settings.json must be written BEFORE
    `pi install` is invoked. The fake `subprocess.run` reads both files
    and fails the test if either lacks the entry at call time.
    """
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    (home / ".pi/agent").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))

    allow_path = home / ".agent-toolkit.yaml"
    settings_path = home / ".pi/agent/settings.json"
    target = "npm:pi-subagents"
    observed: dict[str, bool] = {"allow_written": False, "settings_written": False}

    def fake_run(cmd, *args, **kwargs):
        # Capture state of toolkit-owned config files at the moment `pi`
        # is invoked. Both must already contain the entry.
        if allow_path.exists():
            allow = yaml.safe_load(allow_path.read_text()) or {}
            observed["allow_written"] = target in (allow.get("pi_packages") or [])
        if settings_path.exists():
            settings = json.loads(settings_path.read_text())
            observed["settings_written"] = target in (settings.get("packages") or [])
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", target, "--scope", "user"],
    )
    assert result.exit_code == 0, result.output
    assert observed["allow_written"], (
        "allowlist did not contain the entry when `pi install` was invoked"
    )
    assert observed["settings_written"], (
        "settings.json did not contain the entry when `pi install` was invoked"
    )


def test_pi_load_requires_scope_flag(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    project = tmp_path / "proj"
    project.mkdir()
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--project", str(project), "pi", "load", "npm:pi-subagents"],
    )
    assert result.exit_code != 0
    assert "scope" in result.output.lower()
