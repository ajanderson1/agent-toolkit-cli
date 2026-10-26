"""Package updates: no test can replace the operator's tool installation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sys
from zipfile import ZipFile

from click.testing import CliRunner
import pytest

from agent_toolkit_cli import self_update as updates
from agent_toolkit_cli.cli import main


SHA = "a" * 40
_REAL_API_JSON = updates._api_json


@pytest.fixture(autouse=True)
def isolated_updates(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.delenv("AGENT_TOOLKIT_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(updates, "installed_version", lambda: "7.0.0")
    # Unexpected network access must fail the test, including in headless TUIs.
    monkeypatch.setattr(updates, "_api_json", lambda *a, **kw: pytest.fail("Unexpected network access"))


def test_release_cache_and_force(monkeypatch):
    calls = []
    monkeypatch.setattr(updates, "_api_json", lambda endpoint, timeout: calls.append((endpoint, timeout)) or {"tag_name": "v7.1.0"})
    assert updates.latest_release().version == "7.1.0"
    assert updates.latest_release().version == "7.1.0"
    assert len(calls) == 1
    assert updates.latest_release(force=True).version == "7.1.0"
    assert len(calls) == 2


def test_cache_expiry(monkeypatch):
    now = 100000
    monkeypatch.setattr(updates.time, "time", lambda: now)
    updates._write_json(updates.cache_path(), {"tag": "v7.0.0", "checked_at": now - updates.CACHE_SECONDS})
    monkeypatch.setattr(updates, "_api_json", lambda *a: {"tag_name": "v7.2.0"})
    assert updates.latest_release().version == "7.2.0"


def test_failed_check_keeps_cached_notice_and_backs_off(monkeypatch):
    calls = []
    updates._write_json(updates.cache_path(), {"tag": "v7.1.0", "checked_at": 0})

    def fail(*args):
        calls.append(args)
        raise updates.UpdateError("offline")

    monkeypatch.setattr(updates, "_api_json", fail)
    assert "atc update" in updates.startup_notice()
    assert "atc update" in updates.startup_notice()
    assert len(calls) == 1
    with pytest.raises(updates.UpdateError, match="offline"):
        updates.latest_release(force=True)


def test_first_offline_startup_is_silent(monkeypatch):
    monkeypatch.setattr(updates, "_api_json", lambda *a: (_ for _ in ()).throw(updates.UpdateError("offline")))
    assert updates.startup_notice() is None
    assert updates.startup_notice() is None  # negative cache, no repeated request


def test_corrupt_cache_is_replaced(monkeypatch):
    path = updates.cache_path()
    path.parent.mkdir(parents=True)
    path.write_text("broken json")
    monkeypatch.setattr(updates, "_api_json", lambda *a: {"tag_name": "v7.1.0"})
    assert updates.latest_release().tag == "v7.1.0"
    assert json.loads(path.read_text())["tag"] == "v7.1.0"


@pytest.mark.parametrize("payload", [
    {"tag_name": "v8.0.0rc1"}, {"tag_name": "v8.0.0", "prerelease": True},
    {"tag_name": "v8.0.0", "draft": True}, {"tag_name": "--evil"}, {},
])
def test_rejects_nonstable_release(payload, monkeypatch):
    monkeypatch.setattr(updates, "_api_json", lambda *a: payload)
    with pytest.raises(updates.UpdateError):
        updates.latest_release(force=True)


@pytest.mark.parametrize("version,expected", [("6.9.0", False), ("7.0.0", False), ("7.1.0", True), ("7.10.0", True)])
def test_version_comparison(version, expected):
    assert updates.is_newer(updates.Release("v" + version, version)) is expected


def test_startup_opt_out(monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_NO_UPDATE_CHECK", "1")
    assert updates.startup_notice() is None


def test_check_is_explicit_even_with_opt_out(monkeypatch):
    monkeypatch.setenv("AGENT_TOOLKIT_NO_UPDATE_CHECK", "1")
    monkeypatch.setattr(updates, "_api_json", lambda *a: {"tag_name": "v7.1.0"})
    result = CliRunner().invoke(main, ["update", "--check"])
    assert result.exit_code == 0, result.output
    assert "7.0.0 → 7.1.0" in result.output
    assert "atc update" in result.output


def test_check_failure_exits_nonzero(monkeypatch):
    monkeypatch.setattr(updates, "_api_json", lambda *a: (_ for _ in ()).throw(updates.UpdateError("offline")))
    result = CliRunner().invoke(main, ["update", "--check"])
    assert result.exit_code == 1
    assert "offline" in result.output


@pytest.mark.parametrize("args", [
    ("skills", "list", "--json"), ("instructions", "list", "--format", "json"),
    ("instructions", "list", "--format=json"), ("skills", "--help"),
    ("update",), ("--version",),
])
def test_interactive_notice_suppressed_for_special_output(args, monkeypatch):
    monkeypatch.setattr(updates.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(updates.sys, "stderr", SimpleNamespace(isatty=lambda: True))
    updates.cli_startup_notice(args)


def test_pipe_never_checks(monkeypatch):
    monkeypatch.setattr(updates.sys, "stdout", SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(updates.sys, "stderr", SimpleNamespace(isatty=lambda: True))
    updates.cli_startup_notice(("skills", "list"))


def test_interactive_notice_goes_to_stderr(monkeypatch):
    import click
    messages = []
    monkeypatch.setattr(updates.sys, "stdout", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(updates.sys, "stderr", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(updates, "_api_json", lambda *a: {"tag_name": "v7.1.0"})
    monkeypatch.setattr(click, "echo", lambda message, **kw: messages.append((message, kw)))
    updates.cli_startup_notice(("skills", "list"))
    assert "atc update" in messages[0][0]
    assert messages[0][1] == {"err": True}


def test_cli_help_and_update_dispatch(monkeypatch):
    assert CliRunner().invoke(main, ["update", "--help"]).exit_code == 0
    calls = []
    monkeypatch.setattr(updates, "perform_update", lambda **kw: calls.append(kw))
    result = CliRunner().invoke(main, ["update", "--main"])
    assert result.exit_code == 0, result.output
    assert calls == [{"main": True}]


def test_main_check_compares_commit_not_version(monkeypatch):
    monkeypatch.setattr(updates, "resolve_commit", lambda ref: SHA)
    monkeypatch.setattr(updates, "installed_commit", lambda: "b" * 40)
    result = CliRunner().invoke(main, ["update", "--main", "--check"])
    assert result.exit_code == 0
    assert "atc update --main" in result.output
    monkeypatch.setattr(updates, "installed_commit", lambda: SHA)
    assert "Already at latest" in CliRunner().invoke(main, ["update", "--main", "--check"]).output


@pytest.mark.parametrize("binary", ["att", "agent-toolkit-tui"])
def test_tui_update_dispatch_without_opening_app(binary, monkeypatch):
    from agent_toolkit_tui import app
    monkeypatch.setattr(sys, "argv", [binary, "update", "--check"])
    monkeypatch.setattr(app.TUIApp, "run", lambda self: pytest.fail("TUI opened for update"))
    monkeypatch.setattr(updates, "_api_json", lambda *a: {"tag_name": "v7.1.0"})
    assert app.main() == 0


def test_tui_rejects_unknown_arguments(monkeypatch):
    from agent_toolkit_tui import app
    monkeypatch.setattr(sys, "argv", ["att", "typo"])
    monkeypatch.setattr(app.TUIApp, "run", lambda self: pytest.fail("TUI opened"))
    with pytest.raises(SystemExit) as exc:
        app.main()
    assert exc.value.code == 2


def test_tui_notice_delivered_on_ui_thread(monkeypatch):
    from agent_toolkit_tui.app import TUIApp
    app = TUIApp()
    messages = []
    monkeypatch.setattr(updates, "startup_notice", lambda: "New update available; atc update")
    monkeypatch.setattr(app, "call_from_thread", lambda callback, *args, **kw: messages.append((callback, args, kw)))
    app._check_toolkit_update()
    assert messages[0][0] == app.notify
    assert "atc update" in messages[0][1][0]


@pytest.mark.asyncio
async def test_headless_tui_never_checks():
    from agent_toolkit_tui.app import TUIApp
    async with TUIApp().run_test() as pilot:
        await pilot.pause()


class FakeDistribution:
    def __init__(self, direct=None, installer="uv"):
        self.direct = direct or {}
        self.installer = installer

    def read_text(self, name):
        return json.dumps(self.direct) if name == "direct_url.json" else self.installer


@pytest.mark.parametrize("editable,managed,installer", [(True, True, "uv"), (False, False, "uv"), (False, True, "pip")])
def test_refuses_other_installations(editable, managed, installer, tmp_path, monkeypatch):
    root = tmp_path / "tools"
    monkeypatch.setattr(updates.shutil, "which", lambda name: "/uv")
    monkeypatch.setattr(updates, "_run", lambda *a, **kw: str(root))
    monkeypatch.setattr(sys, "prefix", str(root / "agent-toolkit" if managed else tmp_path / "dev"))
    monkeypatch.setattr(updates.metadata, "distribution", lambda name: FakeDistribution({"dir_info": {"editable": editable}}, installer))
    with pytest.raises(updates.UpdateError, match="non-editable"):
        updates.require_uv_install()


def test_recognizes_uv_tool_install(tmp_path, monkeypatch):
    root = tmp_path / "tools"
    monkeypatch.setattr(updates.shutil, "which", lambda name: "/uv")
    monkeypatch.setattr(updates, "_run", lambda *a, **kw: str(root))
    monkeypatch.setattr(sys, "prefix", str(root / "agent-toolkit"))
    monkeypatch.setattr(updates.metadata, "distribution", lambda name: FakeDistribution())
    assert updates.require_uv_install() == "/uv"


def make_wheel(path, version="7.1.0"):
    path.mkdir(parents=True, exist_ok=True)
    wheel = path / f"agent_toolkit-{version}-py3-none-any.whl"
    with ZipFile(wheel, "w") as archive:
        archive.writestr(f"agent_toolkit-{version}.dist-info/METADATA", f"Name: agent-toolkit\nVersion: {version}\n")
    return wheel


@pytest.fixture
def fake_build(monkeypatch):
    calls = []
    monkeypatch.setattr(updates, "require_uv_install", lambda: "/uv")
    monkeypatch.setattr(updates, "latest_release", lambda **kw: updates.Release("v7.1.0", "7.1.0"))
    monkeypatch.setattr(updates, "resolve_commit", lambda ref: SHA)
    monkeypatch.setattr(updates.shutil, "which", lambda name: "/git")

    def run(args, **kwargs):
        calls.append(args)
        if "rev-parse" in args:
            return SHA
        if "build" in args:
            make_wheel(Path(args[args.index("--out-dir") + 1]))
        return ""

    monkeypatch.setattr(updates, "_run", run)
    return calls


def test_build_pins_commit_and_retains_hashed_wheel(fake_build):
    receipt_path = updates.perform_update()
    receipt = json.loads(receipt_path.read_text())
    wheel = receipt_path.parent / receipt["wheel"]
    assert receipt["commit"] == SHA
    assert receipt["repository"] == updates.REPOSITORY
    assert receipt["wheel_sha256"] == hashlib.sha256(wheel.read_bytes()).hexdigest()
    fetch = next(args for args in fake_build if "fetch" in args)
    assert fetch[-2:] == [updates.REPOSITORY + ".git", SHA]
    install = fake_build[-1]
    assert install[:5] == ["/uv", "--no-config", "tool", "install", "--reinstall-package"]
    assert "--force" not in install
    assert f"agent-toolkit @ {wheel.as_uri()}#sha256={receipt['wheel_sha256']}" in install
    assert not (updates.state_dir() / ".update-lock").exists()


def test_failed_build_never_replaces_installation(fake_build, monkeypatch):
    run = updates._run

    def fail(args, **kw):
        if "build" in args:
            raise updates.UpdateError("build failed")
        return run(args, **kw)

    monkeypatch.setattr(updates, "_run", fail)
    with pytest.raises(updates.UpdateError, match="build failed"):
        updates.perform_update()
    assert not any("install" in args for args in fake_build)
    assert not (updates.state_dir() / ".update-lock").exists()


def test_refuses_source_commit_mismatch(fake_build, monkeypatch):
    run = updates._run
    monkeypatch.setattr(updates, "_run", lambda args, **kw: "b" * 40 if "rev-parse" in args else run(args, **kw))
    with pytest.raises(updates.UpdateError, match="canonical commit"):
        updates.perform_update()
    assert not any("build" in args or "install" in args for args in fake_build)


def test_refuses_wheel_version_mismatch(fake_build, monkeypatch):
    monkeypatch.setattr(updates, "_wheel_version", lambda wheel: "99.0.0")
    with pytest.raises(updates.UpdateError, match="selected release"):
        updates.perform_update()
    assert not any("install" in args for args in fake_build)


def test_no_downgrade_or_unneeded_build(fake_build, monkeypatch):
    monkeypatch.setattr(updates, "installed_version", lambda: "8.0.0")
    assert updates.perform_update() is None
    assert fake_build == []


def test_main_same_version_still_updates_by_commit(fake_build, monkeypatch):
    monkeypatch.setattr(updates, "installed_version", lambda: "7.1.0")
    monkeypatch.setattr(updates, "installed_commit", lambda: "b" * 40)
    receipt = updates.perform_update(main=True)
    assert json.loads(receipt.read_text())["ref"] == "main"


def test_same_main_commit_does_not_rebuild(fake_build, monkeypatch):
    monkeypatch.setattr(updates, "installed_commit", lambda: SHA)
    assert updates.perform_update(main=True) is None
    assert fake_build == []


def test_concurrent_updates_refused(fake_build):
    with updates._update_lock():
        with pytest.raises(updates.UpdateError, match="Another update"):
            updates.perform_update()


def test_receipt_must_match_installed_wheel_hash(fake_build, monkeypatch):
    receipt_path = updates.perform_update()
    receipt = json.loads(receipt_path.read_text())
    direct = {"url": (receipt_path.parent / receipt["wheel"]).as_uri(), "archive_info": {"hashes": {"sha256": receipt["wheel_sha256"]}}}
    monkeypatch.setattr(updates.metadata, "distribution", lambda name: FakeDistribution(direct))
    assert updates.installed_commit() == SHA
    direct["archive_info"]["hashes"]["sha256"] = "bad"
    assert updates.installed_commit() is None


def test_subprocess_scrubs_git_and_virtualenv(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/never/use/operator/repo")
    monkeypatch.setenv("VIRTUAL_ENV", "/never/use/operator/venv")

    def run(args, **kw):
        assert not any(name.startswith("GIT_") for name in kw["env"])
        assert "VIRTUAL_ENV" not in kw["env"]
        assert kw["cwd"] == tmp_path
        assert kw["timeout"] == 600
        return SimpleNamespace(stdout="ok\n")

    monkeypatch.setattr(updates.subprocess, "run", run)
    assert updates._run(["git", "status"], cwd=tmp_path) == "ok"


def test_local_wheel_provenance_checks_installed_contents(fake_build, tmp_path, monkeypatch):
    receipt_path = updates.perform_update()
    receipt = json.loads(receipt_path.read_text())
    wheel = receipt_path.parent / receipt["wheel"]
    installed = tmp_path / "installed"
    installed.mkdir()
    with ZipFile(wheel) as archive:
        archive.extractall(installed)
    dist = FakeDistribution({"url": wheel.as_uri(), "archive_info": {}})
    dist.locate_file = lambda name: installed / name
    monkeypatch.setattr(updates.metadata, "distribution", lambda name: dist)
    assert updates.installed_commit() == SHA
    metadata_file, = installed.glob("*.dist-info/METADATA")
    metadata_file.write_text("tampered")
    assert updates.installed_commit() is None


def test_local_wheel_provenance_rejects_changed_artifact(fake_build, monkeypatch):
    receipt_path = updates.perform_update()
    receipt = json.loads(receipt_path.read_text())
    wheel = receipt_path.parent / receipt["wheel"]
    dist = FakeDistribution({"url": wheel.as_uri(), "archive_info": {}})
    monkeypatch.setattr(updates.metadata, "distribution", lambda name: dist)
    wheel.write_bytes(b"tampered")
    assert updates.installed_commit() is None


def test_cache_write_failure_does_not_break_check(monkeypatch):
    monkeypatch.setattr(updates, "_api_json", lambda *a: {"tag_name": "v7.1.0"})
    monkeypatch.setattr(updates, "_write_json", lambda *a: (_ for _ in ()).throw(PermissionError("read only")))
    assert "atc update" in updates.startup_notice()


@pytest.mark.parametrize("body", [
    b"[]", b"invalid json", b"x" * (updates.MAX_RESPONSE_BYTES + 1),
], ids=["array", "invalid", "oversized"])
def test_malformed_api_response_is_reported(body, monkeypatch):
    from io import BytesIO
    monkeypatch.setattr(updates, "urlopen", lambda *a, **kw: BytesIO(body))
    with pytest.raises(updates.UpdateError, match="Could not check GitHub"):
        _REAL_API_JSON("releases/latest", 1)


def test_incomplete_http_response_is_reported(monkeypatch):
    from http.client import IncompleteRead
    monkeypatch.setattr(updates, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(IncompleteRead(b"")))
    with pytest.raises(updates.UpdateError, match="Could not check GitHub"):
        _REAL_API_JSON("releases/latest", 1)


def test_invalid_built_archive_is_reported(tmp_path):
    wheel = tmp_path / "bad.whl"
    wheel.write_text("not a zip")
    with pytest.raises(updates.UpdateError, match="Built wheel is invalid"):
        updates._wheel_version(wheel)


def test_completion_does_not_check(monkeypatch):
    monkeypatch.setenv("_AGENT_TOOLKIT_CLI_COMPLETE", "bash_complete")
    monkeypatch.setenv("COMP_WORDS", "agent-toolkit-cli sk")
    monkeypatch.setenv("COMP_CWORD", "1")
    result = CliRunner().invoke(main, [], prog_name="agent-toolkit-cli")
    assert result.exit_code == 0, result.output
    assert "skills" in result.output


def test_update_installation_failure_is_nonzero(monkeypatch):
    monkeypatch.setattr(updates, "perform_update", lambda **kw: (_ for _ in ()).throw(updates.UpdateError("uv failed")))
    result = CliRunner().invoke(main, ["update"])
    assert result.exit_code == 1
    assert "uv failed" in result.output
